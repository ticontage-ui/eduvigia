from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.application import (
    AuthSession, Base, Camera, FloorPlan, FloorPlanCamera, School, SessionLocal,
    UserAccount, app, engine, hash_password, role_permissions, token_digest,
)

@pytest.fixture()
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def _auth(db, role="GESTOR_SECRETARIA", school_id=None, suffix="a"):
    user = UserAccount(
        name="Floor", email=f"floor-{role.lower()}-{suffix}@local",
        password_hash=hash_password("Senha@2026"), role=role, school_id=school_id,
        active=True, must_change_password=False,
    )
    db.add(user); db.flush()
    raw=f"floor-token-{role}-{suffix}"; now=datetime.now(timezone.utc)
    db.add(AuthSession(user_id=user.id, token=token_digest(raw), expires_at=now+timedelta(hours=1), last_seen_at=now)); db.flush()
    return user, {"Authorization": f"Bearer {raw}"}


def _seed(db):
    a=School(name="Escola Planta A", address="Rua A", active=True)
    b=School(name="Escola Planta B", address="Rua B", active=True)
    db.add_all([a,b]); db.flush()
    optical=Camera(school_id=a.id,name="Portão Visível",location="Portão",status="ONLINE",device_id=None,logical_channel=1,sensor_type="VISIBLE")
    thermal=Camera(school_id=a.id,name="Portão Térmico",location="Portão",status="ONLINE",device_id=None,logical_channel=2,sensor_type="THERMAL")
    other=Camera(school_id=b.id,name="Outra Escola",location="Pátio",status="ONLINE",logical_channel=1,sensor_type="VISIBLE")
    db.add_all([optical,thermal,other]); db.flush()
    return a,b,optical,thermal,other


def test_floor_plan_upload_and_multisensor_placements(client):
    with SessionLocal() as db:
        a,b,optical,thermal,other=_seed(db); user,headers=_auth(db); db.commit()
        aid=a.id; oid=optical.id; tid=thermal.id
    response=client.post("/floor-plans", headers=headers, data={"school_id":str(aid),"name":"Bloco A","building":"Principal","floor_label":"Térreo"}, files={"file":("planta.png", b"\x89PNG\r\n\x1a\nF7DATA", "image/png")})
    assert response.status_code==200,response.text
    plan=response.json(); assert plan["school_id"]==aid and plan["name"]=="Bloco A"
    save=client.put(f"/floor-plans/{plan['id']}/cameras",headers=headers,json={"placements":[
        {"camera_id":oid,"x_percent":20.5,"y_percent":30.0,"rotation_deg":45},
        {"camera_id":tid,"x_percent":22.0,"y_percent":31.0,"rotation_deg":45},
    ]})
    assert save.status_code==200,save.text
    rows=save.json()["placements"]
    assert {x["sensor_type"] for x in rows}=={"VISIBLE","THERMAL"}
    assert {x["logical_channel"] for x in rows}=={1,2}


def test_floor_plan_school_scope_and_cross_school_camera_guard(client):
    with SessionLocal() as db:
        a,b,optical,thermal,other=_seed(db); manager,headers=_auth(db,"GESTOR_ESCOLA",a.id,"school"); db.commit()
        aid=a.id; bid=b.id; otherid=other.id
    own=client.post("/floor-plans",headers=headers,data={"school_id":str(aid),"name":"Própria"},files={"file":("p.jpg",b"\xff\xd8\xffJPEG","image/jpeg")})
    assert own.status_code==200,own.text
    denied=client.post("/floor-plans",headers=headers,data={"school_id":str(bid),"name":"Outra"},files={"file":("p.jpg",b"\xff\xd8\xffJPEG","image/jpeg")})
    assert denied.status_code==404
    cross=client.put(f"/floor-plans/{own.json()['id']}/cameras",headers=headers,json={"placements":[{"camera_id":otherid,"x_percent":10,"y_percent":10}]})
    assert cross.status_code in {400,404}


def test_floor_plan_write_rbac(client):
    assert "floorplans:write" in role_permissions("GESTOR_SECRETARIA",None)
    assert "floorplans:write" in role_permissions("GESTOR_ESCOLA",1)
    assert "floorplans:write" in role_permissions("TECNICO",None)
    assert "floorplans:write" not in role_permissions("SUPERVISOR_GUARDA",None)
    assert "floorplans:write" not in role_permissions("OPERADOR_ESCOLA",1)


def test_duplicate_camera_placement_is_rejected(client):
    with SessionLocal() as db:
        a,b,optical,thermal,other=_seed(db); user,headers=_auth(db,suffix="dup"); db.commit(); aid=a.id; cid=optical.id
    plan=client.post("/floor-plans",headers=headers,data={"school_id":str(aid),"name":"Duplicada"},files={"file":("p.webp",b"RIFFxxxxWEBPdata","image/webp")}).json()
    r=client.put(f"/floor-plans/{plan['id']}/cameras",headers=headers,json={"placements":[
        {"camera_id":cid,"x_percent":10,"y_percent":10},{"camera_id":cid,"x_percent":20,"y_percent":20}
    ]})
    assert r.status_code==400 and "duas vezes" in r.text


def test_floor_plan_file_requires_scope(client):
    with SessionLocal() as db:
        a,b,optical,thermal,other=_seed(db); admin,admin_h=_auth(db,suffix="admin"); school_user,school_h=_auth(db,"GESTOR_ESCOLA",b.id,"b"); db.commit(); aid=a.id
    plan=client.post("/floor-plans",headers=admin_h,data={"school_id":str(aid),"name":"Restrita"},files={"file":("p.png",b"\x89PNG\r\n\x1a\nX","image/png")}).json()
    assert client.get(f"/floor-plans/{plan['id']}/file",headers=admin_h).status_code==200
    assert client.get(f"/floor-plans/{plan['id']}/file",headers=school_h).status_code==404


def test_floor_plan_rejects_unsafe_mime_and_large_coordinate(client):
    with SessionLocal() as db:
        a,b,optical,thermal,other=_seed(db); user,headers=_auth(db,suffix="safe"); db.commit(); aid=a.id
    bad=client.post("/floor-plans",headers=headers,data={"school_id":str(aid),"name":"SVG"},files={"file":("p.svg",b"<svg/>","image/svg+xml")})
    assert bad.status_code==400
    spoof=client.post("/floor-plans",headers=headers,data={"school_id":str(aid),"name":"Spoof"},files={"file":("p.png",b"not-a-png","image/png")})
    assert spoof.status_code==400
