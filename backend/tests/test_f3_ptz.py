from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession,
    Base,
    Camera,
    CameraPTZLease,
    CameraPTZPreset,
    School,
    SessionLocal,
    UserAccount,
    app,
    encrypt_secret,
    engine,
    hash_password,
    role_permissions,
    token_digest,
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def auth_user(role="OPERADOR_GUARDA", *, school_id=None, suffix="a"):
    with SessionLocal() as db:
        if school_id is None:
            school = School(name=f"Escola PTZ {suffix}", address="Rua PTZ")
            db.add(school)
            db.flush()
            school_id = school.id
        user = UserAccount(
            name=f"Operador PTZ {suffix}",
            email=f"ptz-{role.lower()}-{suffix}@local",
            password_hash=hash_password("SenhaForte@2026"),
            role=role,
            school_id=school_id if role in {"GESTOR_ESCOLA", "OPERADOR_ESCOLA"} else None,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = f"ptz-token-{role.lower()}-{suffix}"
        now = datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id, token=token_digest(raw), expires_at=now + timedelta(hours=2), last_seen_at=now))
        db.commit()
        return school_id, user.id, {"Authorization": f"Bearer {raw}"}


def add_ptz_camera(school_id, *, source_type="CAMERA_IP"):
    with SessionLocal() as db:
        camera = Camera(
            school_id=school_id,
            name="PTZ Pátio",
            location="Pátio",
            ip_address="192.0.2.80",
            port=554,
            username="admin",
            password=encrypt_secret("secret-ptz"),
            manufacturer="Hikvision",
            camera_type="PTZ",
            source_type=source_type,
            ptz_enabled=True,
            ptz_protocol="HIKVISION_ISAPI",
            ptz_http_port=80,
            ptz_https=False,
            ptz_channel=1,
        )
        db.add(camera)
        db.commit()
        return camera.id


def test_ptz_permission_is_available_to_operational_roles():
    for role in [
        "GESTOR_SECRETARIA",
        "SUPERVISOR_GUARDA",
        "OPERADOR_GUARDA",
        "DESPACHANTE_GUARDA",
        "GESTOR_ESCOLA",
        "OPERADOR_ESCOLA",
        "TECNICO",
    ]:
        assert "ptz:control" in role_permissions(role, 1 if "ESCOLA" in role else None)


def test_ptz_lease_move_and_stop_are_auditable_and_isolated(client, monkeypatch):
    school_id, user_id, headers = auth_user()
    camera_id = add_ptz_camera(school_id)
    calls = []
    monkeypatch.setattr(application, "_ptz_target", lambda camera, db: {"channel": 1, "host": "x", "port": 80, "https": False, "username": "", "password": "", "via": "CAMERA"})
    monkeypatch.setattr(application, "_send_ptz_move", lambda db, camera, direction, speed: calls.append(("move", direction, speed)))
    monkeypatch.setattr(application, "_send_ptz_stop", lambda db, camera: calls.append(("stop",)))

    no_lease = client.post(f"/cameras/{camera_id}/ptz/move", json={"direction": "LEFT", "speed": 4}, headers=headers)
    assert no_lease.status_code == 409

    lease = client.post(f"/cameras/{camera_id}/ptz/lease", json={"force": False}, headers=headers)
    assert lease.status_code == 200
    assert lease.json()["lease"]["mine"] is True

    move = client.post(f"/cameras/{camera_id}/ptz/move", json={"direction": "UP_RIGHT", "speed": 6}, headers=headers)
    assert move.status_code == 200
    stop = client.post(f"/cameras/{camera_id}/ptz/stop", headers=headers)
    assert stop.status_code == 200
    assert calls == [("move", "UP_RIGHT", 6), ("stop",)]

    with SessionLocal() as db:
        lease_row = db.query(CameraPTZLease).filter(CameraPTZLease.camera_id == camera_id).one()
        assert lease_row.user_id == user_id
        camera = db.get(Camera, camera_id)
        assert camera.ptz_last_command_at is not None
        assert camera.ptz_last_error is None


