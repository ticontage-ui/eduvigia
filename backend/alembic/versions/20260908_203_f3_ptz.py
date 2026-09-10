"""F3 PTZ operacional: controle, lease e presets.

Revision ID: 20260908_203_f3
Revises: 20260908_202_f2
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260908_203_f3"
down_revision: Union[str, Sequence[str], None] = "20260908_202_f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.cameras') IS NOT NULL THEN
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_enabled BOOLEAN DEFAULT FALSE;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_protocol VARCHAR(30) DEFAULT 'HIKVISION_ISAPI';
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_http_port INTEGER DEFAULT 80;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_https BOOLEAN DEFAULT FALSE;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_channel INTEGER DEFAULT 1;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_last_command_at TIMESTAMPTZ;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS ptz_last_error TEXT;

                UPDATE cameras
                SET ptz_enabled = TRUE
                WHERE camera_type = 'PTZ' AND COALESCE(ptz_enabled, FALSE) = FALSE;

                UPDATE cameras
                SET ptz_channel = COALESCE(NULLIF(ptz_channel, 0), nvr_channel, 1),
                    ptz_protocol = COALESCE(NULLIF(ptz_protocol, ''), 'HIKVISION_ISAPI'),
                    ptz_http_port = COALESCE(NULLIF(ptz_http_port, 0), 80);
            END IF;

            IF to_regclass('public.camera_ptz_leases') IS NULL
               AND to_regclass('public.user_accounts') IS NOT NULL
               AND to_regclass('public.cameras') IS NOT NULL THEN
                CREATE TABLE camera_ptz_leases (
                    id SERIAL PRIMARY KEY,
                    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    acquired_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_camera_ptz_leases_camera UNIQUE(camera_id)
                );
                CREATE INDEX ix_camera_ptz_leases_camera_id ON camera_ptz_leases(camera_id);
                CREATE INDEX ix_camera_ptz_leases_user_id ON camera_ptz_leases(user_id);
            END IF;

            IF to_regclass('public.camera_ptz_presets') IS NULL
               AND to_regclass('public.user_accounts') IS NOT NULL
               AND to_regclass('public.cameras') IS NOT NULL THEN
                CREATE TABLE camera_ptz_presets (
                    id SERIAL PRIMARY KEY,
                    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
                    preset_no INTEGER NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    created_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_camera_ptz_presets_camera_no UNIQUE(camera_id, preset_no),
                    CONSTRAINT ck_camera_ptz_presets_no CHECK (preset_no BETWEEN 1 AND 256)
                );
                CREATE INDEX ix_camera_ptz_presets_camera_id ON camera_ptz_presets(camera_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS camera_ptz_presets;
        DROP TABLE IF EXISTS camera_ptz_leases;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_last_error;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_last_command_at;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_channel;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_https;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_http_port;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_protocol;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS ptz_enabled;
        """
    )
