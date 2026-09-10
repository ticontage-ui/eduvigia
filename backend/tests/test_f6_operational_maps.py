from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from app.application import (
    Alert, AuthSession, Base, Camera, Occurrence, School, SessionLocal, UserAccount,
    app, engine, hash_password, role_permissions, token_digest,
)

@pytest.fixture()
def client():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    with TestClient(app) as c: yield c
    Base.metadata.drop_all(engine)


def _auth(db, role="GESTOR_SECRETARIA", school_id=None, suffix="a"):
    user=UserAccount(name="Mapa",email=f"map-{role.lower()}-{suffix}@local",password_hash=hash_password("Senha@2026"),role=role,school_id=school_id,active=True,must_change_password=False)
    db.add(user); db.flush(); raw=f"map-token-{role}-{suffix}"; now=datetime.now(timezone.utc)
    db.add(AuthSession(user_id=user.id,token=token_digest(raw),expires_at=now+timedelta(hours=1),last_seen_at=now)); db.flush()
    return {"Authorization":f"Bearer {raw}"}


def _seed():
    with SessionLocal() as db:
        a=School(name="Escola Mapa A",address="Rua A",city="Juazeiro",latitude="-7.2100",longitude="-39.3100",active=True)
        b=School(name="Escola Mapa B",address="Rua B",city="Juazeiro",latitude="-7,2200",longitude="-39,3200",active=True)
        c=School(name="Escola Sem GPS",address="Rua C",city="Juazeiro",latitude="",longitude="",active=True)
        db.add_all([a,b,c]); db.flush()
        db.add_all([
            Camera(school_id=a.id,name="Cam A1",location="Portao",status="ONLINE"),
            Camera(school_id=a.id,name="Cam A2",location="Patio",status="OFFLINE"),
            Camera(school_id=b.id,name="Cam B1",location="Entrada",status="ONLINE"),
            Alert(school_id=a.id,school_name=a.name,camera_name="Cam A1",event_type="TESTE",status="NOVO",priority="ALTA"),
            Occurrence(protocol="MAP-A",school_id=a.id,school_name=a.name,description="Ocorrencia mapa",status="ABERTA"),
        ])
        db.commit(); return a.id,b.id,c.id


def test_map_overview_aggregates_school_health_and_coordinates(client):
    a,b,c=_seed()
    with SessionLocal() as db:
        headers=_auth(db); db.commit()
    r=client.get("/maps/overview",headers=headers)
    assert r.status_code==200,r.text
    body=r.json(); assert body["summary"]["schools_total"]==3
    assert body["summary"]["schools_located"]==2 and body["summary"]["schools_unlocated"]==1
    point=next(x for x in body["points"] if x["school_id"]==a)
    assert point["cameras_total"]==2 and point["cameras_online"]==1 and point["cameras_offline"]==1
    assert point["active_alerts"]==1 and point["open_occurrences"]==1 and point["map_status"]=="CRITICAL"
    comma=next(x for x in body["points"] if x["school_id"]==b)
    assert comma["latitude"]==-7.22 and comma["longitude"]==-39.32
    assert body["unlocated"][0]["school_id"]==c


def test_school_user_map_is_scoped_to_own_school(client):
    a,b,_=_seed()
    with SessionLocal() as db:
        headers=_auth(db,"GESTOR_ESCOLA",a,"school"); db.commit()
    r=client.get("/maps/overview",headers=headers)
    assert r.status_code==200
    ids={x["school_id"] for x in r.json()["points"]+r.json()["unlocated"]}
    assert ids=={a} and b not in ids


def test_map_permission_is_available_without_write_escalation(client):
    for role,school_id in [("GESTOR_SECRETARIA",None),("SUPERVISOR_GUARDA",None),("OPERADOR_GUARDA",None),("DESPACHANTE_GUARDA",None),("GESTOR_ESCOLA",1),("OPERADOR_ESCOLA",1),("TECNICO",None)]:
        assert "maps:view" in role_permissions(role,school_id), role
    assert "maps:write" not in role_permissions("GESTOR_ESCOLA",1)


def test_invalid_coordinates_are_not_emitted_as_map_points(client):
    _seed()
    with SessionLocal() as db:
        bad=School(name="GPS invalido",address="Rua D",latitude="999",longitude="abc",active=True); db.add(bad)
        headers=_auth(db,suffix="bad"); db.commit(); bid=bad.id
    body=client.get("/maps/overview",headers=headers).json()
    assert bid not in {x["school_id"] for x in body["points"]}
    assert bid in {x["school_id"] for x in body["unlocated"]}


def test_map_configuration_exposes_configurable_tile_contract(client,monkeypatch):
    _seed()
    monkeypatch.setenv("EDUVIGIA_MAP_TILE_URL","http://tiles.local/{z}/{x}/{y}.png")
    monkeypatch.setenv("EDUVIGIA_MAP_ATTRIBUTION","Mapa interno")
    with SessionLocal() as db:
        headers=_auth(db,suffix="tiles"); db.commit()
    body=client.get("/maps/overview",headers=headers).json()
    assert body["tile_url_template"]=="http://tiles.local/{z}/{x}/{y}.png"
    assert body["attribution"]=="Mapa interno"
