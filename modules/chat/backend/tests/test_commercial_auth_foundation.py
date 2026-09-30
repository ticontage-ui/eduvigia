import os
import unittest

os.environ["CHAT_AUTH_MODE"] = "standalone_qa"
os.environ["CHAT_SESSION_TTL_SECONDS"] = "120"
os.environ["CHAT_WS_TICKET_TTL_SECONDS"] = "45"

from app import auth


class CommercialAuthFoundationTests(unittest.TestCase):
    def test_role_mapping(self):
        self.assertEqual(
            auth.organization_for_role("GESTOR_ESCOLA"),
            "ESCOLA",
        )
        self.assertEqual(
            auth.organization_for_role("OPERADOR_ESCOLA"),
            "ESCOLA",
        )
        self.assertEqual(
            auth.organization_for_role("SUPERVISOR_GUARDA"),
            "GUARDA",
        )
        self.assertEqual(
            auth.organization_for_role("DESPACHANTE_GUARDA"),
            "GUARDA",
        )
        self.assertEqual(
            auth.organization_for_role("ADMIN_SECRETARIA"),
            "SECRETARIA",
        )
        self.assertIsNone(
            auth.organization_for_role("TECNICO")
        )

    def test_opaque_keys_do_not_embed_raw_secret(self):
        raw = "a-very-sensitive-session-value"
        session_key = auth.session_key(raw)
        ticket_key = auth.ws_ticket_key(raw)

        self.assertNotIn(raw, session_key)
        self.assertNotIn(raw, ticket_key)
        self.assertTrue(
            session_key.startswith(
                auth.SESSION_REDIS_PREFIX
            )
        )
        self.assertTrue(
            ticket_key.startswith(
                auth.WS_TICKET_REDIS_PREFIX
            )
        )

    def test_ttl_bounds(self):
        self.assertEqual(
            auth.session_ttl_seconds(),
            120,
        )
        self.assertEqual(
            auth.ws_ticket_ttl_seconds(),
            45,
        )

    def test_foundation_has_no_password_store(self):
        snapshot = auth.foundation_snapshot()

        self.assertEqual(
            snapshot["auth_mode"],
            "standalone_qa",
        )
        self.assertFalse(
            snapshot["chat_password_store"]
        )
        self.assertEqual(
            snapshot["session_cookie"],
            "HTTPONLY_SECURE_SAMESITE_STRICT",
        )

    def test_same_origin_websocket(self):
        self.assertTrue(
            auth.same_origin_websocket(
                "https://eduvigia.local",
                "eduvigia.local",
            )
        )
        self.assertTrue(
            auth.same_origin_websocket(
                "https://192.168.18.122:16443",
                "192.168.18.122:16443",
            )
        )
        self.assertFalse(
            auth.same_origin_websocket(
                "https://attacker.example",
                "eduvigia.local",
            )
        )
        self.assertFalse(
            auth.same_origin_websocket(
                "http://eduvigia.local",
                "eduvigia.local",
            )
        )


if __name__ == "__main__":
    unittest.main()