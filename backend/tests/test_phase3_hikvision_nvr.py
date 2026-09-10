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
    engine,
    hash_password,
    normalize_hikvision_channel_number,
    token_digest,
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _auth_context(role="ADMIN_SECRETARIA"):
    with SessionLocal() as db:
        school = School(name="Escola NVR", address="Rua do NVR")
        db.add(school)
        db.flush()
        user = UserAccount(
            name="Administrador NVR",
            email=f"{role.lower()}-nvr@local",
            password_hash=hash_password("SenhaForte@2026"),
            role=role,
            school_id=None if role in {"ADMIN_SECRETARIA", "GESTOR_SECRETARIA"} else school.id,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = f"token-{role.lower()}-nvr"
        now = datetime.now(timezone.utc)
        db.add(
            AuthSession(
                user_id=user.id,
                token=token_digest(raw),
                expires_at=now + timedelta(hours=2),
                last_seen_at=now,
            )
        )
        db.commit()
        return school.id, {"Authorization": f"Bearer {raw}"}


def _create_recorder(db, school_id, ip="192.0.2.50"):
    recorder = Recorder(
        school_id=school_id,
        name="NVR Principal",
        manufacturer="Hikvision",
        ip_address=ip,
        http_port=80,
        https_port=443,
        rtsp_port=554,
        sdk_port=8000,
        username="admin",
        password=application.encrypt_secret("senha"),
        channel_count=8,
    )
    db.add(recorder)
    db.flush()
    return recorder


def test_hikvision_stream_ids_are_normalized():
    assert normalize_hikvision_channel_number("101", 9) == 1
    assert normalize_hikvision_channel_number("202", 9) == 2
    assert normalize_hikvision_channel_number("8", 1) == 8
    assert normalize_hikvision_channel_number("inválido", 7) == 7


def test_duplicate_recorder_ip_in_same_school_is_rejected(client):
    school_id, headers = _auth_context()
    payload = {
        "school_id": school_id,
        "name": "NVR A",
        "manufacturer": "Hikvision",
        "ip_address": "192.0.2.60",
        "http_port": 80,
        "https_port": 443,
        "rtsp_port": 554,
        "sdk_port": 8000,
        "channel_count": 8,
    }
    assert client.post("/recorders", json=payload, headers=headers).status_code == 200
    payload["name"] = "NVR duplicado"
    response = client.post("/recorders", json=payload, headers=headers)
    assert response.status_code == 409


def test_discovery_updates_inventory_and_marks_existing_channels(client, monkeypatch):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        camera = Camera(
            school_id=school_id,
            name="Canal existente",
            location="Portão",
            source_type="NVR",
            recorder_id=recorder.id,
            nvr_channel=1,
        )
        db.add(camera)
        db.commit()
        recorder_id = recorder.id

    monkeypatch.setattr(
        application,
        "hikvision_device_info",
        lambda row: {
            "http_status": 200,
            "device_name": "NVR Escola",
            "model": "DS-7616",
            "serial_number": "SERIE-123",
            "mac_address": "00:11:22:33:44:55",
            "firmware_version": "V5.0",
            "firmware_released_date": "2026-01-01",
            "device_type": "NVR",
        },
    )
    monkeypatch.setattr(
        application,
        "hikvision_channels",
        lambda row: [
            {"channel": 1, "name": "Entrada", "enabled": True, "online": True},
            {"channel": 2, "name": "Pátio", "enabled": True, "online": False},
        ],
    )
    monkeypatch.setattr(
        application,
        "hikvision_stream_capabilities",
        lambda row, channel: {
            "MAIN": {"success": True, "video_codec_type": "H.264", "resolution": "1920x1080", "max_frame_rate": "1500"},
            "SUB": {"success": True, "video_codec_type": "H.264", "resolution": "640x360", "max_frame_rate": "1000"},
        },
    )

    response = client.post(
        f"/recorders/{recorder_id}/discover?include_capabilities=true",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["channel_count"] == 2
    assert body["configured_count"] == 1
    assert body["channels"][0]["configured"] is True
    assert body["channels"][1]["online"] is False
    assert body["channels"][0]["capabilities"]["SUB"]["resolution"] == "640x360"

    with SessionLocal() as db:
        recorder = db.get(Recorder, recorder_id)
        assert recorder.model == "DS-7616"
        assert recorder.device_type == "NVR"
        assert recorder.discovered_channel_count == 2
        assert recorder.last_discovery_at is not None


def test_import_channels_creates_and_updates_without_duplicates(client, monkeypatch):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        db.commit()
        recorder_id = recorder.id

    monkeypatch.setattr(
        application,
        "hikvision_channels",
        lambda row: [
            {"channel": 1, "name": "Entrada", "model": "IPC-A"},
            {"channel": 2, "name": "Pátio", "model": "IPC-B"},
        ],
    )
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "MAIN=OK; SUB=OK"))

    payload = {
        "channels": [
            {"channel": 1, "name": "Entrada", "location": "Portão", "codec": "H.264", "resolution": "640x360", "fps": 10},
            {"channel": 2, "name": "Pátio", "location": "Pátio", "codec": "H.264", "resolution": "640x360", "fps": 10},
        ],
        "update_existing": False,
        "test_after_import": False,
    }
    response = client.post(f"/recorders/{recorder_id}/import-channels", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["created"] == 2

    response = client.post(f"/recorders/{recorder_id}/import-channels", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["skipped"] == 2

    payload["update_existing"] = True
    payload["channels"][0]["name"] = "Entrada atualizada"
    response = client.post(f"/recorders/{recorder_id}/import-channels", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["updated"] == 2

    with SessionLocal() as db:
        cameras = db.query(Camera).filter(Camera.recorder_id == recorder_id).order_by(Camera.nvr_channel).all()
        assert len(cameras) == 2
        assert cameras[0].name == "Entrada atualizada"
        assert cameras[0].ip_address is None
        assert cameras[0].stream_name_main.endswith("-main")
        assert cameras[0].stream_name_sub.endswith("-sub")


def test_camera_test_probes_main_and_sub_using_recorder(client, monkeypatch):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        camera = Camera(
            school_id=school_id,
            name="Canal 1",
            location="Entrada",
            source_type="NVR",
            recorder_id=recorder.id,
            nvr_channel=1,
            stream_profile="SUB",
        )
        db.add(camera)
        db.commit()
        camera_id = camera.id

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(application.socket, "create_connection", lambda *args, **kwargs: FakeSocket())
    seen = []

    def fake_probe(source, timeout=15):
        seen.append(source)
        return {"ok": True, "codec": "H.264", "resolution": "1280x720", "fps": 15}

    monkeypatch.setattr(application, "probe_rtsp_source", fake_probe)
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))

    response = client.post(f"/cameras/{camera_id}/test", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ONLINE"
    assert body["profiles"]["MAIN"]["ok"] is True
    assert body["profiles"]["SUB"]["ok"] is True
    assert any("/Streaming/Channels/101" in source for source in seen)
    assert any("/Streaming/Channels/102" in source for source in seen)
    assert all("admin:senha@192.0.2.50:554" in source for source in seen)


def test_recorder_test_records_isapi_inventory(client, monkeypatch):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        db.commit()
        recorder_id = recorder.id

    monkeypatch.setattr(
        application,
        "test_recorder_connectivity",
        lambda row: {
            "status": "ONLINE",
            "tests": {"RTSP": {"ok": True}, "ISAPI": {"ok": True}},
            "device": {
                "model": "DS-7732",
                "serial_number": "ABC",
                "firmware_version": "V6",
                "firmware_released_date": "2026-02-02",
                "device_type": "NVR",
                "mac_address": "AA:BB:CC:DD:EE:FF",
            },
        },
    )
    response = client.post(f"/recorders/{recorder_id}/test", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ONLINE"
    with SessionLocal() as db:
        recorder = db.get(Recorder, recorder_id)
        assert recorder.model == "DS-7732"
        assert recorder.mac_address == "AA:BB:CC:DD:EE:FF"
        assert recorder.last_check_at is not None


def test_recorder_channel_batch_is_limited_to_linked_channels(client, monkeypatch):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        db.add_all(
            [
                Camera(school_id=school_id, name="C1", location="L1", source_type="NVR", recorder_id=recorder.id, nvr_channel=1),
                Camera(school_id=school_id, name="C2", location="L2", source_type="NVR", recorder_id=recorder.id, nvr_channel=2),
            ]
        )
        db.commit()
        recorder_id = recorder.id

    monkeypatch.setattr(
        application,
        "test_camera_profiles",
        lambda db, camera, profiles=("MAIN", "SUB"), provision=True: {
            "camera_id": camera.id,
            "status": "ONLINE",
            "profiles": {profile: {"ok": True} for profile in profiles},
            "provisioned": True,
        },
    )
    response = client.post(
        f"/recorders/{recorder_id}/test-channels",
        headers=headers,
        json={"channels": [2], "profile": "SUB", "provision": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tested"] == 1
    assert body["online"] == 1


def test_duplicate_camera_channel_is_rejected(client):
    school_id, headers = _auth_context()
    with SessionLocal() as db:
        recorder = _create_recorder(db, school_id)
        db.commit()
        recorder_id = recorder.id

    payload = {
        "school_id": school_id,
        "name": "Canal 1",
        "location": "Entrada",
        "manufacturer": "Hikvision",
        "camera_type": "FIXA",
        "stream_profile": "SUB",
        "source_type": "NVR",
        "recorder_id": recorder_id,
        "nvr_channel": 1,
        "codec": "H.264",
        "resolution": "640x360",
        "fps": 10,
    }
    first = client.post("/cameras", json=payload, headers=headers)
    assert first.status_code == 200
    payload["name"] = "Duplicada"
    second = client.post("/cameras", json=payload, headers=headers)
    assert second.status_code == 409
