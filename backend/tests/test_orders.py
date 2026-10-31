import datetime as dt
import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from .test_security import error_code

TODAY = dt.date.today()
FUTURE = TODAY + dt.timedelta(days=10)


@pytest.fixture(autouse=True)
def no_minimum(db):
    """Most tests use small orders; the food minimum has its own test."""
    db.execute(text("UPDATE business_settings SET min_food_total = 0"))
    db.commit()


@pytest.fixture
def slot(admin):
    body = {"fulfillment_type": "pickup", "start_time": "10:00", "end_time": "12:00"}
    return admin.post("/api/admin/time-slots", json=body).json()


@pytest.fixture
def zone(admin):
    return admin.post("/api/admin/delivery-zones", json={"name": "Haifa", "fee": "25.00"}).json()


@pytest.fixture
def body(slot):
    return {
        "customer": {"full_name": "Dana Levi", "email": "dana@example.com"},
        "event": {
            "event_type": "birthday",
            "event_date": str(FUTURE),
            "adults": 10,
            "children": 4,
            "vegetarian_guests": 3,
        },
        "fulfillment_type": "pickup",
        "time_slot_id": slot["id"],
    }


@pytest.fixture
def order(client, body):
    return new(client, body)


TOKENS = {}


def new(client, body):
    created = client.post("/api/orders", json=body).json()
    TOKENS[created["id"]] = created["access_token"]
    return created


def hdr(order):
    return {"X-Order-Token": TOKENS[order["id"]]}


def put_item(client, order, dish, quantity="2", version=None):
    return client.put(
        f"/api/orders/{order['id']}/items/{dish['id']}",
        json={"quantity": quantity, "version": version or order["version"]},
        headers=hdr(order),
    )


def submit(client, order, version):
    return client.post(
        f"/api/orders/{order['id']}/submit", json={"version": version}, headers=hdr(order)
    )


def test_create_returns_token_once(client, order):
    assert order["status"] == "draft" and order["version"] == 1
    assert len(order["access_token"]) >= 40
    assert order["total"] == "0.00" and order["items"] == []
    # Compare the instant in the business timezone; the DB may render it in UTC (CI) or local time.
    requested = dt.datetime.fromisoformat(order["requested_at"].replace("Z", "+00:00"))
    local = requested.astimezone(ZoneInfo("Asia/Jerusalem"))
    assert (local.date(), local.hour, local.minute) == (FUTURE, 10, 0)
    again = client.get(f"/api/orders/{order['id']}", headers=hdr(order))
    assert again.status_code == 200 and "access_token" not in again.json()
    assert again.json()["customer"]["full_name"] == "Dana Levi"


def test_event_types(client):
    assert "birthday" in client.get("/api/catalog/event-types").json()


def test_token_required_and_wrong_token_is_404(client, order, body):
    url = f"/api/orders/{order['id']}"
    for headers in ({}, {"X-Order-Token": "nope"}):
        response = client.get(url, headers=headers)
        assert response.status_code == 404 and error_code(response) == "not_found"
    unknown = client.get(f"/api/orders/{uuid.uuid4()}", headers=hdr(order))
    assert unknown.status_code == 404 and unknown.json() == client.get(url).json()


def test_other_customers_token_cannot_access(client, order, body):
    other = new(client, body)
    assert client.get(f"/api/orders/{order['id']}", headers=hdr(other)).status_code == 404
    assert client.get(f"/api/orders/{order['id']}/pricing", headers=hdr(other)).status_code == 404
    mine = client.get(f"/api/orders/{other['id']}", headers=hdr(other))
    assert mine.status_code == 200


def test_items_pricing_and_version(client, make_dish, order, zone, slot):
    tray = make_dish(unit_price="120.00")
    weight = make_dish(name_he="אורז", pricing_unit="per_weight", unit_price="89.90")
    first = put_item(client, order, tray).json()
    assert first["version"] == 2 and first["subtotal"] == "240.00"
    second = put_item(client, first, weight, "1.5").json()
    assert second["subtotal"] == "374.85" and second["total"] == "374.85"
    assert {i["name"] for i in second["items"]} == {"שניצל", "אורז"}
    changed = put_item(client, second, tray, "3").json()  # recalculated
    assert changed["subtotal"] == "494.85" and len(changed["items"]) == 2
    pricing = client.get(f"/api/orders/{order['id']}/pricing", headers=hdr(order)).json()
    assert pricing["total"] == "494.85" and pricing["currency"] == "ILS"
    removed = client.delete(
        f"/api/orders/{order['id']}/items/{weight['id']}?version={changed['version']}",
        headers=hdr(order),
    ).json()
    assert removed["subtotal"] == "360.00" and removed["version"] == changed["version"] + 1


