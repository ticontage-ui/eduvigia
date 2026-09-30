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

from app import main


class MessageWriteIdentityRegressionTests(unittest.TestCase):
    def test_text_message_uses_legacy_hint_only_for_identity_resolution(self):
        source = inspect.getsource(main.create_channel_message)

        self.assertIn(
            "payload.sender_identity_id",
            source,
        )
        self.assertNotIn(
            'resolve_effective_identity(\n'
            '                request,\n'
            '                conn,\n'
            '                identity["id"],',
            source,
        )

    def test_attachment_sql_uses_real_sender_identity_column(self):
        source = inspect.getsource(
            main.create_channel_message_with_attachments
        )

        self.assertIn(
            "conversation_id,\n"
            "                        sender_identity_id,\n"
            "                        display_name,",
            source,
        )
        self.assertIn(
            "conversation_id,\n"
            "                        sender_identity_id,\n"
            "                        display_name,\n"
            "                        body,\n"
            "                        created_at",
            source,
        )

    def test_attachment_insert_persists_effective_identity(self):
        source = inspect.getsource(
            main.create_channel_message_with_attachments
        )

        self.assertIn(
            'channel_id,\n'
            '                    identity["id"],\n'
            '                    identity["display_name"],',
            source,
        )
        self.assertNotIn(
            'channel_id,\n'
            '                    sender_identity_id,\n'
            '                    identity["display_name"],',
            source,
        )

    def test_no_python_expression_is_used_as_sql_column(self):
        source = inspect.getsource(
            main.create_channel_message_with_attachments
        )

        sql_area = source.split(
            "INSERT INTO chat_messages(",
            1,
        )[1].split(
            '""",',
            1,
        )[0]

        self.assertNotIn(
            'identity["id"]',
            sql_area,
        )


if __name__ == "__main__":
    unittest.main()