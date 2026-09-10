from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.application import AuthSession, Base, Camera, School, SessionLocal, UserAccount, VideoWallLayout, VideoWallSlot, app, engine, hash_password, token_digest

@pytest.fixture()
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestClient(app) as c: yield c
    Base.metadata.drop_all(engine)

def auth(role="GESTOR_SECRETARIA", school_bound=False, suffix="a"):
    with SessionLocal() as db:
        school=School(name=f"Escola Wall {suffix}",address="Rua 1"); db.add(school); db.flush()
        user=UserAccount(name="Operador",email=f"wall-{role.lower()}-{suffix}@local",password_hash=hash_password("Senha@2026"),role=role,school_id=school.id if school_bound else None,active=True,must_change_password=False)
        db.add(user); db.flush(); raw=f"wall-token-{role}-{suffix}"; now=datetime.now(timezone.utc)
        db.add(AuthSession(user_id=user.id,token=token_digest(raw),expires_at=now+timedelta(hours=1),last_seen_at=now))
        cam1=Camera(school_id=school.id,name="Portao Visivel",location="Portao",source_type="CAMERA_IP",logical_channel=1,sensor_type="VISIBLE")
        cam2=Camera(school_id=school.id,name="Portao Termica",location="Portao",source_type="CAMERA_IP",logical_channel=2,sensor_type="THERMAL")
        db.add_all([cam1,cam2]); db.commit(); return school.id,[cam1.id,cam2.id],{"Authorization":f"Bearer {raw}"}

def test_video_wall_layout_persists_multisensor_channels(client):
    _,cams,headers=auth()
    r=client.post("/video-wall/layouts",headers=headers,json={"name":"Portao Duplo","grid_size":4,"quality_mode":"AUTO","camera_ids":[cams[0],cams[1],None,None]})
    assert r.status_code==200,r.text
    body=r.json(); assert body["grid_size"]==4 and body["camera_ids"][:2]==cams and len(body["slots"])==2
    listing=client.get("/video-wall/layouts",headers=headers); assert listing.status_code==200 and listing.json()[0]["camera_ids"][:2]==cams

def test_video_wall_duplicate_camera_is_rejected(client):
    _,cams,headers=auth(suffix="dup")
    r=client.post("/video-wall/layouts",headers=headers,json={"name":"Duplicado","grid_size":4,"camera_ids":[cams[0],cams[0]]})
    assert r.status_code==400

def test_video_wall_default_is_unique_per_user(client):
    _,cams,headers=auth(suffix="default")
    ids=[]
    for name in ["A","B"]:
        r=client.post("/video-wall/layouts",headers=headers,json={"name":name,"grid_size":1,"camera_ids":[cams[0]]}); ids.append(r.json()["id"])
    assert client.post(f"/video-wall/layouts/{ids[0]}/default",headers=headers).status_code==200
    assert client.post(f"/video-wall/layouts/{ids[1]}/default",headers=headers).status_code==200
    rows=client.get("/video-wall/layouts",headers=headers).json(); assert sum(1 for x in rows if x["is_default"])==1 and next(x for x in rows if x["is_default"])["id"]==ids[1]

def test_school_profiles_cannot_access_video_wall(client):
    _,_,headers=auth("GESTOR_ESCOLA",True,"school")
    assert client.get("/video-wall/layouts",headers=headers).status_code==403

def test_video_wall_layout_owner_isolated(client):
    _,cams,h1=auth(suffix="one")
    r=client.post("/video-wall/layouts",headers=h1,json={"name":"Privado","grid_size":1,"camera_ids":[cams[0]]}); assert r.status_code==200
    _,_,h2=auth(suffix="two")
    assert client.get("/video-wall/layouts",headers=h2).json()==[]

def test_video_wall_delete_cascades_slots(client):
    _,cams,headers=auth(suffix="delete")
    layout=client.post("/video-wall/layouts",headers=headers,json={"name":"Excluir","grid_size":4,"camera_ids":cams}).json()
    assert client.delete(f"/video-wall/layouts/{layout['id']}",headers=headers).status_code==200
    with SessionLocal() as db:
        assert db.get(VideoWallLayout,layout["id"]) is None
        assert db.query(VideoWallSlot).filter(VideoWallSlot.layout_id==layout["id"]).count()==0
