from app.application import VideoWallLayout, VideoWallSlot, VideoWallLayoutIn, role_permissions

assert VideoWallLayout.__tablename__ == "video_wall_layouts"
assert VideoWallSlot.__tablename__ == "video_wall_slots"
assert VideoWallLayoutIn.model_fields.get("grid_size")
for role in ["GESTOR_SECRETARIA","SUPERVISOR_GUARDA","OPERADOR_GUARDA","DESPACHANTE_GUARDA"]:
    perms=role_permissions(role,None)
    assert "wall:view" in perms and "wall:write" in perms, (role,perms)
assert "wall:view" in role_permissions("TECNICO",None)
assert "wall:write" not in role_permissions("GESTOR_ESCOLA",1)
print("EDUVIGIA_F5_VIDEO_WALL_PREFLIGHT_OK")
