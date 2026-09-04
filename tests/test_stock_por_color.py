"""Stock por color: cada color se agota por su cuenta.

Antes los colores eran decorativos para comprar: la clienta tocaba el
círculo azul y el pedido llegaba diciendo "Bolso Totto" sin el color. Y el
stock era del producto, así que se podían vender tres azules teniendo dos.

Dos reglas que estos tests fijan:

1. Si el producto viene en colores, elegir uno es OBLIGATORIO. Sin eso la
   dueña recibe el pedido sin saber cuál llevar.
2. La disponibilidad se mira del color, no del total. Un producto puede
   tener 10 en el catálogo y 0 del azul.

`products.stock` se conserva como la suma de los colores —lo usan el
catálogo, `in_stock` y los reportes— y lo recalcula solo el backend.
"""

import pytest

from app.models.color import Color
from app.models.order import PaymentMethod
from app.repositories import cart_repository
from app.services import cart_service, order_service, product_service

# 6 grises y 4 negros: 10 en total, pero repartidos.
COLORES = {Color.GRIS: 6, Color.NEGRO: 4}


@pytest.fixture
def bolso(crear_producto):
    return crear_producto(colores=COLORES)


@pytest.fixture
def bolso_sin_colores(crear_producto):
    return crear_producto(stock=10)


# --- El total es la suma --------------------------------------------------


def test_el_stock_del_producto_es_la_suma_de_sus_colores(bolso):
    assert bolso.stock == 10
    assert {c.color: c.stock for c in bolso.colors} == COLORES


def test_la_ficha_muestra_el_stock_de_cada_color(client, bolso):
    """Sin esto la clienta ve "quedan 10" y pide un color agotado."""
    ficha = client.get(f"/api/v1/products/{bolso.id}").json()

    por_color = {c["value"]: c["stock"] for c in ficha["colors"]}
    assert por_color == {"GRIS": 6, "NEGRO": 4}


# --- Elegir color es obligatorio ------------------------------------------


def test_sin_color_no_se_puede_agregar_al_carrito(db, usuario, bolso):
    with pytest.raises(cart_service.ColorRequiredError):
        cart_service.add_to_cart(db, user_id=usuario.id, product_id=bolso.id, quantity=1)


def test_un_color_que_el_producto_no_tiene_se_rechaza(db, usuario, bolso):
    with pytest.raises(cart_service.ColorNotAvailableError):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.ROJO
        )


def test_un_producto_sin_colores_no_acepta_color(db, usuario, bolso_sin_colores):
    """Mandar un color donde no los hay sería inventarlo."""
    with pytest.raises(cart_service.ColorNotAvailableError):
        cart_service.add_to_cart(
            db,
            user_id=usuario.id,
            product_id=bolso_sin_colores.id,
            quantity=1,
            color=Color.GRIS,
        )


def test_un_producto_sin_colores_se_agrega_sin_color(db, usuario, bolso_sin_colores):
    item = cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso_sin_colores.id, quantity=2
    )

    assert item.color is None


# --- La disponibilidad es del color ---------------------------------------


def test_no_se_puede_pedir_mas_de_lo_que_hay_de_ese_color(db, usuario, bolso):
    """Hay 10 en total, pero solo 4 negros. Pedir 5 negros no se puede
    aunque el total alcance de sobra."""
    with pytest.raises(cart_service.InsufficientStockError):
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=bolso.id, quantity=5, color=Color.NEGRO
        )


def test_lo_que_hay_de_ese_color_si_se_puede(db, usuario, bolso):
    item = cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=4, color=Color.NEGRO
    )

    assert item.quantity == 4


def test_el_mensaje_dice_de_que_color_falta(db, usuario, bolso):
    with pytest.raises(cart_service.InsufficientStockError) as excinfo:
        cart_service.add_to_cart(
            db, user_id=usuario.id, product_id=bolso.id, quantity=9, color=Color.GRIS
        )

    assert "negro" in str(excinfo.value).lower() or "gris" in str(excinfo.value).lower()


# --- Dos colores, dos lineas ----------------------------------------------


