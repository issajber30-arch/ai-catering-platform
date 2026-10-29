import datetime as dt
import uuid

from .test_security import error_code


def dietary(admin, dish_id, **body):
    response = admin.put(f"/api/admin/dishes/{dish_id}/dietary", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def names(client, query=""):
    return {d["name_he"] for d in client.get(f"/api/catalog/dishes{query}").json()}


def test_public_catalog_needs_no_token(client, db):
    assert client.get("/api/catalog/categories").json() == []
    assert client.get("/api/catalog/dishes").json() == []


def test_dietary_filters(admin, make_dish):
    vegan = make_dish(name_he="סלט")
    dairy = make_dish(name_he="גבינות")
    meat = make_dish(name_he="בשר")
    make_dish(name_he="לא ידוע")
    dietary(admin, vegan["id"], is_vegan=True, is_vegetarian=True, kashrut_class="pareve")
    dietary(admin, dairy["id"], is_vegan=False, is_vegetarian=True, kashrut_class="dairy")
    dietary(admin, meat["id"], is_vegan=False, is_vegetarian=False, kashrut_class="meat")

    assert names(admin, "?vegan=true") == {"סלט"}
    assert names(admin, "?vegetarian=true") == {"סלט", "גבינות"}
    assert names(admin, "?kashrut=meat") == {"בשר"}
    assert names(admin, "?vegan=false&kashrut=dairy") == {"גבינות"}
    assert len(names(admin)) == 4
    assert admin.get("/api/catalog/dishes?kashrut=bogus").status_code == 422


def test_unknown_dietary_is_null_never_false(admin, make_dish):
    dish = make_dish()
    assert dish["dietary"] == {"kashrut_class": None, "is_vegetarian": None, "is_vegan": None}
    assert all(a["status"] == "unknown" for a in dish["allergens"]) and dish["allergens"]
    listed = admin.get("/api/catalog/dishes").json()[0]
    assert listed["dietary"]["is_vegan"] is None

    dietary(admin, dish["id"], is_vegan=True)  # vegetarian left null
    detail = admin.get(f"/api/catalog/dishes/{dish['id']}").json()
    assert detail["dietary"] == {"kashrut_class": None, "is_vegetarian": None, "is_vegan": True}


def test_allergen_statuses_and_missing_rows(admin, make_dish):
    dish = make_dish()
    first, second = dish["allergens"][0], dish["allergens"][1]
    detail = dietary(admin, dish["id"], allergens=[{"allergen_id": first["allergen_id"],
                                                    "status": "free"}])  # fmt: skip
    status = {a["allergen_id"]: a["status"] for a in detail["allergens"]}
    assert status[first["allergen_id"]] == "free"
    assert status[second["allergen_id"]] == "unknown"
    bad = admin.put(f"/api/admin/dishes/{dish['id']}/dietary",
                    json={"allergens": [{"allergen_id": 9999, "status": "free"}]})  # fmt: skip
    assert bad.status_code == 422


def test_hebrew_name_required(admin, category):
    base = {"category_id": category["id"], "pricing_unit": "per_item", "unit_price": "5"}
    for body in (base, base | {"name_he": ""}, base | {"name_he": "  "}, base | {"name_en": "x"}):
        response = admin.post("/api/admin/dishes", json=body)
        assert response.status_code == 422
        assert error_code(response) == "validation_error"
    assert admin.post("/api/admin/categories", json={"name_en": "Mains"}).status_code == 422


def test_language_fallback(admin, make_dish):
    make_dish(name_he="שניצל", name_en="Schnitzel", description_he="תיאור")
    make_dish(name_he="חומוס")
    by_he = {d["name_he"]: d for d in admin.get("/api/catalog/dishes?lang=en").json()}
    assert by_he["שניצל"]["name"] == "Schnitzel"
    assert by_he["חומוס"]["name"] == "חומוס"  # no English -> Hebrew
    assert by_he["שניצל"]["description"] == "תיאור"
    ar = admin.get("/api/catalog/dishes?lang=ar").json()
    assert {d["name"] for d in ar} == {"שניצל", "חומוס"}
    assert admin.get("/api/catalog/dishes?lang=fr").status_code == 422
    assert admin.get("/api/catalog/categories?lang=en").json()[0]["name"] == "עיקריות"


def test_unavailable_dish_hidden_publicly(admin, make_dish):
    dish = make_dish(is_available=False)
    assert names(admin) == set()
    assert admin.get(f"/api/catalog/dishes/{dish['id']}").status_code == 404
    assert len(admin.get("/api/admin/dishes").json()) == 1


def test_inactive_category_hidden_publicly(admin, category):
    admin.patch(f"/api/admin/categories/{category['id']}", json={"is_active": False})
    assert admin.get("/api/catalog/categories").json() == []


def test_category_delete_conflict(admin, category, make_dish):
    dish = make_dish()
    response = admin.delete(f"/api/admin/categories/{category['id']}")
    assert response.status_code == 409
    assert error_code(response) == "conflict"
    assert admin.delete(f"/api/admin/dishes/{dish['id']}").status_code == 204
    assert admin.delete(f"/api/admin/categories/{category['id']}").status_code == 204


def test_negative_price_422(admin, category, make_dish):
    body = {"category_id": category["id"], "name_he": "x", "pricing_unit": "per_item"}
    assert admin.post("/api/admin/dishes", json=body | {"unit_price": "-1"}).status_code == 422
    dish = make_dish()
    patch = admin.patch(f"/api/admin/dishes/{dish['id']}", json={"unit_price": "-0.01"})
    assert patch.status_code == 422


def test_huge_name_rejected_without_echo(admin, category):
    body = {"category_id": category["id"], "name_he": "א" * 10_000,
            "pricing_unit": "per_item", "unit_price": "5"}  # fmt: skip
    response = admin.post("/api/admin/dishes", json=body)
    assert response.status_code == 422
    assert "אאאא" not in response.text


def test_patch_cannot_null_required_fields(admin, make_dish):
    dish = make_dish()
    for field in ("name_he", "unit_price", "pricing_unit"):
        assert admin.patch(f"/api/admin/dishes/{dish['id']}", json={field: None}).status_code == 422
    ok = admin.patch(f"/api/admin/dishes/{dish['id']}", json={"name_en": None, "unit_price": "9.5"})
    assert ok.status_code == 200 and ok.json()["unit_price"] == "9.50"


def test_currency_defaults_to_ils_and_prices_are_strings(make_dish):
    dish = make_dish()
    assert dish["currency"] == "ILS"
    assert dish["unit_price"] == "120.00"


def test_not_found_and_bad_ids(admin):
    missing = admin.get(f"/api/catalog/dishes/{uuid.uuid4()}")
    assert missing.status_code == 404 and error_code(missing) == "not_found"
    assert admin.get("/api/catalog/dishes/not-a-uuid").status_code == 422
    orphan = {"category_id": str(uuid.uuid4()), "name_he": "x"}
    orphan |= {"pricing_unit": "per_item", "unit_price": "1"}
    assert admin.post("/api/admin/dishes", json=orphan).status_code == 404
    assert admin.get("/api/nope").status_code == 404


def test_upload_accepts_real_images(admin, make_dish, uploads):
    dish = make_dish()
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    webp = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 100
    for data in (jpeg, png, webp):
        files = {"file": ("../../evil.exe", data, "application/x-msdownload")}
        response = admin.post(f"/api/admin/dishes/{dish['id']}/image", files=files)
        assert response.status_code == 200, response.text
        assert response.json()["image_path"].startswith("fake-")  # name is server generated
    assert [k for k, _ in uploads] == ["jpeg", "png", "webp"]


def test_upload_rejects_renamed_exe_empty_and_big(admin, make_dish, uploads):
    dish = make_dish()
    url = f"/api/admin/dishes/{dish['id']}/image"
    exe = admin.post(url, files={"file": ("cat.jpg", b"MZ\x90\x00" + b"0" * 50, "image/jpeg")})
    assert exe.status_code == 415 and error_code(exe) == "unsupported_media_type"
    assert admin.post(url, files={"file": ("a.png", b"", "image/png")}).status_code == 415
    six_mb = b"\xff\xd8\xff" + b"0" * (6 * 1024 * 1024)
    big = admin.post(url, files={"file": ("big.jpg", six_mb, "image/jpeg")})
    assert big.status_code == 413 and error_code(big) == "file_too_large"
    assert admin.post(url).status_code == 422  # no file
    assert uploads == []


def test_public_config_has_no_service_key(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "supabase_service_role_key", "SECRET-VALUE")
    body = client.get("/api/public-config").json()
    assert set(body) == {"supabase_url", "supabase_anon_key"}
    assert "SECRET-VALUE" not in str(body)


def test_blocked_date_in_availability(admin):
    day = dt.date.today() + dt.timedelta(days=3)
    assert admin.post("/api/admin/blocked-dates", json={"date": str(day)}).status_code == 201
    assert admin.post("/api/admin/blocked-dates", json={"date": str(day)}).status_code == 409
