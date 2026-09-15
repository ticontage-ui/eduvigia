from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    Alert,
    AuthSession,
    Base,
    Camera,
    CameraEvent,
    CameraHealth,
    Notification,
    Recorder,
    RecorderHealth,
    School,
    SessionLocal,
    UserAccount,
    app,
    engine,
    hash_password,
    normalize_camera_event_type,
    parse_hikvision_event_xml,
    token_digest,
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(application, "DATA_DIR", tmp_path)
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    monkeypatch.setenv("EDUVIGIA_EVENT_INGEST_KEY", "event-test-key")
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def _auth(role="ADMIN_SECRETARIA", school_id=None, suffix="f7r3"):
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


def _seed_camera():
    with SessionLocal() as db:
        school = School(code="ESC-EVT", name="Escola Eventos", address="Rua Eventos", kit_type="KIT_16")
        db.add(school)
        db.flush()
        recorder = Recorder(
            school_id=school.id,
            name="NVR Eventos",
            ip_address="192.0.2.50",
            username="admin",
            password=application.encrypt_secret("senha"),
            status="ONLINE",
        )
        db.add(recorder)
        db.flush()
        camera = Camera(
            code="CAM-700001",
            school_id=school.id,
            name="Entrada Principal",
            location="Portão",
            source_type="NVR",
            recorder_id=recorder.id,
            nvr_channel=1,
            status="ONLINE",
            main_status="ONLINE",
            sub_status="ONLINE",
        )
        db.add(camera)
        db.commit()
        return school.id, recorder.id, camera.id


def test_event_catalog_normalizes_hikvision_and_onvif_names():
    assert normalize_camera_event_type("linedetection", "HIKVISION_ISAPI") == "LINE_CROSSING"
    assert normalize_camera_event_type("fielddetection", "HIKVISION_ISAPI") == "INTRUSION"
    assert normalize_camera_event_type("tns1:RuleEngine/CellMotionDetector/Motion", "ONVIF") == "MOTION"
    assert normalize_camera_event_type("tns1:VideoSource/Tamper", "ONVIF") == "TAMPER"


