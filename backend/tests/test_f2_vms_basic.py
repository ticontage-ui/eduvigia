from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession,
    Base,
    Camera,
    Recorder,
    School,
    SessionLocal,
    UserAccount,
    app,
    build_camera_rtsp,
    engine,
    hash_password,
    test_camera_profiles as run_camera_profile_test,
    token_digest,
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def auth_context(role="ADMIN_SECRETARIA", school_id=None):
    with SessionLocal() as db:
        if school_id is None:
            school = School(name="Escola VMS", address="Rua VMS")
            db.add(school)
            db.flush()
            school_id = school.id
        user = UserAccount(
            name="Operador VMS",
            email=f"vms-{role.lower()}-{school_id}@local",
            password_hash=hash_password("SenhaForte@2026"),
            role=role,
            school_id=school_id if role in {"GESTOR_ESCOLA", "OPERADOR_ESCOLA"} else None,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = f"vms-token-{role.lower()}-{school_id}"
        now = datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id, token=token_digest(raw), expires_at=now + timedelta(hours=2), last_seen_at=now))
        db.commit()
        return school_id, user.id, {"Authorization": f"Bearer {raw}"}


def test_nvr_main_and_sub_rtsp_are_independent():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        school = School(name="Escola NVR F2", address="Rua 1")
        db.add(school); db.flush()
        recorder = Recorder(school_id=school.id, name="NVR", ip_address="192.0.2.20", rtsp_port=554, username="admin", password=application.encrypt_secret("senha"))
        db.add(recorder); db.flush()
        camera = Camera(school_id=school.id, name="Cam 3", location="Pátio", source_type="NVR", recorder_id=recorder.id, nvr_channel=3)
        db.add(camera); db.flush()
        assert "/Streaming/Channels/301" in build_camera_rtsp(db, camera, "MAIN")
        assert "/Streaming/Channels/302" in build_camera_rtsp(db, camera, "SUB")
    Base.metadata.drop_all(engine)


def test_custom_rtsp_has_distinct_main_and_sub():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        school = School(name="Escola RTSP", address="Rua 2")
        db.add(school); db.flush()
        camera = Camera(
            school_id=school.id,
            name="Cam custom",
            location="Entrada",
            source_type="RTSP_CUSTOM",
            rtsp_url_main="rtsp://example/main",
            rtsp_url_sub="rtsp://example/sub",
        )
        db.add(camera); db.flush()
        assert build_camera_rtsp(db, camera, "MAIN") == "rtsp://example/main"
        assert build_camera_rtsp(db, camera, "SUB") == "rtsp://example/sub"
    Base.metadata.drop_all(engine)


def test_profile_probe_persists_main_and_sub_metadata(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        school = School(name="Escola Probe", address="Rua 3")
        db.add(school); db.flush()
        camera = Camera(school_id=school.id, name="Cam Probe", location="Pátio", ip_address="127.0.0.1", port=554)
        db.add(camera); db.flush()
        
        class DummySocket:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
        monkeypatch.setattr(application.socket, "create_connection", lambda *args, **kwargs: DummySocket())
        results = iter([
            {"ok": True, "codec": "H.264", "resolution": "1920x1080", "fps": 15.0},
            {"ok": True, "codec": "H.264", "resolution": "640x360", "fps": 10.0},
        ])
        monkeypatch.setattr(application, "probe_rtsp_source", lambda source: next(results))
        monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
        result = run_camera_profile_test(db, camera, profiles=("MAIN", "SUB"), provision=True)
        assert result["status"] == "ONLINE"
        assert camera.main_status == "ONLINE"
        assert camera.sub_status == "ONLINE"
        assert camera.main_resolution == "1920x1080"
        assert camera.sub_resolution == "640x360"
        assert camera.main_fps == 15
        assert camera.sub_fps == 10
    Base.metadata.drop_all(engine)


def test_favorites_are_persisted_per_user(client):
    school_id, _, headers = auth_context()
    with SessionLocal() as db:
        camera = Camera(school_id=school_id, name="Favorita", location="Entrada", ip_address="192.0.2.30")
        db.add(camera); db.commit(); camera_id = camera.id
    assert client.get("/monitoring/favorites", headers=headers).json()["camera_ids"] == []
    assert client.put(f"/monitoring/favorites/{camera_id}", headers=headers).status_code == 200
    assert client.get("/monitoring/favorites", headers=headers).json()["camera_ids"] == [camera_id]
    assert client.delete(f"/monitoring/favorites/{camera_id}", headers=headers).status_code == 200
    assert client.get("/monitoring/favorites", headers=headers).json()["camera_ids"] == []


def test_status_refresh_is_limited_to_visible_camera_batch(client, monkeypatch):
    school_id, _, headers = auth_context()
    with SessionLocal() as db:
        cameras = []
        for idx in range(2):
            camera = Camera(school_id=school_id, name=f"Cam {idx}", location="Pátio", ip_address=f"192.0.2.{40+idx}")
            db.add(camera); db.flush(); cameras.append(camera.id)
        db.commit()
    monkeypatch.setattr(application, "_tcp_camera_status", lambda item: (item[0], True, None))
    response = client.post("/monitoring/status-refresh", json={"camera_ids": cameras}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["checked"] == 2
    assert all(item["status"] == "ONLINE" for item in body["cameras"])


def test_camera_response_exposes_profile_metadata_but_not_rtsp_secrets(client, monkeypatch):
    school_id, _, headers = auth_context()
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    payload = {
        "school_id": school_id,
        "name": "Cam Perfis",
        "location": "Entrada",
        "source_type": "RTSP_CUSTOM",
        "rtsp_url_main": "rtsp://user:secret@example/main",
        "rtsp_url_sub": "rtsp://user:secret@example/sub",
        "main_codec": "H.264",
        "main_resolution": "1920x1080",
        "main_fps": 15,
        "main_bitrate_kbps": 4096,
        "sub_codec": "H.264",
        "sub_resolution": "640x360",
        "sub_fps": 10,
        "sub_bitrate_kbps": 512,
    }
    response = client.post("/cameras", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["main_resolution"] == "1920x1080"
    assert body["sub_resolution"] == "640x360"
    serialized = response.text
    assert "secret" not in serialized
    assert "rtsp_url_main" not in body
    assert "rtsp_url_sub" not in body
