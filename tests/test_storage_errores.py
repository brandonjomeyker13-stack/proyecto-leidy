"""Los errores de Supabase Storage tienen que decir qué hay que arreglar.

Los tres motivos de abajo son casi siempre la causa cuando "subir una
imagen lanza error", y los tres llegaban al admin como un 500 sin
detalle: había que ir a los logs de Render para distinguirlos.
"""

import pytest
from fastapi import HTTPException
from storage3.exceptions import StorageApiError

from app.core import storage
from app.core.storage import BUCKET_NAME, _traducir_error_de_storage


def _error(message: str, code: str = "", status: int | str = 400) -> StorageApiError:
    return StorageApiError(message=message, code=code, status=status)


def test_bucket_que_no_existe_dice_como_crearlo():
    http = _traducir_error_de_storage(
        _error("Bucket not found", code="NoSuchBucket", status=404)
    )

    assert BUCKET_NAME in http.detail
    assert "Storage" in http.detail


def test_clave_anon_en_vez_de_service_role_lo_dice():
    http = _traducir_error_de_storage(
        _error(
            "new row violates row-level security policy",
            code="Unauthorized",
            status=403,
        )
    )

    assert "service_role" in http.detail


def test_clave_invalida_lo_dice():
    http = _traducir_error_de_storage(
        _error("Invalid Compact JWS", code="InvalidJWT", status=401)
    )

    # 401 entra por la rama de permisos, que también apunta a SUPABASE_KEY:
    # lo que importa es que el admin sepa que el problema es la clave.
    assert "SUPABASE_KEY" in http.detail


def test_un_error_desconocido_no_se_traga_el_mensaje():
    http = _traducir_error_de_storage(
        _error("payload too large", code="EntityTooLarge", status=413)
    )

    assert "payload too large" in http.detail


@pytest.mark.parametrize(
    "exc",
    [
        _error("Bucket not found", code="NoSuchBucket", status=404),
        _error("new row violates row-level security policy", status=403),
        _error("payload too large", status=413),
    ],
)
def test_siempre_devuelve_un_500_y_no_revienta(exc):
    http = _traducir_error_de_storage(exc)

    assert http.status_code == 500
    assert http.detail


# --- Variables de entorno que faltan -------------------------------------


@pytest.mark.parametrize(
    ("url", "key", "esperados"),
    [
        (None, None, ["SUPABASE_URL", "SUPABASE_KEY"]),
        ("https://x.supabase.co", None, ["SUPABASE_KEY"]),
        (None, "service-role-key", ["SUPABASE_URL"]),
        ("", "", ["SUPABASE_URL", "SUPABASE_KEY"]),
        ("https://x.supabase.co", "service-role-key", []),
    ],
)
def test_dice_exactamente_cual_variable_falta(monkeypatch, url, key, esperados):
    """Que falte UNA sola apunta a un nombre mal escrito; que falten las
    DOS, a que la app no está viendo el entorno. Por eso importa saberlo."""
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", url)
    monkeypatch.setattr(storage.settings, "SUPABASE_KEY", key)

    assert storage._variables_de_supabase_que_faltan() == esperados


def test_el_error_no_manda_a_buscar_un_env_que_en_render_no_existe(monkeypatch):
    monkeypatch.setattr(storage.settings, "SUPABASE_URL", None)
    monkeypatch.setattr(storage.settings, "SUPABASE_KEY", None)

    with pytest.raises(HTTPException) as excinfo:
        storage._get_client()

    assert "Environment" in excinfo.value.detail
