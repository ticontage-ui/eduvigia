"""F4 playback and forensic evidence.

Revision ID: 20260909_205_f4
Revises: 20260909_204_f3r2
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260909_205_f4"
down_revision: Union[str, Sequence[str], None] = "20260909_204_f3r2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
    ALTER TABLE IF EXISTS evidence ALTER COLUMN occurrence_id DROP NOT NULL;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES schools(id) ON DELETE SET NULL;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS device_id INTEGER REFERENCES video_devices(id) ON DELETE SET NULL;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS logical_channel INTEGER;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS sensor_type VARCHAR(30);
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS sha256 VARCHAR(64);
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS source_start_at TIMESTAMPTZ;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS source_end_at TIMESTAMPTZ;
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS source_origin VARCHAR(40);
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS integrity_status VARCHAR(20) DEFAULT 'PENDING';
    ALTER TABLE IF EXISTS evidence ADD COLUMN IF NOT EXISTS created_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL;
    CREATE INDEX IF NOT EXISTS ix_evidence_school_id ON evidence(school_id);
    CREATE INDEX IF NOT EXISTS ix_evidence_camera_id ON evidence(camera_id);
    CREATE INDEX IF NOT EXISTS ix_evidence_device_id ON evidence(device_id);
    CREATE INDEX IF NOT EXISTS ix_evidence_sha256 ON evidence(sha256);
    CREATE TABLE IF NOT EXISTS evidence_custody_events (
      id SERIAL PRIMARY KEY, evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
      action VARCHAR(40) NOT NULL, user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
      user_name VARCHAR(160) DEFAULT 'Sistema', sha256_observed VARCHAR(64), detail TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS ix_evidence_custody_events_evidence_id ON evidence_custody_events(evidence_id);
    CREATE INDEX IF NOT EXISTS ix_evidence_custody_events_created_at ON evidence_custody_events(created_at);
    UPDATE evidence e SET school_id=c.school_id, device_id=c.device_id, logical_channel=c.logical_channel, sensor_type=c.sensor_type
      FROM cameras c WHERE e.camera_id=c.id AND e.school_id IS NULL;
    """)

def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS evidence_custody_events;
    DROP INDEX IF EXISTS ix_evidence_sha256;
    DROP INDEX IF EXISTS ix_evidence_device_id;
    DROP INDEX IF EXISTS ix_evidence_school_id;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS created_by_user_id;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS integrity_status;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS source_origin;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS source_end_at;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS source_start_at;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS file_size_bytes;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS sha256;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS sensor_type;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS logical_channel;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS device_id;
    ALTER TABLE IF EXISTS evidence DROP COLUMN IF EXISTS school_id;
    """)
