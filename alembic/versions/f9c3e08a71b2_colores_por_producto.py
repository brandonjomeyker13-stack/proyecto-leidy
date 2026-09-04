"""colores por producto, y fotos por color

El mismo bolso en gris y en negro pasa a ser UN producto con dos colores,
no dos productos. Antes `products.color` era texto libre: un producto
solo podía tener un color, y el mismo tono se escribía distinto cada vez
("gris", "Gris", "gris oscuro"), así que no servía ni para filtrar.

Las fotos ahora pueden pertenecer a un color (`product_images.color`).
En NULL siguen siendo generales y se muestran con cualquier color — el
detalle del cierre o de la etiqueta no cambia entre variantes.

MIGRACIÓN DE DATOS: los colores que ya existen se pasan a la tabla nueva
adivinándolos del texto (ver _ALIAS). Lo que no se pueda mapear NO se
inventa: ese producto queda sin colores y la dueña se los marca a mano en
el panel. Preferimos un dato faltante y visible a un dato inventado que
parezca real.

La llave única de las fotos cambia de (product_id, position) a
(product_id, color, position), porque cada color tiene su propia galería
numerada desde 0: sin el color en la llave, la primera foto del negro
chocaría con la primera del gris.

Revision ID: f9c3e08a71b2
Revises: e5b147fa2d09
Create Date: 2026-09-02 10:15:00.000000

"""
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f9c3e08a71b2'
down_revision: str | Sequence[str] | None = 'e5b147fa2d09'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALORES = (
    "NEGRO", "GRIS", "BLANCO", "BEIGE", "CAFE", "AZUL", "AZUL_CLARO",
    "VERDE", "VERDE_MILITAR", "ROJO", "VINOTINTO", "ROSADO", "MORADO",
    "AMARILLO", "NARANJA", "ESTAMPADO",
)

_COLOR = sa.Enum(*_VALORES, name="color")

# Cómo se escribe en la vida real -> qué valor del catálogo es. Se compara
# sin tildes y en minúsculas, así que "Café" y "cafe" caen en la misma
# entrada.
_ALIAS = {
    "negro": "NEGRO",
    "gris": "GRIS",
    "gris oscuro": "GRIS",
    "gris claro": "GRIS",
    "plateado": "GRIS",
    "blanco": "BLANCO",
    "beige": "BEIGE",
    "crema": "BEIGE",
    "cafe": "CAFE",
    "marron": "CAFE",
    "azul": "AZUL",
    "azul oscuro": "AZUL",
    "azul claro": "AZUL_CLARO",
    "celeste": "AZUL_CLARO",
    "verde": "VERDE",
    "verde militar": "VERDE_MILITAR",
    "militar": "VERDE_MILITAR",
    "rojo": "ROJO",
    "vinotinto": "VINOTINTO",
    "vino tinto": "VINOTINTO",
    "vino": "VINOTINTO",
    "rosado": "ROSADO",
    "rosa": "ROSADO",
    "morado": "MORADO",
    "violeta": "MORADO",
    "lila": "MORADO",
    "amarillo": "AMARILLO",
    "naranja": "NARANJA",
    "naranjado": "NARANJA",
    "estampado": "ESTAMPADO",
    "multicolor": "ESTAMPADO",
}


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(
        letra
        for letra in unicodedata.normalize("NFD", texto)
        if unicodedata.category(letra) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def upgrade() -> None:
    bind = op.get_bind()
    _COLOR.create(bind, checkfirst=True)

    op.create_table(
        "product_colors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("color", _COLOR, nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id", "color", name="uq_product_colors_product_color"
        ),
    )
    op.create_index(
        op.f("ix_product_colors_product_id"), "product_colors", ["product_id"]
    )

    # Pasar los colores que ya existían, antes de borrar la columna.
    filas = bind.execute(
        sa.text("SELECT id, color FROM products WHERE color IS NOT NULL")
    ).fetchall()
    for product_id, texto in filas:
        valor = _ALIAS.get(_normalizar(texto or ""))
        if valor is None:
            # No se inventa: queda sin color y se marca a mano.
            continue
        bind.execute(
            sa.text(
                "INSERT INTO product_colors (product_id, color) "
                "VALUES (:product_id, :color)"
            ),
            {"product_id": product_id, "color": valor},
        )

    op.drop_column("products", "color")

    op.add_column("product_images", sa.Column("color", _COLOR, nullable=True))
    op.create_index(
        op.f("ix_product_images_color"), "product_images", ["color"]
    )
    op.drop_constraint(
        "uq_product_images_product_position", "product_images", type_="unique"
    )
    op.create_unique_constraint(
        "uq_product_images_product_color_position",
        "product_images",
        ["product_id", "color", "position"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_product_images_product_color_position", "product_images", type_="unique"
    )
    # Volver a (product_id, position) solo funciona si no hay dos fotos
    # del mismo producto compartiendo posición en colores distintos, que
    # es justo lo que esta migración habilitó. Se borran las de color
    # antes de restaurar la llave: son las que no existían antes.
    op.execute("DELETE FROM product_images WHERE color IS NOT NULL")
    op.create_unique_constraint(
        "uq_product_images_product_position",
        "product_images",
        ["product_id", "position"],
    )
    op.drop_index(op.f("ix_product_images_color"), table_name="product_images")
    op.drop_column("product_images", "color")

    # La columna vuelve con un valor de relleno: era NOT NULL y los
    # productos que ya existen tienen que traer algo.
    op.add_column(
        "products",
        sa.Column("color", sa.String(length=50), nullable=False, server_default="Sin color"),
    )
    op.alter_column("products", "color", server_default=None)

    op.drop_index(op.f("ix_product_colors_product_id"), table_name="product_colors")
    op.drop_table("product_colors")
    _COLOR.drop(op.get_bind(), checkfirst=True)
