"""stock por color, y el color en carrito y pedidos

Hasta acá los colores eran decorativos para comprar: la clienta tocaba el
círculo azul, veía las fotos del azul, y el pedido que le llegaba a la
dueña decía "Bolso Totto" sin decir de qué color. Faltaba guardarlo.

Y una vez guardado, el stock tenía que separarse: de nada sirve saber que
pidió el azul si el sistema deja aceptar tres azules cuando quedan dos.

CÓMO QUEDA EL STOCK
  - `product_colors.stock` es el stock de cada color.
  - `products.stock` se conserva y pasa a ser la SUMA de los colores.
    No es un segundo lugar donde editarlo: lo recalcula solo quien mueve
    el stock de un color (product_color_repository). Se mantiene para que
    el catálogo, `in_stock` y los reportes sigan funcionando igual.
  - Un producto SIN colores sigue usando `products.stock` directo.

MIGRACIÓN DE DATOS, y esto hay que revisarlo después de desplegar:
  - Producto con UN color: se le pasa todo el stock a ese color. No hay
    ambigüedad posible.
  - Producto con VARIOS colores: no hay forma de saber cuántas unidades
    son de cada uno, así que quedan todos en 0 y el producto aparece
    AGOTADO. Es a propósito: repartir el total a ojo habría dejado un
    número que parece real y no lo es, y la dueña vendería algo que no
    tiene. Agotado se ve, y obliga a cargar las cantidades de verdad.

Revision ID: a4d71e6b0c38
Revises: f9c3e08a71b2
Create Date: 2026-09-03 09:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4d71e6b0c38'
down_revision: str | Sequence[str] | None = 'f9c3e08a71b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALORES = (
    "NEGRO", "GRIS", "BLANCO", "BEIGE", "CAFE", "AZUL", "AZUL_CLARO",
    "VERDE", "VERDE_MILITAR", "ROJO", "VINOTINTO", "ROSADO", "MORADO",
    "AMARILLO", "NARANJA", "ESTAMPADO",
)


def _tipo_color(bind):
    """El tipo enum como REFERENCIA, sin volver a crearlo.

    El tipo `color` ya existe desde la migración f9c3e08a71b2. Sin
    create_type=False, add_column volvería a emitir un CREATE TYPE y esto
    reventaría con "type color already exists" — que es exactamente el
    error que rompió aquel despliegue.
    """
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects import postgresql

        return postgresql.ENUM(*_VALORES, name="color", create_type=False)
    return sa.Enum(*_VALORES, name="color")


def upgrade() -> None:
    bind = op.get_bind()
    tipo_color = _tipo_color(bind)

    op.add_column(
        "product_colors",
        sa.Column("stock", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("cart_items", sa.Column("color", tipo_color, nullable=True))
    op.add_column("order_items", sa.Column("color", tipo_color, nullable=True))

    # Un solo color: el stock del producto es, sin ambigüedad, el de ese
    # color.
    op.execute(
        """
        UPDATE product_colors AS pc
        SET stock = p.stock
        FROM products AS p
        WHERE pc.product_id = p.id
          AND (SELECT COUNT(*) FROM product_colors x WHERE x.product_id = p.id) = 1
        """
    )

    # Varios colores: quedan en 0 (el server_default) y el producto pasa a
    # AGOTADO, para que la dueña cargue las cantidades reales.
    op.execute(
        """
        UPDATE products AS p
        SET stock = 0, in_stock = false
        WHERE (SELECT COUNT(*) FROM product_colors x WHERE x.product_id = p.id) > 1
        """
    )


def downgrade() -> None:
    # El total vuelve a vivir solo en products.stock. Para no dejar la
    # tienda en cero, se le devuelve la suma de sus colores.
    op.execute(
        """
        UPDATE products AS p
        SET stock = COALESCE(
            (SELECT SUM(x.stock) FROM product_colors x WHERE x.product_id = p.id),
            p.stock
        )
        """
    )
    op.execute("UPDATE products SET in_stock = (stock > 0)")

    op.drop_column("order_items", "color")
    op.drop_column("cart_items", "color")
    op.drop_column("product_colors", "stock")
