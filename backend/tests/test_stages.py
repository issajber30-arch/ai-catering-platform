# ruff: noqa: F811  (imported fixtures are used as arguments)
from sqlalchemy import text

from .test_orders import (  # noqa: F401  (fixtures)
    body,
    hdr,
    no_minimum,
    order,
    reopen,
    slot,
    submitted,
    zone,
)

ADV = "/api/admin/orders/{}/advance"


def advance(admin, o, version=None):
    return admin.post(ADV.format(o["id"]), json={"version": version or o["version"]})


def approved(admin, client, make_dish, body):
    o = submitted(client, make_dish, body)
    return admin.post(f"/api/admin/orders/{o['id']}/approve", json={}).json()


def walk(admin, o, steps):
    for status in steps:
        r = advance(admin, o)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["status"] == status
    return o


def test_pickup_path(admin, client, make_dish, body):
    o = walk(admin, approved(admin, client, make_dish, body),
             ["in_kitchen", "ready_for_pickup", "delivered"])  # fmt: skip
    assert o["kitchen_at"] and o["dispatched_at"] and o["delivered_at"] and o["rating"] is None
    assert o["version"] >= 4


def test_delivery_path(admin, client, make_dish, body, db):
    o = approved(admin, client, make_dish, body)
    db.execute(text("UPDATE orders SET fulfillment_type = 'delivery', delivery_address = 'x'"))
    db.commit()
    walk(admin, o, ["in_kitchen", "out_for_delivery", "delivered"])


def test_illegal_advances(admin, client, make_dish, body):
    draft = client.post("/api/orders", json=body).json()
    pending = submitted(client, make_dish, body)
    rejected = submitted(client, make_dish, body)
    admin.post(f"/api/admin/orders/{rejected['id']}/reject", json={})
    cancelled = submitted(client, make_dish, body)
    admin.post(f"/api/admin/orders/{cancelled['id']}/cancel", json={"note": "x"})
    done = walk(admin, approved(admin, client, make_dish, body),
                ["in_kitchen", "ready_for_pickup", "delivered"])  # fmt: skip
    for o in (draft, pending, rejected, cancelled, done):
        cur = admin.get(f"/api/admin/orders/{o['id']}").json()
        r = advance(admin, cur)
        assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"


def test_advance_unknown_and_version_conflict(admin, client, make_dish, body):
    assert admin.post(ADV.format("0" * 8 + "-0000-0000-0000-" + "0" * 12), json={"version": 1})\
        .status_code == 404  # fmt: skip
    o = approved(admin, client, make_dish, body)
    r = advance(admin, o, o["version"] - 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "order_version_conflict"


def test_reopen_and_cancel_refused_after_kitchen(admin, client, make_dish, body):
    o = walk(admin, approved(admin, client, make_dish, body), ["in_kitchen"])
    r = reopen(client, o, o["version"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    r = admin.post(f"/api/admin/orders/{o['id']}/cancel", json={"note": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"


def test_safety_car(admin, client):
    anon = type(client)(client.app)
    assert client.get("/api/public-settings").json()["safety_car"] is False
    assert anon.put("/api/admin/safety-car", json={"on": True}).status_code == 401
    assert admin.put("/api/admin/safety-car", json={"on": True}).json() == {"safety_car": True}
    assert client.get("/api/public-settings").json()["safety_car"] is True
    assert admin.put("/api/admin/safety-car", json={"on": False}).json() == {"safety_car": False}


def test_rating(admin, client, make_dish, body):
    o = approved(admin, client, make_dish, body)
    url = f"/api/orders/{o['id']}/rating"

    def rate(**kw):
        return client.post(url, json=kw, headers=hdr(o))

    r = rate(stars=5)
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    walk(admin, o, ["in_kitchen", "ready_for_pickup", "delivered"])
    for bad in ({"stars": 0}, {"stars": 6}, {"stars": 3, "comment": "x" * 501}):
        assert rate(**bad).status_code == 422
    assert client.post(url, json={"stars": 4}, headers={"X-Order-Token": "nope"}).status_code == 404
    r = rate(stars=4, comment="great")
    assert r.status_code == 200 and r.json()["rating"]["stars"] == 4
    assert rate(stars=5).status_code == 409
    got = client.get(f"/api/orders/{o['id']}", headers=hdr(o)).json()
    assert got["rating"]["comment"] == "great" and got["delivered_at"]
    assert admin.get(f"/api/admin/orders/{o['id']}").json()["rating"]["stars"] == 4
