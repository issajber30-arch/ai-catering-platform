import psycopg

from app.core.config import get_settings
from app.migrate import migrate


def test_migrate_applies_each_file_once(tmp_path, engine):
    url = get_settings().test_database_url
    (tmp_path / "001_a.sql").write_text("CREATE SCHEMA mig_test; CREATE TABLE mig_test.a (id int);")
    (tmp_path / "002_b.sql").write_text("CREATE TABLE mig_test.b (id int);")
    try:
        assert migrate(url, tmp_path) == ["001_a.sql", "002_b.sql"]
        assert migrate(url, tmp_path) == []  # second deploy: nothing to do
        (tmp_path / "003_c.sql").write_text("CREATE TABLE mig_test.c (id int);")
        assert migrate(url, tmp_path) == ["003_c.sql"]
    finally:
        with psycopg.connect(url.replace("+psycopg", ""), autocommit=True) as conn:
            conn.execute(
                "DROP SCHEMA IF EXISTS mig_test CASCADE; DROP TABLE IF EXISTS schema_migrations"
            )


def test_failed_migration_is_not_recorded(tmp_path, engine):
    url = get_settings().test_database_url
    (tmp_path / "001_bad.sql").write_text("CREATE TABLE no_such_schema.x (id int);")
    try:
        try:
            migrate(url, tmp_path)
        except psycopg.Error:
            pass
        with psycopg.connect(url.replace("+psycopg", "")) as conn:
            assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 0
    finally:
        with psycopg.connect(url.replace("+psycopg", ""), autocommit=True) as conn:
            conn.execute("DROP TABLE IF EXISTS schema_migrations")