def test_delivery_fee_legacy_zone(client, make_dish, order, zone, slot, admin, db):
    """Orders priced by zone before distance pricing keep their zone fee."""
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    patched = client.patch(
        f"/api/orders/{order['id']}",
        json={"version": 1, "fulfillment_type": "delivery", "delivery_address": "1 Herzl St"},
        headers=hdr(order),
    ).json()
    db.execute(
        text("UPDATE orders SET delivery_fee_estimated = false, delivery_zone_id = :z"),
        {"z": zone["id"]},
    )
    db.commit()
    done = put_item(client, patched, make_dish(unit_price="100.00"), "1").json()
    assert (done["subtotal"], done["delivery_fee"], done["total"]) == ("100.00", "25.00", "125.00")


def test_stale_version_conflict(client, make_dish, order):
    dish = make_dish()
    put_item(client, order, dish)
    stale = put_item(client, order, dish, "3")  # still version 1
    assert stale.status_code == 409 and error_code(stale) == "order_version_conflict"
    stale_delete = client.delete(
        f"/api/orders/{order['id']}/items/{dish['id']}?version=1", headers=hdr(order)
    )
    assert stale_delete.status_code == 409


def test_item_validation(client, make_dish, order, admin):
    dish = make_dish(min_quantity="2")
    off = make_dish(name_he="כבוי", is_available=False)
    for quantity in ("0", "-1", "100001", "abc", "1.999"):
        assert put_item(client, order, dish, quantity).status_code == 422
    assert put_item(client, order, dish, "1").status_code == 422  # below min_quantity
    assert put_item(client, order, off, "1").status_code == 422
    assert put_item(client, order, {"id": str(uuid.uuid4())}, "1").status_code == 404
    assert put_item(client, order, dish, "100000").status_code == 200


def test_mixed_currency_rejected(client, make_dish, order):
    first = put_item(client, order, make_dish(currency="ILS")).json()
    usd = make_dish(name_he="USD", currency="USD")
    response = put_item(client, first, usd)
    assert response.status_code == 422


def test_submit_snapshots_and_freezes(client, make_dish, admin, order):
    dish = make_dish(unit_price="120.00")
    current = put_item(client, order, dish).json()
    submitted = submit(client, current, current["version"])
    assert submitted.status_code == 200, submitted.text
    s = submitted.json()
    assert s["status"] == "pending_approval" and s["submitted_at"] and s["total"] == "240.00"
    admin.patch(f"/api/admin/dishes/{dish['id']}", json={"unit_price": "999.00", "name_he": "חדש"})
    after = client.get(f"/api/orders/{order['id']}", headers=hdr(order)).json()
    assert after["total"] == "240.00" and after["items"][0]["unit_price"] == "120.00"
    assert after["items"][0]["name"] == "שניצל"
    detail = admin.get(f"/api/admin/orders/{order['id']}").json()
    assert detail["total"] == "240.00" and detail["customer"]["email"] == "dana@example.com"


def test_edit_after_submit_conflicts(client, make_dish, order):
    dish = make_dish()
    current = put_item(client, order, dish).json()
    done = submit(client, current, current["version"]).json()
    for response in (
        put_item(client, done, dish, "5"),
        client.delete(
            f"/api/orders/{order['id']}/items/{dish['id']}?version={done['version']}",
            headers=hdr(order),
        ),
        client.patch(
            f"/api/orders/{order['id']}", json={"version": done["version"]}, headers=hdr(order)
        ),
        submit(client, order, done["version"]),
    ):
        assert response.status_code == 409 and error_code(response) == "invalid_transition"


def test_submit_rules(client, make_dish, admin, order):
    assert submit(client, order, 1).status_code == 422  # empty
    dish = make_dish()
    current = put_item(client, order, dish).json()
    admin.patch(f"/api/admin/dishes/{dish['id']}", json={"is_available": False})
    assert submit(client, current, current["version"]).status_code == 422
    admin.patch(f"/api/admin/dishes/{dish['id']}", json={"is_available": True})
    blocked = admin.post("/api/admin/blocked-dates", json={"date": str(FUTURE)})
    assert blocked.status_code == 201
    assert submit(client, current, current["version"]).status_code == 422
    stale = submit(client, current, 1)
    assert stale.status_code == 409 and error_code(stale) == "order_version_conflict"


