from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.application import (
    Alert,
    AuditLog,
    AuthSession,
    Base,
    Camera,
    Equipment,
    Evidence,
    Occurrence,
    School,
    SessionLocal,
    UserAccount,
    app,
    engine,
    hash_password,
    token_digest,
)


def _session_token(db, user: UserAccount, raw_token: str) -> str:
    now = datetime.now(timezone.utc)
    db.add(
        AuthSession(
            user_id=user.id,
            token=token_digest(raw_token),
            expires_at=now + timedelta(hours=2),
            last_seen_at=now,
        )
    )
    return raw_token


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _seed_two_schools():
    with SessionLocal() as db:
        school_a = School(name="Escola A", address="Rua A")
        school_b = School(name="Escola B", address="Rua B")
        db.add_all([school_a, school_b])
        db.flush()

        camera_a = Camera(school_id=school_a.id, name="Câmera A", location="Portão A")
        camera_b = Camera(school_id=school_b.id, name="Câmera B", location="Portão B")
        occurrence_b = Occurrence(
            protocol="EDU-TESTE-B",
            school_id=school_b.id,
            school_name=school_b.name,
            description="Ocorrência da escola B",
        )
        db.add_all([camera_a, camera_b, occurrence_b])

        school_user = UserAccount(
            name="Usuário Escola A",
            email="escola.a@local",
            password_hash=hash_password("SenhaForte@2026"),
            role="GESTOR_ESCOLA",
            school_id=school_a.id,
            active=True,
            must_change_password=False,
        )
        operator = UserAccount(
            name="Operador Escola A",
            email="operador.a@local",
            password_hash=hash_password("SenhaForte@2026"),
            role="OPERADOR_ESCOLA",
            school_id=school_a.id,
            active=True,
            must_change_password=False,
        )
        db.add_all([school_user, operator])
        db.flush()
        school_token = _session_token(db, school_user, "token-escola-a")
        operator_token = _session_token(db, operator, "token-operador-a")
        db.commit()
        return {
            "school_a": school_a.id,
            "school_b": school_b.id,
            "occurrence_b": occurrence_b.id,
            "school_token": school_token,
            "operator_token": operator_token,
        }


def test_school_user_cannot_read_other_school_or_global_settings(client):
    data = _seed_two_schools()
    headers = {"Authorization": f"Bearer {data['school_token']}"}

    response = client.get(f"/schools/{data['school_b']}", headers=headers)
    assert response.status_code == 404

    response = client.get("/cameras", headers=headers)
    assert response.status_code == 200
    assert {item["school_id"] for item in response.json()} == {data["school_a"]}

    assert client.get("/settings", headers=headers).status_code == 403
    assert client.get("/audit", headers=headers).status_code == 403


def test_school_scoped_operator_cannot_modify_other_school_occurrence(client):
    data = _seed_two_schools()
    headers = {"Authorization": f"Bearer {data['operator_token']}"}
    response = client.patch(
        f"/occurrences/{data['occurrence_b']}",
        headers=headers,
        json={"status": "EM_ANALISE", "assigned_team": None},
    )
    assert response.status_code == 403


def test_password_change_is_mandatory_and_revokes_other_sessions(client):
    with SessionLocal() as db:
        school = School(name="Escola da Troca de Senha", code="ETS", address="Rua Teste, 1")
        db.add(school)
        db.flush()
        user = UserAccount(
            name="Usuário Temporário",
            email="temporario@local",
            password_hash=hash_password("SenhaAtual@2026"),
            role="OPERADOR_ESCOLA",
            school_id=school.id,
            active=True,
            must_change_password=True,
        )
        db.add(user)
        db.flush()
        current_token = _session_token(db, user, "token-atual")
        other_token = _session_token(db, user, "token-antigo")
        db.commit()

    current_headers = {"Authorization": f"Bearer {current_token}"}
    blocked = client.get("/dashboard", headers=current_headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

    changed = client.post(
        "/auth/change-password",
        headers=current_headers,
        json={"current_password": "SenhaAtual@2026", "new_password": "NovaSenha@2026!"},
    )
    assert changed.status_code == 200
    assert changed.json()["revoked_sessions"] == 1

    assert client.get("/dashboard", headers=current_headers).status_code == 200
    assert client.get(
        "/dashboard", headers={"Authorization": f"Bearer {other_token}"}
    ).status_code == 401


def test_audit_records_authenticated_actor(client):
    with SessionLocal() as db:
        admin = UserAccount(
            name="Administrador Teste",
            email="admin.teste@local",
            password_hash=hash_password("SenhaAdmin@2026"),
            role="ADMIN_SECRETARIA",
            active=True,
            must_change_password=False,
        )
        db.add(admin)
        db.flush()
        token = _session_token(db, admin, "token-admin")
        admin_id = admin.id
        db.commit()

    response = client.put(
        "/settings/teste_seguranca",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "pytest-eduvigia"},
        json={"value": "ativo", "description": "Teste"},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        row = (
            db.query(AuditLog)
            .filter(AuditLog.action == "Parâmetro alterado")
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert row is not None
        assert row.user_id == admin_id
        assert row.user_email == "admin.teste@local"
        assert row.user_role == "ADMIN_SECRETARIA"
        assert row.user_agent == "pytest-eduvigia"


def test_evidence_and_equipment_are_isolated_by_school(client, tmp_path):
    data = _seed_two_schools()
    evidence_path = tmp_path / "evidence-b.txt"
    evidence_path.write_text("conteudo", encoding="utf-8")
    with SessionLocal() as db:
        occurrence = db.get(Occurrence, data["occurrence_b"])
        evidence = Evidence(
            occurrence_id=occurrence.id,
            evidence_type="ANEXO",
            filename="evidence-b.txt",
            original_name="evidence-b.txt",
            mime_type="text/plain",
            file_path=str(evidence_path),
        )
        equipment = Equipment(
            school_id=data["school_b"],
            category="CAMERA",
            name="Equipamento B",
        )
        technician = UserAccount(
            name="Técnico Escola A",
            email="tecnico.a@local",
            password_hash=hash_password("SenhaForte@2026"),
            role="TECNICO",
            school_id=data["school_a"],
            active=True,
            must_change_password=False,
        )
        db.add_all([evidence, equipment, technician])
        db.flush()
        evidence_id = evidence.id
        equipment_id = equipment.id
        tech_token = _session_token(db, technician, "token-tecnico-a")
        db.commit()

    school_headers = {"Authorization": f"Bearer {data['school_token']}"}
    assert client.get(f"/evidence/{evidence_id}/file", headers=school_headers).status_code == 404

    tech_headers = {"Authorization": f"Bearer {tech_token}"}
    response = client.post(
        f"/equipment/{equipment_id}/maintenance",
        headers=tech_headers,
        json={"maintenance_type": "CORRETIVA", "description": "Teste indevido"},
    )
    assert response.status_code == 404


def test_school_report_summary_contains_only_its_scope(client):
    data = _seed_two_schools()
    headers = {"Authorization": f"Bearer {data['school_token']}"}
    response = client.get("/reports/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["schools"] == 1
    assert body["cameras"] == 1
    assert body["occurrences_total"] == 0

def test_operational_profile_without_school_is_denied(client):
    with SessionLocal() as db:
        user = UserAccount(
            name="Operador sem escola",
            email="operador.sem.escola@local",
            password_hash=hash_password("SenhaForte@2026"),
            role="OPERADOR_ESCOLA",
            school_id=None,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        token = _session_token(db, user, "token-operador-sem-escola")
        db.commit()

    response = client.get(
        "/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

