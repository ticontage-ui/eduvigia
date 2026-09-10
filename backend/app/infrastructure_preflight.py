from __future__ import annotations

import json
import os
import socket
import urllib.request
from pathlib import Path

from app.application import APP_VERSION, DB_MAX_OVERFLOW, DB_POOL_SIZE


def _url_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return json.loads(response.read().decode("utf-8"))


def _url_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}: {url}")
        return response.read().decode("utf-8")


def _validate_running_readiness(snapshot: dict) -> None:
    if not snapshot.get("ready") or snapshot.get("status") != "READY":
        raise RuntimeError(f"Readiness reprovada: {snapshot}")
    if snapshot.get("version") != APP_VERSION:
        raise RuntimeError(f"Versão inesperada na readiness: {snapshot}")
    if snapshot.get("startup_complete") is not True:
        raise RuntimeError(f"Inicialização da API ainda não concluída: {snapshot}")

    services = snapshot.get("services") or {}
    for service_name in ("database", "redis", "mediamtx"):
        if (services.get(service_name) or {}).get("status") != "ONLINE":
            raise RuntimeError(f"Serviço obrigatório indisponível ({service_name}): {snapshot}")
    storage_status = (services.get("storage") or {}).get("status")
    if storage_status in {None, "OFFLINE", "CRITICAL"}:
        raise RuntimeError(f"Armazenamento sem prontidão: {snapshot}")


def main() -> None:
    if not APP_VERSION.startswith("2.0.0-"):
        raise RuntimeError(f"Versão inválida: {APP_VERSION}")
    if DB_POOL_SIZE < 2 or DB_MAX_OVERFLOW < 0:
        raise RuntimeError("Configuração do pool PostgreSQL inválida")

    live = _url_json("http://127.0.0.1:8000/live")
    if live.get("version") != APP_VERSION or live.get("status") != "alive":
        raise RuntimeError(f"Liveness inválida: {live}")

    # A prontidão deve ser lida do processo Uvicorn em execução. Importar e chamar
    # collect_readiness() neste processo auxiliar recria APP_STARTUP_COMPLETE=False
    # e produz um falso negativo mesmo quando /ready já está aprovado.
    ready = _url_json("http://127.0.0.1:8000/ready")
    _validate_running_readiness(ready)

    metrics = _url_text("http://127.0.0.1:8000/metrics")
    required_metrics = (
        "eduvigia_info",
        "eduvigia_database_up 1",
        "eduvigia_http_requests_total",
        "eduvigia_database_pool_size",
    )
    missing = [item for item in required_metrics if item not in metrics]
    if missing:
        raise RuntimeError(f"Métricas obrigatórias ausentes: {missing}")

    for host, port in (("proxy", 80), ("proxy", 443), ("prometheus", 9090)):
        with socket.create_connection((host, port), timeout=5):
            pass

    cert_dir = Path(os.getenv("EDUVIGIA_TLS_CERT_DIR", "/certs"))
    for name in ("eduvigia.crt", "eduvigia.key"):
        if not (cert_dir / name).is_file():
            raise RuntimeError(f"Arquivo TLS ausente: {name}")

    print(
        json.dumps(
            {
                "ok": True,
                "version": APP_VERSION,
                "readiness": ready["status"],
                "prometheus": True,
                "proxy_http": True,
                "proxy_https": True,
                "message": "INFRA_PHASE4_PREFLIGHT_OK",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
