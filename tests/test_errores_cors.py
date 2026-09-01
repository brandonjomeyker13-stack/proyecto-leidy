"""Un error 500 del backend tiene que salir CON cabeceras CORS.

Por qué existe este archivo: el manejo de errores no controlados estaba
como `@app.exception_handler(Exception)`, y ese handler corre en el
ServerErrorMiddleware de Starlette, que va por FUERA del CORSMiddleware.
El 500 salía sin `Access-Control-Allow-Origin` y el navegador lo
reportaba como:

    blocked by CORS policy: No 'Access-Control-Allow-Origin' header

o sea, escondía el error real y mandaba a revisar la configuración de
CORS. Pasó de verdad: el login con Google fallaba porque faltaba la
columna `users.phone`, y en el navegador se veía como problema de CORS.

Si alguien mueve `app.add_middleware(UnhandledErrorsMiddleware)` para
después del CORSMiddleware en app/main_app.py, estos tests fallan.
"""

import pytest
from fastapi import APIRouter

from app.main_app import app

ORIGEN_DEL_FRONTEND = "https://sohee.org"

# La ruta se cuelga de la app REAL a propósito: lo que se está probando
# es el orden de middlewares de app/main_app.py, no una app de mentira
# armada acá que podría tener otro orden.
_router_de_prueba = APIRouter()


@_router_de_prueba.get("/_explota")
def _explota():
    raise RuntimeError("error a propósito, para el test")


app.include_router(_router_de_prueba)


@pytest.fixture
def cliente_que_no_relanza(client):
    """El TestClient normal relanza la excepción del server en vez de
    devolver el 500, y así no se puede mirar la respuesta."""
    client.raise_server_exceptions = False
    return client


def test_un_500_sale_con_cabeceras_cors(cliente_que_no_relanza):
    respuesta = cliente_que_no_relanza.get(
        "/_explota", headers={"Origin": ORIGEN_DEL_FRONTEND}
    )

    assert respuesta.status_code == 500
    # Esta es la línea que importa: sin ella el navegador nunca deja ver
    # el 500 y reporta un error de CORS que no existe.
    assert respuesta.headers["access-control-allow-origin"] == ORIGEN_DEL_FRONTEND


def test_un_500_no_filtra_detalles_internos(cliente_que_no_relanza):
    respuesta = cliente_que_no_relanza.get(
        "/_explota", headers={"Origin": ORIGEN_DEL_FRONTEND}
    )

    cuerpo = respuesta.json()
    assert "error a propósito" not in cuerpo["detail"]
    assert "RuntimeError" not in cuerpo["detail"]
    assert "Traceback" not in cuerpo["detail"]
