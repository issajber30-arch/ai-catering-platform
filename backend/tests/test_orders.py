import datetime as dt
import uuid
from decimal import Decimal

import pytest

from .test_security import error_code

TODAY = dt.date.today()
FUTURE = TODAY + dt.timedelta(days=10)


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
    assert order["requested_at"].startswith(f"{FUTURE}T10:00")
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


def test_delivery_fee_in_total(client, make_dish, order, zone, slot, admin):
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    patched = client.patch(
        f"/api/orders/{order['id']}",
        json={
            "version": 1,
            "fulfillment_type": "delivery",
            "delivery_address": "1 Herzl St",
            "delivery_zone_id": zone["id"],
        },
        headers=hdr(order),
    )
    assert patched.status_code == 200, patched.text
    done = put_item(client, patched.json(), make_dish(unit_price="100.00"), "1").json()
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
    assert started.status_code == 422
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


def test_delivery_requires_address_and_active_zone(client, admin, body, zone, slot):
    admin.patch(f"/api/admin/time-slots/{slot['id']}", json={"fulfillment_type": "delivery"})
    d = body | {"fulfillment_type": "delivery"}
    assert client.post("/api/orders", json=d).status_code == 422
    assert client.post("/api/orders", json=d | {"delivery_zone_id": zone["id"]}).status_code == 422
    assert client.post("/api/orders", json=d | {"delivery_address": "a"}).status_code == 422
    full = d | {"delivery_address": "1 Herzl", "delivery_zone_id": zone["id"]}
    assert client.post("/api/orders", json=full).status_code == 201
    admin.patch(f"/api/admin/delivery-zones/{zone['id']}", json={"is_active": False})
    assert client.post("/api/orders", json=full).status_code == 422
    admin.patch(f"/api/admin/delivery-zones/{zone['id']}", json={"is_active": True})
    assert client.post("/api/orders", json=full | {"delivery_zone_id": str(uuid.uuid4())}
                       ).status_code == 422  # fmt: skip


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
