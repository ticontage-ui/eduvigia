"""F7-R2 stabilization: schools, cameras, notifications and occurrence sequencing.

Revision ID: 20260911_208_f7r2
Revises: 20260910_207_f7
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260911_208_f7r2"
down_revision: Union[str, Sequence[str], None] = "20260910_207_f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE cameras ADD COLUMN IF NOT EXISTS code VARCHAR(40);
    UPDATE cameras
       SET code = 'CAM-' || LPAD(id::text, 6, '0')
     WHERE code IS NULL OR BTRIM(code) = '';
    CREATE UNIQUE INDEX IF NOT EXISTS ix_cameras_code ON cameras(code);

    ALTER TABLE notifications
      ADD COLUMN IF NOT EXISTS school_id INTEGER REFERENCES schools(id) ON DELETE CASCADE;
    CREATE INDEX IF NOT EXISTS ix_notifications_school_id ON notifications(school_id);

    CREATE TABLE IF NOT EXISTS notification_reads (
      id SERIAL PRIMARY KEY,
      notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
      read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      CONSTRAINT uq_notification_reads_notification_user UNIQUE(notification_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS ix_notification_reads_notification_id ON notification_reads(notification_id);
    CREATE INDEX IF NOT EXISTS ix_notification_reads_user_id ON notification_reads(user_id);

    INSERT INTO notification_reads (notification_id, user_id, read_at)
    SELECT n.id, u.id, n.read_at
      FROM notifications n
      JOIN user_accounts u ON (n.user_id IS NULL OR n.user_id = u.id)
     WHERE n.read_at IS NOT NULL
    ON CONFLICT (notification_id, user_id) DO NOTHING;

    CREATE TABLE IF NOT EXISTS occurrence_sequences (
      year INTEGER PRIMARY KEY,
      last_value INTEGER NOT NULL DEFAULT 0,
      CONSTRAINT ck_occurrence_sequences_last_value CHECK (last_value >= 0)
    );

    INSERT INTO occurrence_sequences (year, last_value)
    SELECT CAST(SUBSTRING(protocol FROM 5 FOR 4) AS INTEGER) AS year,
           MAX(CAST(SPLIT_PART(protocol, '-', 3) AS INTEGER)) AS last_value
      FROM occurrences
     WHERE protocol ~ '^EDU-[0-9]{4}-[0-9]+$'
     GROUP BY CAST(SUBSTRING(protocol FROM 5 FOR 4) AS INTEGER)
    ON CONFLICT (year) DO UPDATE
      SET last_value = GREATEST(occurrence_sequences.last_value, EXCLUDED.last_value);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS occurrence_sequences;
    DROP TABLE IF EXISTS notification_reads;
    DROP INDEX IF EXISTS ix_notifications_school_id;
    ALTER TABLE notifications DROP COLUMN IF EXISTS school_id;
    DROP INDEX IF EXISTS ix_cameras_code;
    ALTER TABLE cameras DROP COLUMN IF EXISTS code;
    """)
