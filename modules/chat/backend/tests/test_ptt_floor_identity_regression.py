import inspect
import os
import unittest

os.environ.setdefault(
    "CHAT_DATABASE_DSN",
    "postgresql://qa:qa@127.0.0.1:5432/qa",
)
os.environ.setdefault(
    "CHAT_REDIS_URL",
    "redis://127.0.0.1:6379/0",
)

from app import ptt


class PttFloorIdentityRegressionTests(unittest.TestCase):
    def test_floor_request_uses_payload_identity_only_as_legacy_hint(self):
        source = inspect.getsource(
            ptt.ptt_request_floor
        )

        self.assertIn(
            "payload.identity_id",
            source,
        )

        self.assertNotIn(
            "resolve_effective_identity("
            "request, conn, effective_identity_id",
            source.replace("\n", " "),
        )

    def test_effective_identity_is_assigned_after_authorization(self):
        source = inspect.getsource(
            ptt.ptt_request_floor
        )

        assignment = (
            'effective_identity_id = '
            'identity["id"]'
        )

        self.assertIn(
            assignment,
            source,
        )

        self.assertIn(
            "principal = await "
            "resolve_effective_identity",
            source,
        )

        self.assertLess(
            source.index(
                "principal = await "
                "resolve_effective_identity"
            ),
            source.index(assignment),
        )

    def test_floor_value_uses_server_validated_identity(self):
        source = inspect.getsource(
            ptt.ptt_request_floor
        )

        self.assertIn(
            "floor_value("
            "effective_identity_id, "
            "floor_id",
            source.replace("\n", " "),
        )

    def test_broadcast_uses_effective_identity(self):
        source = inspect.getsource(
            ptt.ptt_request_floor
        )

        self.assertIn(
            '"identity_id": '
            "effective_identity_id",
            source,
        )


if __name__ == "__main__":
    unittest.main()