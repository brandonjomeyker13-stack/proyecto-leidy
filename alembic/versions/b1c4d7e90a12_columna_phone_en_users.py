"""columna phone en users

La columna se agregó al modelo `User` en el commit c26ba25 pero nunca se
creó la migración, así que la base se quedó sin ella. El resultado es que
CUALQUIER consulta sobre `users` falla con `UndefinedColumn` — incluido
el login con Google, que consulta por `google_id` antes de nada.

Nullable a propósito: los usuarios que ya existen no tienen teléfono, y
el frontend se lo pide después de que se logueen.

Revision ID: b1c4d7e90a12
Revises: a2374800a354
Create Date: 2026-08-23 12:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c4d7e90a12'
down_revision: str | Sequence[str] | None = 'a2374800a354'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'phone')