def test_ptz_lease_blocks_concurrent_operator(client, monkeypatch):
    school_id, _, headers_a = auth_user(suffix="a")
    _, _, headers_b = auth_user(school_id=school_id, suffix="b")
    camera_id = add_ptz_camera(school_id)
    monkeypatch.setattr(application, "_ptz_target", lambda camera, db: {"channel": 1})

    assert client.post(f"/cameras/{camera_id}/ptz/lease", json={"force": False}, headers=headers_a).status_code == 200
    second = client.post(f"/cameras/{camera_id}/ptz/lease", json={"force": False}, headers=headers_b)
    assert second.status_code == 409
    assert "Em uso" in second.text or "em uso" in second.text


def test_ptz_school_operator_cannot_control_other_school(client, monkeypatch):
    school_a, _, _ = auth_user(suffix="central")
    school_b, _, headers_school = auth_user(role="OPERADOR_ESCOLA", suffix="school")
    camera_id = add_ptz_camera(school_a)
    monkeypatch.setattr(application, "_ptz_target", lambda camera, db: {"channel": 1})

    response = client.get(f"/cameras/{camera_id}/ptz/status", headers=headers_school)
    assert response.status_code == 404
    assert school_a != school_b


def test_ptz_presets_are_persisted_and_called(client, monkeypatch):
    school_id, _, headers = auth_user(suffix="preset")
    camera_id = add_ptz_camera(school_id)
    actions = []
    monkeypatch.setattr(application, "_ptz_target", lambda camera, db: {"channel": 1})
    monkeypatch.setattr(application, "_send_ptz_preset_set", lambda db, camera, preset_no, name: actions.append(("set", preset_no, name)))
    monkeypatch.setattr(application, "_send_ptz_preset_goto", lambda db, camera, preset_no: actions.append(("goto", preset_no)))
    monkeypatch.setattr(application, "_send_ptz_preset_delete", lambda db, camera, preset_no: actions.append(("delete", preset_no)))
    monkeypatch.setattr(application, "_send_ptz_stop", lambda db, camera: None)

    assert client.post(f"/cameras/{camera_id}/ptz/lease", json={"force": False}, headers=headers).status_code == 200
    saved = client.post(f"/cameras/{camera_id}/ptz/presets", json={"preset_no": 3, "name": "Portão"}, headers=headers)
    assert saved.status_code == 200
    listing = client.get(f"/cameras/{camera_id}/ptz/presets", headers=headers).json()
    assert listing["presets"] == [{"preset_no": 3, "name": "Portão"}]
    assert client.post(f"/cameras/{camera_id}/ptz/presets/3/goto", headers=headers).status_code == 200
    assert client.delete(f"/cameras/{camera_id}/ptz/presets/3", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.query(CameraPTZPreset).filter(CameraPTZPreset.camera_id == camera_id).count() == 0
    assert actions == [("set", 3, "Portão"), ("goto", 3), ("delete", 3)]


def test_ptz_target_uses_encrypted_camera_credentials_without_serializing_them(client):
    school_id, _, headers = auth_user(suffix="secret")
    camera_id = add_ptz_camera(school_id)
    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        target = application._ptz_target(camera, db)
        assert target["password"] == "secret-ptz"
        assert target["host"] == "192.0.2.80"
        assert target["port"] == 80
    body = client.get("/cameras", headers=headers).json()
    row = next(item for item in body if item["id"] == camera_id)
    assert "password" not in row
    assert row["ptz_enabled"] is True
    assert row["ptz_protocol"] == "HIKVISION_ISAPI"


def test_ptz_enabled_requires_ptz_camera_type(client, monkeypatch):
    school_id, _, headers = auth_user(role="GESTOR_SECRETARIA", suffix="validation")
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    payload = {
        "school_id": school_id,
        "name": "Fixa incorreta",
        "location": "Entrada",
        "ip_address": "192.0.2.95",
        "source_type": "CAMERA_IP",
        "camera_type": "FIXA",
        "ptz_enabled": True,
        "ptz_protocol": "HIKVISION_ISAPI",
        "ptz_http_port": 80,
        "ptz_channel": 1,
    }
    response = client.post("/cameras", json=payload, headers=headers)
    assert response.status_code == 400
    assert "tipo PTZ" in response.text
