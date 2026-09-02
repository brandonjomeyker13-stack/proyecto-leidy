"""Los atributos físicos del bolso: medidas, compartimientos y material.

Reemplazan a `size`, que no significaba nada para un bolso (un morral no
es S/M/L). Son todos opcionales: ya había productos cargados cuando se
agregaron, y obligarlos habría roto el catálogo hasta editarlos uno a uno.
"""

def _crear(admin_client, categoria, **extra):
    cuerpo = {
        "name": "Morral deportivo con cartuchera",
        "color": "Gris",
        "price": "26000.00",
        "stock": 5,
        "category_id": categoria.id,
    }
    cuerpo.update(extra)
    return admin_client.post("/api/v1/products/", json=cuerpo)


def test_se_crea_con_todos_los_atributos_del_bolso(admin_client, categoria):
    respuesta = _crear(
        admin_client,
        categoria,
        height_cm="43.0",
        width_cm="33.0",
        compartments=3,
        material="Lona satinada",
    )

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["height_cm"] == "43.0"
    assert cuerpo["width_cm"] == "33.0"
    assert cuerpo["compartments"] == 3
    assert cuerpo["material"] == "Lona satinada"


def test_se_puede_crear_sin_ninguno_de_ellos(admin_client, categoria):
    """Al cargar un producto puede que todavía no lo hayan medido."""
    respuesta = _crear(admin_client, categoria)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["height_cm"] is None
    assert cuerpo["width_cm"] is None
    assert cuerpo["compartments"] is None
    assert cuerpo["material"] is None


def test_las_medidas_aceptan_decimales(admin_client, categoria):
    """43.5 cm no es lo mismo que 43: el cliente compra sin poder tocarlo."""
    respuesta = _crear(admin_client, categoria, height_cm="43.5")

    assert respuesta.status_code == 201
    assert respuesta.json()["height_cm"] == "43.5"


def test_una_medida_en_cero_o_negativa_se_rechaza(admin_client, categoria):
    assert _crear(admin_client, categoria, height_cm="0").status_code == 422
    assert _crear(admin_client, categoria, width_cm="-10").status_code == 422


def test_cero_compartimientos_es_valido(admin_client, categoria):
    """Un bolso de un solo espacio existe: cero es un dato, no un error."""
    respuesta = _crear(admin_client, categoria, compartments=0)

    assert respuesta.status_code == 201
    assert respuesta.json()["compartments"] == 0


def test_editar_solo_el_material_no_pisa_lo_demas(admin_client, crear_producto):
    producto = crear_producto()

    respuesta = admin_client.put(
        f"/api/v1/products/{producto.id}", json={"material": "Cuero sintético"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["material"] == "Cuero sintético"
    # Lo que traía de antes sigue ahí.
    assert cuerpo["height_cm"] == "43.0"
    assert cuerpo["compartments"] == 3


def test_la_talla_ya_no_existe(admin_client, categoria):
    """Si alguien manda `size`, se ignora en vez de crear un producto con
    un campo fantasma que nadie va a leer."""
    respuesta = _crear(admin_client, categoria, size="M")

    assert respuesta.status_code == 201
    assert "size" not in respuesta.json()
