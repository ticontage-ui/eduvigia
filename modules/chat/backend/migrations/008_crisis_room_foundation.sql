-- EDUVIGIA_CHAT_CRISIS_ROOM_FOUNDATION_008
-- V0.8-R1: Sala de Crise - Foundation.
-- Sem WebRTC e sem gravacao nesta etapa.

BEGIN;

CREATE TABLE IF NOT EXISTS chat_crisis_rooms (
    id TEXT PRIMARY KEY,
    school_code VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    incident_id VARCHAR(255),
    incident_source VARCHAR(80),
    external_reference VARCHAR(255),
    triggered_by_identity_id VARCHAR(255)
        REFERENCES chat_identities(id),
    triggered_at TIMESTAMPTZ,
    school_audio_state VARCHAR(20) NOT NULL DEFAULT 'OFF',
    school_audio_publisher_identity_id VARCHAR(255)
        REFERENCES chat_identities(id),
    school_audio_started_at TIMESTAMPTZ,
    school_audio_stopped_at TIMESTAMPTZ,
    created_by_identity_id VARCHAR(255) NOT NULL
        REFERENCES chat_identities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    CONSTRAINT chat_crisis_rooms_status_check
        CHECK (status IN ('READY', 'ACTIVE', 'ENDED')),
    CONSTRAINT chat_crisis_rooms_audio_state_check
        CHECK (school_audio_state IN ('OFF', 'PTT', 'LIVE'))
);

CREATE UNIQUE INDEX IF NOT EXISTS
    ux_chat_crisis_rooms_external_incident
ON chat_crisis_rooms(
    COALESCE(incident_source, 'UNKNOWN'),
    incident_id
)
WHERE incident_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS
    ix_chat_crisis_rooms_school_status
ON chat_crisis_rooms(school_code, status);

CREATE INDEX IF NOT EXISTS
    ix_chat_crisis_rooms_created_at
ON chat_crisis_rooms(created_at DESC);

CREATE TABLE IF NOT EXISTS chat_crisis_room_participants (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT NOT NULL
        REFERENCES chat_crisis_rooms(id) ON DELETE CASCADE,
    identity_id VARCHAR(255) NOT NULL
        REFERENCES chat_identities(id),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS
    ux_chat_crisis_room_active_participant
ON chat_crisis_room_participants(room_id, identity_id)
WHERE left_at IS NULL;

CREATE INDEX IF NOT EXISTS
    ix_chat_crisis_room_participants_room
ON chat_crisis_room_participants(room_id, joined_at);

CREATE TABLE IF NOT EXISTS chat_crisis_room_audit (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT NOT NULL
        REFERENCES chat_crisis_rooms(id) ON DELETE CASCADE,
    actor_identity_id VARCHAR(255)
        REFERENCES chat_identities(id),
    action VARCHAR(80) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS
    ix_chat_crisis_room_audit_room
ON chat_crisis_room_audit(room_id, created_at);

COMMIT;