def test_ingest_creates_device_event_alert_notification_and_health(client):
    school_id, recorder_id, camera_id = _seed_camera()
    response = client.post(
        "/integrations/camera-events/ingest",
        headers={"X-EduVigIA-Event-Key": "event-test-key"},
        json={
            "provider": "HIKVISION_ISAPI",
            "provider_event_type": "fielddetection",
            "event_state": "active",
            "recorder_id": recorder_id,
            "source_channel": 1,
            "metadata": {"zone": "Portão", "fps": 15, "bitrate_kbps": 2048},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["event_type"] == "INTRUSION"
    assert body["alert_id"] is not None

    with SessionLocal() as db:
        event = db.get(CameraEvent, body["event_id"])
        assert event.camera_id == camera_id
        assert event.school_id == school_id
        assert event.repeat_count == 1
        alert = db.get(Alert, body["alert_id"])
        assert alert is not None
        assert alert.source == "DISPOSITIVO"
        assert alert.confidence is None
        health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        assert health.fps == 15
        assert health.bitrate_kbps == 2048
        assert db.query(Notification).filter(Notification.entity_type == "alert", Notification.entity_id == alert.id).count() == 1


def test_repeated_active_event_is_deduplicated_and_does_not_duplicate_alert(client):
    _, recorder_id, _ = _seed_camera()
    headers = {"X-EduVigIA-Event-Key": "event-test-key"}
    payload = {
        "provider": "HIKVISION_ISAPI",
        "provider_event_type": "linedetection",
        "event_state": "active",
        "recorder_id": recorder_id,
        "source_channel": 1,
    }
    first = client.post("/integrations/camera-events/ingest", headers=headers, json=payload)
    second = client.post("/integrations/camera-events/ingest", headers=headers, json=payload)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["deduplicated"] is True
    assert second.json()["event_id"] == first.json()["event_id"]
    assert second.json()["repeat_count"] == 2
    with SessionLocal() as db:
        assert db.query(CameraEvent).filter(CameraEvent.event_type == "LINE_CROSSING").count() == 1
        assert db.query(Alert).filter(Alert.id == first.json()["alert_id"]).count() == 1


def test_health_fault_recovery_closes_technical_alert(client):
    _, _, camera_id = _seed_camera()
    headers = {"X-EduVigIA-Event-Key": "event-test-key"}
    failed = client.post(
        "/integrations/camera-events/ingest",
        headers=headers,
        json={
            "provider": "EDUVIGIA_HEALTH",
            "provider_event_type": "CAMERA_OFFLINE",
            "event_state": "ACTIVE",
            "camera_id": camera_id,
            "metadata": {"error": "timeout"},
        },
    )
    assert failed.status_code == 200
    recovered = client.post(
        "/integrations/camera-events/ingest",
        headers=headers,
        json={
            "provider": "EDUVIGIA_HEALTH",
            "provider_event_type": "CAMERA_OFFLINE",
            "event_state": "INACTIVE",
            "camera_id": camera_id,
        },
    )
    assert recovered.status_code == 200
    assert recovered.json()["state"] == "INACTIVE"
    with SessionLocal() as db:
        event = db.get(CameraEvent, failed.json()["event_id"])
        assert event.active is False
        assert event.repeat_count == 2
        alert = db.get(Alert, failed.json()["alert_id"])
        assert alert.status == "ENCERRADO"
        health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        assert health.state == "ONLINE"
        assert health.rtsp_online is True


def test_hikvision_xml_ingress_maps_channel_to_camera(client):
    _, recorder_id, camera_id = _seed_camera()
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<EventNotificationAlert xmlns="http://www.hikvision.com/ver20/XMLSchema" version="2.0">
  <ipAddress>192.0.2.50</ipAddress>
  <channelID>1</channelID>
  <dateTime>2026-09-11T13:30:00-03:00</dateTime>
  <eventType>tamperdetection</eventType>
  <eventState>active</eventState>
  <eventDescription>tamper alarm</eventDescription>
</EventNotificationAlert>'''
    parsed = parse_hikvision_event_xml(xml)
    assert len(parsed) == 1
    assert parsed[0]["provider_event_type"] == "tamperdetection"
    response = client.post(
        f"/integrations/camera-events/hikvision?recorder_id={recorder_id}",
        headers={"X-EduVigIA-Event-Key": "event-test-key", "Content-Type": "application/xml"},
        content=xml,
    )
    assert response.status_code == 200, response.text
    assert response.json()["events"][0]["event_type"] == "TAMPER"
    with SessionLocal() as db:
        event = db.query(CameraEvent).filter(CameraEvent.event_type == "TAMPER").one()
        assert event.camera_id == camera_id


def test_hikvision_videoloss_inactive_without_active_alarm_is_heartbeat(client):
    _, recorder_id, camera_id = _seed_camera()
    xml = b'''<EventNotificationAlert>
      <channelID>1</channelID>
      <dateTime>2026-09-11T13:31:00-03:00</dateTime>
      <eventType>videoloss</eventType>
      <eventState>inactive</eventState>
    </EventNotificationAlert>'''
    response = client.post(
        f"/integrations/camera-events/hikvision?recorder_id={recorder_id}",
        headers={"X-EduVigIA-Event-Key": "event-test-key", "Content-Type": "application/xml"},
        content=xml,
    )
    assert response.status_code == 200
    event = response.json()["events"][0]
    assert event["heartbeat"] is True
    assert event["event_id"] is None
    with SessionLocal() as db:
        assert db.query(CameraEvent).count() == 0
        health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        assert health.rtsp_online is True


def test_camera_event_and_health_respect_school_scope(client):
    school_a, recorder_a, _ = _seed_camera()
    with SessionLocal() as db:
        school_b = School(code="ESC-B", name="Escola B", address="Rua B")
        db.add(school_b); db.flush()
        camera_b = Camera(code="CAM-700002", school_id=school_b.id, name="Pátio B", location="Pátio", status="ONLINE")
        db.add(camera_b); db.commit(); school_b_id = school_b.id; camera_b_id = camera_b.id

    key = {"X-EduVigIA-Event-Key": "event-test-key"}
    client.post("/integrations/camera-events/ingest", headers=key, json={
        "provider": "GENERIC", "provider_event_type": "motion", "event_state": "active", "recorder_id": recorder_a, "source_channel": 1,
    })
    client.post("/integrations/camera-events/ingest", headers=key, json={
        "provider": "GENERIC", "provider_event_type": "motion", "event_state": "active", "camera_id": camera_b_id,
    })

    school_headers, _ = _auth(role="GESTOR_ESCOLA", school_id=school_a, suffix="scope")
    events = client.get("/camera-events", headers=school_headers)
    assert events.status_code == 200
    assert events.json()
    assert all(item["school_id"] == school_a for item in events.json())
    health = client.get("/camera-health", headers=school_headers)
    assert health.status_code == 200
    assert all(item["school_id"] == school_a for item in health.json())
    assert not any(item["school_id"] == school_b_id for item in events.json())


def test_monitoring_offline_transition_generates_single_deduplicated_event(client, monkeypatch):
    school_id, _, camera_id = _seed_camera()
    headers, _ = _auth(role="TECNICO", suffix="monitor")
    monkeypatch.setattr(application, "_tcp_camera_status", lambda item: (item[0], False, "timeout"))
    first = client.post("/monitoring/status-refresh", headers=headers, json={"camera_ids": [camera_id]})
    assert first.status_code == 200
    second = client.post("/monitoring/status-refresh", headers=headers, json={"camera_ids": [camera_id]})
    assert second.status_code == 200
    with SessionLocal() as db:
        rows = db.query(CameraEvent).filter(CameraEvent.camera_id == camera_id, CameraEvent.event_type == "CAMERA_OFFLINE").all()
        assert len(rows) == 1
        # Second refresh does not create another transition/event because status is already OFFLINE.
        assert rows[0].repeat_count == 1
        health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        assert health.rtsp_online is False
        assert health.state == "OFFLINE"


def test_camera_health_refresh_syncs_profiles_without_generating_events(client, monkeypatch):
    _, _, camera_id = _seed_camera()
    headers, _ = _auth(role="ADMIN_SECRETARIA", suffix="health-refresh")

    class DummySocket:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(application.socket, "create_connection", lambda *args, **kwargs: DummySocket())
    monkeypatch.setattr(
        application,
        "probe_rtsp_source",
        lambda source, timeout=15: {
            "ok": True,
            "codec": "H264",
            "width": 1280,
            "height": 720,
            "resolution": "1280x720",
            "fps": 15.0,
        },
    )

    response = client.post(
        "/camera-health/refresh",
        headers=headers,
        json={"camera_ids": [camera_id]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checked"] == 1
    assert body["online"] == 1
    assert body["events_generated"] == 0

    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        assert camera.status == "ONLINE"
        assert camera.main_status == "ONLINE"
        assert camera.sub_status == "ONLINE"
        assert health.state == "ONLINE"
        assert health.rtsp_online is True
        assert health.main_online is True
        assert health.sub_online is True
        assert health.resolution == "1280x720"
        assert health.codec == "H264"
        assert db.query(CameraEvent).filter(CameraEvent.camera_id == camera_id).count() == 0


def test_health_inventory_reconciles_devices_registered_after_f7r3_migration(client):
    school_id, recorder_id, camera_id = _seed_camera()

    with SessionLocal() as db:
        assert db.query(CameraHealth).count() == 0
        assert db.query(RecorderHealth).count() == 0

        result = application.reconcile_health_inventory(db)
        db.commit()

        assert result["camera_created"] == 1
        assert result["recorder_created"] == 1
        assert result["camera_total"] == 1
        assert result["recorder_total"] == 1

        camera_health = db.query(CameraHealth).filter(CameraHealth.camera_id == camera_id).one()
        recorder_health = db.query(RecorderHealth).filter(RecorderHealth.recorder_id == recorder_id).one()
        assert camera_health.school_id == school_id
        assert recorder_health.school_id == school_id

        second = application.reconcile_health_inventory(db)
        db.commit()
        assert second["camera_created"] == 0
        assert second["recorder_created"] == 0
        assert db.query(CameraHealth).count() == 1
        assert db.query(RecorderHealth).count() == 1
