"""Colores de un producto, y fotos por color.

El mismo bolso en gris y en negro es UN producto con dos colores, no dos
productos: comparte nombre, precio, medidas y material. Lo que cambia son
las fotos, y por eso cada color tiene su propia galería — cuando la
clienta toca un círculo, ve ese color.

Antes `color` era una columna de texto libre: un producto solo podía
tener un color, y el mismo tono se escribía distinto cada vez ("gris",
"Gris", "gris oscuro"), así que no servía ni para filtrar.
"""

import io

import pytest

from app.api.v1 import products as products_api
from app.core.storage import UploadedImage
from app.models.color import Color
from app.services import product_service

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
MAX = product_service.MAX_PRODUCT_IMAGES

# Los productos de este archivo se manejan por colores, y nacen SIN
# unidades a propósito: acá se prueban los círculos y las fotos, no el
# stock (eso está en test_stock_por_color.py). Además, un color con
# unidades no se puede quitar — ver test_auditoria.py — y varios de estos
# tests quitan colores.
CON_COLORES = {Color.GRIS: 0, Color.NEGRO: 0}


@pytest.fixture(autouse=True)
def supabase_falso(monkeypatch):
    borrados: list[str] = []
    subidas: list[str] = []

    async def _subir(file, product_id: int) -> UploadedImage:
        await file.read()
        path = f"product-{product_id}-{len(subidas)}.png"
        subidas.append(path)
        return UploadedImage(
            url=f"https://supabase.test/storage/v1/object/public/product-images/{path}",
            path=path,
        )

    monkeypatch.setattr(products_api, "upload_product_image", _subir)
    monkeypatch.setattr(products_api, "delete_product_image_file", borrados.append)
    return borrados


def subir(client, product_id, cantidad=1, color=None):
    archivos = [
        ("files", (f"foto-{i}.png", io.BytesIO(PNG), "image/png"))
        for i in range(cantidad)
    ]
    url = f"/api/v1/products/{product_id}/images"
    if color is not None:
        url += f"?color={color.value}"
    return client.post(url, files=archivos)


# --- El catalogo ----------------------------------------------------------


def test_el_catalogo_trae_nombre_y_hex(client):
    """El frontend pinta los círculos con esto. Si tuviera que copiar la
    paleta a mano, las dos se irían separando."""
    respuesta = client.get("/api/v1/products/colors")

    assert respuesta.status_code == 200
    catalogo = respuesta.json()
    negro = next(c for c in catalogo if c["value"] == "NEGRO")
    assert negro["label"] == "Negro"
    assert negro["hex"].startswith("#")


def test_el_catalogo_no_choca_con_la_ruta_de_un_producto(client, crear_producto):
    """/colors se declara antes que /{product_id}. Si fuera al revés,
    FastAPI leería "colors" como id y devolvería 422."""
    producto = crear_producto(colores=CON_COLORES)

    assert client.get("/api/v1/products/colors").status_code == 200
    assert client.get(f"/api/v1/products/{producto.id}").status_code == 200


# --- Marcar los colores disponibles ---------------------------------------


def test_se_crea_un_producto_con_varios_colores(admin_client, categoria):
    respuesta = admin_client.post(
        "/api/v1/products/",
        json={
            "name": "Bolso Totto",
            "price": "89000.00",
            "stock": 5,
            "category_id": categoria.id,
            "colors": ["NEGRO", "AZUL", "VINOTINTO"],
        },
    )

    assert respuesta.status_code == 201
    colores = respuesta.json()["colors"]
    assert [c["value"] for c in colores] == ["NEGRO", "AZUL", "VINOTINTO"]
    # Cada uno viene listo para pintar el círculo.
    assert all(c["hex"].startswith("#") and c["label"] for c in colores)


