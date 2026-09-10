"""Marca a estrutura funcional existente como baseline da v1.3.0.

Revision ID: 20260625_130
Revises:
"""
from typing import Sequence, Union

revision: str = "20260625_130"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A estrutura atual é criada de forma idempotente pelo startup legado.
    # Esta revisão estabelece o ponto inicial para migrações futuras.
    pass


def downgrade() -> None:
    pass
