from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (
    AuthSession, Base, Camera, School, SessionLocal, UserAccount, VideoDevice,
    app, build_camera_rtsp, decrypt_secret, engine, hash_password, token_digest,
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def auth_headers():
    with SessionLocal() as db:
        school = School(name="Escola MultiSensor", address="Rua 1")
        db.add(school); db.flush()
        user = UserAccount(
            name="Gestor", email="gestor-multi@local", password_hash=hash_password("Senha@2026"),
            role="GESTOR_SECRETARIA", active=True, must_change_password=False,
        )
        db.add(user); db.flush()
        raw="multi-token"
        now=datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id, token=token_digest(raw), expires_at=now+timedelta(hours=1), last_seen_at=now))
        db.commit()
        return school.id, {"Authorization": f"Bearer {raw}"}


def create_device(client, school_id, headers):
    response=client.post("/video-devices", headers=headers, json={
        "school_id": school_id,
        "name": "Termica Portao",
        "manufacturer": "Hikvision",
        "model": "BiSpectrum",
        "ip_address": "192.0.2.50",
        "http_port": 80,
        "https_port": 443,
        "rtsp_port": 554,
        "username": "admin",
        "password": "secret-device",
        "device_type": "BISPECTRUM",
        "channel_count": 2,
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_one_physical_device_can_have_visible_and_thermal_channels(client, monkeypatch):
    school_id, headers = auth_headers()
    device_id = create_device(client, school_id, headers)
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    response=client.post(f"/video-devices/{device_id}/channels", headers=headers, json={"channels": [
        {"name":"Portao - Visivel","location":"Portao","logical_channel":1,"sensor_type":"VISIBLE","primary_sensor":True,"camera_type":"FIXA"},
        {"name":"Portao - Termica","location":"Portao","logical_channel":2,"sensor_type":"THERMAL","primary_sensor":False,"camera_type":"TERMICA"},
    ]})
    assert response.status_code == 200, response.text
    rows=response.json()
    assert len(rows)==2
    assert {row["sensor_type"] for row in rows} == {"VISIBLE", "THERMAL"}
    assert {row["logical_channel"] for row in rows} == {1,2}
    assert all(row["device_id"] == device_id for row in rows)
    with SessionLocal() as db:
        cams=db.query(Camera).filter(Camera.device_id==device_id).order_by(Camera.logical_channel).all()
        assert build_camera_rtsp(db,cams[0],"MAIN").endswith("/Streaming/Channels/101")
        assert build_camera_rtsp(db,cams[0],"SUB").endswith("/Streaming/Channels/102")
        assert build_camera_rtsp(db,cams[1],"MAIN").endswith("/Streaming/Channels/201")
        assert build_camera_rtsp(db,cams[1],"SUB").endswith("/Streaming/Channels/202")
        assert decrypt_secret(db.get(VideoDevice,device_id).password)=="secret-device"
        assert cams[0].password is None and cams[1].password is None


def test_device_credentials_are_not_serialized(client):
    school_id, headers = auth_headers()
    device_id=create_device(client,school_id,headers)
    listing=client.get("/video-devices",headers=headers)
    assert listing.status_code==200
    item=next(row for row in listing.json() if row["id"]==device_id)
    assert "password" not in item


def test_same_device_logical_channel_cannot_be_duplicated(client, monkeypatch):
    school_id, headers=auth_headers()
    device_id=create_device(client,school_id,headers)
    monkeypatch.setattr(application, "provision_camera_path", lambda camera, db=None: (True, "OK"))
    payload={"channels":[{"name":"Sensor 1","location":"Portao","logical_channel":1,"sensor_type":"VISIBLE"}]}
    assert client.post(f"/video-devices/{device_id}/channels",headers=headers,json=payload).status_code==200
    second=client.post(f"/video-devices/{device_id}/channels",headers=headers,json=payload)
    assert second.status_code==409


def test_discovery_normalizes_hikvision_stream_ids(client, monkeypatch):
    school_id, headers=auth_headers()
    device_id=create_device(client,school_id,headers)
    xml=b'''<?xml version="1.0"?><StreamingChannelList xmlns="http://www.hikvision.com/ver20/XMLSchema"><StreamingChannel><id>101</id><enabled>true</enabled></StreamingChannel><StreamingChannel><id>102</id><enabled>true</enabled></StreamingChannel><StreamingChannel><id>201</id><enabled>true</enabled></StreamingChannel><StreamingChannel><id>202</id><enabled>true</enabled></StreamingChannel></StreamingChannelList>'''
    monkeypatch.setattr(application,"_video_device_request",lambda device,path,timeout=8:(200,xml,"application/xml"))
    result=client.post(f"/video-devices/{device_id}/discover",headers=headers)
    assert result.status_code==200,result.text
    assert result.json()["channels"] == [
        {"logical_channel":1,"main":True,"sub":True,"enabled":True},
        {"logical_channel":2,"main":True,"sub":True,"enabled":True},
    ]


def test_ptz_target_uses_shared_device_credentials(client):
    school_id, headers=auth_headers()
    device_id=create_device(client,school_id,headers)
    with SessionLocal() as db:
        cam=Camera(school_id=school_id,name="PTZ sensor",location="Patio",source_type="CAMERA_IP",device_id=device_id,logical_channel=2,sensor_type="VISIBLE",camera_type="PTZ",ptz_enabled=True,ptz_channel=2)
        db.add(cam); db.commit(); db.refresh(cam)
        target=application._ptz_target(cam,db)
        assert target["host"]=="192.0.2.50"
        assert target["password"]=="secret-device"
        assert target["channel"]==2
        assert target["via"]=="VIDEO_DEVICE"


def test_school_scope_applies_to_video_devices(client):
    school_id, headers=auth_headers()
    create_device(client,school_id,headers)
    response=client.get("/video-devices",headers=headers)
    assert response.status_code==200
    assert len(response.json())==1
