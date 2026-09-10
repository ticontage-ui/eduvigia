"""Validação de integração usada exclusivamente pela simulação do instalador."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request


API = os.getenv("EDUVIGIA_PREFLIGHT_API", "http://127.0.0.1:8000").rstrip("/")
MEDIAMTX = os.getenv("EDUVIGIA_PREFLIGHT_MEDIAMTX", "https://mediamtx:8889").rstrip("/")
EMAIL = os.getenv("EDUVIGIA_BOOTSTRAP_ADMIN_EMAIL", "admin@eduvigia.local")
PASSWORD = os.getenv("EDUVIGIA_BOOTSTRAP_ADMIN_PASSWORD", "")
NEW_PASSWORD = "NovaSenhaPreflight@2026!"
TLS_CONTEXT = ssl._create_unverified_context() if MEDIAMTX.startswith("https://") else None


def request_json(method: str, url: str, body: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    if not PASSWORD:
        raise RuntimeError("Senha bootstrap ausente na simulação")

    login = request_json(
        "POST",
        f"{API}/auth/login",
        {"email": EMAIL, "password": PASSWORD},
    )
    token = login["token"]
    if login.get("user", {}).get("must_change_password"):
        request_json(
            "POST",
            f"{API}/auth/change-password",
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            token,
        )

    access = request_json("GET", f"{API}/streams/test-access", token=token)
    query = urllib.parse.urlsplit(access["webrtc_url"]).query
    token_value = urllib.parse.parse_qs(query)["token"][0]

    anonymous_denied = False
    try:
        urllib.request.urlopen(f"{MEDIAMTX}/teste", timeout=15, context=TLS_CONTEXT)
    except urllib.error.HTTPError as error:
        anonymous_denied = error.code in (401, 403)
    if not anonymous_denied:
        raise RuntimeError("MediaMTX aceitou leitura anônima do stream de teste")

    authorized_url = f"{MEDIAMTX}/teste?{urllib.parse.urlencode({'token': token_value})}"
    with urllib.request.urlopen(authorized_url, timeout=20, context=TLS_CONTEXT) as response:
        body = response.read(4096).decode("utf-8", errors="replace").lower()
        if response.status != 200 or "<!doctype html" not in body:
            raise RuntimeError("Player WebRTC autenticado não respondeu HTML válido")

    print("VIDEO_SECURE_PREFLIGHT_OK")


if __name__ == "__main__":
    main()
