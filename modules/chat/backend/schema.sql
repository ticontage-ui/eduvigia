CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT NOT NULL DEFAULT 'general',
    display_name VARCHAR(80) NOT NULL,
    body TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_messages_room_id_id
    ON chat_messages(room_id, id);

CREATE TABLE IF NOT EXISTS chat_outbox (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    aggregate_id BIGINT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_chat_outbox_pending
    ON chat_outbox(id)
    WHERE published_at IS NULL;