def test_approve_reject_and_transitions(admin, client, make_dish, body):
    def pending():
        o = new(client, body)
        o = put_item(client, o, make_dish()).json()
        submit(client, o, o["version"])
        return o

    first, second = pending(), pending()
    base = "/api/admin/orders"
    draft = new(client, body)
    bad = admin.post(f"{base}/{draft['id']}/approve")
    assert bad.status_code == 409 and error_code(bad) == "invalid_transition"
    ok = admin.post(f"{base}/{first['id']}/approve", json={"note": "see you"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "approved" and ok.json()["decision_note"] == "see you"
    assert ok.json()["decided_at"]
    assert admin.post(f"{base}/{first['id']}/reject").status_code == 409
    assert admin.post(f"{base}/{first['id']}/approve").status_code == 409
    rejected = admin.post(f"{base}/{second['id']}/reject", json={"note": "full"})
    assert rejected.json()["status"] == "rejected"
    assert admin.post(f"{base}/{second['id']}/reject", json={"note": "x" * 1001}).status_code == 422
    seen = client.get(f"/api/orders/{first['id']}", headers=hdr(first)).json()
    assert seen["status"] == "approved"
    assert admin.post(f"{base}/{uuid.uuid4()}/approve").status_code == 404


def test_cancel_order(admin, client, make_dish, body):
    def pending():
        o = new(client, body)
        o = put_item(client, o, make_dish()).json()
        submit(client, o, o["version"])
        return o

    base = "/api/admin/orders"
    waiting, approved, rejected = pending(), pending(), pending()
    admin.post(f"{base}/{approved['id']}/approve", json={"note": "ok"})
    admin.post(f"{base}/{rejected['id']}/reject")
    draft = new(client, body)
    for o in (draft, rejected):
        r = admin.post(f"{base}/{o['id']}/cancel", json={"note": "x"})
        assert r.status_code == 409 and error_code(r) == "invalid_transition"
    for note in ("", "   ", "x" * 1001):
        assert admin.post(f"{base}/{waiting['id']}/cancel", json={"note": note}).status_code == 422
    assert admin.post(f"{base}/{waiting['id']}/cancel").status_code == 422
    done = admin.post(f"{base}/{approved['id']}/cancel", json={"note": "  sorry  "}).json()
    assert done["status"] == "cancelled" and done["cancel_note"] == "sorry"
    assert done["cancelled_at"] and done["decision_note"] == "ok" and done["decided_at"]
    again = admin.post(f"{base}/{approved['id']}/cancel", json={"note": "x"})
    assert again.status_code == 409
    assert admin.post(f"{base}/{waiting['id']}/cancel", json={"note": "no"}).status_code == 200
    seen = client.get(f"/api/orders/{approved['id']}", headers=hdr(approved)).json()
    assert seen["status"] == "cancelled" and seen["cancel_note"] == "sorry"
    edit = client.patch(f"/api/orders/{approved['id']}", headers=hdr(approved), json={"version": 9})
    assert edit.status_code == 409
    assert len(admin.get(f"{base}?status=cancelled").json()) == 2
    assert admin.post(f"{base}/{uuid.uuid4()}/cancel", json={"note": "x"}).status_code == 404


def test_admin_list_filter_and_order(admin, client, make_dish, body):
    a = new(client, body)
    b = new(client, body)
    o = put_item(client, b, make_dish()).json()
    submit(client, o, o["version"])
    rows = admin.get("/api/admin/orders").json()
    assert [r["id"] for r in rows] == [b["id"], a["id"]]  # newest first
    only = admin.get("/api/admin/orders?status=pending_approval").json()
    assert [r["id"] for r in only] == [b["id"]]
    assert only[0]["guests"] == 14 and only[0]["customer_name"] == "Dana Levi"
    assert admin.get("/api/admin/orders?status=bogus").status_code == 422


def test_recommendations(admin, client, make_dish, category, order):
    dish = make_dish()
    guest = make_dish(name_he="ארוחה", pricing_unit="per_guest")
    current = put_item(client, order, dish).json()
    current = put_item(client, current, guest, "1").json()
    url = f"/api/orders/{order['id']}/recommendations"
    recs = {r["dish_id"]: r for r in client.get(url, headers=hdr(order)).json()}
    assert recs[dish["id"]]["reason"] == "no_rule" and recs[dish["id"]]["recommended"] is None
    assert Decimal(recs[guest["id"]]["recommended"]) == 14
    rule = {"per_adult": "0.25", "per_child": "0.1", "round_step": "1"}
    assert admin.put(f"/api/admin/quantity-rules/{category['id']}", json=rule).status_code == 200
    recs = {r["dish_id"]: r for r in client.get(url, headers=hdr(order)).json()}
    assert Decimal(recs[dish["id"]]["recommended"]) == 3  # 10*0.25 + 4*0.1 = 2.9 -> 3, /1 dish
    assert client.get(url).status_code == 404


def test_quantity_rule_admin(admin, category):
    url = f"/api/admin/quantity-rules/{category['id']}"
    rule = {"per_adult": "0.5", "per_child": "0.25"}
    assert admin.put(url, json=rule).json()["round_step"] == "1.000"
    assert admin.put(url, json=rule | {"per_adult": "1"}).status_code == 200
    rows = admin.get("/api/admin/quantity-rules").json()
    assert len(rows) == 1 and rows[0]["per_adult"] == "1.000"
    for bad in ({"round_step": "0"}, {"per_child": "-1"}, {"per_adult": "x"}):
        assert admin.put(url, json=rule | bad).status_code == 422
    assert admin.put(f"/api/admin/quantity-rules/{uuid.uuid4()}", json=rule).status_code == 404
    assert admin.delete(url).status_code == 204
    assert admin.delete(url).status_code == 404


def set_settings(admin, **changes):
    row = admin.get("/api/admin/settings").json() | changes
    return admin.put("/api/admin/settings", json=row)


def test_date_rules(client, admin, body, slot):
    def post(**event):
        return client.post("/api/orders", json=body | {"event": body["event"] | event})

    assert post(event_date=str(TODAY - dt.timedelta(days=1))).status_code == 422
    early = admin.post(
        "/api/admin/time-slots",
        json={"fulfillment_type": "pickup", "start_time": "00:00", "end_time": "00:30"},
    ).json()
    started = client.post(
        "/api/orders",
        json=body
        | {"event": body["event"] | {"event_date": str(TODAY)}, "time_slot_id": early["id"]},
    )
    assert started.status_code == 422 and "notice" in started.json()["error"]["message"]
    set_settings(admin, lead_time_days=0)
    started = client.post(
        "/api/orders",
        json=body
        | {"event": body["event"] | {"event_date": str(TODAY)}, "time_slot_id": early["id"]},
    )
    assert started.status_code == 422 and "already started" in started.json()["error"]["message"]
    admin.post("/api/admin/blocked-dates", json={"date": str(FUTURE)})
    blocked = post()
    assert blocked.status_code == 422 and error_code(blocked) == "validation_error"


def test_slot_rules(client, admin, body, slot):
    other_day = (FUTURE.weekday() + 1) % 7
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"weekday": other_day})
    assert client.post("/api/orders", json=body).status_code == 422
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"weekday": FUTURE.weekday()})
    assert client.post("/api/orders", json=body).status_code == 201
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"is_active": False})
    assert client.post("/api/orders", json=body).status_code == 422
    unknown = body | {"time_slot_id": str(uuid.uuid4())}
    assert client.post("/api/orders", json=unknown).status_code == 422
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"is_active": True})
    delivery = body | {"fulfillment_type": "delivery", "delivery_address": "x"}
    assert client.post("/api/orders", json=delivery).status_code == 422  # wrong slot type + no zone


