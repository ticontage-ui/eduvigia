from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession,
    Base,
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
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _session(role="ADMIN_SECRETARIA"):
    with SessionLocal() as db:
        school = School(name="Escola Infra", address="Rua Infra")
        db.add(school)
        db.flush()
        user = UserAccount(
            name=f"Usuário {role}",
            email=f"{role.lower()}-infra@local",
            password_hash=hash_password("SenhaForte@2026"),
            role=role,
            school_id=None if role in {"ADMIN_SECRETARIA", "GESTOR_SECRETARIA"} else school.id,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = f"token-{role.lower()}-infra"
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
        return {"Authorization": f"Bearer {raw}"}


def test_liveness_is_public_and_returns_request_id(client):
    response = client.get("/live", headers={"X-Request-ID": "req-phase4"})
    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0-F7-R3"
    assert response.headers["X-Request-ID"] == "req-phase4"


def test_metrics_are_public_prometheus_text(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'eduvigia_info{version="2.0.0-F7-R3"' in response.text
    assert "eduvigia_http_requests_total" in response.text
    assert "eduvigia_database_up 1" in response.text


def test_readiness_returns_200_when_dependencies_are_ready(client, monkeypatch):
    monkeypatch.setattr(
        application,
        "collect_readiness",
        lambda db=None: {
            "ready": True,
            "status": "READY",
            "version": "2.0.0-F7-R3",
            "checked_at": "2026-07-08T00:00:00Z",
            "startup_complete": True,
            "services": {},
        },
    )
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_readiness_returns_503_when_dependency_fails(client, monkeypatch):
    monkeypatch.setattr(
        application,
        "collect_readiness",
        lambda db=None: {
            "ready": False,
            "status": "NOT_READY",
            "version": "2.0.0-F7-R3",
            "checked_at": "2026-07-08T00:00:00Z",
            "startup_complete": True,
            "services": {"database": {"status": "OFFLINE"}},
        },
    )
    response = client.get("/ready")
    assert response.status_code == 503


def test_capacity_requires_privileged_role(client):
    operator_headers = _session("OPERADOR_ESCOLA")
    response = client.get("/infrastructure/capacity", headers=operator_headers)
    assert response.status_code == 403


def test_capacity_exposes_pool_retention_and_scaling(client):
    admin_headers = _session("ADMIN_SECRETARIA")
    response = client.get("/infrastructure/capacity", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "2.0.0-F7-R3"
    assert "database_pool" in body
    assert body["retention"]["backup_days"] >= 1
    assert body["scaling"]["recommended_api_workers"] >= 1
    assert body["endpoints"]["proxy_https"] == 18443


def test_metric_paths_do_not_keep_numeric_identifiers():
    assert application._normalized_metric_path("/cameras/123/stream") == "/cameras/{id}/stream"

def test_infrastructure_preflight_validates_running_api_readiness(monkeypatch, tmp_path, capsys):
    from contextlib import nullcontext

    import app.infrastructure_preflight as infrastructure_preflight

    cert_dir = tmp_path / "certs"
    cert_dir.mkdir()
    (cert_dir / "eduvigia.crt").write_text("cert", encoding="utf-8")
    (cert_dir / "eduvigia.key").write_text("key", encoding="utf-8")

    live = {"status": "alive", "version": "2.0.0-F7-R3"}
    ready = {
        "ready": True,
        "status": "READY",
        "version": "2.0.0-F7-R3",
        "startup_complete": True,
        "services": {
            "database": {"status": "ONLINE"},
            "redis": {"status": "ONLINE"},
            "mediamtx": {"status": "ONLINE"},
            "storage": {"status": "ONLINE"},
        },
    }

    monkeypatch.setattr(
        infrastructure_preflight,
        "_url_json",
        lambda url: live if url.endswith("/live") else ready,
    )
    monkeypatch.setattr(
        infrastructure_preflight,
        "_url_text",
        lambda _url: "\n".join(
            (
                "eduvigia_info 1",
                "eduvigia_database_up 1",
                "eduvigia_http_requests_total 1",
                "eduvigia_database_pool_size 10",
            )
        ),
    )
    monkeypatch.setattr(
        infrastructure_preflight.socket,
        "create_connection",
        lambda *_args, **_kwargs: nullcontext(),
    )
    monkeypatch.setenv("EDUVIGIA_TLS_CERT_DIR", str(cert_dir))

    infrastructure_preflight.main()
    output = capsys.readouterr().out
    assert "INFRA_PHASE4_PREFLIGHT_OK" in output

