"""CRUD de categorías.

Antes solo se podían crear y listar: una categoría mal escrita se quedaba
así para siempre, y le salía a las clientas en el filtro del catálogo.

Lo delicado es el borrado. `Product.category_id` es NOT NULL, así que
todo producto tiene que pertenecer a una categoría: borrar una que tenga
productos los dejaría huérfanos. Por eso se niega y dice cuántos son.
"""

import pytest

from app.models.category import Category


@pytest.fixture
def crear_categoria(db):
    def _crear(nombre: str) -> Category:
        categoria = Category(name=nombre)
        db.add(categoria)
        db.commit()
        db.refresh(categoria)
        return categoria

    return _crear


# --- Leer una sola --------------------------------------------------------


def test_se_puede_consultar_una_categoria(client, crear_categoria):
    categoria = crear_categoria("Riñoneras")

    respuesta = client.get(f"/api/v1/categories/{categoria.id}")

    assert respuesta.status_code == 200
    assert respuesta.json()["name"] == "Riñoneras"


def test_una_categoria_que_no_existe_da_404(client):
    assert client.get("/api/v1/categories/9999").status_code == 404


# --- Renombrar ------------------------------------------------------------


def test_se_puede_corregir_el_nombre(admin_client, crear_categoria):
    """El caso real: quedó mal escrita y hay que arreglarla."""
    categoria = crear_categoria("Morrrales")

    respuesta = admin_client.patch(
        f"/api/v1/categories/{categoria.id}", json={"name": "Morrales"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["name"] == "Morrales"


def test_renombrar_no_mueve_los_productos(admin_client, crear_producto, db):
    producto = crear_producto()
    categoria_id = producto.category_id

    admin_client.patch(f"/api/v1/categories/{categoria_id}", json={"name": "Otro nombre"})

    db.refresh(producto)
    assert producto.category_id == categoria_id


def test_no_se_puede_pisar_el_nombre_de_otra(admin_client, crear_categoria):
    crear_categoria("Morrales")
    otra = crear_categoria("Riñoneras")

    respuesta = admin_client.patch(
        f"/api/v1/categories/{otra.id}", json={"name": "Morrales"}
    )

    assert respuesta.status_code == 409


def test_guardar_sin_cambiar_el_nombre_no_falla(admin_client, crear_categoria):
    """Que ya exista una categoría con ese nombre solo es problema si es
    OTRA. El admin puede estar guardando sin haber cambiado nada."""
    categoria = crear_categoria("Morrales")

    respuesta = admin_client.patch(
        f"/api/v1/categories/{categoria.id}", json={"name": "Morrales"}
    )

    assert respuesta.status_code == 200


def test_renombrar_exige_admin(client, crear_categoria):
    categoria = crear_categoria("Morrales")

    respuesta = client.patch(
        f"/api/v1/categories/{categoria.id}", json={"name": "Otro"}
    )

    assert respuesta.status_code == 401


# --- Borrar ---------------------------------------------------------------


def test_se_puede_borrar_una_categoria_vacia(admin_client, crear_categoria):
    categoria = crear_categoria("Se creó por error")

    respuesta = admin_client.delete(f"/api/v1/categories/{categoria.id}")

    assert respuesta.status_code == 204
    assert admin_client.get(f"/api/v1/categories/{categoria.id}").status_code == 404


def test_no_se_puede_borrar_una_con_productos(admin_client, crear_producto):
    """Sin esta guarda, los productos quedarían apuntando a una categoría
    que ya no existe — y category_id es NOT NULL."""
    producto = crear_producto()

    respuesta = admin_client.delete(f"/api/v1/categories/{producto.category_id}")

    assert respuesta.status_code == 409
    # El mensaje tiene que decir cuántos son, si no el admin no sabe qué
    # tiene que mover antes de poder borrarla.
    assert "1 producto" in respuesta.json()["detail"]


def test_el_producto_sobrevive_al_intento_de_borrado(
    admin_client, crear_producto, db
):
    producto = crear_producto()

    admin_client.delete(f"/api/v1/categories/{producto.category_id}")

    db.refresh(producto)
    assert producto.category_id is not None


def test_borrar_exige_admin(client, crear_categoria):
    categoria = crear_categoria("Morrales")

    assert client.delete(f"/api/v1/categories/{categoria.id}").status_code == 401


def test_borrar_una_que_no_existe_da_404(admin_client):
    assert admin_client.delete("/api/v1/categories/9999").status_code == 404
