"""quien cerro el pedido

Sin esta columna, un pedido que la clienta confirmó y uno que la tienda
cerró sola quedaban IDÉNTICOS en la base: los dos en DELIVERED con una
fecha en `delivery_confirmed_at`. Y no son lo mismo — uno es un acuerdo
de las dos partes y el otro es la declaración de una sola.

Queda en NULL mientras el pedido siga abierto. Los pedidos que ya estén
en DELIVERED también quedan en NULL: no hay forma de saber quién los
cerró, y rellenarlos con una suposición sería peor que dejar el dato
vacío, porque parecería un registro real.

Revision ID: e5b147fa2d09
Revises: d3a86b52c104
Create Date: 2026-09-01 16:05:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5b147fa2d09'
down_revision: str | Sequence[str] | None = 'd3a86b52c104'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLOSED_BY = sa.Enum("CUSTOMER", "SELLER", name="closedby")


def upgrade() -> None:
    _CLOSED_BY.create(op.get_bind(), checkfirst=True)
    op.add_column("orders", sa.Column("closed_by", _CLOSED_BY, nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "closed_by")
    _CLOSED_BY.drop(op.get_bind(), checkfirst=True)
