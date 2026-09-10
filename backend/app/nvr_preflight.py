from __future__ import annotations

import json
import shutil

from app.application import APP_VERSION, app, normalize_hikvision_channel_number


def main() -> None:
    if shutil.which("ffprobe") is None:
        raise SystemExit("ffprobe não encontrado no container da API")
    if normalize_hikvision_channel_number("101", 9) != 1:
        raise SystemExit("Normalização do canal Hikvision 101 falhou")
    if normalize_hikvision_channel_number("202", 9) != 2:
        raise SystemExit("Normalização do canal Hikvision 202 falhou")

    paths = set(app.openapi().get("paths", {}))
    required = {
        "/recorders/{recorder_id}/discover",
        "/recorders/{recorder_id}/import-channels",
        "/recorders/{recorder_id}/test-channels",
        "/recorders/{recorder_id}/reprovision",
        "/recorders/{recorder_id}/inventory",
        "/cameras/{camera_id}/test",
        "/cameras/test-batch",
    }
    missing = sorted(required - paths)
    if missing:
        raise SystemExit("Rotas da Fase 3 ausentes: " + ", ".join(missing))

    print(
        json.dumps(
            {
                "ok": True,
                "version": APP_VERSION,
                "ffprobe": True,
                "required_routes": len(required),
                "message": "NVR_PHASE3_PREFLIGHT_OK",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
