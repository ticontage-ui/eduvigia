from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession,
    Base,
    Camera,
    Notification,
    NotificationRead,
    Occurrence,
    School,
    SessionLocal,
    UserAccount,
    app,
    engine,
    hash_password,
    token_digest,
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(application, "DATA_DIR", tmp_path)
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _auth(role="ADMIN_SECRETARIA", school_id=None, suffix="f7r2"):
    with SessionLocal() as db:
        user = UserAccount(
            name=f"Usuário {role}",
            email=f"{role.lower()}-{suffix}@local",
            password_hash=hash_password("SenhaForte@2026"),
            role=role,
            school_id=school_id,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = f"token-{role.lower()}-{suffix}"
        now = datetime.now(timezone.utc)
        db.add(
            AuthSession(
                user_id=user.id,
                token=token_digest(raw),
                expires_at=now + timedelta(hours=1),
                last_seen_at=now,
            )
        )
        db.commit()
        return {"Authorization": f"Bearer {raw}"}, user.id


def _school_payload(code="ESC-001", name="Escola Central", kit_type="KIT_16"):
    return {
        "code": code,
        "name": name,
        "address": "Rua Central, 100",
        "neighborhood": "Centro",
        "city": "Cidade",
        "phone": "",
        "email": "",
        "latitude": "",
        "longitude": "",
        "kit_type": kit_type,
        "responsible": "Direção",
        "operational_status": "OPERACIONAL",
        "notes": "",
    }


def test_school_edit_accepts_kits_to_64_and_toggle_notifies_per_user(client):
    admin_a, user_a = _auth(suffix="school-a")
    admin_b, user_b = _auth(suffix="school-b")

    created = client.post("/schools", headers=admin_a, json=_school_payload())
    assert created.status_code == 200, created.text
    school = created.json()
    assert school["kit_type"] == "KIT_16"

    edited_payload = _school_payload(name="Escola Central Editada", kit_type="KIT_15")
    edited = client.put(f"/schools/{school['id']}", headers=admin_a, json=edited_payload)
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "Escola Central Editada"
    assert edited.json()["kit_type"] == "KIT_15"

    toggled = client.patch(f"/schools/{school['id']}/toggle", headers=admin_a)
    assert toggled.status_code == 200
    assert toggled.json()["active"] is False

    rows_a = client.get("/notifications", headers=admin_a).json()
    school_notification = next(item for item in rows_a if item.get("entity_type") == "school" and item.get("entity_id") == school["id"])
    assert school_notification["read_at"] is None
    assert "inativada" in school_notification["title"].lower()

    read_a = client.patch(f"/notifications/{school_notification['id']}/read", headers=admin_a)
    assert read_a.status_code == 200
    assert read_a.json()["read_at"] is not None

    rows_b = client.get("/notifications", headers=admin_b).json()
    same_for_b = next(item for item in rows_b if item["id"] == school_notification["id"])
    assert same_for_b["read_at"] is None

    with SessionLocal() as db:
        assert db.query(NotificationRead).filter(NotificationRead.notification_id == school_notification["id"]).count() == 1
        assert db.query(NotificationRead).filter(NotificationRead.user_id == user_a).count() >= 1
        assert db.query(NotificationRead).filter(NotificationRead.user_id == user_b).count() == 0


def test_camera_code_is_generated_automatically_and_searchable(client):
    headers, _ = _auth(suffix="camera-code")
    school = client.post("/schools", headers=headers, json=_school_payload(code="ESC-CAM", kit_type="KIT_16")).json()

    payload = {
        "school_id": school["id"],
        "name": "Câmera Entrada",
        "location": "Entrada",
        "ip_address": "192.0.2.20",
        "port": 554,
        "manufacturer": "Hikvision",
        "camera_type": "FIXA",
        "source_type": "CAMERA_IP",
        "stream_profile": "SUB",
        "logical_channel": 1,
        "sensor_type": "VISIBLE",
        "primary_sensor": True,
        "nvr_channel": 1,
        "ptz_enabled": False,
        "ptz_protocol": "HIKVISION_ISAPI",
        "ptz_http_port": 80,
        "ptz_https": False,
        "ptz_channel": 1,
    }
    first = client.post("/cameras", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["code"].startswith("CAM-")

    payload["name"] = "Câmera Pátio"
    payload["location"] = "Pátio"
    payload["ip_address"] = "192.0.2.21"
    second = client.post("/cameras", headers=headers, json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["code"] != first_body["code"]

    listing = client.get(f"/cameras?search={first_body['code']}", headers=headers)
    assert listing.status_code == 200
    assert [row["id"] for row in listing.json()] == [first_body["id"]]


def test_alerts_are_operational_without_ai_contract_and_create_occurrence(client):
    headers, _ = _auth(role="OPERADOR_GUARDA", suffix="alert")
    with SessionLocal() as db:
        school = School(code="ESC-ALT", name="Escola Alerta", address="Rua Alerta", kit_type="KIT_16")
        db.add(school)
        db.flush()
        camera = Camera(code="CAM-999001", school_id=school.id, name="Entrada", location="Portão", status="ONLINE")
        db.add(camera)
        db.commit()
        school_id, camera_id = school.id, camera.id

    created = client.post(
        "/alerts",
        headers=headers,
        json={
            "school_id": school_id,
            "camera_id": camera_id,
            "event_type": "Acesso não autorizado",
            "priority": "ALTA",
            "summary": "Pessoa em área restrita",
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["status"] == "NOVO"
    assert "source" not in body
    assert "confidence" not in body

    detail = client.get(f"/alerts/{body['id']}/details", headers=headers)
    assert detail.status_code == 200
    assert "source" not in detail.json()
    assert "confidence" not in detail.json()

    occurrence = client.post(f"/alerts/{body['id']}/occurrence", headers=headers)
    assert occurrence.status_code == 200, occurrence.text
    assert occurrence.json()["category"] == "SEGURANCA"
    assert occurrence.json()["protocol"].startswith("EDU-")

    with SessionLocal() as db:
        sequence_rows = db.query(application.OccurrenceSequence).all()
        assert len(sequence_rows) == 1
        assert sequence_rows[0].last_value >= 1


def test_school_notification_scope_does_not_leak_to_other_school(client):
    admin, _ = _auth(suffix="scope-admin")
    school_a = client.post("/schools", headers=admin, json=_school_payload(code="ESC-A", name="Escola A")).json()
    school_b = client.post("/schools", headers=admin, json=_school_payload(code="ESC-B", name="Escola B")).json()
    school_user, _ = _auth(role="GESTOR_ESCOLA", school_id=school_b["id"], suffix="scope-school")

    client.patch(f"/schools/{school_a['id']}/toggle", headers=admin)
    rows = client.get("/notifications", headers=school_user)
    assert rows.status_code == 200
    assert not any(item.get("entity_type") == "school" and item.get("entity_id") == school_a["id"] for item in rows.json())