def test_delivery_requires_address(client, admin, body, slot):
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    d = body | {"fulfillment_type": "delivery"}
    assert client.post("/api/orders", json=d).status_code == 422
    assert client.post("/api/orders", json=d | {"delivery_address": "   "}).status_code == 422
    assert client.post("/api/orders", json=d | {"delivery_address": "x" * 501}).status_code == 422
    assert client.post("/api/orders", json=d | {"delivery_address": "a"}).status_code == 201


def test_guest_validation(client, body):
    def post(**event):
        return client.post("/api/orders", json=body | {"event": body["event"] | event})

    assert post(adults=0, children=0).status_code == 422
    assert post(adults=0, children=1, vegetarian_guests=0).status_code == 201
    assert post(adults=-1).status_code == 422
    assert post(vegan_guests=15).status_code == 422  # > 14 guests
    assert post(vegetarian_guests=14).status_code == 201  # boundary: equal to total
    assert post(restricted_guests=15).status_code == 422
    assert post(event_type="wedding").status_code == 422
    assert post(adults=100001).status_code == 422
    assert post(dietary_notes="x" * 2001).status_code == 422


def test_customer_validation(client, body):
    def post(**customer):
        return client.post("/api/orders", json=body | {"customer": customer})

    assert post(full_name="x" * 1000, email="a@b.co").status_code == 422
    assert post(full_name="  ", email="a@b.co").status_code == 422
    assert post(full_name="Dana").status_code == 422  # no contact
    assert post(full_name="Dana", email="not-an-email").status_code == 422
    assert post(full_name="Dana", phone="050-1234567").status_code == 201
    assert client.post("/api/orders", json={}).status_code == 422


def test_patch_event(client, order):
    event = {"event_type": "shabbat", "event_date": str(FUTURE), "adults": 20, "children": 0}
    ok = client.patch(
        f"/api/orders/{order['id']}", json={"version": 1, "event": event}, headers=hdr(order)
    )
    assert ok.status_code == 200 and ok.json()["event"]["adults"] == 20
    assert ok.json()["version"] == 2
    bad = client.patch(
        f"/api/orders/{order['id']}",
        json={"version": 2, "event": event | {"vegan_guests": 21}},
        headers=hdr(order),
    )
    assert bad.status_code == 422


def test_lang_fallback(client, make_dish, order):
    dish = make_dish(name_en="Schnitzel")
    current = put_item(client, order, dish).json()
    en = client.get(f"/api/orders/{order['id']}?lang=en", headers=hdr(order)).json()
    ar = client.get(f"/api/orders/{order['id']}?lang=ar", headers=hdr(order)).json()
    assert (en["items"][0]["name"], ar["items"][0]["name"]) == ("Schnitzel", "שניצל")
    assert current["items"][0]["name"] == "שניצל"


