"""F2 VMS basico: perfis MAIN/SUB e favoritos por usuario.

Revision ID: 20260908_202_f2
Revises: 20260908_201_f1
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260908_202_f2"
down_revision: Union[str, Sequence[str], None] = "20260908_201_f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.cameras') IS NOT NULL THEN
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_url_main VARCHAR(600);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS rtsp_url_sub VARCHAR(600);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_status VARCHAR(20) DEFAULT 'PENDING';
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_status VARCHAR(20) DEFAULT 'PENDING';
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_codec VARCHAR(30);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_resolution VARCHAR(40);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_fps INTEGER;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS main_bitrate_kbps INTEGER;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_codec VARCHAR(30);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_resolution VARCHAR(40);
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_fps INTEGER;
                ALTER TABLE cameras ADD COLUMN IF NOT EXISTS sub_bitrate_kbps INTEGER;

                UPDATE cameras
                SET
                    sub_codec = COALESCE(sub_codec, codec),
                    sub_resolution = COALESCE(sub_resolution, resolution),
                    sub_fps = COALESCE(sub_fps, fps),
                    rtsp_url_main = CASE
                        WHEN source_type = 'RTSP_CUSTOM' THEN COALESCE(rtsp_url_main, rtsp_url)
                        ELSE rtsp_url_main
                    END,
                    rtsp_url_sub = CASE
                        WHEN source_type = 'RTSP_CUSTOM' THEN COALESCE(rtsp_url_sub, rtsp_url)
                        ELSE rtsp_url_sub
                    END;
            END IF;

            IF to_regclass('public.camera_favorites') IS NULL
               AND to_regclass('public.user_accounts') IS NOT NULL
               AND to_regclass('public.cameras') IS NOT NULL THEN
                CREATE TABLE camera_favorites (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
                    camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    CONSTRAINT uq_camera_favorites_user_camera UNIQUE(user_id, camera_id)
                );
                CREATE INDEX ix_camera_favorites_user_id ON camera_favorites(user_id);
                CREATE INDEX ix_camera_favorites_camera_id ON camera_favorites(camera_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS camera_favorites;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sub_bitrate_kbps;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sub_fps;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sub_resolution;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sub_codec;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS main_bitrate_kbps;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS main_fps;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS main_resolution;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS main_codec;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sub_status;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS main_status;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS rtsp_url_sub;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS rtsp_url_main;
        """
    )
