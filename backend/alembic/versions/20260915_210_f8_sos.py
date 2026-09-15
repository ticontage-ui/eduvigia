"""F8 SOS Digital / Emergencia.

Revision ID: 20260915_210_f8_sos
Revises: 20260911_209_f7r3
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260915_210_f8_sos"
down_revision: Union[str, Sequence[str], None] = "20260911_209_f7r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sos_events (
          id SERIAL PRIMARY KEY,
          school_id INTEGER NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
          school_name VARCHAR(200) NOT NULL,
          status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
          repeat_count INTEGER NOT NULL DEFAULT 1,
          note TEXT,
          alert_id INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
          occurrence_id INTEGER REFERENCES occurrences(id) ON DELETE SET NULL,
          activated_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
          activated_by_name VARCHAR(160) NOT NULL DEFAULT 'Sistema',
          activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          last_triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          acknowledged_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
          acknowledged_by_name VARCHAR(160),
          acknowledged_at TIMESTAMPTZ,
          cancel_requested_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
          cancel_requested_by_name VARCHAR(160),
          cancel_requested_at TIMESTAMPTZ,
          resolved_by_user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
          resolved_by_name VARCHAR(160),
          resolved_at TIMESTAMPTZ,
          resolution_note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          CONSTRAINT ck_sos_events_status CHECK (
            status IN ('ACTIVE','ACKNOWLEDGED','CANCEL_REQUESTED','RESOLVED','FALSE_ALARM')
          ),
          CONSTRAINT ck_sos_events_repeat_count CHECK (repeat_count >= 1)
        );
        CREATE INDEX IF NOT EXISTS ix_sos_events_school_id ON sos_events(school_id);
        CREATE INDEX IF NOT EXISTS ix_sos_events_status ON sos_events(status);
        CREATE INDEX IF NOT EXISTS ix_sos_events_alert_id ON sos_events(alert_id);
        CREATE INDEX IF NOT EXISTS ix_sos_events_occurrence_id ON sos_events(occurrence_id);
        CREATE INDEX IF NOT EXISTS ix_sos_events_last_triggered_at ON sos_events(last_triggered_at);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sos_events_school_active
          ON sos_events(school_id)
          WHERE status IN ('ACTIVE','ACKNOWLEDGED','CANCEL_REQUESTED');

        CREATE TABLE IF NOT EXISTS sos_activities (
          id SERIAL PRIMARY KEY,
          sos_event_id INTEGER NOT NULL REFERENCES sos_events(id) ON DELETE CASCADE,
          action VARCHAR(60) NOT NULL,
          from_status VARCHAR(30),
          to_status VARCHAR(30),
          note TEXT,
          user_id INTEGER REFERENCES user_accounts(id) ON DELETE SET NULL,
          user_name VARCHAR(160) NOT NULL DEFAULT 'Sistema',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS ix_sos_activities_sos_event_id ON sos_activities(sos_event_id);
        CREATE INDEX IF NOT EXISTS ix_sos_activities_created_at ON sos_activities(created_at);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS sos_activities;
        DROP TABLE IF EXISTS sos_events;
        """
    )