def test_referenced_dish_cannot_be_deleted(admin, client, make_dish, order):
    dish = make_dish()
    put_item(client, order, dish)
    assert admin.delete(f"/api/admin/dishes/{dish['id']}").status_code == 409


def test_total_too_large_is_422(client, make_dish, order):
    dish = make_dish(unit_price="99999.00")
    response = put_item(client, order, dish, quantity="100000")
    assert response.status_code == 422


def test_submit_rechecks_min_quantity(client, make_dish, admin, order):
    dish = make_dish()
    assert put_item(client, order, dish, quantity="2").status_code == 200
    admin.patch(f"/api/admin/dishes/{dish['id']}", json={"min_quantity": "5"})
    assert submit(client, order, 2).status_code == 422


def test_requested_at_has_timezone(order):
    assert order["requested_at"].endswith(("+02:00", "+03:00", "Z", "+00:00"))


def test_public_delivery_zones_hide_inactive_and_definition(client, admin, zone):
    off = admin.post("/api/admin/delivery-zones", json={"name": "Eilat", "fee": "90.00"}).json()
    admin.patch(f"/api/admin/delivery-zones/{off['id']}", json={"is_active": False})
    assert client.get("/api/delivery-zones").json() == [
        {"id": zone["id"], "name": "Haifa", "fee": "25.00"}
    ]


# ---- business rules (lead time, minimum, kashrut warning, distance fee)
KITCHEN = (31.7683, 35.2137)
NEAR = (KITCHEN[0] + 0.1619, KITCHEN[1])  # ~18.0 km north
FAR = (KITCHEN[0] + 0.3640, KITCHEN[1])  # ~40.5 km north


def post_on(client, body, day):
    return client.post(
        "/api/orders", json=body | {"event": body["event"] | {"event_date": str(day)}}
    )


def test_lead_time(client, body):
    refused = post_on(client, body, TODAY + dt.timedelta(days=6))
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == "Events need at least 7 days' notice"
    assert post_on(client, body, TODAY + dt.timedelta(days=7)).status_code == 201


def test_food_minimum(client, admin, make_dish, order):
    set_settings(admin, min_food_total="500.00")
    cheap = make_dish(unit_price="499.99")
    current = put_item(client, order, cheap, "1").json()
    refused = submit(client, current, current["version"])
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == "Food total must reach ₪500"
    ok = put_item(client, current, make_dish(name_he="x", unit_price="0.01"), "1").json()
    assert ok["subtotal"] == "500.00"
    assert submit(client, ok, ok["version"]).status_code == 200


def test_minimum_excludes_delivery(client, admin, make_dish, order, slot, places):
    set_settings(admin, min_food_total="500.00")
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    places["Near"] = NEAR
    patched = client.patch(
        f"/api/orders/{order['id']}",
        json={"version": 1, "fulfillment_type": "delivery", "delivery_address": "Near"},
        headers=hdr(order),
    ).json()
    current = put_item(client, patched, make_dish(unit_price="450.00"), "1").json()
    assert current["delivery_fee"] == "122.00" and current["total"] == "572.00"
    assert submit(client, current, current["version"]).status_code == 422


def test_kashrut_warning(client, admin, make_dish, order):
    def dish(name, kashrut):
        d = make_dish(name_he=name)
        body = {"kashrut_class": kashrut, "allergens": []}
        assert admin.put(f"/api/admin/dishes/{d['id']}/dietary", json=body).status_code == 200
        return d

    meat, dairy, pareve = dish("m", "meat"), dish("d", "dairy"), dish("p", "pareve")
    unknown = make_dish(name_he="u")  # no dietary row at all
    cur = put_item(client, order, meat).json()
    assert cur["warnings"] == []
    cur = put_item(client, cur, pareve).json()
    cur = put_item(client, cur, unknown).json()
    assert cur["warnings"] == []
    cur = put_item(client, cur, dairy).json()
    assert cur["warnings"] == ["mixes_meat_dairy"]
    cur = client.delete(
        f"/api/orders/{order['id']}/items/{meat['id']}?version={cur['version']}", headers=hdr(order)
    ).json()
    assert cur["warnings"] == []


def test_fee_and_distance_maths():
    from decimal import Decimal as D

    from app.services.geo import fee_for, haversine_km

    assert haversine_km(*KITCHEN, *NEAR) == D("18.0")
    assert fee_for(D("18.0"), D("50"), D("4")) == D("122.00")
    assert fee_for(D("0.1"), D("50.00"), D("4.00")) == D("50.40")
    assert fee_for(D("1.1"), D("0"), D("0.05")) == D("0.06")  # 0.055 rounds half up


def delivery_order(client, admin, body, slot, address):
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    response = client.post(
        "/api/orders", json=body | {"fulfillment_type": "delivery", "delivery_address": address}
    )
    if response.status_code == 201:
        TOKENS[response.json()["id"]] = response.json()["access_token"]
    return response


