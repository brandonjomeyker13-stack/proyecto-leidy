"""
App de FastAPI. Se corre con:

    uvicorn app.main:app --reload

(el `main.py` de la raíz sigue siendo solo para crear las tablas, no lo
mezcles con este archivo).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import auth, cart, categories, orders, products, sales, webhooks
from app.core.cors import ALLOWED_ORIGIN_REGEX, ALLOWED_ORIGINS
from app.core.errors import UnhandledErrorsMiddleware
from app.core.limiter import limiter
from app.core.security_headers import SecurityHeadersMiddleware

app = FastAPI(title="Tienda API", version="1.0.0")


# Rate limit global para proteger principalmente /auth/login y /auth/register.
# Los límites puntuales se definen en cada endpoint con @limiter.limit(...).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# OJO CON EL ORDEN: add_middleware apila al reves — el ULTIMO que se
# agrega queda por fuera. Entonces la pila real es
#   CORS -> SecurityHeaders -> UnhandledErrors -> router
# y por eso el 500 de UnhandledErrors sale con cabeceras CORS. Si se
# mueve esta linea despues del CORSMiddleware, los errores del backend
# vuelven a aparecer en el navegador como errores de CORS.
app.add_middleware(UnhandledErrorsMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# CORS para orígenes locales y dominios Lovable. El regex cubre el subdominio
# de preview, que cambia por proyecto/sesión.
# allow_credentials=True es OBLIGATORIO ahora que el refresh token viaja
# en una cookie httpOnly cross-site (Lovable != dominio del backend); sin
# esto el navegador ni siquiera la manda. Por eso NO se puede usar "*" en
# allow_origins/allow_origin_regex — el navegador lo rechaza cuando hay
# credentials de por medio, así que la lista de orígenes de abajo debe
# mantenerse explícita.
#
# ALLOWED_ORIGINS/ALLOWED_ORIGIN_REGEX viven en app/core/cors.py — es la
# MISMA lista que usa require_trusted_origin (protección CSRF de
# /auth/refresh y /auth/logout). Un solo lugar para editarla evita que
# las dos protecciones queden desincronizadas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(products.router, prefix="/api/v1/products", tags=["products"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
app.include_router(cart.router, prefix="/api/v1/cart", tags=["cart"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(sales.router, prefix="/api/v1/sales", tags=["sales"])


@app.get("/")
def root():
    return {"message": "Tienda API está corriendo"}


@app.get("/health")
def health_check():
    return {"status": "ok"}