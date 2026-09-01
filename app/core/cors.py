"""
Qué orígenes (dominios del frontend) pueden hablarle a esta API.

Vive acá y no en `main_app.py` porque la lista la usan dos cosas: el
middleware de CORS y el chequeo de Origin de los endpoints que se
autentican con la cookie del refresh token (`require_trusted_origin`).
"""

import re
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import settings

ALLOWED_ORIGINS = [
    # El dominio propio de la tienda. Las dos formas: el navegador manda
    # el host tal cual lo escribió el usuario, y "sohee.org" y
    # "www.sohee.org" son orígenes DISTINTOS para CORS.
    "https://sohee.org",
    "https://www.sohee.org",
    # Desarrollo local.
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# El subdominio de preview de Lovable cambia por proyecto/sesión, así que
# no se puede listar: hay que aceptarlo por patrón o no aceptarlo.
#
# Y aceptarlo por patrón significa confiar en CUALQUIER proyecto de
# Lovable, no solo en el nuestro. Con la cookie del refresh token en
# SameSite=None y allow_credentials activo, una página en
# cualquier-cosa.lovable.app puede llamar a /auth/refresh con la cookie
# de un cliente nuestro y LEER el access_token de la respuesta. Eso es
# tomar la cuenta del cliente.
#
# Por eso solo se activa en local, o si se prende a mano mientras se
# construye el frontend. En producción, con el dominio propio ya
# funcionando, no hace falta.
_LOVABLE_PREVIEW_REGEX = r"https://.*\.(lovable\.app|lovableproject\.com)"

_preview_permitido = settings.ALLOW_LOVABLE_PREVIEW or settings.ENVIRONMENT == "local"

ALLOWED_ORIGIN_REGEX = _LOVABLE_PREVIEW_REGEX if _preview_permitido else None

_ORIGIN_PATTERN = re.compile(ALLOWED_ORIGIN_REGEX) if ALLOWED_ORIGIN_REGEX else None


def is_trusted_origin(origin: str) -> bool:
    if origin in ALLOWED_ORIGINS:
        return True
    return _ORIGIN_PATTERN is not None and _ORIGIN_PATTERN.fullmatch(origin) is not None


def require_trusted_origin(request: Request) -> None:
    """Rechaza el request si viene de una página que no es nuestra.

    Es protección CSRF. La cookie del refresh token sale con
    `SameSite=None` (obligatorio: el frontend está en otro dominio), así
    que el navegador la manda también cuando la petición la dispara
    CUALQUIER sitio — una página maliciosa podía hacerle POST a
    /auth/logout o /auth/refresh al visitante y sacarlo de su sesión.

    El navegador siempre manda `Origin` en un POST cross-site y no se
    puede falsificar desde JavaScript. Si no viene `Origin`, la petición
    no la originó una página web (curl, la app móvil), y ahí no hay CSRF
    que valga: esos clientes no tienen la cookie del usuario a menos que
    se las den.
    """
    origin = request.headers.get("origin")
    if origin is None or is_trusted_origin(origin):
        return

    # Same-origin: la petición sale de una página servida por esta misma
    # API (el /docs de Swagger, por ejemplo). Se compara solo el host
    # porque detrás del proxy la app ve http:// aunque afuera sea https.
    if urlsplit(origin).netloc == request.headers.get("host"):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Origen no permitido.",
    )