def test_delivery_fee_from_distance(client, admin, body, slot, places):
    places["Near"] = NEAR
    created = delivery_order(client, admin, body, slot, "Near").json()
    assert (created["delivery_km"], created["delivery_fee"]) == ("18.00", "122.00")
    assert created["delivery_fee_estimated"] is False and created["total"] == "122.00"
    back = client.patch(
        f"/api/orders/{created['id']}",
        json={"version": 1, "fulfillment_type": "pickup"},
        headers={"X-Order-Token": created["access_token"]},
    )
    # pickup is served by a delivery slot only if it matches; the slot type is wrong here
    assert back.status_code == 422


def test_pickup_clears_distance(client, admin, body, slot, places, db):
    places["Near"] = NEAR
    pickup_slot = slot
    delivery_slot = admin.post(
        "/api/admin/time-slots",
        json={"fulfillment_type": "delivery", "start_time": "10:00", "end_time": "12:00"},
    ).json()
    created = client.post(
        "/api/orders",
        json=body
        | {"fulfillment_type": "delivery", "delivery_address": "Near",
           "time_slot_id": delivery_slot["id"]},
    ).json()  # fmt: skip
    assert created["delivery_km"] == "18.00"
    back = client.patch(
        f"/api/orders/{created['id']}",
        json={"version": 1, "fulfillment_type": "pickup", "time_slot_id": pickup_slot["id"]},
        headers={"X-Order-Token": created["access_token"]},
    ).json()
    assert (back["delivery_km"], back["delivery_fee"], back["delivery_address"]) == (
        None, "0.00", None,
    )  # fmt: skip
    assert back["delivery_fee_estimated"] is False


def test_too_far(client, admin, body, slot, places):
    places["Far"] = FAR
    refused = delivery_order(client, admin, body, slot, "Far")
    assert refused.status_code == 422
    assert refused.json()["error"]["message"] == (
        "Delivery isn't available this far (max 40 km); choose pickup."
    )
    quote = client.post("/api/delivery-quote", json={"address": "Far"}).json()
    assert quote["found"] and quote["too_far"] and quote["fee"] is None


def test_max_km_boundary(admin, client, places):
    places["Near"] = NEAR
    set_settings(admin, delivery_max_km="18.00")
    assert client.post("/api/delivery-quote", json={"address": "Near"}).json()["too_far"] is False
    set_settings(admin, delivery_max_km="17.90")
    assert client.post("/api/delivery-quote", json={"address": "Near"}).json()["too_far"] is True


def test_address_not_found_is_estimated(client, admin, make_dish, body, slot):
    created = delivery_order(client, admin, body, slot, "Nowhere 1").json()
    assert created["delivery_fee"] is None and created["delivery_fee_estimated"] is True
    assert created["delivery_km"] is None
    token = {"X-Order-Token": created["access_token"]}
    current = put_item(client, created, make_dish(unit_price="100.00"), "1").json()
    assert current["delivery_fee"] is None and current["total"] == "100.00"
    done = submit(client, current, current["version"])
    assert done.status_code == 200 and done.json()["delivery_fee"] is None
    assert done.json()["delivery_fee_estimated"] is True
    assert client.get(f"/api/orders/{created['id']}", headers=token).json()["total"] == "100.00"


def test_geocode_cache(client, places, geo_calls):
    places["Near"] = NEAR
    first = client.post("/api/delivery-quote", json={"address": "Near"}).json()
    again = client.post("/api/delivery-quote", json={"address": "  NEAR "}).json()
    assert first == again and first["fee"] == "122.00" and len(geo_calls) == 1
    client.post("/api/delivery-quote", json={"address": "Nowhere"})
    client.post("/api/delivery-quote", json={"address": "nowhere"})  # not-found is cached too
    assert len(geo_calls) == 2


def test_delivery_quote_validation(client):
    for address in ("", "x" * 501):
        assert client.post("/api/delivery-quote", json={"address": address}).status_code == 422
    assert client.post("/api/delivery-quote", json={}).status_code == 422
    assert client.get("/api/delivery-quote").status_code in (404, 405)  # static mount answers
    blank = client.post("/api/delivery-quote", json={"address": "   "}).json()
    assert blank["found"] is False


def test_public_settings(client):
    assert client.get("/api/public-settings").json() == {
        "lead_time_days": 7, "edit_cutoff_hours": 4, "min_food_total": "0.00", "max_km": "40.00",
    }  # fmt: skip