def test_un_producto_puede_no_tener_colores(admin_client, categoria):
    respuesta = admin_client.post(
        "/api/v1/products/",
        json={
            "name": "Bolso sin definir",
            "price": "50000.00",
            "stock": 1,
            "category_id": categoria.id,
        },
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["colors"] == []


def test_marcar_colores_reemplaza_la_lista_completa(admin_client, crear_producto):
    """El formulario del panel manda el estado final de los círculos
    marcados, no altas y bajas por separado."""
    producto = crear_producto(colores=CON_COLORES)  # GRIS y NEGRO

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": ["AZUL"]}
    )

    assert respuesta.status_code == 200
    assert [c["value"] for c in respuesta.json()["colors"]] == ["AZUL"]


def test_se_puede_dejar_un_producto_sin_colores(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": []}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["colors"] == []


def test_un_color_repetido_no_duplica_el_circulo(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}/colors",
        json={"colors": ["AZUL", "AZUL", "NEGRO"]},
    )

    valores = [c["value"] for c in respuesta.json()["colors"]]
    assert sorted(valores) == ["AZUL", "NEGRO"]


def test_los_colores_que_ya_estaban_no_cambian_de_lugar(admin_client, crear_producto):
    """`set_colors` conserva las filas de los colores que siguen marcados
    en vez de borrarlas y recrearlas. Si las recreara, cambiarían de id en
    cada guardado del formulario y el orden de los círculos en la ficha
    bailaría sin que nadie tocara nada.

    La contrapartida: el orden lo da cuándo se agregó cada color, no el
    orden en que el admin los mandó. Para un selector de círculos importa
    más que no se muevan solos que poder ordenarlos a mano.
    """
    producto = crear_producto(colores=CON_COLORES)  # GRIS y NEGRO, en ese orden

    # Se quita el GRIS y se agrega AZUL: el NEGRO no se tocó.
    primero = admin_client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": ["NEGRO", "AZUL"]}
    ).json()["colors"]
    # Se vuelve a guardar exactamente lo mismo, como haría el formulario.
    segundo = admin_client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": ["NEGRO", "AZUL"]}
    ).json()["colors"]

    assert [c["value"] for c in primero] == ["NEGRO", "AZUL"]
    assert [c["value"] for c in segundo] == [c["value"] for c in primero]


def test_un_color_que_no_existe_se_rechaza(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": ["FUCSIA_NEON"]}
    )

    assert respuesta.status_code == 422


