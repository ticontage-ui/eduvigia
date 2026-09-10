"""F7 floor plans and camera placements.

Revision ID: 20260910_207_f7
Revises: 20260910_206_f5
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260910_207_f7"
down_revision: Union[str, Sequence[str], None] = "20260910_206_f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS floor_plans (
      id SERIAL PRIMARY KEY,
      school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
      name VARCHAR(160) NOT NULL,
      building VARCHAR(120),
      floor_label VARCHAR(80),
      filename VARCHAR(220) NOT NULL,
      original_name VARCHAR(260),
      mime_type VARCHAR(80) NOT NULL,
      file_path VARCHAR(700) NOT NULL,
      created_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      CONSTRAINT uq_floor_plans_school_name UNIQUE(school_id, name)
    );
    CREATE INDEX IF NOT EXISTS ix_floor_plans_school_id ON floor_plans(school_id);

    CREATE TABLE IF NOT EXISTS floor_plan_cameras (
      id SERIAL PRIMARY KEY,
      floor_plan_id INTEGER NOT NULL REFERENCES floor_plans(id) ON DELETE CASCADE,
      camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
      x_percent DOUBLE PRECISION NOT NULL,
      y_percent DOUBLE PRECISION NOT NULL,
      rotation_deg DOUBLE PRECISION NOT NULL DEFAULT 0,
      label VARCHAR(120),
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      CONSTRAINT uq_floor_plan_camera UNIQUE(floor_plan_id, camera_id),
      CONSTRAINT ck_floor_plan_x_percent CHECK (x_percent >= 0 AND x_percent <= 100),
      CONSTRAINT ck_floor_plan_y_percent CHECK (y_percent >= 0 AND y_percent <= 100)
    );
    CREATE INDEX IF NOT EXISTS ix_floor_plan_cameras_floor_plan_id ON floor_plan_cameras(floor_plan_id);
    CREATE INDEX IF NOT EXISTS ix_floor_plan_cameras_camera_id ON floor_plan_cameras(camera_id);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS floor_plan_cameras;
    DROP TABLE IF EXISTS floor_plans;
    """)
