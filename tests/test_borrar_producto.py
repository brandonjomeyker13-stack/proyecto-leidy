"""Por qué un producto no se deja borrar.

El mensaje importa tanto como la regla: antes se intentaba borrar y, si la
base se quejaba, se asumía que la causa eran ventas confirmadas. Con
contra entrega eso dejó de ser cierto — un pedido apenas CONFIRMED no
cobró nada y no expira nunca, pero bloquea igual. La dueña veía "tiene
ventas confirmadas" en un producto que nadie compró.
"""

import pytest

from app.models.order import OrderStatus, PaymentMethod
from app.repositories import cart_repository
from app.services import order_service, product_service


@pytest.fixture
def pedido_con_producto(db, usuario, crear_producto):
    def _hacer(estado: OrderStatus, metodo=PaymentMethod.CASH):
        producto = crear_producto(stock=10)
        cart_repository.create(
            db, user_id=usuario.id, product_id=producto.id, quantity=1
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=metodo
        )
        pedido.status = estado
        db.commit()
        return producto, pedido

    return _hacer


def test_un_producto_sin_pedidos_se_borra(db, crear_producto):
    producto = crear_producto()

    product_service.delete_product(db, producto.id)

    with pytest.raises(product_service.ProductNotFoundError):
        product_service.get_product_or_raise(db, producto.id)


@pytest.mark.parametrize(
    "estado",
    [
        OrderStatus.CONFIRMED,
        OrderStatus.APPROVED,
        OrderStatus.IN_TRANSIT,
        OrderStatus.AWAITING_CONFIRMATION,
        OrderStatus.DELIVERED,
    ],
)
def test_un_pedido_vivo_bloquea_el_borrado(db, pedido_con_producto, estado):
    producto, _ = pedido_con_producto(estado)

    with pytest.raises(product_service.ProductHasOrdersError):
        product_service.delete_product(db, producto.id)


def test_el_mensaje_dice_QUE_pedido_bloquea(db, pedido_con_producto):
    """Sin el número y el estado, la dueña no sabe qué cancelar."""
    producto, pedido = pedido_con_producto(OrderStatus.CONFIRMED)

    with pytest.raises(product_service.ProductHasOrdersError) as excinfo:
        product_service.delete_product(db, producto.id)

    mensaje = str(excinfo.value)
    assert f"#{pedido.id}" in mensaje
    # Y en palabras, no con el nombre interno del estado.
    assert "confirmado" in mensaje
    assert "CONFIRMED" not in mensaje


def test_un_contra_entrega_sin_pagar_no_se_llama_venta(db, pedido_con_producto):
    """El mensaje viejo decía "tiene ventas confirmadas" para un pedido que
    nadie pagó. Eso mandaba a buscar una venta que no existe."""
    producto, _ = pedido_con_producto(OrderStatus.CONFIRMED)

    with pytest.raises(product_service.ProductHasOrdersError) as excinfo:
        product_service.delete_product(db, producto.id)

    assert "ventas confirmadas" not in str(excinfo.value)


def test_cancelar_el_pedido_desbloquea_el_borrado(db, usuario, pedido_con_producto):
    """La salida para un pedido de prueba que quedó estorbando."""
    producto, pedido = pedido_con_producto(OrderStatus.CONFIRMED)

    order_service.cancel_order(db, pedido.id, usuario.id)
    product_service.delete_product(db, producto.id)

    with pytest.raises(product_service.ProductNotFoundError):
        product_service.get_product_or_raise(db, producto.id)


def test_un_pedido_abandonado_no_bloquea(db, pedido_con_producto):
    """Un carrito que nadie terminó de pagar no es motivo para conservar
    un producto: sus referencias se limpian solas al borrar."""
    producto, _ = pedido_con_producto(OrderStatus.EXPIRED)

    product_service.delete_product(db, producto.id)

    with pytest.raises(product_service.ProductNotFoundError):
        product_service.get_product_or_raise(db, producto.id)
