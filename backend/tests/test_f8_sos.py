from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application import (
    Alert,
    AuthSession,
    Base,
    Notification,
    Occurrence,
    School,
    SessionLocal,
    SosActivity,
    SosEvent,
    UserAccount,
    app,
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


def _auth(db, role, school_id=None, suffix="a"):
    user = UserAccount(
        name=f"SOS {role}",
        email=f"sos-{role.lower()}-{suffix}@local",
        password_hash=hash_password("Senha@2026a"),
        role=role,
        school_id=school_id,
        active=True,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    raw = f"sos-token-{role}-{suffix}"
    now = datetime.now(timezone.utc)
    db.add(
        AuthSession(
            user_id=user.id,
            token=token_digest(raw),
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
        )
    )
    db.flush()
    return {"Authorization": f"Bearer {raw}"}


def _schools(db):
    a = School(name="Escola SOS A", address="Rua A", active=True)
    b = School(name="Escola SOS B", address="Rua B", active=True)
    db.add_all([a, b])
    db.flush()
    return a, b


def test_f8_permissions_contract():
    assert {"sos:view", "sos:use"}.issubset(role_permissions("GESTOR_ESCOLA", 1))
    assert {"sos:view", "sos:use"}.issubset(role_permissions("OPERADOR_ESCOLA", 1))
    assert "sos:operate" not in role_permissions("GESTOR_ESCOLA", 1)
    assert "sos:operate" not in role_permissions("OPERADOR_ESCOLA", 1)

    for role in [
        "GESTOR_SECRETARIA",
        "SUPERVISOR_GUARDA",
        "OPERADOR_GUARDA",
        "DESPACHANTE_GUARDA",
    ]:
        assert {"sos:view", "sos:operate"}.issubset(role_permissions(role, None)), role
        assert "sos:use" not in role_permissions(role, None), role

    assert "sos:view" not in role_permissions("TECNICO", None)
    assert "sos:use" not in role_permissions("TECNICO", None)
    assert "sos:operate" not in role_permissions("TECNICO", None)


def test_school_activation_creates_critical_alert_occurrence_notification_and_timeline(client):
    with SessionLocal() as db:
        school, _ = _schools(db)
        headers = _auth(db, "GESTOR_ESCOLA", school.id, "activate")
        db.commit()
        school_id = school.id

    response = client.post(
        "/sos/activate",
        headers=headers,
        json={"note": "Pessoa estranha no portão"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["school_id"] == school_id
    assert body["status"] == "ACTIVE"
    assert body["repeat_count"] == 1

    with SessionLocal() as db:
        row = db.get(SosEvent, body["id"])
        alert = db.get(Alert, row.alert_id)
        occurrence = db.get(Occurrence, row.occurrence_id)
        assert alert.priority == "CRITICA"
        assert alert.source == "SOS"
        assert alert.status == "NOVO"
        assert occurrence.category == "EMERGENCIA"
        assert occurrence.priority == "CRITICA"
        assert occurrence.status == "ABERTA"
        assert occurrence.alert_id == alert.id
        assert db.query(SosActivity).filter(SosActivity.sos_event_id == row.id).count() == 1
        notification = db.query(Notification).filter(Notification.entity_type == "sos").one()
        assert notification.school_id == school_id
        assert notification.severity == "CRITICAL"


def test_repeat_activation_reuses_open_event_alert_and_occurrence(client):
    with SessionLocal() as db:
        school, _ = _schools(db)
        headers = _auth(db, "OPERADOR_ESCOLA", school.id, "repeat")
        db.commit()

    first = client.post("/sos/activate", headers=headers, json={}).json()
    second_response = client.post(
        "/sos/activate",
        headers=headers,
        json={"note": "Reforço"},
    )
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    assert second["id"] == first["id"]
    assert second["repeat_count"] == 2

    with SessionLocal() as db:
        assert db.query(SosEvent).count() == 1
        assert db.query(Alert).filter(Alert.source == "SOS").count() == 1
        assert db.query(Occurrence).filter(Occurrence.category == "EMERGENCIA").count() == 1
        assert db.query(SosActivity).filter(SosActivity.action == "REFORCO").count() == 1


def test_school_scope_and_technical_denial(client):
    with SessionLocal() as db:
        school_a, school_b = _schools(db)
        a_headers = _auth(db, "GESTOR_ESCOLA", school_a.id, "a")
        b_headers = _auth(db, "GESTOR_ESCOLA", school_b.id, "b")
        tech_headers = _auth(db, "TECNICO", None, "tech")
        db.commit()

    event = client.post("/sos/activate", headers=a_headers, json={}).json()
    assert len(client.get("/sos", headers=a_headers).json()) == 1
    assert client.get(f"/sos/{event['id']}/details", headers=b_headers).status_code == 404
    assert client.get("/sos", headers=tech_headers).status_code == 403
    assert client.post("/sos/activate", headers=tech_headers, json={}).status_code == 403


def test_central_acknowledges_and_resolves_but_school_cannot_operate(client):
    with SessionLocal() as db:
        school, _ = _schools(db)
        school_headers = _auth(db, "GESTOR_ESCOLA", school.id, "school")
        central_headers = _auth(db, "SUPERVISOR_GUARDA", None, "central")
        db.commit()

    event = client.post("/sos/activate", headers=school_headers, json={}).json()
    assert (
        client.post(
            f"/sos/{event['id']}/acknowledge",
            headers=school_headers,
            json={},
        ).status_code
        == 403
    )

    ack = client.post(
        f"/sos/{event['id']}/acknowledge",
        headers=central_headers,
        json={"note": "Central ciente"},
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["status"] == "ACKNOWLEDGED"

    resolved = client.post(
        f"/sos/{event['id']}/resolve",
        headers=central_headers,
        json={"status": "RESOLVED", "note": "Equipe confirmou normalização"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"

    with SessionLocal() as db:
        row = db.get(SosEvent, event["id"])
        alert = db.get(Alert, row.alert_id)
        occurrence = db.get(Occurrence, row.occurrence_id)
        assert alert.status == "ENCERRADO"
        assert occurrence.status == "ENCERRADA"
        assert occurrence.closed_at is not None


def test_cancel_request_requires_central_validation_and_false_alarm(client):
    with SessionLocal() as db:
        school, _ = _schools(db)
        school_headers = _auth(db, "OPERADOR_ESCOLA", school.id, "school-cancel")
        central_headers = _auth(db, "DESPACHANTE_GUARDA", None, "dispatch")
        db.commit()

    event = client.post("/sos/activate", headers=school_headers, json={}).json()
    cancel = client.post(
        f"/sos/{event['id']}/request-cancel",
        headers=school_headers,
        json={"note": "Acionamento acidental"},
    )
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "CANCEL_REQUESTED"

    with SessionLocal() as db:
        row = db.get(SosEvent, event["id"])
        assert db.get(Occurrence, row.occurrence_id).status != "ENCERRADA"

    final = client.post(
        f"/sos/{event['id']}/resolve",
        headers=central_headers,
        json={"status": "FALSE_ALARM", "note": "Validado com a escola"},
    )
    assert final.status_code == 200, final.text
    assert final.json()["status"] == "FALSE_ALARM"

    with SessionLocal() as db:
        row = db.get(SosEvent, event["id"])
        alert = db.get(Alert, row.alert_id)
        occurrence = db.get(Occurrence, row.occurrence_id)
        assert alert.status == "DESCARTADO"
        assert occurrence.status == "ENCERRADA"


def test_new_trigger_after_cancel_request_reactivates_same_event(client):
    with SessionLocal() as db:
        school, _ = _schools(db)
        headers = _auth(db, "GESTOR_ESCOLA", school.id, "reactivate")
        db.commit()

    event = client.post("/sos/activate", headers=headers, json={}).json()
    cancel = client.post(
        f"/sos/{event['id']}/request-cancel",
        headers=headers,
        json={"note": "Possível engano"},
    )
    assert cancel.json()["status"] == "CANCEL_REQUESTED"

    reinforced = client.post(
        "/sos/activate",
        headers=headers,
        json={"note": "Emergência confirmada"},
    )
    assert reinforced.status_code == 200, reinforced.text
    body = reinforced.json()
    assert body["id"] == event["id"]
    assert body["status"] == "ACTIVE"
    assert body["repeat_count"] == 2
    assert body["cancel_requested_at"] is None
