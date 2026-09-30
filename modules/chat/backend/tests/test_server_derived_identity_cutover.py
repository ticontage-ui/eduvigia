import asyncio
import os
import unittest
from pathlib import Path

os.environ["CHAT_AUTH_MODE"] = "standalone_qa"
os.environ["CHAT_SESSION_TTL_SECONDS"] = "120"
os.environ["CHAT_WS_TICKET_TTL_SECONDS"] = "45"

from fastapi import HTTPException
from app import auth


class FakeConn:
    def __init__(self, rows):
        self.rows = rows

    async def fetchrow(self, _sql, identity_id):
        return self.rows.get(identity_id)


class ServerDerivedIdentityCutoverTests(unittest.TestCase):
    def test_legacy_role_canonicalization(self):
        self.assertEqual(
            auth.canonical_core_role("OPERADOR", 10),
            "OPERADOR_ESCOLA",
        )
        self.assertEqual(
            auth.canonical_core_role("OPERADOR", None),
            "OPERADOR_GUARDA",
        )
        self.assertEqual(
            auth.canonical_core_role("ESCOLA", 10),
            "GESTOR_ESCOLA",
        )
        self.assertEqual(
            auth.canonical_core_role("ADMIN", None),
            "ADMIN_SECRETARIA",
        )

    def test_core_mode_rejects_client_identity_mismatch(self):
        original_mode = auth.auth_mode
        original_loader = auth.load_commercial_session

        async def fake_loader(_request, require_csrf=None):
            return {
                "principal": {
                    "identity_id": "core:user:42",
                },
                "csrf_token": "csrf",
            }

        try:
            auth.auth_mode = lambda: "core"
            auth.load_commercial_session = fake_loader
            conn = FakeConn(
                {
                    "core:user:42": {
                        "id": "core:user:42",
                        "display_name": "Gestor",
                        "organization_kind": "ESCOLA",
                        "school_code": "ESC-42",
                        "role": "GESTOR_ESCOLA",
                        "active": True,
                    }
                }
            )

            with self.assertRaises(HTTPException) as captured:
                asyncio.run(
                    auth.resolve_effective_identity(
                        object(),
                        conn,
                        "mock:escola-a",
                    )
                )

            self.assertEqual(captured.exception.status_code, 403)
        finally:
            auth.auth_mode = original_mode
            auth.load_commercial_session = original_loader

    def test_core_mode_uses_session_identity_when_client_omits_identity(self):
        original_mode = auth.auth_mode
        original_loader = auth.load_commercial_session

        async def fake_loader(_request, require_csrf=None):
            return {
                "principal": {
                    "identity_id": "core:user:42",
                },
                "csrf_token": "csrf",
            }

        try:
            auth.auth_mode = lambda: "core"
            auth.load_commercial_session = fake_loader
            expected = {
                "id": "core:user:42",
                "display_name": "Gestor",
                "organization_kind": "ESCOLA",
                "school_code": "ESC-42",
                "role": "GESTOR_ESCOLA",
                "active": True,
            }
            conn = FakeConn({"core:user:42": expected})

            row = asyncio.run(
                auth.resolve_effective_identity(
                    object(),
                    conn,
                    None,
                )
            )

            self.assertEqual(row["id"], "core:user:42")
        finally:
            auth.auth_mode = original_mode
            auth.load_commercial_session = original_loader

    def test_backend_routes_contain_commercial_cutover_hooks(self):
        root = Path(__file__).resolve().parents[1] / "app"

        main = (root / "main.py").read_text(encoding="utf-8")
        ptt = (root / "ptt.py").read_text(encoding="utf-8")
        crisis = (root / "crisis.py").read_text(encoding="utf-8")
        media = (root / "crisis_media.py").read_text(encoding="utf-8")

        self.assertIn("resolve_effective_identity", main)
        self.assertIn('expected_purpose="CHAT"', main)
        self.assertIn("consume_ws_ticket", ptt)
        self.assertIn('expected_purpose="PTT"', ptt)
        self.assertIn("require_crisis_request_identity", crisis)
        self.assertIn("require_crisis_request_identity", media)

        self.assertNotIn("identity_id: str = Query(...)", main)
        self.assertNotIn("identity_id: str = Query(...)", ptt)
        self.assertNotIn("identity_id: str = Query(...)", crisis)
        self.assertNotIn(
            "identity_id: str = Field(min_length=1, max_length=255)",
            crisis,
        )
        self.assertNotIn(
            "identity_id: str = Field(min_length=1, max_length=255)",
            media,
        )


if __name__ == "__main__":
    unittest.main()