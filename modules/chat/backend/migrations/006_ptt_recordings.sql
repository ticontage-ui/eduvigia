CREATE TABLE IF NOT EXISTS chat_ptt_recordings (
    id TEXT PRIMARY KEY,
    floor_id TEXT NOT NULL UNIQUE,
    channel_id TEXT NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    speaker_identity_id TEXT NOT NULL REFERENCES chat_identities(id),
    mime_type VARCHAR(120) NOT NULL DEFAULT 'audio/webm;codecs=opus',
    stored_name VARCHAR(255) NOT NULL UNIQUE,
    storage_path TEXT NOT NULL UNIQUE,
    size_bytes BIGINT NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    sha256 CHAR(64),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    end_reason VARCHAR(40),
    status VARCHAR(20) NOT NULL DEFAULT 'RECORDING'
        CHECK (status IN ('RECORDING', 'READY', 'ABORTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_ptt_recordings_channel_started
    ON chat_ptt_recordings(channel_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_chat_ptt_recordings_speaker_started
    ON chat_ptt_recordings(speaker_identity_id, started_at DESC);

CREATE INDEX IF NOT EXISTS ix_chat_ptt_recordings_sha256
    ON chat_ptt_recordings(sha256)
    WHERE sha256 IS NOT NULL;