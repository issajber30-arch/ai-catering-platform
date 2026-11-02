"""Apply database/migrations/*.sql that haven't run yet, in name order, one transaction each.

shortcut: runs at container start because Render's free plan has no pre-deploy hook;
move it to `preDeployCommand` on a paid plan.
"""

import sys
from pathlib import Path

import psycopg
from sqlalchemy import DefaultClause, Engine, func, insert, make_url, select, text

from app.core.config import get_settings
from app.core.db import Base, make_engine

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


# Seed rows the SQL migrations insert (20261029000001_catalog, 20261029000003_business_rules).
ALLERGENS = (
    "peanuts", "tree nuts", "milk", "eggs", "gluten", "soy", "sesame", "fish", "shellfish",
)  # fmt: skip
SETTINGS = {
    "lead_time_days": 7, "edit_cutoff_hours": 4, "min_food_total": 500, "delivery_base_fee": 50,
    "delivery_per_km": 4, "delivery_max_km": 40, "kitchen_address": "Jerusalem",
    "kitchen_lat": 31.7683, "kitchen_lon": 35.2137, "safety_car": False,
}  # fmt: skip


def create_sqlite_schema(engine: Engine, seed: bool = True) -> list[str]:
    """Local/test only: build the schema from the models and seed it like the migrations do.

    shortcut: SQLite gets only what the models declare (no SQL CHECK constraints, RLS or row
    locks); the SQL files stay the real schema and CI/deploys run them on Postgres.
    """
    from app.models import logistics, orders  # noqa: F401  registers their tables
    from app.models.ai import AiMessage
    from app.models.catalog import Allergen
    from app.models.settings import BusinessSettings

    # ai_messages.seq is a Postgres identity; SQLite gets it from next_seq() (core/db.py).
    AiMessage.__table__.c.seq.server_default = DefaultClause(text("(next_seq())"))
    Base.metadata.create_all(engine)
    if not seed:
        return []
    with engine.begin() as conn:
        if not conn.scalar(select(func.count()).select_from(Allergen)):
            conn.execute(insert(Allergen), [{"name": n} for n in ALLERGENS])
        if not conn.scalar(select(func.count()).select_from(BusinessSettings)):
            conn.execute(insert(BusinessSettings).values(id=True, **SETTINGS))
    return ["sqlite schema"]


if __name__ == "__main__":
    url = get_settings().database_url
    if not url:
        sys.exit("DATABASE_URL is not set")
    is_sqlite = make_url(url).get_backend_name() == "sqlite"
    for name in create_sqlite_schema(make_engine(url)) if is_sqlite else migrate(url):
        print(f"applied {name}")  # file names only; never the URL (it holds the password)
