from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app.application as application
from app.application import (Alert, AlertActivity, AuthSession, Base, Camera, School, SessionLocal, UserAccount, app, engine, hash_password, token_digest)

@pytest.fixture()
def client(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(application, "DATA_DIR", tmp_path)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)

def _auth(role="ADMIN_SECRETARIA", school_id=None, suffix="f0"):
    with SessionLocal() as db:
        user=UserAccount(name=f"Operador {role}",email=f"{role.lower()}-{suffix}@local",password_hash=hash_password("SenhaForte@2026"),role=role,school_id=school_id,active=True,must_change_password=False)
        db.add(user); db.flush(); raw=f"token-{role.lower()}-{suffix}"; now=datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id,token=token_digest(raw),expires_at=now+timedelta(hours=1),last_seen_at=now)); db.commit()
        return {"Authorization":f"Bearer {raw}"}, user.id

def _seed_alert(tmp_path=None, school_name="Escola Central"):
    with SessionLocal() as db:
        school=School(name=school_name,address="Rua Central"); db.add(school); db.flush()
        camera=Camera(school_id=school.id,name="Câmera Pátio",location="Pátio",status="ONLINE",stream_name_main="central-main",stream_name_sub="central-sub"); db.add(camera); db.flush()
        alert=Alert(school_id=school.id,camera_id=camera.id,school_name=school.name,camera_name=camera.name,event_type="EVENTO_TECNICO",priority="ALTA",status="NOVO",source="SISTEMA",summary="Evento operacional para triagem",event_occurred_at=datetime.now(timezone.utc))
        db.add(alert); db.flush(); application.add_alert_activity(db,alert,"CRIADO",to_status="NOVO",user_name="Sistema"); db.commit()
        return school.id,camera.id,alert.id

def test_alert_workflow_and_assignment_are_audited(client):
    _,_,alert_id=_seed_alert(); headers,user_id=_auth(suffix="workflow")
    assigned=client.post(f"/alerts/{alert_id}/assign",headers=headers,json={"assigned_user_id":user_id,"note":"Operador assumiu"})
    assert assigned.status_code==200
    workflow=client.patch(f"/alerts/{alert_id}/workflow",headers=headers,json={"status":"EM_ATENDIMENTO","note":"Em análise"})
    assert workflow.status_code==200 and workflow.json()["status"]=="EM_ATENDIMENTO"
    assert len(workflow.json()["activities"])>=3

def test_evidence_endpoint_is_private_and_path_safe(client,tmp_path):
    _,_,alert_id=_seed_alert(); evidence=tmp_path/"evidence"; evidence.mkdir(); f=evidence/"alert.jpg"; f.write_bytes(b"\xff\xd8\xff\xd9")
    with SessionLocal() as db:
        a=db.get(Alert,alert_id); a.evidence_path="evidence/alert.jpg"; db.commit()
    assert client.get(f"/alerts/{alert_id}/evidence").status_code==401
    headers,_=_auth(suffix="evidence"); assert client.get(f"/alerts/{alert_id}/evidence",headers=headers).status_code==200
    with SessionLocal() as db:
        a=db.get(Alert,alert_id); a.evidence_path="../../etc/passwd"; db.commit()
    assert client.get(f"/alerts/{alert_id}/evidence",headers=headers).status_code==404

def test_school_isolation_applies_to_alert_center(client):
    school_a,_,_=_seed_alert(school_name="Escola A"); _seed_alert(school_name="Escola B")
    headers,_=_auth(role="GESTOR_ESCOLA",school_id=school_a,suffix="scope")
    response=client.get("/alerts",headers=headers); assert response.status_code==200; assert len(response.json())==1; assert response.json()[0]["school_id"]==school_a

def test_alert_can_create_occurrence_and_close_workflow(client):
    _,_,alert_id=_seed_alert(); headers,_=_auth(suffix="occurrence")
    response=client.post(f"/alerts/{alert_id}/occurrence",headers=headers)
    assert response.status_code==200 and response.json()["alert_id"]==alert_id
    details=client.get(f"/alerts/{alert_id}/details",headers=headers)
    assert details.status_code==200 and details.json()["status"]=="ENCERRADO" and details.json()["occurrence"]["protocol"].startswith("EDU-")
