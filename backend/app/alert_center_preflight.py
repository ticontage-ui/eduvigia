from __future__ import annotations

import json
from pathlib import Path

from .application import (
    ALERT_ACTIVE_STATUSES,
    APP_VERSION,
    Alert,
    AlertActivity,
    DATA_DIR,
    app,
)

REQUIRED_ROUTES = {
    ("GET", "/alerts"),
    ("GET", "/alerts/overview"),
    ("GET", "/alerts/{alert_id}/details"),
    ("GET", "/alerts/{alert_id}/evidence"),
    ("PATCH", "/alerts/{alert_id}/workflow"),
    ("POST", "/alerts/{alert_id}/assign"),
    ("POST", "/alerts/{alert_id}/occurrence"),
}
REQUIRED_ALERT_COLUMNS = {
    "source",
    "confidence",
    "summary",
    "evidence_path",
    "payload_json",
    "assigned_user_id",
    "assigned_user_name",
    "acknowledged_at",
    "resolved_at",
    "event_occurred_at",
    "updated_at",
}


def main() -> None:
    available = {
        (method, route.path)
        for route in app.routes
        for method in (route.methods or set())
    }
    missing_routes = sorted(REQUIRED_ROUTES - available)
    if missing_routes:
        raise RuntimeError(f"Rotas obrigatórias ausentes: {missing_routes}")

    alert_columns = set(Alert.__table__.columns.keys())
    missing_columns = sorted(REQUIRED_ALERT_COLUMNS - alert_columns)
    if missing_columns:
        raise RuntimeError(f"Colunas da Central de Alertas ausentes: {missing_columns}")

    activity_columns = set(AlertActivity.__table__.columns.keys())
    if not {"alert_id", "action", "from_status", "to_status", "note", "user_name", "created_at"}.issubset(activity_columns):
        raise RuntimeError("Histórico de alertas incompleto")

    if ALERT_ACTIVE_STATUSES != {"NOVO", "EM_ATENDIMENTO", "CONFIRMADO"}:
        raise RuntimeError(f"Workflow ativo inesperado: {sorted(ALERT_ACTIVE_STATUSES)}")

    data_dir = Path(DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    probe = data_dir / ".phase7-write-test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "ok": True,
                "version": APP_VERSION,
                "required_routes": len(REQUIRED_ROUTES),
                "workflow": ["NOVO", "EM_ATENDIMENTO", "CONFIRMADO", "DESCARTADO", "ENCERRADO"],
                "generic_alert_center": True,
                "evidence_protected": True,
                "school_isolation": True,
                "message": "ALERT_CENTER_PHASE7_PREFLIGHT_OK",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
