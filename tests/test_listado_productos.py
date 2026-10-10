"""El catálogo no se corta en 100.

El panel y la tienda piden GET /products/ sin paginar. Con tope 100, el
producto 101 en adelante se guardaba y no salía: la consulta ordena por
id y se queda con los primeros.
"""

from app.services.product_service import MAX_PRODUCTS_LISTED


def test_el_listado_incluye_el_producto_101(client, crear_producto):
    for numero in range(1, 102):
        crear_producto(nombre=f"Bolso {numero:03d}")

    respuesta = client.get("/api/v1/products/")

    assert respuesta.status_code == 200
    nombres = {producto["name"] for producto in respuesta.json()}
    assert len(nombres) == 101
    assert "Bolso 101" in nombres


def test_sigue_pudiendo_pedirse_una_pagina_chica(client, crear_producto):
    for numero in range(1, 4):
        crear_producto(nombre=f"Bolso {numero}")

    respuesta = client.get("/api/v1/products/", params={"limit": 2})

    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 2


def test_pedir_mas_del_tope_se_rechaza(client):
    respuesta = client.get(
        "/api/v1/products/", params={"limit": MAX_PRODUCTS_LISTED + 1}
    )

    assert respuesta.status_code == 422
