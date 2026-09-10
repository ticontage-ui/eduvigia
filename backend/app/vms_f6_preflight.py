from app.application import _map_coordinate, _school_map_status, role_permissions

assert _map_coordinate("-7,22", latitude=True) == -7.22
assert _map_coordinate("999", latitude=True) is None
assert _map_coordinate("-39.31", latitude=False) == -39.31
assert _school_map_status(0,0,0,4) == "NORMAL"
assert _school_map_status(1,0,0,4) == "ATTENTION"
assert _school_map_status(0,1,0,4) == "CRITICAL"
for role, school_id in [
    ("GESTOR_SECRETARIA",None),("SUPERVISOR_GUARDA",None),("OPERADOR_GUARDA",None),
    ("DESPACHANTE_GUARDA",None),("GESTOR_ESCOLA",1),("OPERADOR_ESCOLA",1),("TECNICO",None)
]:
    assert "maps:view" in role_permissions(role, school_id), (role, role_permissions(role, school_id))
print("EDUVIGIA_F6_OPERATIONAL_MAPS_PREFLIGHT_OK")
