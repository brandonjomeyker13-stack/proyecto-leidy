"""
Subida de archivos a Supabase Storage.

Requiere que en el .env SUPABASE_URL y SUPABASE_KEY estén configurados,
y que SUPABASE_KEY sea la clave "service_role" (no la "anon"), porque
solo el service_role puede subir archivos sin pasar por las políticas
de acceso del bucket.
"""

import logging
import uuid
from typing import NamedTuple

from fastapi import HTTPException, UploadFile, status
from storage3.exceptions import StorageApiError
from supabase import create_client

from app.core.config import settings

logger = logging.getLogger("tienda.storage")

BUCKET_NAME = "product-images"

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Firmas binarias reales (magic bytes) de cada formato permitido. El
# Content-Type del header lo manda el cliente y se puede falsificar
# fácilmente (ej. subir un .html/.svg con script y decir que es
# image/png); esto verifica los bytes de verdad, no lo que dice el header.
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    # WEBP: header RIFF....WEBP — el tamaño va en los bytes 4-8, no importa.
    "image/webp": (b"RIFF",),
}


def _detect_real_content_type(contents: bytes) -> str | None:
    for content_type, signatures in _MAGIC_SIGNATURES.items():
        for signature in signatures:
            if contents.startswith(signature):
                if content_type == "image/webp" and contents[8:12] != b"WEBP":
                    continue
                return content_type
    return None


def _variables_de_supabase_que_faltan() -> list[str]:
    """Cuáles de las dos llegan vacías. Se devuelven por nombre porque
    saber si falta UNA o las DOS es lo que distingue un nombre mal escrito
    (falta una) de que la app no esté viendo el entorno (faltan las dos)."""
    return [
        nombre
        for nombre, valor in (
            ("SUPABASE_URL", settings.SUPABASE_URL),
            ("SUPABASE_KEY", settings.SUPABASE_KEY),
        )
        if not valor
    ]


def _get_client():
    faltantes = _variables_de_supabase_que_faltan()
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            # Decía "en el .env", y en Render no hay ningún .env: se
            # configuran en Environment. El mensaje mandaba a buscar el
            # problema en un archivo que allá no existe.
            detail=(
                f"Falta configurar {' y '.join(faltantes)}. En local van en el "
                "archivo .env; en Render, en Environment (allá no hay .env). "
                "Después de agregarlas hay que esperar a que el servicio "
                "termine de redesplegar."
            ),
        )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def _traducir_error_de_storage(exc: StorageApiError) -> HTTPException:
    """Convierte el error crudo de Supabase en algo que se pueda accionar.

    Sin esto, los tres errores de configuración más comunes (bucket que no
    existe, clave `anon` en vez de `service_role`, clave inválida) llegan
    al admin como un 500 mudo y hay que ir a leer los logs de Render para
    saber cuál de los tres fue.
    """
    texto = f"{exc.code} {exc.message}".lower()

    if "bucket" in texto and "not found" in texto:
        detalle = (
            f"El bucket «{BUCKET_NAME}» no existe en este proyecto de Supabase. "
            "Créalo en Storage → New bucket, con ese nombre exacto y marcado "
            "como público."
        )
    elif "row-level security" in texto or "unauthorized" in texto or exc.status in (401, 403):
        detalle = (
            "Supabase rechazó la subida por permisos. Casi siempre es que "
            "SUPABASE_KEY está con la clave «anon»: tiene que ser la "
            "«service_role», que es la única que escribe sin pasar por las "
            "políticas del bucket."
        )
    elif "jws" in texto or "jwt" in texto:
        detalle = (
            "SUPABASE_KEY no es una clave válida de este proyecto de Supabase. "
            "Revisa que sea la del proyecto correcto y que esté completa."
        )
    else:
        detalle = f"Supabase Storage rechazó la subida: {exc.message}"

    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detalle)


class UploadedImage(NamedTuple):
    """La URL es la que consume el frontend; el path es lo que hay que
    mandarle a Supabase para borrar el archivo después."""

    url: str
    path: str


async def upload_product_image(file: UploadFile, product_id: int) -> UploadedImage:
    """Sube la imagen al bucket y devuelve su URL pública y su ruta."""

    # Chequeo rápido del header como primer filtro (no es la validación
    # real, solo evita leer el archivo completo si viene claramente mal).
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten imágenes JPG, PNG o WEBP.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no puede pesar más de 5 MB.",
        )

    # Validación REAL: los bytes tienen que coincidir con la firma binaria
    # del formato, sin importar lo que diga el Content-Type del header.
    real_content_type = _detect_real_content_type(contents)
    if real_content_type is None or real_content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una imagen JPG, PNG o WEBP válida.",
        )

    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[
        real_content_type
    ]
    # Nombre único por producto para evitar sobrescribir el archivo anterior.
    path = f"product-{product_id}-{uuid.uuid4().hex}.{extension}"

    client = _get_client()
    try:
        client.storage.from_(BUCKET_NAME).upload(
            path, contents, {"content-type": real_content_type}
        )
    except StorageApiError as exc:
        # El detalle completo va a los logs; al admin le llega la versión
        # traducida de _traducir_error_de_storage.
        logger.error(
            "Supabase rechazó la subida al bucket %s: status=%s code=%s %s",
            BUCKET_NAME,
            exc.status,
            exc.code,
            exc.message,
        )
        raise _traducir_error_de_storage(exc) from exc

    return UploadedImage(
        url=client.storage.from_(BUCKET_NAME).get_public_url(path),
        path=path,
    )


def delete_product_image_file(storage_path: str) -> None:
    """Borra el archivo del bucket. No revienta si falla: la imagen ya se
    quitó de la base y para el usuario desapareció; lo peor que puede
    pasar es que quede un archivo huérfano ocupando espacio, y eso no
    justifica devolverle un error al admin."""
    try:
        _get_client().storage.from_(BUCKET_NAME).remove([storage_path])
    except Exception:
        logger.exception("No se pudo borrar %s del bucket %s", storage_path, BUCKET_NAME)