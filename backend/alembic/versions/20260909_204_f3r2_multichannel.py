"""F3-R2 multi-channel / multi-sensor device foundation.

Revision ID: 20260909_204_f3r2
Revises: 20260908_203_f3
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260909_204_f3r2"
down_revision: Union[str, Sequence[str], None] = "20260908_203_f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS video_devices (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
            name VARCHAR(180) NOT NULL,
            manufacturer VARCHAR(80) DEFAULT 'Hikvision',
            model VARCHAR(120),
            serial_number VARCHAR(120),
            ip_address VARCHAR(64) NOT NULL,
            http_port INTEGER DEFAULT 80,
            https_port INTEGER DEFAULT 443,
            rtsp_port INTEGER DEFAULT 554,
            username VARCHAR(120),
            password VARCHAR(180),
            device_type VARCHAR(40) DEFAULT 'CAMERA',
            channel_count INTEGER DEFAULT 1,
            status VARCHAR(20) DEFAULT 'PENDING',
            last_check_at TIMESTAMPTZ,
            last_error TEXT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_video_devices_school_ip_rtsp UNIQUE(school_id, ip_address, rtsp_port)
        );
        CREATE INDEX IF NOT EXISTS ix_video_devices_school_id ON video_devices(school_id);

        ALTER TABLE IF EXISTS cameras ADD COLUMN IF NOT EXISTS device_id INTEGER REFERENCES video_devices(id) ON DELETE SET NULL;
        ALTER TABLE IF EXISTS cameras ADD COLUMN IF NOT EXISTS logical_channel INTEGER DEFAULT 1;
        ALTER TABLE IF EXISTS cameras ADD COLUMN IF NOT EXISTS sensor_type VARCHAR(30) DEFAULT 'VISIBLE';
        ALTER TABLE IF EXISTS cameras ADD COLUMN IF NOT EXISTS sensor_label VARCHAR(120);
        ALTER TABLE IF EXISTS cameras ADD COLUMN IF NOT EXISTS primary_sensor BOOLEAN DEFAULT TRUE;
        CREATE INDEX IF NOT EXISTS ix_cameras_device_id ON cameras(device_id);

        INSERT INTO video_devices (
            school_id, name, manufacturer, model, ip_address, http_port, https_port,
            rtsp_port, username, password, device_type, channel_count, status, last_check_at, last_error, active
        )
        SELECT DISTINCT ON (c.school_id, c.ip_address, c.port)
            c.school_id,
            c.name,
            COALESCE(NULLIF(c.manufacturer, ''), 'Hikvision'),
            c.model,
            c.ip_address,
            COALESCE(NULLIF(c.ptz_http_port, 0), 80),
            443,
            COALESCE(NULLIF(c.port, 0), 554),
            c.username,
            c.password,
            CASE WHEN c.camera_type = 'TERMICA' THEN 'BISPECTRUM' ELSE 'CAMERA' END,
            1,
            c.status,
            c.last_check_at,
            c.last_error,
            TRUE
        FROM cameras c
        WHERE c.source_type = 'CAMERA_IP'
          AND c.ip_address IS NOT NULL
          AND c.ip_address <> ''
          AND c.device_id IS NULL
        ON CONFLICT (school_id, ip_address, rtsp_port) DO NOTHING;

        UPDATE cameras c
        SET device_id = d.id,
            logical_channel = COALESCE(NULLIF(c.logical_channel, 0), 1),
            sensor_type = CASE WHEN c.camera_type = 'TERMICA' THEN 'THERMAL' ELSE COALESCE(NULLIF(c.sensor_type, ''), 'VISIBLE') END,
            primary_sensor = COALESCE(c.primary_sensor, TRUE)
        FROM video_devices d
        WHERE c.device_id IS NULL
          AND c.source_type = 'CAMERA_IP'
          AND c.ip_address = d.ip_address
          AND c.school_id = d.school_id
          AND COALESCE(NULLIF(c.port, 0), 554) = d.rtsp_port;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS ix_cameras_device_id;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS primary_sensor;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sensor_label;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS sensor_type;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS logical_channel;
        ALTER TABLE IF EXISTS cameras DROP COLUMN IF EXISTS device_id;
        DROP TABLE IF EXISTS video_devices;
        """
    )
