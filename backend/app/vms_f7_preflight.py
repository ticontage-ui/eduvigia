from app.application import role_permissions

for role, school_id in [
    ("GESTOR_SECRETARIA", None), ("SUPERVISOR_GUARDA", None),
    ("OPERADOR_GUARDA", None), ("DESPACHANTE_GUARDA", None),
    ("GESTOR_ESCOLA", 1), ("OPERADOR_ESCOLA", 1), ("TECNICO", None),
]:
    assert "floorplans:view" in role_permissions(role, school_id), role

for role, school_id in [("GESTOR_SECRETARIA", None), ("GESTOR_ESCOLA", 1), ("TECNICO", None)]:
    assert "floorplans:write" in role_permissions(role, school_id), role

for role, school_id in [("SUPERVISOR_GUARDA", None), ("OPERADOR_GUARDA", None), ("DESPACHANTE_GUARDA", None), ("OPERADOR_ESCOLA", 1)]:
    assert "floorplans:write" not in role_permissions(role, school_id), role

print("EDUVIGIA_F7_FLOOR_PLANS_PREFLIGHT_OK")
