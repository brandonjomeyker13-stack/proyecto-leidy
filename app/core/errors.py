"""Red de seguridad para cualquier error no controlado de la API.

Esto es un MIDDLEWARE y no un `@app.exception_handler(Exception)` por un
motivo puntual: ese handler lo ejecuta el `ServerErrorMiddleware` de
Starlette, que es la capa MÁS EXTERNA de toda la pila — por fuera del
CORSMiddleware. Su respuesta sale entonces sin `Access-Control-Allow-Origin`,
y el navegador no muestra el 500: muestra

    "blocked by CORS policy: No 'Access-Control-Allow-Origin' header"

que manda a buscar el problema al lado equivocado (la configuración de
CORS, el frontend) cuando en realidad el backend reventó por otra cosa.
Ya pasó una vez con una columna que faltaba en la base.

Como middleware queda POR DENTRO del CORSMiddleware, así que el 500 sale
con sus cabeceras y el navegador deja ver el error de verdad.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("tienda.errors")


class UnhandledErrorsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception:
            # El traceback completo queda en los logs de Render; al
            # cliente no se le manda ningún detalle interno.
            logger.exception(
                "Error no controlado en %s %s", request.method, request.url.path
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Ocurrió un error inesperado de nuestro lado. Ya "
                    "quedó registrado — inténtalo de nuevo en un momento."
                },
            )
