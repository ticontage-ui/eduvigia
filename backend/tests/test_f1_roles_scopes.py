from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application import (
    AuthSession,
    Base,
    Camera,
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
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _session(db, *, role: str, email: str, school_id=None) -> dict:
    user = UserAccount(
        name=email.split("@")[0],
        email=email,
        password_hash=hash_password("SenhaForte@2026"),
        role=role,
        school_id=school_id,
        active=True,
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    raw = f"token-{user.id}-{role.lower()}"
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


def _seed_two_schools():
    with SessionLocal() as db:
        a = School(name="Escola F1 A", address="Rua A")
        b = School(name="Escola F1 B", address="Rua B")
        db.add_all([a, b])
        db.flush()
        db.add_all(
            [
                Camera(school_id=a.id, name="Cam A", location="Portão A"),
                Camera(school_id=b.id, name="Cam B", location="Portão B"),
                Occurrence(
                    protocol="EDU-F1-B",
                    school_id=b.id,
                    school_name=b.name,
                    description="Ocorrência B",
                ),
            ]
        )
        db.commit()
        return a.id, b.id


def test_school_profile_is_scoped_and_identifies_environment(client):
    school_a, school_b = _seed_two_schools()
    with SessionLocal() as db:
        headers = _session(
            db,
            role="GESTOR_ESCOLA",
            email="gestor.escola@local",
            school_id=school_a,
        )
        db.commit()

    permissions = client.get("/auth/permissions", headers=headers)
    assert permissions.status_code == 200
    body = permissions.json()
    assert body["role"] == "GESTOR_ESCOLA"
    assert body["environment"] == "ESCOLA"
    assert body["school_id"] == school_a
    assert body["school_required"] is True
    assert "monitor:view" in body["permissions"]

    cameras = client.get("/cameras", headers=headers)
    assert cameras.status_code == 200
    assert {row["school_id"] for row in cameras.json()} == {school_a}
    assert client.get(f"/schools/{school_b}", headers=headers).status_code == 404
    assert client.post(
        "/schools",
        headers=headers,
        json={"name": "Indevida", "address": "Rua X"},
    ).status_code == 403


def test_guard_operator_has_municipal_read_scope_but_no_asset_admin(client):
    school_a, school_b = _seed_two_schools()
    with SessionLocal() as db:
        headers = _session(
            db,
            role="OPERADOR_GUARDA",
            email="operador.guarda@local",
        )
        db.commit()

    permissions = client.get("/auth/permissions", headers=headers)
    assert permissions.status_code == 200
    body = permissions.json()
    assert body["environment"] == "GUARDA"
    assert "command:view" in body["permissions"]
    assert "cameras:write" not in body["permissions"]

    cameras = client.get("/cameras", headers=headers)
    assert cameras.status_code == 200
    assert {row["school_id"] for row in cameras.json()} == {school_a, school_b}

    assert client.post(
        "/schools",
        headers=headers,
        json={"name": "Escola indevida", "address": "Rua X"},
    ).status_code == 403

    occurrence = client.post(
        "/occurrences",
        headers=headers,
        json={"school_name": "Escola F1 A", "description": "Atendimento da Guarda"},
    )
    assert occurrence.status_code == 200


def test_secretaria_manager_can_manage_school_but_not_guard_dispatch(client):
    _seed_two_schools()
    with SessionLocal() as db:
        headers = _session(
            db,
            role="GESTOR_SECRETARIA",
            email="gestor.secretaria@local",
        )
        db.commit()

    permissions = client.get("/auth/permissions", headers=headers)
    assert permissions.status_code == 200
    body = permissions.json()
    assert body["environment"] == "SECRETARIA"
    assert "schools:write" in body["permissions"]
    assert "dispatch:operate" not in body["permissions"]

    created = client.post(
        "/schools",
        headers=headers,
        json={"name": "Escola F1 C", "address": "Rua C"},
    )
    assert created.status_code == 200
    assert client.get("/teams", headers=headers).status_code == 403


def test_admin_can_create_only_canonical_roles_and_school_binding_is_validated(client):
    school_a, _ = _seed_two_schools()
    with SessionLocal() as db:
        headers = _session(
            db,
            role="ADMIN_SECRETARIA",
            email="admin.secretaria@local",
        )
        db.commit()

    missing_school = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Gestor sem escola",
            "email": "sem.escola@local",
            "password": "SenhaForte@2026!",
            "role": "GESTOR_ESCOLA",
            "school_id": None,
            "active": True,
        },
    )
    assert missing_school.status_code == 400

    invalid_global_binding = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Guarda vinculada indevidamente",
            "email": "guarda.vinculada@local",
            "password": "SenhaForte@2026!",
            "role": "OPERADOR_GUARDA",
            "school_id": school_a,
            "active": True,
        },
    )
    assert invalid_global_binding.status_code == 400

    created = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Operador Escola",
            "email": "operador.escola.f1@local",
            "password": "SenhaForte@2026!",
            "role": "OPERADOR_ESCOLA",
            "school_id": school_a,
            "active": True,
        },
    )
    assert created.status_code == 200
    assert created.json()["role"] == "OPERADOR_ESCOLA"

    legacy = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Perfil legado",
            "email": "legado@local",
            "password": "SenhaForte@2026!",
            "role": "OPERADOR",
            "school_id": school_a,
            "active": True,
        },
    )
    assert legacy.status_code == 422
