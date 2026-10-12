"""Cuatro fallas encontradas en una revisión del sistema de colores.

Ninguna se veía en los tests que ya existían: los cuatro caminos eran
válidos según las reglas escritas hasta ese momento, y solo se rompían al
combinar cosas (colores + edición del producto, contra entrega + carrito,
contra entrega + stock reservado). Quedan acá para que no vuelvan.
"""

import pytest

from app.models.color import Color
from app.models.order import OrderStatus, PaymentMethod
from app.services import cart_service, order_service, product_service

COLORES = {Color.GRIS: 6, Color.NEGRO: 4}


@pytest.fixture
def bolso(crear_producto):
    return crear_producto(colores=COLORES)


# --- 1. El total no se puede desincronizar del detalle --------------------


def test_no_se_puede_editar_el_stock_de_un_producto_con_colores(admin_client, bolso):
    """`products.stock` es la suma de los colores y la calcula el backend.

    Editarlo a mano lo desincronizaba en silencio: el catálogo mostraba
    999 disponibles y al elegir cualquier color saltaba "no hay stock".
    """
    respuesta = admin_client.put(f"/api/v1/products/{bolso.id}", json={"stock": 999})

    assert respuesta.status_code == 400
    assert "por color" in respuesta.json()["detail"]


def test_el_total_sigue_cuadrando_despues_del_intento(admin_client, bolso, db):
    admin_client.put(f"/api/v1/products/{bolso.id}", json={"stock": 999})

    db.refresh(bolso)
    assert bolso.stock == sum(c.stock for c in bolso.colors) == 10


def test_un_producto_sin_colores_si_deja_editar_el_stock(admin_client, crear_producto):
    """Sin colores el stock vive en el producto: ahí sí es el lugar."""
    producto = crear_producto(stock=5)

    respuesta = admin_client.put(f"/api/v1/products/{producto.id}", json={"stock": 20})

    assert respuesta.status_code == 200
    assert respuesta.json()["stock"] == 20


# --- 2. El carrito se limpia al comprar contra entrega --------------------


def test_el_carrito_se_limpia_tras_un_contra_entrega(db, usuario, bolso):
    """La compra queda cerrada al confirmar: no hay pasarela que esperar.

    Si el carrito quedaba lleno, la clienta veía ahí los productos que
    acababa de comprar y podía volver a pedirlos sin darse cuenta.
    """
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )

    order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert cart_service.get_cart(db, usuario.id) == []


def test_con_wompi_el_carrito_se_conserva_hasta_que_paguen(db, usuario, bolso):
    """Acá sí tiene que quedarse: hasta que Wompi apruebe, la compra
    todavía se puede caer y la clienta tiene que poder reintentar."""
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )

    order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
    )

    assert len(cart_service.get_cart(db, usuario.id)) == 1


# --- 3. Quitar un color no borra su inventario en silencio ---------------


def test_no_se_puede_quitar_un_color_que_tiene_unidades(admin_client, bolso):
    """Quitar un color borra su fila, y con ella su stock.

    La dueña quitaba el negro un rato, lo volvía a poner, y aparecía en
    cero sin que nada se lo hubiera avisado.
    """
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors", json={"colors": ["GRIS"]}
    )

    assert respuesta.status_code == 409
    assert "negro" in respuesta.json()["detail"].lower()


def test_poniendolo_en_cero_si_se_puede_quitar(admin_client, bolso):
    """La salida: mirar el número antes de perderlo."""
    admin_client.put(f"/api/v1/products/{bolso.id}/colors/NEGRO/stock", json={"stock": 0})

    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors", json={"colors": ["GRIS"]}
    )

    assert respuesta.status_code == 200
    assert [c["value"] for c in respuesta.json()["colors"]] == ["GRIS"]


# --- 4. Nadie puede acaparar la tienda con pedidos que no expiran --------


def test_hay_un_tope_de_pedidos_contra_entrega_abiertos(db, usuario, crear_producto):
    """Un contra entrega reserva stock y NO expira, a diferencia de
    PENDING, que se barre a las 2 h. Sin tope, cualquiera que se registre
    podía dejar la tienda entera reservada con pedidos que nunca iba a
    recibir, y a la dueña le tocaba cancelarlos uno por uno.
    """
    producto = crear_producto(colores={Color.GRIS: 20})
    tope = order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS

    # Cantidades distintas para que la idempotencia no reuse el pedido:
    # un atacante variaría el carrito igual.
    for cantidad in range(1, tope + 1):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=producto.id,
            quantity=cantidad,
            color=Color.GRIS,
        )
        order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )

    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=producto.id, quantity=9, color=Color.GRIS
    )
    with pytest.raises(order_service.TooManyOpenOrdersError):
        order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )


def test_cancelar_uno_libera_el_cupo(db, usuario, crear_producto):
    producto = crear_producto(colores={Color.GRIS: 20})
    tope = order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS
    primero = None

    for cantidad in range(1, tope + 1):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=producto.id,
            quantity=cantidad,
            color=Color.GRIS,
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.CASH
        )
        primero = primero or pedido

    order_service.cancel_order(db, primero.id, usuario.id)

    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=producto.id, quantity=9, color=Color.GRIS
    )
    nuevo = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert nuevo.status == OrderStatus.CONFIRMED


def test_el_tope_no_aplica_a_wompi(db, usuario, crear_producto):
    """Un PENDING de Wompi se barre solo a las 2 h, así que no hace falta
    limitarlo: la tienda se recupera sin que nadie intervenga."""
    producto = crear_producto(stock=50)

    for cantidad in range(1, order_service.MAX_PEDIDOS_CONTRA_ENTREGA_ABIERTOS + 3):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=producto.id, quantity=cantidad
        )
        pedido = order_service.create_order_from_cart(
            db, user_id=usuario.id, payment_method=PaymentMethod.WOMPI
        )
        pedido.status = OrderStatus.PENDING
        db.commit()

    assert product_service.get_product_or_raise(db, producto.id) is not None
