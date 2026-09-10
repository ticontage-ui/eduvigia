import os
import urllib.parse
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession,
    Base,
    Camera,
    School,
    SessionLocal,
    UserAccount,
    app,
    engine,
    ensure_secure_camera_streams,
    hash_password,
    provision_camera_paths,
    token_digest,
)


os.environ["EDUVIGIA_STREAM_SIGNING_KEY"] = "teste-stream-signing-key-2026-com-mais-de-32-caracteres"


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _token(db, user: UserAccount, raw: str) -> str:
    now = datetime.now(timezone.utc)
    db.add(
        AuthSession(
            user_id=user.id,
            token=token_digest(raw),
            expires_at=now + timedelta(hours=2),
            last_seen_at=now,
        )
    )
    return raw


def _seed():
    with SessionLocal() as db:
        school_a = School(name="Escola Vídeo A", address="Rua A")
        school_b = School(name="Escola Vídeo B", address="Rua B")
        db.add_all([school_a, school_b])
        db.flush()
        camera_a = Camera(
            school_id=school_a.id,
            name="Câmera Portão A",
            location="Portão",
            ip_address="192.0.2.10",
            username="admin",
            password="senha",
            stream_profile="SUB",
            status="ONLINE",
        )
        camera_b = Camera(
            school_id=school_b.id,
            name="Câmera Portão B",
            location="Portão",
            ip_address="192.0.2.11",
            username="admin",
            password="senha",
            stream_profile="SUB",
            status="ONLINE",
        )
        db.add_all([camera_a, camera_b])
        db.flush()
        ensure_secure_camera_streams(db, camera_a)
        ensure_secure_camera_streams(db, camera_b)
        user = UserAccount(
            name="Operador A",
            email="operador.video.a@local",
            password_hash=hash_password("SenhaForte@2026"),
            role="OPERADOR_ESCOLA",
            school_id=school_a.id,
            active=True,
            must_change_password=False,
        )
        db.add(user)
        db.flush()
        raw = _token(db, user, "token-video-a")
        ids = (school_a.id, school_b.id, camera_a.id, camera_b.id, raw)
        db.commit()
        return ids


def test_stream_access_token_authorizes_only_correct_path(client, monkeypatch):
    _, _, camera_a_id, camera_b_id, raw = _seed()

    def fake_request(method, endpoint, body=None, timeout=5.0):
        if endpoint.startswith("/v3/paths/get/"):
            return 200, {"ready": True, "source": {"type": "rtspSource"}}
        return 200, {}

    monkeypatch.setattr(application, "mediamtx_request", fake_request)
    headers = {"Authorization": f"Bearer {raw}"}
    response = client.get(
        f"/cameras/{camera_a_id}/stream-access?profile=SUB",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "SUB"
    assert body["stream_name"].endswith("-sub")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(body["webrtc_url"]).query)
    token = query["token"][0]

    auth = client.post(
        "/internal/mediamtx-auth",
        json={
            "action": "read",
            "path": body["stream_name"],
            "protocol": "webrtc",
            "query": urllib.parse.urlencode({"token": token}),
        },
    )
    assert auth.status_code == 200

    wrong_path = client.post(
        "/internal/mediamtx-auth",
        json={
            "action": "read",
            "path": "outra-camera-sub",
            "protocol": "webrtc",
            "query": urllib.parse.urlencode({"token": token}),
        },
    )
    assert wrong_path.status_code == 403

    other_school = client.get(
        f"/cameras/{camera_b_id}/stream-access?profile=SUB",
        headers=headers,
    )
    assert other_school.status_code == 404


def test_invalid_or_missing_token_is_denied(client):
    response = client.post(
        "/internal/mediamtx-auth",
        json={
            "action": "read",
            "path": "qualquer-stream",
            "protocol": "webrtc",
            "query": "",
        },
    )
    assert response.status_code == 403

    publish = client.post(
        "/internal/mediamtx-auth",
        json={
            "action": "publish",
            "path": "stream-falso",
            "protocol": "rtsp",
            "query": "",
        },
    )
    assert publish.status_code == 403


def test_main_and_sub_are_provisioned_together(client, monkeypatch):
    calls = []

    def fake_request(method, endpoint, body=None, timeout=5.0):
        calls.append((method, endpoint, body))
        if method == "GET":
            return 404, {}
        return 201, {}

    monkeypatch.setattr(application, "mediamtx_request", fake_request)
    with SessionLocal() as db:
        school = School(name="Escola Duplo Perfil", address="Rua A")
        db.add(school)
        db.flush()
        camera = Camera(
            school_id=school.id,
            name="Câmera Duplo Perfil",
            location="Pátio",
            ip_address="192.0.2.20",
            username="admin",
            password="senha",
            stream_profile="SUB",
        )
        db.add(camera)
        db.flush()
        ok, result = provision_camera_paths(camera, db)
        assert ok is True
        assert result["MAIN"]["ok"] is True
        assert result["SUB"]["ok"] is True
        assert camera.stream_name_main.endswith("-main")
        assert camera.stream_name_sub.endswith("-sub")
        assert camera.stream_name_main != camera.stream_name_sub
        assert camera.stream_name_main.rsplit("-", 1)[0] == camera.stream_name_sub.rsplit("-", 1)[0]
        added = [endpoint for method, endpoint, _ in calls if method == "POST"]
        assert any(camera.stream_name_main in endpoint for endpoint in added)
        assert any(camera.stream_name_sub in endpoint for endpoint in added)


def test_authenticated_test_stream_receives_temporary_token(client, monkeypatch):
    _, _, _, _, raw = _seed()
    monkeypatch.setattr(application, "mediamtx_request", lambda *args, **kwargs: (200, {"ready": True}))
    response = client.get(
        "/streams/test-access",
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stream_name"] == "teste"
    token = urllib.parse.parse_qs(urllib.parse.urlsplit(body["webrtc_url"]).query)["token"][0]
    auth = client.post(
        "/internal/mediamtx-auth",
        json={
            "action": "read",
            "path": "teste",
            "protocol": "webrtc",
            "query": urllib.parse.urlencode({"token": token}),
        },
    )
    assert auth.status_code == 200
