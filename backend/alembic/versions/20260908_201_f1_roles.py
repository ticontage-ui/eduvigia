"""Organiza perfis de Secretaria, Guarda e Escola para a F1.

Revision ID: 20260908_201_f1
Revises: 20260908_200_f0
"""
from typing import Sequence, Union
from alembic import op

revision: str = "20260908_201_f1"
down_revision: Union[str, Sequence[str], None] = "20260908_200_f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.user_accounts') IS NOT NULL THEN
                UPDATE user_accounts
                SET role = CASE
                    WHEN role = 'ADMIN' THEN 'ADMIN_SECRETARIA'
                    WHEN role IN ('SUPERVISOR', 'GESTAO') THEN 'GESTOR_SECRETARIA'
                    WHEN role = 'DESPACHANTE' THEN 'DESPACHANTE_GUARDA'
                    WHEN role = 'ESCOLA' THEN 'GESTOR_ESCOLA'
                    WHEN role = 'OPERADOR' AND school_id IS NOT NULL THEN 'OPERADOR_ESCOLA'
                    WHEN role = 'OPERADOR' AND school_id IS NULL THEN 'OPERADOR_GUARDA'
                    ELSE role
                END
                WHERE role IN ('ADMIN','SUPERVISOR','GESTAO','DESPACHANTE','ESCOLA','OPERADOR');

                UPDATE user_accounts
                SET school_id = NULL
                WHERE role IN (
                    'ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA',
                    'OPERADOR_GUARDA','DESPACHANTE_GUARDA'
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.user_accounts') IS NOT NULL THEN
                UPDATE user_accounts
                SET role = CASE
                    WHEN role = 'ADMIN_SECRETARIA' THEN 'ADMIN'
                    WHEN role = 'GESTOR_SECRETARIA' THEN 'SUPERVISOR'
                    WHEN role = 'SUPERVISOR_GUARDA' THEN 'SUPERVISOR'
                    WHEN role = 'OPERADOR_GUARDA' THEN 'OPERADOR'
                    WHEN role = 'DESPACHANTE_GUARDA' THEN 'DESPACHANTE'
                    WHEN role = 'GESTOR_ESCOLA' THEN 'ESCOLA'
                    WHEN role = 'OPERADOR_ESCOLA' THEN 'OPERADOR'
                    ELSE role
                END
                WHERE role IN (
                    'ADMIN_SECRETARIA','GESTOR_SECRETARIA','SUPERVISOR_GUARDA',
                    'OPERADOR_GUARDA','DESPACHANTE_GUARDA','GESTOR_ESCOLA','OPERADOR_ESCOLA'
                );
            END IF;
        END $$;
        """
    )
