"""Pago contra entrega: efectivo y Nequi.

La diferencia de fondo con Wompi es CUÁNDO entra la plata. Con la
pasarela se cobra antes de entregar; acá se cobra en la puerta, así que
el pedido pasa un buen rato existiendo, con stock reservado y sin estar
pagado. Eso obliga a tres cosas que estos tests fijan:

1. Un estado propio (CONFIRMED) que el barrido de pedidos viejos no toque.
2. Confirmación de las DOS partes: la dueña marca que entregó y le
   pagaron, la clienta confirma que recibió y pagó.
3. Que los reportes no cuenten como ingreso un pedido que va en camino.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.order import OrderStatus, PaymentMethod
from app.repositories import cart_repository, sales_repository
from app.services import order_service


@pytest.fixture
def hacer_pedido(db, usuario, crear_producto):
    def _hacer(metodo: PaymentMethod, *, stock: int = 10, cantidad: int = 2):
        producto = crear_producto(stock=stock)
        cart_repository.create(
            db, user_id=usuario.id, product_id=producto.id, quantity=cantidad
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=metodo
        )
        return pedido, producto

    return _hacer


# --- El pedido nace distinto segun el metodo -----------------------------


@pytest.mark.parametrize("metodo", [PaymentMethod.CASH, PaymentMethod.NEQUI])
def test_contra_entrega_nace_confirmado_y_sin_pagar(hacer_pedido, metodo):
    pedido, _ = hacer_pedido(metodo)

    assert pedido.status == OrderStatus.CONFIRMED
    assert pedido.payment_method == metodo
    # Nadie ha pagado todavía: la plata llega en la puerta.
    assert pedido.paid_at is None


def test_wompi_sigue_naciendo_pendiente(hacer_pedido):
    pedido, _ = hacer_pedido(PaymentMethod.WOMPI)

    assert pedido.status == OrderStatus.PENDING
    assert pedido.paid_at is None


def test_el_contra_entrega_reserva_stock_igual(hacer_pedido, db):
    _, producto = hacer_pedido(PaymentMethod.CASH, stock=10, cantidad=2)

    db.refresh(producto)
    assert producto.stock == 8


# --- Lo que motivo el estado aparte --------------------------------------


def test_un_contra_entrega_no_se_cancela_solo_a_las_2_horas(hacer_pedido, db):
    """PENDING se barre a las 2 h porque es un carrito abandonado en la
    pasarela. Un contra entrega vive días hasta que la dueña reparta: si
    compartieran estado, el barrido le cancelaría la compra a la clienta
    y le devolvería el stock a la tienda."""
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    pedido.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db.commit()

    order_service.expire_stale_orders(db)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.CONFIRMED


def test_un_wompi_abandonado_si_se_barre(hacer_pedido, db):
    pedido, _ = hacer_pedido(PaymentMethod.WOMPI)
    pedido.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
    db.commit()

    order_service.expire_stale_orders(db)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.EXPIRED


# --- Las dos confirmaciones ----------------------------------------------


def test_la_duena_confirma_entrega_y_pago(hacer_pedido, db):
    """Primera mitad del acuerdo: quien lleva el producto declara que lo
    entregó y que le pagaron. Ahí es cuando la plata existe."""
    pedido, _ = hacer_pedido(PaymentMethod.CASH)

    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.AWAITING_CONFIRMATION)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.AWAITING_CONFIRMATION
    assert pedido.delivered_at is not None
    assert pedido.paid_at is not None


def test_la_clienta_confirma_que_recibio_y_pago(hacer_pedido, db, usuario):
    """Segunda mitad: hasta que ella no confirma, el pedido no se cierra."""
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.AWAITING_CONFIRMATION)

    order_service.confirm_delivery(db, pedido.id, usuario.id)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.DELIVERED
    assert pedido.delivery_confirmed_at is not None


def test_a_los_5_dias_se_confirma_solo(hacer_pedido, db):
    """El acuerdo de los 5 días: si la clienta nunca confirma, el pedido
    no puede quedar abierto para siempre."""
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.AWAITING_CONFIRMATION)

    dias = order_service.DELIVERY_AUTO_CONFIRM_DAYS
    pedido.delivered_at = datetime.now(timezone.utc) - timedelta(days=dias, hours=1)
    db.commit()

    order_service.auto_confirm_stale_deliveries(db)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.DELIVERED


def test_antes_de_los_5_dias_no_se_confirma_solo(hacer_pedido, db):
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.AWAITING_CONFIRMATION)

    pedido.delivered_at = datetime.now(timezone.utc) - timedelta(days=2)
    db.commit()

    order_service.auto_confirm_stale_deliveries(db)

    db.refresh(pedido)
    assert pedido.status == OrderStatus.AWAITING_CONFIRMATION


# --- La plata en los reportes --------------------------------------------


def test_un_pedido_en_camino_no_es_ingreso_todavia(hacer_pedido, db):
    """Lo más importante de todo esto: si el reporte contara por estado,
    la dueña vería como ingreso una plata que nadie le ha dado."""
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)

    assert sales_repository.get_total_sales(db)["revenue"] == 0


def test_cuando_la_duena_confirma_el_pago_si_entra_al_reporte(hacer_pedido, db):
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.AWAITING_CONFIRMATION)

    assert sales_repository.get_total_sales(db)["revenue"] > 0


# --- No mezclar los dos mundos -------------------------------------------


@pytest.mark.parametrize("metodo", [PaymentMethod.CASH, PaymentMethod.NEQUI])
def test_un_contra_entrega_no_se_puede_pagar_por_la_pasarela(
    hacer_pedido, db, usuario, metodo
):
    """Sin esta guarda se le abriría el widget de Wompi y la clienta
    terminaría pagando dos veces: una en la app y otra en la puerta."""
    pedido, _ = hacer_pedido(metodo)

    with pytest.raises(order_service.InvalidStatusTransitionError):
        order_service.get_checkout_payload_for_order(db, pedido.id, usuario.id)


def test_el_checkout_de_contra_entrega_no_trae_datos_del_widget(hacer_pedido):
    pedido, _ = hacer_pedido(PaymentMethod.NEQUI)

    payload = order_service.build_checkout_payload(pedido)

    assert payload["payment_method"] == PaymentMethod.NEQUI
    assert payload["public_key"] is None
    assert payload["signature"] is None
    # El monto y la referencia sí van: la clienta necesita saber cuánto
    # pagar, y la dueña con qué referencia cuadrar el Nequi.
    assert payload["amount_in_cents"] > 0
    assert payload["reference"]


# --- Cancelacion ----------------------------------------------------------


def test_se_puede_cancelar_antes_de_que_salga_y_vuelve_el_stock(
    hacer_pedido, db, usuario
):
    pedido, producto = hacer_pedido(PaymentMethod.CASH, stock=10, cantidad=2)

    order_service.cancel_order(db, pedido.id, usuario.id)

    db.refresh(pedido)
    db.refresh(producto)
    assert pedido.status == OrderStatus.CANCELLED
    assert producto.stock == 10


def test_ya_no_se_puede_cancelar_si_la_duena_salio_a_entregar(
    hacer_pedido, db, usuario
):
    pedido, _ = hacer_pedido(PaymentMethod.CASH)
    order_service.update_delivery_status(db, pedido.id, OrderStatus.IN_TRANSIT)

    with pytest.raises(order_service.InvalidStatusTransitionError):
        order_service.cancel_order(db, pedido.id, usuario.id)