def test_el_mismo_bolso_en_dos_colores_son_dos_lineas(db, usuario, bolso):
    """Se agotan por separado y se entregan por separado: sumarlos en una
    sola línea perdería cuál es cuál."""
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.NEGRO
    )

    lineas = cart_repository.list_by_user(db, usuario.id)
    assert len(lineas) == 2
    assert {linea.color for linea in lineas} == {Color.GRIS, Color.NEGRO}


def test_agregar_el_mismo_color_dos_veces_suma_en_la_misma_linea(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=1, color=Color.GRIS
    )
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=2, color=Color.GRIS
    )

    lineas = cart_repository.list_by_user(db, usuario.id)
    assert len(lineas) == 1
    assert lineas[0].quantity == 3


# --- El pedido guarda el color y descuenta del color correcto -------------


def test_el_pedido_recuerda_que_color_pidio(db, usuario, bolso):
    """Es lo que la dueña necesita para saber cuál llevar."""
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=2, color=Color.NEGRO
    )

    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    assert [item.color for item in pedido.items] == [Color.NEGRO]


def test_la_reserva_sale_del_color_pedido(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=2, color=Color.NEGRO
    )

    order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    db.refresh(bolso)
    por_color = {c.color: c.stock for c in bolso.colors}
    assert por_color == {Color.GRIS: 6, Color.NEGRO: 2}
    # Y el total se mantiene cuadrado con el detalle.
    assert bolso.stock == 8


def test_cancelar_devuelve_al_color_correcto(db, usuario, bolso):
    cart_service.add_to_cart(
        db, user_id=usuario.id, product_id=bolso.id, quantity=3, color=Color.GRIS
    )
    pedido = order_service.create_order_from_cart(
        db, user_id=usuario.id, payment_method=PaymentMethod.CASH
    )

    order_service.cancel_order(db, pedido.id, usuario.id)

    db.refresh(bolso)
    assert {c.color: c.stock for c in bolso.colors} == COLORES
    assert bolso.stock == 10


# --- Cargar el stock desde el panel ---------------------------------------


def test_el_admin_carga_el_stock_de_un_color(admin_client, bolso):
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors/NEGRO/stock", json={"stock": 12}
    )

    assert respuesta.status_code == 200
    por_color = {c["value"]: c["stock"] for c in respuesta.json()["colors"]}
    assert por_color["NEGRO"] == 12
    # El total se recalcula solo: 6 grises + 12 negros.
    assert respuesta.json()["stock"] == 18


def test_dejar_un_color_en_cero_no_agota_el_producto(admin_client, bolso):
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors/NEGRO/stock", json={"stock": 0}
    )

    assert respuesta.json()["stock"] == 6
    assert respuesta.json()["in_stock"] is True


def test_sin_stock_en_ningun_color_el_producto_queda_agotado(admin_client, bolso):
    admin_client.put(f"/api/v1/products/{bolso.id}/colors/GRIS/stock", json={"stock": 0})
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors/NEGRO/stock", json={"stock": 0}
    )

    assert respuesta.json()["stock"] == 0
    assert respuesta.json()["in_stock"] is False


def test_no_se_puede_cargar_stock_de_un_color_que_no_ofrece(admin_client, bolso):
    respuesta = admin_client.put(
        f"/api/v1/products/{bolso.id}/colors/ROJO/stock", json={"stock": 5}
    )

    assert respuesta.status_code == 400


def test_cargar_stock_exige_admin(client, bolso):
    respuesta = client.put(
        f"/api/v1/products/{bolso.id}/colors/GRIS/stock", json={"stock": 5}
    )

    assert respuesta.status_code == 401


# --- Quitar un color no se lleva el stock de los demas --------------------


def test_quitar_un_color_recalcula_el_total(admin_client, bolso, db):
    admin_client.put(
        f"/api/v1/products/{bolso.id}/colors", json={"colors": ["GRIS"]}
    )

    db.refresh(bolso)
    product_service.get_product_or_raise(db, bolso.id)
    assert {c.color: c.stock for c in bolso.colors} == {Color.GRIS: 6}
