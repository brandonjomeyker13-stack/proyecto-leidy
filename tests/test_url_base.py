"""La URL de Supabase tiene que usar el driver que está instalado.

Sin el `+psycopg2`, SQLAlchemy reciente pide el módulo `psycopg` (v3)
y el arranque en Render muere antes de migrar.
"""

from app.core.config import url_con_psycopg2


def test_la_uri_de_supabase_queda_en_psycopg2():
    url = url_con_psycopg2("postgresql://usuario:clave@db.supabase.co:5432/postgres")

    assert url == "postgresql+psycopg2://usuario:clave@db.supabase.co:5432/postgres"


def test_el_esquema_corto_de_postgres_tambien():
    url = url_con_psycopg2("postgres://usuario:clave@localhost:5432/tienda")

    assert url.startswith("postgresql+psycopg2://")


def test_no_reescribe_una_url_que_ya_trae_el_driver():
    original = "postgresql+psycopg2://usuario:clave@localhost:5432/tienda"

    assert url_con_psycopg2(original) == original


def test_una_url_que_pide_psycopg3_se_baja_al_driver_instalado():
    url = url_con_psycopg2("postgresql+psycopg://usuario:clave@localhost/tienda")

    assert url == "postgresql+psycopg2://usuario:clave@localhost/tienda"


def test_sqlite_de_los_tests_no_se_toca():
    original = "sqlite+pysqlite:///:memory:"

    assert url_con_psycopg2(original) == original
