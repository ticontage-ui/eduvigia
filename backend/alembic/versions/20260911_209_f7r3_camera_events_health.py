"""F7-R3 camera events and health telemetry.

Revision ID: 20260911_209_f7r3
Revises: 20260911_208_f7r2
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260911_209_f7r3"
down_revision: Union[str, Sequence[str], None] = "20260911_208_f7r2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS camera_events (
      id SERIAL PRIMARY KEY,
      school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
      camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
      recorder_id INTEGER REFERENCES recorders(id) ON DELETE SET NULL,
      provider VARCHAR(40) NOT NULL DEFAULT 'GENERIC',
      provider_event_type VARCHAR(160) NOT NULL,
      event_type VARCHAR(80) NOT NULL,
      event_state VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
      severity VARCHAR(20) NOT NULL DEFAULT 'MEDIA',
      correlation_key VARCHAR(240) NOT NULL,
      event_uid VARCHAR(180),
      source_channel INTEGER,
      first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      repeat_count INTEGER NOT NULL DEFAULT 1,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      alert_id INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
      metadata_json TEXT,
      raw_payload_json TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT ck_camera_events_state CHECK (event_state IN ('ACTIVE','INACTIVE','INFO')),
      CONSTRAINT ck_camera_events_severity CHECK (severity IN ('INFO','BAIXA','MEDIA','ALTA','CRITICA')),
      CONSTRAINT ck_camera_events_repeat_count CHECK (repeat_count >= 1)
    );
    CREATE INDEX IF NOT EXISTS ix_camera_events_school_id ON camera_events(school_id);
    CREATE INDEX IF NOT EXISTS ix_camera_events_camera_id ON camera_events(camera_id);
    CREATE INDEX IF NOT EXISTS ix_camera_events_recorder_id ON camera_events(recorder_id);
    CREATE INDEX IF NOT EXISTS ix_camera_events_event_type ON camera_events(event_type);
    CREATE INDEX IF NOT EXISTS ix_camera_events_event_state ON camera_events(event_state);
    CREATE INDEX IF NOT EXISTS ix_camera_events_occurred_at ON camera_events(occurred_at DESC);
    CREATE INDEX IF NOT EXISTS ix_camera_events_active ON camera_events(active);
    CREATE INDEX IF NOT EXISTS ix_camera_events_alert_id ON camera_events(alert_id);
    CREATE INDEX IF NOT EXISTS ix_camera_events_correlation_key ON camera_events(correlation_key);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_camera_events_event_uid
      ON camera_events(event_uid) WHERE event_uid IS NOT NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS uq_camera_events_correlation_active
      ON camera_events(correlation_key) WHERE active IS TRUE;

    CREATE TABLE IF NOT EXISTS camera_health (
      id SERIAL PRIMARY KEY,
      camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
      school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
      state VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
      rtsp_online BOOLEAN,
      main_online BOOLEAN,
      sub_online BOOLEAN,
      recording_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
      storage_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
      tamper_active BOOLEAN NOT NULL DEFAULT FALSE,
      motion_active BOOLEAN NOT NULL DEFAULT FALSE,
      ntp_offset_ms INTEGER,
      fps INTEGER,
      bitrate_kbps INTEGER,
      resolution VARCHAR(40),
      codec VARCHAR(30),
      last_event_at TIMESTAMPTZ,
      last_seen_at TIMESTAMPTZ,
      last_video_at TIMESTAMPTZ,
      last_error TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT uq_camera_health_camera UNIQUE(camera_id),
      CONSTRAINT ck_camera_health_state CHECK (state IN ('UNKNOWN','ONLINE','DEGRADADO','OFFLINE'))
    );
    CREATE INDEX IF NOT EXISTS ix_camera_health_camera_id ON camera_health(camera_id);
    CREATE INDEX IF NOT EXISTS ix_camera_health_school_id ON camera_health(school_id);
    CREATE INDEX IF NOT EXISTS ix_camera_health_state ON camera_health(state);

    CREATE TABLE IF NOT EXISTS recorder_health (
      id SERIAL PRIMARY KEY,
      recorder_id INTEGER NOT NULL REFERENCES recorders(id) ON DELETE CASCADE,
      school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
      state VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN',
      recording_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
      storage_status VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
      last_event_at TIMESTAMPTZ,
      last_seen_at TIMESTAMPTZ,
      last_error TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT uq_recorder_health_recorder UNIQUE(recorder_id),
      CONSTRAINT ck_recorder_health_state CHECK (state IN ('UNKNOWN','ONLINE','DEGRADADO','OFFLINE'))
    );
    CREATE INDEX IF NOT EXISTS ix_recorder_health_recorder_id ON recorder_health(recorder_id);
    CREATE INDEX IF NOT EXISTS ix_recorder_health_school_id ON recorder_health(school_id);
    CREATE INDEX IF NOT EXISTS ix_recorder_health_state ON recorder_health(state);

    INSERT INTO camera_health (
      camera_id, school_id, state, rtsp_online, main_online, sub_online,
      fps, bitrate_kbps, resolution, codec, last_seen_at, last_video_at, last_error, updated_at
    )
    SELECT
      c.id,
      c.school_id,
      CASE
        WHEN c.status = 'ONLINE' THEN 'ONLINE'
        WHEN c.status = 'OFFLINE' THEN 'OFFLINE'
        ELSE 'UNKNOWN'
      END,
      CASE WHEN c.status = 'ONLINE' THEN TRUE WHEN c.status = 'OFFLINE' THEN FALSE ELSE NULL END,
      CASE WHEN c.main_status = 'ONLINE' THEN TRUE WHEN c.main_status = 'OFFLINE' THEN FALSE ELSE NULL END,
      CASE WHEN c.sub_status = 'ONLINE' THEN TRUE WHEN c.sub_status = 'OFFLINE' THEN FALSE ELSE NULL END,
      c.fps,
      COALESCE(c.main_bitrate_kbps, c.sub_bitrate_kbps),
      c.resolution,
      c.codec,
      c.last_check_at,
      c.last_frame_at,
      c.last_error,
      NOW()
    FROM cameras c
    ON CONFLICT (camera_id) DO NOTHING;

    INSERT INTO recorder_health (
      recorder_id, school_id, state, last_seen_at, last_error, updated_at
    )
    SELECT
      r.id,
      r.school_id,
      CASE
        WHEN r.status IN ('ONLINE','OFFLINE','DEGRADADO') THEN r.status
        ELSE 'UNKNOWN'
      END,
      r.last_check_at,
      r.last_error,
      NOW()
    FROM recorders r
    ON CONFLICT (recorder_id) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS recorder_health;
    DROP TABLE IF EXISTS camera_health;
    DROP TABLE IF EXISTS camera_events;
    """)
