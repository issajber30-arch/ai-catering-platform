import time
from pathlib import Path
from types import SimpleNamespace

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.db import get_db
from app.core.storage import get_uploader
from app.main import app
from app.services.geo import get_geocoder

MIGRATIONS = Path(__file__).resolve().parents[2] / "database" / "migrations"
SUPABASE_URL = "https://test-project.supabase.co"
TABLES = (
    "dish_allergens, dish_dietary, dishes, dish_categories, allergens, "
    "delivery_zones, time_slots, blocked_dates, order_items, orders, events, customers, "
    "quantity_rules, geocode_cache, business_settings"
)


@pytest.fixture(scope="session")
def engine():
    url = get_settings().test_database_url
    assert url, "Set TEST_DATABASE_URL (e.g. postgresql+psycopg://localhost/catering_test)"
    # The schema is dropped below, so refuse anything that isn't clearly a throwaway test DB.
    assert make_url(url).database.endswith("_test"), "TEST_DATABASE_URL must name a *_test database"
    with psycopg.connect(url.replace("+psycopg", ""), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        for sql in sorted(MIGRATIONS.glob("*.sql")):
            conn.execute(sql.read_text())
    return create_engine(url)


@pytest.fixture
def db(engine):
    with Session(engine) as session:
        session.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        session.execute(text("INSERT INTO business_settings DEFAULT VALUES"))
        session.execute(text("INSERT INTO allergens (name) VALUES ('peanuts'), ('milk')"))
        session.commit()
        yield session


@pytest.fixture(scope="session")
def key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def make_token(key, monkeypatch):
    """Signs tokens with a local ES256 key; the JWKS client is faked to return its public half."""
    monkeypatch.setattr(get_settings(), "supabase_url", SUPABASE_URL)
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=key.public_key())
    )
    monkeypatch.setattr(security, "get_jwks_client", lambda: fake)

    def make(role="admin", **overrides):
        claims = {
            "exp": int(time.time()) + 600,
            "aud": "authenticated",
            "iss": f"{SUPABASE_URL}/auth/v1",
            "sub": "user-1",
            "app_metadata": {"role": role} if role else {},
        } | overrides
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key, algorithm="ES256")

    return make


@pytest.fixture
def uploads():
    return []


@pytest.fixture
def places():
    """Fake geocoder data: address -> (lat, lon). Addresses not listed are 'not found'."""
    return {}


@pytest.fixture
def geo_calls():
    return []


@pytest.fixture
def client(db, uploads, places, geo_calls):
    def fake_uploader():
        return lambda data, kind: uploads.append((kind, len(data))) or f"fake-{len(uploads)}.{kind}"

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_uploader] = fake_uploader
    app.dependency_overrides[get_geocoder] = lambda: lambda a: geo_calls.append(a) or places.get(a)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin(client, make_token):
    client.headers["Authorization"] = f"Bearer {make_token()}"
    return client


@pytest.fixture
def category(admin):
    return admin.post("/api/admin/categories", json={"name_he": "עיקריות"}).json()


@pytest.fixture
def make_dish(admin, category):
    def make(**fields):
        body = {
            "category_id": category["id"],
            "name_he": "שניצל",
            "pricing_unit": "per_tray",
            "unit_price": "120.00",
        } | fields
        response = admin.post("/api/admin/dishes", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return make