def test_admin_settings(admin, client, places, geo_calls):
    got = admin.get("/api/admin/settings").json()
    assert got["lead_time_days"] == 7 and got["delivery_base_fee"] == "50.00"
    assert got["kitchen_address"] == "Jerusalem" and got["kitchen_lat"] == 31.7683
    ok = set_settings(admin, lead_time_days=3, delivery_per_km="5.50")
    assert ok.status_code == 200 and ok.json()["delivery_per_km"] == "5.50"
    assert geo_calls == []  # unchanged kitchen address is not geocoded
    for bad in (
        {"lead_time_days": -1}, {"lead_time_days": 366}, {"min_food_total": "-1"},
        {"delivery_base_fee": "-0.01"}, {"delivery_per_km": "-1"}, {"delivery_max_km": "-1"},
        {"delivery_max_km": "501"}, {"kitchen_address": ""}, {"kitchen_address": "x" * 301},
        {"lead_time_days": "abc"},
    ):  # fmt: skip
        assert set_settings(admin, **bad).status_code == 422, bad
    assert admin.put("/api/admin/settings", json={"lead_time_days": 1}).status_code == 422
    assert admin.get("/api/admin/settings").json()["lead_time_days"] == 3


def test_admin_settings_kitchen_geocode(admin, places):
    places["Haifa"] = (32.794, 34.9896)
    ok = set_settings(admin, kitchen_address="Haifa")
    assert ok.status_code == 200 and ok.json()["kitchen_lat"] == 32.794
    failed = set_settings(admin, kitchen_address="Atlantis", lead_time_days=1)
    assert failed.status_code == 422
    after = admin.get("/api/admin/settings").json()
    assert (after["kitchen_address"], after["lead_time_days"]) == ("Haifa", 7)  # nothing saved


def test_admin_order_detail_has_rule_fields(admin, client, order):
    detail = admin.get(f"/api/admin/orders/{order['id']}").json()
    assert detail["warnings"] == [] and detail["delivery_fee_estimated"] is False


def test_geocode_failure_is_not_cached(db):
    from app.services import geo

    calls = []

    def flaky(address):
        calls.append(address)
        if len(calls) == 1:
            raise geo.GeocodeError
        return (31.78, 35.22)

    assert geo.locate(db, flaky, "Jaffa St 1, Jerusalem") is None
    assert geo.locate(db, flaky, "Jaffa St 1, Jerusalem") == (31.78, 35.22)
    assert len(calls) == 2


def test_geocoder_lock_timeout_is_a_failure_not_a_hang(monkeypatch):
    from types import SimpleNamespace

    from app.services import geo

    monkeypatch.setattr(geo, "_lock", SimpleNamespace(acquire=lambda timeout: False))
    with pytest.raises(geo.GeocodeError):
        geo.nominatim("anything")


def test_geocoder_falls_back_to_second_provider_on_error(monkeypatch):
    import httpx

    from app.services import geo

    def refused(_address):
        raise httpx.HTTPStatusError("403", request=None, response=None)

    calls = []
    monkeypatch.setattr(geo, "PROVIDERS", (
        ("first", refused),
        ("second", lambda a: calls.append(a) or (31.78, 35.21)),
    ))  # fmt: skip
    assert geo.nominatim("Jaffa St 97") == (31.78, 35.21)
    assert calls == ["Jaffa St 97"]


def test_geocoder_not_found_does_not_fall_back(monkeypatch):
    from app.services import geo

    second = []
    monkeypatch.setattr(geo, "PROVIDERS", (
        ("first", lambda a: None),
        ("second", lambda a: second.append(a) or (1.0, 1.0)),
    ))  # fmt: skip
    assert geo.nominatim("nowhere") is None
    assert second == []


def test_geocoder_all_providers_failing_raises(monkeypatch):
    from app.services import geo

    def boom(_address):
        raise ValueError("bad json")

    monkeypatch.setattr(geo, "PROVIDERS", (("first", boom), ("second", boom)))
    with pytest.raises(geo.GeocodeError):
        geo.nominatim("x")


def test_order_rate_limit_per_ip(client, body):
    def create(xff):
        return client.post("/api/orders", json=body, headers={"X-Forwarded-For": xff})

    for _ in range(10):
        assert create("9.9.9.9").status_code == 201
    r = create("9.9.9.9")
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) > 0
    assert create("8.8.8.8").status_code == 201  # rightmost IP differs: counted separately
    assert create("1.1.1.1, 9.9.9.9").status_code == 429  # spoofed leftmost entry doesn't help
    assert create("1.1.1.1, 7.7.7.7").status_code == 201


def test_quote_rate_limit(client):
    for _ in range(30):
        assert client.post("/api/delivery-quote", json={"address": "  "}).status_code == 200
    r = client.post("/api/delivery-quote", json={"address": "  "})
    assert r.status_code == 429 and "Retry-After" in r.headers


