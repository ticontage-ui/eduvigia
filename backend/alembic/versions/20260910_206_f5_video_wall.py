"""F5 video wall operational layouts.

Revision ID: 20260910_206_f5
Revises: 20260909_205_f4
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260910_206_f5"
down_revision: Union[str, Sequence[str], None] = "20260909_205_f4"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS video_wall_layouts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
      name VARCHAR(120) NOT NULL,
      grid_size INTEGER NOT NULL DEFAULT 4,
      quality_mode VARCHAR(10) NOT NULL DEFAULT 'AUTO',
      is_default BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      CONSTRAINT uq_video_wall_layouts_user_name UNIQUE(user_id, name),
      CONSTRAINT ck_video_wall_grid_size CHECK (grid_size IN (1,4,9,16)),
      CONSTRAINT ck_video_wall_quality_mode CHECK (quality_mode IN ('AUTO','SUB','MAIN'))
    );
    CREATE INDEX IF NOT EXISTS ix_video_wall_layouts_user_id ON video_wall_layouts(user_id);
    CREATE TABLE IF NOT EXISTS video_wall_slots (
      id SERIAL PRIMARY KEY,
      layout_id INTEGER NOT NULL REFERENCES video_wall_layouts(id) ON DELETE CASCADE,
      slot_index INTEGER NOT NULL,
      camera_id INTEGER NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      CONSTRAINT uq_video_wall_slots_layout_slot UNIQUE(layout_id, slot_index),
      CONSTRAINT ck_video_wall_slot_index CHECK (slot_index >= 0 AND slot_index < 16)
    );
    CREATE INDEX IF NOT EXISTS ix_video_wall_slots_layout_id ON video_wall_slots(layout_id);
    CREATE INDEX IF NOT EXISTS ix_video_wall_slots_camera_id ON video_wall_slots(camera_id);
    """)

def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS video_wall_slots;
    DROP TABLE IF EXISTS video_wall_layouts;
    """)
