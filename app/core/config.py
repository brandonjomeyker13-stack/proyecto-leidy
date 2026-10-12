"""
Configuración centralizada de la aplicación.

Toda variable de entorno se lee UNA sola vez, aquí. El resto del código
importa `settings` en vez de llamar a os.getenv disperso por archivos.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def url_con_psycopg2(url: str) -> str:
    """Deja la URL apuntando al driver que sí instalamos, psycopg2.

    Supabase entrega la URI como `postgresql://` o `postgres://`.
    SQLAlchemy reciente lee eso como el driver `psycopg` (versión 3),
    que no está en requirements. En Render el contenedor construía bien
    y moría al arrancar, en `import psycopg`, cuando Alembic abre la base.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql+psycopg://"):
        return "postgresql+psycopg2://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    DATABASE_URL: str
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    SECRET_KEY: str
    ENVIRONMENT: str = "local"

    # Aceptar CUALQUIER subdominio *.lovable.app como origen de confianza.
    # En local siempre se acepta (el preview de Lovable cambia de
    # subdominio por sesión). En producción está apagado a propósito:
    # con allow_credentials activo, un origen de confianza puede llamar a
    # /auth/refresh con la cookie de un cliente y LEER su access token —
    # o sea que dejarlo abierto le da esa puerta a cualquier proyecto de
    # Lovable del mundo, no solo al nuestro. Se prende temporalmente
    # (ALLOW_LOVABLE_PREVIEW=true) solo mientras se construye el frontend.
    ALLOW_LOVABLE_PREVIEW: bool = False

    # Expiración del access token (JWT), en minutos. Corto a propósito:
    # si se roba, la ventana de uso es chica. La sesión larga la maneja
    # el refresh token de abajo.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Refresh token: vive en cookie httpOnly, no en el JWT ni en el body.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    # Google OAuth: el "Client ID" de tu proyecto en Google Cloud Console
    # (OAuth consent screen / Credentials). Se usa para verificar que un
    # id_token realmente fue emitido para TU aplicación. Es público (el
    # frontend lo muestra). Si Render define GOOGLE_CLIENT_ID, ese gana.
    GOOGLE_CLIENT_ID: str | None = (
        "469926197059-3jh9i11p3ohatakpu4gne0nen3hmccla.apps.googleusercontent.com"
    )

    # Wompi (pasarela de pagos). En Sandbox estas llaves empiezan con
    # "pub_test_", "prv_test_", etc. En producción, con "pub_prod_".
    WOMPI_PUBLIC_KEY: str | None = None
    WOMPI_PRIVATE_KEY: str | None = None
    WOMPI_INTEGRITY_SECRET: str | None = None
    WOMPI_EVENTS_SECRET: str | None = None
    # Colombia: siempre COP.
    WOMPI_CURRENCY: str = "COP"

    # Cuántos proxies de confianza hay delante de la app. En Render y
    # detrás de Cloudflare es 1; corriendo directo, 0. Se usa para sacar
    # la IP real del cliente en el rate limit (ver app/core/limiter.py).
    TRUSTED_PROXY_HOPS: int = 0

    # Dónde lleva la cuenta el rate limiter. "memory://" sirve con una
    # sola instancia; con varias hay que apuntarlo a un Redis compartido
    # (ej. redis://default:...@host:6379) o cada una contará por su lado.
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _forzar_driver_instalado(cls, url: str) -> str:
        return url_con_psycopg2(url)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instancia única reutilizada en todo el proyecto
settings = Settings()