def test_client_ip_behind_render_proxies():
    from types import SimpleNamespace

    from app.core.ratelimit import client_ip

    def req(headers, host="10.197.204.143"):
        return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))

    # Render's internal hop (10.x) after the visitor is skipped, not used as the key
    assert client_ip(req({"x-forwarded-for": "81.218.40.7, 10.197.204.143"})) == "81.218.40.7"
    # A forged entry further left can't replace the real visitor
    assert client_ip(req({"x-forwarded-for": "1.1.1.1, 81.218.40.7, 10.0.0.5"})) == "81.218.40.7"
    # The edge's own header wins when present
    assert client_ip(req({"cf-connecting-ip": "77.137.5.4",
                          "x-forwarded-for": "81.218.40.7"})) == "77.137.5.4"  # fmt: skip
    # Garbage in the edge header is ignored; local development falls back to the socket
    assert client_ip(req({"cf-connecting-ip": "not-an-ip"}, host="127.0.0.1")) == "127.0.0.1"


# ---- customer edit window (reopen)
def reopen(client, order, version):
    return client.post(
        f"/api/orders/{order['id']}/reopen", json={"version": version}, headers=hdr(order)
    )


def submitted(client, make_dish, body):
    o = put_item(client, new(client, body), make_dish()).json()
    return submit(client, o, o["version"]).json()


def test_reopen_from_pending_and_approved(client, admin, make_dish, body):
    for approve in (False, True):
        o = submitted(client, make_dish, body)
        first = o["first_submitted_at"]
        assert first and first == o["submitted_at"]
        if approve:
            admin.post(f"/api/admin/orders/{o['id']}/approve", json={"note": "ok"})
            o = client.get(f"/api/orders/{o['id']}", headers=hdr(o)).json()
        r = reopen(client, o, o["version"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "draft" and d["version"] == o["version"] + 1
        assert d["submitted_at"] is None and d["decided_at"] is None and d["decision_note"] is None
        assert d["first_submitted_at"] == first and d["reopened_at"]
        assert admin.get(f"/api/admin/orders/{o['id']}").json()["reopened_at"]
        again = submit(client, d, d["version"])  # same date, 10 days out
        assert again.status_code == 200 and again.json()["status"] == "pending_approval"
        assert again.json()["first_submitted_at"] == first


def test_reopen_refused(client, admin, make_dish, body, db):
    draft = new(client, body)
    r = reopen(client, draft, draft["version"])
    assert r.status_code == 409 and error_code(r) == "invalid_transition"
    rejected, cancelled, late = (submitted(client, make_dish, body) for _ in range(3))
    admin.post(f"/api/admin/orders/{rejected['id']}/reject")
    admin.post(f"/api/admin/orders/{cancelled['id']}/cancel", json={"note": "x"})
    for o in (rejected, cancelled):
        assert reopen(client, o, o["version"] + 1).status_code == 409

    def move(hours):
        t = dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)
        sql = text("UPDATE orders SET requested_at = :t WHERE id = :i")
        db.execute(sql, {"t": t, "i": late["id"]})
        db.commit()

    move(3)
    r = reopen(client, late, late["version"])
    assert r.status_code == 409 and error_code(r) == "invalid_transition"
    assert r.json()["error"]["message"] == "Changes are closed 4 hours before the event"
    move(5)
    assert reopen(client, late, late["version"]).status_code == 200


def test_reopen_version_conflict_and_token(client, make_dish, body):
    o = submitted(client, make_dish, body)
    stale = reopen(client, o, o["version"] + 5)
    assert stale.status_code == 409 and error_code(stale) == "order_version_conflict"
    assert client.post(f"/api/orders/{o['id']}/reopen", json={"version": 2}).status_code == 404


def test_reopen_date_rules(client, make_dish, body, db):
    o = submitted(client, make_dish, body)
    near = TODAY + dt.timedelta(days=3)  # the event is now 3 days out
    db.execute(text("UPDATE events SET event_date = :d"), {"d": near})
    at = dt.datetime.combine(near, dt.time(10), tzinfo=ZoneInfo("Asia/Jerusalem"))
    db.execute(text("UPDATE orders SET requested_at = :t"), {"t": at})
    db.commit()
    d = reopen(client, o, o["version"]).json()
    assert submit(client, d, d["version"]).status_code == 200  # original date stays editable
    o = client.get(f"/api/orders/{o['id']}", headers=hdr(o)).json()
    d = reopen(client, o, o["version"]).json()
    event = {**body["event"], "event_date": str(near + dt.timedelta(days=1))}
    moved = client.patch(
        f"/api/orders/{o['id']}", json={"version": d["version"], "event": event}, headers=hdr(o)
    )
    assert moved.status_code == 422 and "notice" in moved.json()["error"]["message"]
    soon = body | {"event": body["event"] | {"event_date": str(near)}}
    assert client.post("/api/orders", json=soon).status_code == 422  # new orders: full lead time


def test_edit_cutoff_setting(admin, client):
    assert admin.get("/api/admin/settings").json()["edit_cutoff_hours"] == 4
    assert client.get("/api/public-settings").json()["edit_cutoff_hours"] == 4
    assert set_settings(admin, edit_cutoff_hours=24).status_code == 200
    for bad in (-1, 169, "x"):
        assert set_settings(admin, edit_cutoff_hours=bad).status_code == 422
