"""Remove o domínio legado de IA da baseline EduVigIA 2.0 F0.

Revision ID: 20260908_200_f0
Revises: 20260625_130
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260908_200_f0"
down_revision: Union[str, Sequence[str], None] = "20260625_130"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O projeto legado criava o schema no startup. Os blocos condicionais
    # permitem aplicar esta migration tanto sobre uma base 1.9.0-R1 quanto
    # sobre uma instalação nova já criada pelo startup da aplicação.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.alerts') IS NOT NULL THEN
                ALTER TABLE alerts DROP CONSTRAINT IF EXISTS alerts_ai_event_id_fkey;
                DROP INDEX IF EXISTS ix_alerts_ai_event_id;
                ALTER TABLE alerts DROP COLUMN IF EXISTS ai_event_id;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.cameras') IS NOT NULL THEN
                ALTER TABLE cameras DROP COLUMN IF EXISTS ai_enabled;
            END IF;
        END $$;
        """
    )
    op.execute("DROP TABLE IF EXISTS ai_telemetry")
    op.execute("DROP TABLE IF EXISTS ai_events")
    op.execute("DROP TABLE IF EXISTS ai_rules")
    op.execute("DROP TABLE IF EXISTS ai_servers")


def downgrade() -> None:
    # A F0 é uma remoção de escopo com perda intencional dos dados legados de IA.
    # Para retorno com dados, use o backup obrigatório da baseline 1.9.0-R1.
    raise RuntimeError("Downgrade da F0 exige restauração do backup 1.9.0-R1")
