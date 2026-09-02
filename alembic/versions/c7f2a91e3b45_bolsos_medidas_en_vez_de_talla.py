"""bolsos: medidas, compartimientos y material en vez de talla

La tienda pasó de ropa deportiva a bolsos, y ahí la talla no significa
nada: un morral no es S/M/L, se describe por cuánto mide, cuántos
compartimientos tiene y de qué material es.

`size` era NOT NULL, así que al revertir hay que devolverla con un valor
para las filas que ya existan — de ahí el server_default en el downgrade,
que se quita enseguida para dejar la columna como estaba.

Las columnas nuevas son todas nullable a propósito: ya hay productos
cargados en la base y obligarlos a tener medidas rompería el catálogo
hasta que alguien los edite uno por uno.

Revision ID: c7f2a91e3b45
Revises: b1c4d7e90a12
Create Date: 2026-09-01 13:20:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7f2a91e3b45'
down_revision: str | Sequence[str] | None = 'b1c4d7e90a12'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('products', sa.Column('height_cm', sa.Numeric(5, 1), nullable=True))
    op.add_column('products', sa.Column('width_cm', sa.Numeric(5, 1), nullable=True))
    op.add_column('products', sa.Column('compartments', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('material', sa.String(length=100), nullable=True))
    op.drop_column('products', 'size')


def downgrade() -> None:
    # server_default temporal: sin él, volver a poner una columna NOT NULL
    # en una tabla con filas falla.
    op.add_column(
        'products',
        sa.Column('size', sa.String(length=20), nullable=False, server_default='UNICA'),
    )
    op.alter_column('products', 'size', server_default=None)
    op.drop_column('products', 'material')
    op.drop_column('products', 'compartments')
    op.drop_column('products', 'width_cm')
    op.drop_column('products', 'height_cm')
