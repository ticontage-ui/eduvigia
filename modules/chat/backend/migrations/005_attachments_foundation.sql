CREATE TABLE IF NOT EXISTS chat_attachments (
    id TEXT PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    uploader_identity_id TEXT NOT NULL REFERENCES chat_identities(id),
    original_name VARCHAR(255) NOT NULL,
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    mime_type VARCHAR(160) NOT NULL,
    extension VARCHAR(20) NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    sha256 CHAR(64) NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    validation_status VARCHAR(30) NOT NULL DEFAULT 'TYPE_VALIDATED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_attachments_message
    ON chat_attachments(message_id, created_at);

CREATE INDEX IF NOT EXISTS ix_chat_attachments_channel
    ON chat_attachments(channel_id, created_at);

CREATE INDEX IF NOT EXISTS ix_chat_attachments_sha256
    ON chat_attachments(sha256);