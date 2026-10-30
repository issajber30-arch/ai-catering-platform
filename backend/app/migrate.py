"""Apply database/migrations/*.sql that haven't run yet, in name order, one transaction each.

shortcut: runs at container start because Render's free plan has no pre-deploy hook;
move it to `preDeployCommand` on a paid plan.
"""

import sys
from pathlib import Path

import psycopg

from app.core.config import get_settings

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"


def migrate(url: str, folder: Path = MIGRATIONS) -> list[str]:
    applied = []
    with psycopg.connect(url.replace("+psycopg", "")) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        conn.commit()
        done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
        for sql in sorted(folder.glob("*.sql")):
            if sql.name in done:
                continue
            with conn.transaction():
                conn.execute(sql.read_text())
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (sql.name,))
            applied.append(sql.name)
    return applied


if __name__ == "__main__":
    url = get_settings().database_url
    if not url:
        sys.exit("DATABASE_URL is not set")
    for name in migrate(url):
        print(f"applied {name}")  # file names only; never the URL (it holds the password)
