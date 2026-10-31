import time

import jwt
from fastapi.routing import APIRoute

from app.core.security import require_admin
from app.main import app

from .conftest import SUPABASE_URL

URL = "/api/admin/categories"


def api_routes():
    """Flatten routes; newer FastAPI wraps included routers in a lazy container."""
    for r in app.routes:
        yield from getattr(r, "original_router", r).routes if hasattr(r, "original_router") else [r]


def error_code(response):
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    return body["error"]["code"]


def get(client, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(URL, headers=headers)


def test_admin_token_ok(client, make_token):
    assert get(client, make_token()).status_code == 200


def test_missing_token_401(client, make_token):
    response = get(client)
    assert response.status_code == 401
    assert error_code(response) == "unauthenticated"


def test_garbage_token_401(client, make_token):
    assert get(client, "not-a-jwt").status_code == 401


def test_non_admin_403(client, make_token):
    for token in (make_token(role="customer"), make_token(role=None)):
        response = get(client, token)
        assert response.status_code == 403
        assert error_code(response) == "forbidden"


def test_expired_401(client, make_token):
    assert get(client, make_token(exp=int(time.time()) - 10)).status_code == 401


def test_missing_exp_401(client, make_token):
    assert get(client, make_token(exp=None)).status_code == 401


def test_wrong_issuer_and_audience_401(client, make_token):
    assert get(client, make_token(iss="https://evil.example/auth/v1")).status_code == 401
    assert get(client, make_token(aud="anon")).status_code == 401


def test_alg_none_401(client, make_token):
    claims = {
        "exp": int(time.time()) + 600,
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "app_metadata": {"role": "admin"},
    }
    token = jwt.encode(claims, key=None, algorithm="none")
    assert get(client, token).status_code == 401


def test_hs256_token_signed_with_public_material_401(client, make_token):
    claims = {"exp": int(time.time()) + 600, "aud": "authenticated",
              "iss": f"{SUPABASE_URL}/auth/v1", "app_metadata": {"role": "admin"}}  # fmt: skip
    token = jwt.encode(claims, "x" * 40, algorithm="HS256")
    assert get(client, token).status_code == 401


def test_every_admin_route_requires_admin():
    def deps(dependant):
        for d in dependant.dependencies:
            yield d.call
            yield from deps(d)

    admin_routes = [
        r for r in api_routes() if isinstance(r, APIRoute) and r.path.startswith("/api/admin")
    ]
    assert len(admin_routes) > 20
    for route in admin_routes:
        assert require_admin in deps(route.dependant), route.path


def test_admin_routes_reject_anonymous(client, make_token):
    for route in api_routes():
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin"):
            path = route.path.replace("{", "").replace("}", "")
            path = path.replace("category_id", "00000000-0000-0000-0000-000000000000")
            for method in route.methods:
                assert client.request(method, path).status_code == 401, (method, route.path)


def test_oversized_body_rejected_before_auth(client):
    # Anonymous: the size cap must answer before multipart parsing and the auth check.
    path = "/api/admin/dishes/00000000-0000-0000-0000-000000000000/image"
    big = client.post(path, files={"file": ("x.jpg", b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024))})
    assert big.status_code == 413 and error_code(big) == "file_too_large"


def test_security_headers_on_api_and_pages(client):
    for path in ("/health", "/customer/"):
        headers = client.get(path).headers
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"


def test_static_files_revalidate_so_deploys_reach_customers(client):
    assert client.get("/customer/").headers["cache-control"] == "no-cache"
    assert client.get("/customer/customer.js").headers["cache-control"] == "no-cache"
