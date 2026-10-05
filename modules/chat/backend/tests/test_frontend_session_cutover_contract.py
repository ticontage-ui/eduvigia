import inspect
import os
from pathlib import Path
import unittest

os.environ.setdefault(
    "CHAT_DATABASE_DSN",
    "postgresql://qa:qa@127.0.0.1:5432/qa",
)
os.environ.setdefault(
    "CHAT_REDIS_URL",
    "redis://127.0.0.1:6379/0",
)

from app import auth


CHAT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = CHAT_ROOT / "frontend"


class FrontendSessionCutoverContractTests(unittest.TestCase):
    def read_frontend(self, name):
        return (FRONTEND / name).read_text(encoding="utf-8")

    def test_context_exposes_csrf_and_renews_secure_cookie(self):
        source = inspect.getsource(auth.session_context)

        self.assertIn(
            '"csrf_token": session["csrf_token"]',
            source,
        )
        self.assertIn(
            "set_session_cookie(",
            source,
        )

        cookie_source = inspect.getsource(
            auth.set_session_cookie
        )
        self.assertIn("httponly=True", cookie_source)
        self.assertIn("secure=True", cookie_source)
        self.assertIn('samesite="strict"', cookie_source)

    def test_session_adapter_has_core_fail_closed_contract(self):
        source = self.read_frontend(
            "session-auth.js"
        )

        self.assertIn(
            "EDUVIGIA_CHAT_SESSION_AUTH_V083_R32R3",
            source,
        )
        self.assertIn(
            "eduvigia:chat-auth-required",
            source,
        )
        self.assertIn(
            "X-CSRF-Token",
            source,
        )
        self.assertIn(
            'purpose: String(purpose || "").toUpperCase()',
            source,
        )
        self.assertNotIn(
            "localStorage",
            source,
        )

    def test_main_chat_uses_session_ticket_in_core_mode(self):
        source = self.read_frontend("app.js")

        self.assertIn(
            'issueWsTicket("CHAT")',
            source,
        )
        self.assertIn(
            "chatIdentityPayload(",
            source,
        )
        self.assertIn(
            "authorizedFetch(",
            source,
        )
        self.assertIn(
            "currentIdentity = null",
            source,
        )

    def test_ptt_ticket_is_bound_to_selected_channel(self):
        source = self.read_frontend("ptt.js")

        self.assertIn(
            'issueWsTicket(\n        "PTT",\n        channel',
            source,
        )
        self.assertIn(
            "ticket: issued.ticket",
            source,
        )
        self.assertIn(
            "channel_id: channel",
            source,
        )

    def test_crisis_and_media_use_shared_session_adapter(self):
        crisis = self.read_frontend("crisis.js")
        media = self.read_frontend(
            "crisis-media.js"
        )

        for source in (crisis, media):
            self.assertIn(
                "EduVigIAChatAuth?.withIdentityQuery",
                source,
            )
            self.assertIn(
                "EduVigIAChatAuth?.withIdentityPayload",
                source,
            )

    def test_index_loads_core_bridge_then_session_adapter_before_app(self):
        source = self.read_frontend("index.html")

        bridge_pos = source.index(
            "core-bridge.js"
        )
        auth_pos = source.index(
            "session-auth.js"
        )
        app_pos = source.index(
            "app.js"
        )

        self.assertLess(bridge_pos, auth_pos)
        self.assertLess(auth_pos, app_pos)

    def test_core_bridge_sets_same_origin_paths_and_uses_core_bearer_once(self):
        source = self.read_frontend(
            "core-bridge.js"
        )

        self.assertIn(
            "EDUVIGIA_CHAT_CORE_BRIDGE_V083_R522",
            source,
        )
        self.assertIn(
            'apiBase: "/api/chat"',
            source,
        )
        self.assertIn(
            'wsBase: "/ws/chat"',
            source,
        )
        self.assertIn(
            'rtcBase: "/rtc/chat"',
            source,
        )
        self.assertIn(
            'window.localStorage.getItem(CORE_TOKEN_KEY)',
            source,
        )
        self.assertIn(
            "await auth.exchange(coreBearer)",
            source,
        )

    def test_crisis_livekit_resolves_same_origin_rtc_base(self):
        source = self.read_frontend(
            "crisis-media.js"
        )

        self.assertIn(
            "window.EduVigIAChatConfig?.rtcBase",
            source,
        )
        self.assertEqual(
            source.count(
                "liveKitServerUrl(token.server_url)"
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()