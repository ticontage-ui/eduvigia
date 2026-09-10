from __future__ import annotations

import json

from app.application import APP_VERSION, Camera, CameraFavorite, app


def main() -> None:

    paths = set(app.openapi().get("paths", {}))
    required = {
        "/recorders",
        "/recorders/{recorder_id}/discover",
        "/recorders/{recorder_id}/import-channels",
        "/cameras",
        "/cameras/{camera_id}/test",
        "/cameras/{camera_id}/stream-access",
        "/cameras/{camera_id}/stream-status",
        "/monitoring/favorites",
        "/monitoring/favorites/{camera_id}",
        "/monitoring/status-refresh",
    }
    missing = sorted(required - paths)
    if missing:
        raise SystemExit("Rotas F2 ausentes: " + ", ".join(missing))

    camera_columns = set(Camera.__table__.columns.keys())
    required_columns = {
        "rtsp_url_main", "rtsp_url_sub",
        "main_status", "sub_status",
        "main_codec", "main_resolution", "main_fps", "main_bitrate_kbps",
        "sub_codec", "sub_resolution", "sub_fps", "sub_bitrate_kbps",
        "stream_name_main", "stream_name_sub",
    }
    missing_columns = sorted(required_columns - camera_columns)
    if missing_columns:
        raise SystemExit("Colunas F2 ausentes: " + ", ".join(missing_columns))

    if CameraFavorite.__tablename__ != "camera_favorites":
        raise SystemExit("Tabela de favoritos F2 inválida")

    print(json.dumps({
        "ok": True,
        "version": APP_VERSION,
        "routes": len(required),
        "camera_profile_columns": len(required_columns),
        "favorites_table": CameraFavorite.__tablename__,
        "message": "EDUVIGIA_F2_VMS_PREFLIGHT_OK",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
