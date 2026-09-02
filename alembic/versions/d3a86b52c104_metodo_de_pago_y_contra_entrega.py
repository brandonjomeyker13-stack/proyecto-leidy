"""metodo de pago y contra entrega

Tres formas de pago: WOMPI (se paga antes de entregar) y CASH/NEQUI (se
paga al recibir). Las dos últimas necesitan un estado propio, CONFIRMED:
el pedido está cerrado y el stock reservado, pero todavía nadie pagó.

No se reusó PENDING para eso porque PENDING se cancela solo a las 2 horas
(es un carrito abandonado en la pasarela). Un contra entrega vive días
hasta que la dueña salga a repartir, y compartiendo estado el barrido de
pedidos viejos le cancelaría la compra a la clienta y le devolvería el
stock a la tienda.

`paid_at` es la columna que ahora usan los reportes de /sales, en vez del
estado del pedido. Con Wompi daba igual (se paga antes de entregar), pero
un contra entrega en camino todavía no cobró: contarlo por estado le
mostraría a la dueña ingresos que no tiene en la mano.

OJO con el ALTER TYPE: agregar un valor a un enum de Postgres no puede
correr dentro de la misma transacción que después lo usa, de ahí el
autocommit_block.

Revision ID: d3a86b52c104
Revises: c7f2a91e3b45
Create Date: 2026-09-01 15:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd3a86b52c104'
down_revision: str | Sequence[str] | None = 'c7f2a91e3b45'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los estados que, antes de esta migración, significaban "ya se cobró".
# Se usan una sola vez, para rellenar paid_at de los pedidos que ya
# existían: sin esto, los reportes de ventas arrancarían en cero.
_ESTADOS_YA_COBRADOS = ("APPROVED", "IN_TRANSIT", "AWAITING_CONFIRMATION", "DELIVERED")

_PAYMENT_METHOD = sa.Enum("WOMPI", "CASH", "NEQUI", name="paymentmethod")


def upgrade() -> None:
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    if es_postgres:
        # En Postgres el estado es un tipo enum de verdad y hay que
        # agregarle el valor nuevo aparte. En SQLite (los tests) es un
        # VARCHAR y no hace falta nada.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'CONFIRMED'")

    _PAYMENT_METHOD.create(bind, checkfirst=True)

    # server_default WOMPI: los pedidos que ya existen son todos de la
    # pasarela, que era lo único que había.
    op.add_column(
        "orders",
        sa.Column("payment_method", _PAYMENT_METHOD, nullable=False, server_default="WOMPI"),
    )
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))

    # Rellenar paid_at con created_at para los pedidos que ya estaban
    # cobrados. Es una aproximación (el pago fue poco después de crearse
    # el pedido), pero los reportes agrupan por created_at de todos modos,
    # así que no mueve ninguna cifra de período.
    marcadores = ", ".join(f"'{estado}'" for estado in _ESTADOS_YA_COBRADOS)
    op.execute(
        f"UPDATE orders SET paid_at = created_at WHERE status IN ({marcadores})"
    )


def downgrade() -> None:
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "payment_method")
    _PAYMENT_METHOD.drop(op.get_bind(), checkfirst=True)
    # El valor CONFIRMED del enum de estados NO se quita: Postgres no
    # permite borrar un valor de un enum, habría que recrear el tipo
    # entero y reescribir la columna. Dejarlo ahí no molesta a nadie.