def test_marcar_colores_exige_admin(client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    respuesta = client.put(
        f"/api/v1/products/{producto.id}/colors", json={"colors": ["AZUL"]}
    )

    assert respuesta.status_code == 401


# --- Fotos por color ------------------------------------------------------


def test_una_foto_queda_ligada_a_su_color(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    respuesta = subir(admin_client, producto.id, color=Color.NEGRO)

    assert respuesta.status_code == 200
    assert respuesta.json()["images"][0]["color"] == "NEGRO"


def test_una_foto_sin_color_es_general(admin_client, crear_producto):
    """El detalle del cierre o de la etiqueta vale para cualquier color."""
    producto = crear_producto(colores=CON_COLORES)

    respuesta = subir(admin_client, producto.id)

    assert respuesta.json()["images"][0]["color"] is None


def test_cada_color_tiene_su_propia_numeracion(admin_client, crear_producto):
    """Sin el color en la llave única, la primera foto del negro chocaría
    contra la primera del gris."""
    producto = crear_producto(colores=CON_COLORES)

    subir(admin_client, producto.id, cantidad=2, color=Color.NEGRO)
    respuesta = subir(admin_client, producto.id, cantidad=2, color=Color.GRIS)

    imagenes = respuesta.json()["images"]
    negras = [i["position"] for i in imagenes if i["color"] == "NEGRO"]
    grises = [i["position"] for i in imagenes if i["color"] == "GRIS"]
    assert negras == [0, 1]
    assert grises == [0, 1]


def test_el_tope_es_por_color_y_no_por_producto(admin_client, crear_producto):
    """Un bolso en cuatro colores necesita fotos de cada uno: un tope
    global le dejaría dos o tres por color."""
    producto = crear_producto(colores=CON_COLORES)

    assert subir(admin_client, producto.id, cantidad=MAX, color=Color.NEGRO).status_code == 200
    assert subir(admin_client, producto.id, cantidad=MAX, color=Color.GRIS).status_code == 200
    # Y las generales son su propio grupo.
    assert subir(admin_client, producto.id, cantidad=MAX).status_code == 200


def test_pasarse_del_tope_en_un_color_se_rechaza(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)
    subir(admin_client, producto.id, cantidad=MAX, color=Color.NEGRO)

    respuesta = subir(admin_client, producto.id, color=Color.NEGRO)

    assert respuesta.status_code == 409
    assert "negro" in respuesta.json()["detail"].lower()


def test_llenar_un_color_no_bloquea_a_los_demas(admin_client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)
    subir(admin_client, producto.id, cantidad=MAX, color=Color.NEGRO)

    assert subir(admin_client, producto.id, color=Color.GRIS).status_code == 200


def test_borrar_una_foto_solo_renumera_su_color(admin_client, crear_producto):
    """Correr las fotos del gris porque se borró una del negro sería
    reordenar la galería de alguien sin ningún motivo."""
    producto = crear_producto(colores=CON_COLORES)
    negras = subir(admin_client, producto.id, cantidad=3, color=Color.NEGRO).json()
    grises = subir(admin_client, producto.id, cantidad=3, color=Color.GRIS).json()
    id_negra_del_medio = [i for i in negras["images"] if i["color"] == "NEGRO"][1]["id"]
    posiciones_grises_antes = [
        i["position"] for i in grises["images"] if i["color"] == "GRIS"
    ]

    respuesta = admin_client.delete(
        f"/api/v1/products/{producto.id}/images/{id_negra_del_medio}"
    )

    imagenes = respuesta.json()["images"]
    assert [i["position"] for i in imagenes if i["color"] == "NEGRO"] == [0, 1]
    assert [
        i["position"] for i in imagenes if i["color"] == "GRIS"
    ] == posiciones_grises_antes


def test_quitar_un_color_no_borra_sus_fotos(admin_client, crear_producto):
    """Si la dueña deja de ofrecer el negro un tiempo y después vuelve, no
    tiene que volver a fotografiarlo."""
    producto = crear_producto(colores=CON_COLORES)
    subir(admin_client, producto.id, cantidad=2, color=Color.NEGRO)

    admin_client.put(f"/api/v1/products/{producto.id}/colors", json={"colors": ["GRIS"]})

    ficha = admin_client.get(f"/api/v1/products/{producto.id}").json()
    assert [c["value"] for c in ficha["colors"]] == ["GRIS"]
    assert len([i for i in ficha["images"] if i["color"] == "NEGRO"]) == 2


# --- La portada del catalogo ----------------------------------------------


def test_la_portada_prefiere_una_foto_general(admin_client, crear_producto):
    """En el listado todavía no se eligió color, así que la que vale es
    una que sirva para cualquiera."""
    producto = crear_producto(colores=CON_COLORES)
    subir(admin_client, producto.id, color=Color.NEGRO)
    respuesta = subir(admin_client, producto.id)

    generales = [i for i in respuesta.json()["images"] if i["color"] is None]
    assert respuesta.json()["image_url"] == generales[0]["image_url"]


def test_sin_generales_la_portada_es_la_primera_de_color(admin_client, crear_producto):
    """Mejor mostrar una foto de color que dejar el hueco vacío."""
    producto = crear_producto(colores=CON_COLORES)

    respuesta = subir(admin_client, producto.id, cantidad=2, color=Color.NEGRO)

    assert respuesta.json()["image_url"] == respuesta.json()["images"][0]["image_url"]


def test_un_producto_sin_fotos_no_tiene_portada(client, crear_producto):
    producto = crear_producto(colores=CON_COLORES)

    assert client.get(f"/api/v1/products/{producto.id}").json()["image_url"] is None
