from __future__ import annotations

import json

from app.application import (
    APP_VERSION,
    Camera,
    CameraPTZLease,
    CameraPTZPreset,
    PTZ_DIRECTIONS,
    PTZ_SPEED_MAP,
    ROLE_PROFILES,
    app,
)


def main() -> None:

    paths = set(app.openapi().get("paths", {}))
    required_routes = {
        "/cameras/{camera_id}/ptz/status",
        "/cameras/{camera_id}/ptz/lease",
        "/cameras/{camera_id}/ptz/move",
        "/cameras/{camera_id}/ptz/stop",
        "/cameras/{camera_id}/ptz/presets",
        "/cameras/{camera_id}/ptz/presets/{preset_no}/goto",
        "/cameras/{camera_id}/ptz/presets/{preset_no}",
    }
    missing_routes = sorted(required_routes - paths)
    if missing_routes:
        raise SystemExit("Rotas F3 ausentes: " + ", ".join(missing_routes))

    camera_columns = set(Camera.__table__.columns.keys())
    required_columns = {
        "ptz_enabled",
        "ptz_protocol",
        "ptz_http_port",
        "ptz_https",
        "ptz_channel",
        "ptz_last_command_at",
        "ptz_last_error",
    }
    missing_columns = sorted(required_columns - camera_columns)
    if missing_columns:
        raise SystemExit("Colunas F3 ausentes: " + ", ".join(missing_columns))

    if CameraPTZLease.__tablename__ != "camera_ptz_leases":
        raise SystemExit("Tabela de lease PTZ inválida")
    if CameraPTZPreset.__tablename__ != "camera_ptz_presets":
        raise SystemExit("Tabela de presets PTZ inválida")

    required_roles = {
        "GESTOR_SECRETARIA",
        "SUPERVISOR_GUARDA",
        "OPERADOR_GUARDA",
        "DESPACHANTE_GUARDA",
        "GESTOR_ESCOLA",
        "OPERADOR_ESCOLA",
        "TECNICO",
    }
    missing_permissions = sorted(
        role for role in required_roles
        if "ptz:control" not in ROLE_PROFILES[role]["permissions"]
    )
    if missing_permissions:
        raise SystemExit("Permissão PTZ ausente: " + ", ".join(missing_permissions))

    if len(PTZ_DIRECTIONS) != 10 or set(PTZ_SPEED_MAP) != set(range(1, 8)):
        raise SystemExit("Contrato de movimento PTZ inválido")

    print(json.dumps({
        "ok": True,
        "version": APP_VERSION,
        "routes": len(required_routes),
        "camera_ptz_columns": len(required_columns),
        "lease_table": CameraPTZLease.__tablename__,
        "preset_table": CameraPTZPreset.__tablename__,
        "message": "EDUVIGIA_F3_PTZ_PREFLIGHT_OK",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
