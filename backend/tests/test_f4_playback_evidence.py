from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import app.application as application
from app.application import AuthSession, Base, Camera, Evidence, EvidenceCustodyEvent, Recorder, School, SessionLocal, UserAccount, VideoDevice, app, engine, encrypt_secret, hash_password, token_digest

@pytest.fixture()
def client(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    monkeypatch.setattr(application,"EVIDENCE_DIR",tmp_path/"evidence"); application.EVIDENCE_DIR.mkdir()
    monkeypatch.setattr(application,"PLAYBACK_DIR",tmp_path/"playback"); application.PLAYBACK_DIR.mkdir()
    application.PLAYBACK_PREVIEWS.clear()
    with TestClient(app) as c: yield c
    Base.metadata.drop_all(engine)

def auth(role="GESTOR_SECRETARIA", school_bound=False):
    with SessionLocal() as db:
        school=School(name=f"Escola {role}",address="Rua 1"); db.add(school); db.flush()
        user=UserAccount(name="Operador",email=f"{role.lower()}@local",password_hash=hash_password("Senha@2026"),role=role,school_id=school.id if school_bound else None,active=True,must_change_password=False)
        db.add(user); db.flush(); raw=f"token-{role}"; now=datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id,token=token_digest(raw),expires_at=now+timedelta(hours=1),last_seen_at=now)); db.commit()
        return school.id,user.id,{"Authorization":f"Bearer {raw}"}

def add_recorder_camera(school_id):
    with SessionLocal() as db:
        r=Recorder(school_id=school_id,name="NVR",ip_address="192.0.2.10",rtsp_port=554,http_port=80,https_port=0,username="admin",password=encrypt_secret("secret")); db.add(r); db.flush()
        c=Camera(school_id=school_id,name="Portao",location="Portao",source_type="NVR",recorder_id=r.id,nvr_channel=2,logical_channel=2,sensor_type="THERMAL"); db.add(c); db.commit(); return c.id

def test_playback_url_uses_nvr_channel_without_serializing_credentials(client):
    school,_,headers=auth(); camera_id=add_recorder_camera(school)
    with SessionLocal() as db:
        cam=db.get(Camera,camera_id); start=datetime(2026,9,9,12,0,tzinfo=timezone.utc); end=start+timedelta(minutes=2)
        url=application.build_hikvision_playback_rtsp(db,cam,start,end)
        assert "admin:secret@192.0.2.10:554" in url
        assert "/Streaming/tracks/201" in url
        assert "starttime=20260909T120000Z" in url
    response=client.get(f"/cameras/{camera_id}/playback/capabilities",headers=headers)
    assert response.status_code==200
    assert "secret" not in response.text and "192.0.2.10" not in response.text
    assert response.json()["channel"]==2

def test_multisensor_playback_uses_logical_channel(client):
    school,_,headers=auth()
    with SessionLocal() as db:
        d=VideoDevice(school_id=school,name="BiSpectrum",ip_address="192.0.2.20",rtsp_port=554,http_port=80,https_port=0,username="admin",password=encrypt_secret("pw"),device_type="BISPECTRUM",channel_count=2); db.add(d); db.flush()
        c=Camera(school_id=school,name="Termica",location="Portao",source_type="CAMERA_IP",device_id=d.id,logical_channel=2,sensor_type="THERMAL"); db.add(c); db.commit(); cid=c.id
    with SessionLocal() as db:
        url=application.build_hikvision_playback_rtsp(db,db.get(Camera,cid),datetime(2026,9,9,10,tzinfo=timezone.utc),datetime(2026,9,9,10,1,tzinfo=timezone.utc))
        assert "/Streaming/tracks/201" in url

def test_search_parses_hikvision_timeline(client,monkeypatch):
    school,_,headers=auth(); camera_id=add_recorder_camera(school)
    xml=b'<?xml version="1.0"?><CMSearchResult xmlns="http://www.hikvision.com/ver20/XMLSchema"><matchList><searchMatchItem><timeSpan><startTime>2026-09-09T12:00:00Z</startTime><endTime>2026-09-09T12:05:00Z</endTime></timeSpan><metadataDescriptor>continuous</metadataDescriptor></searchMatchItem></matchList></CMSearchResult>'
    monkeypatch.setattr(application,"_playback_xml_request",lambda db,camera,body,timeout=8:(200,xml))
    response=client.post(f"/cameras/{camera_id}/playback/search",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T13:00:00Z"})
    assert response.status_code==200,response.text
    assert response.json()["count"]==1 and response.json()["segments"][0]["record_type"]=="continuous"

def test_forensic_export_generates_sha256_and_custody(client,monkeypatch):
    school,uid,headers=auth(); camera_id=add_recorder_camera(school)
    def fake_export(source,target,duration_seconds,timeout_seconds=None): target.write_bytes(b"forensic-video-data")
    monkeypatch.setattr(application,"_run_playback_export",fake_export)
    response=client.post(f"/cameras/{camera_id}/playback/export",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T12:01:00Z","observation":"Teste"})
    assert response.status_code==200,response.text
    body=response.json(); assert body["evidence_type"]=="VIDEO_EXPORT" and len(body["sha256"])==64 and body["integrity_status"]=="VERIFIED"
    with SessionLocal() as db:
        row=db.get(Evidence,body["id"]); assert row.logical_channel==2 and row.sensor_type=="THERMAL" and row.created_by_user_id==uid
        assert db.query(EvidenceCustodyEvent).filter_by(evidence_id=row.id,action="CREATED").count()==1

def test_integrity_verify_detects_tampering(client,monkeypatch):
    school,_,headers=auth(); camera_id=add_recorder_camera(school)
    monkeypatch.setattr(application,"_run_playback_export",lambda source,target,duration_seconds,timeout_seconds=None: target.write_bytes(b"original"))
    exp=client.post(f"/cameras/{camera_id}/playback/export",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T12:00:30Z"}).json()
    ok=client.get(f"/evidence/{exp['id']}/verify",headers=headers); assert ok.json()["integrity_status"]=="VERIFIED"
    with SessionLocal() as db: Path(db.get(Evidence,exp["id"]).file_path).write_bytes(b"tampered")
    bad=client.get(f"/evidence/{exp['id']}/verify",headers=headers); assert bad.json()["integrity_status"]=="MISMATCH"

def test_school_user_can_playback_but_cannot_export(client):
    school,_,headers=auth("GESTOR_ESCOLA",True); camera_id=add_recorder_camera(school)
    assert client.get(f"/cameras/{camera_id}/playback/capabilities",headers=headers).status_code==200
    denied=client.post(f"/cameras/{camera_id}/playback/export",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T12:01:00Z"})
    assert denied.status_code==403

def test_preview_is_limited_and_private(client,monkeypatch):
    school,_,headers=auth(); camera_id=add_recorder_camera(school)
    monkeypatch.setattr(application,"_run_playback_export",lambda source,target,duration_seconds,timeout_seconds=None: target.write_bytes(b"preview"))
    good=client.post(f"/cameras/{camera_id}/playback/preview",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T12:01:00Z"})
    assert good.status_code==200
    file=client.get(f"/playback/previews/{good.json()['token']}",headers=headers); assert file.status_code==200 and file.content==b"preview"
    too_long=client.post(f"/cameras/{camera_id}/playback/preview",headers=headers,json={"start_at":"2026-09-09T12:00:00Z","end_at":"2026-09-09T12:10:00Z"})
    assert too_long.status_code==400
