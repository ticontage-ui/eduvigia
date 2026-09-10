from app.application import Evidence, EvidenceCustodyEvent, PlaybackRangeIn, PlaybackExportIn, build_hikvision_playback_rtsp, role_permissions

required = [
    "sha256", "file_size_bytes", "source_start_at", "source_end_at", "source_origin",
    "integrity_status", "logical_channel", "sensor_type", "device_id", "school_id"
]
missing=[name for name in required if not hasattr(Evidence,name)]
roles=["GESTOR_SECRETARIA","SUPERVISOR_GUARDA","OPERADOR_GUARDA","DESPACHANTE_GUARDA"]
assert not missing, missing
assert all("playback:view" in role_permissions(r,None) for r in roles)
assert all("evidence:export" in role_permissions(r,None) for r in roles)
assert EvidenceCustodyEvent.__tablename__ == "evidence_custody_events"
assert PlaybackRangeIn.model_fields.get("start_at") and PlaybackExportIn.model_fields.get("end_at")
print("EDUVIGIA_F4_PLAYBACK_EVIDENCE_PREFLIGHT_OK")
