# ruff: noqa: F811  (imported fixtures are used as arguments)
import datetime as dt
import logging
import uuid
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import text

from app.main import app
from app.models.orders import Order
from app.services import notify

from .test_orders import body, hdr, new, no_minimum, put_item, slot  # noqa: F401  (fixtures)

ADV = "/api/admin/orders/{}/advance"


class FakeSender:
    def __init__(self, channels=("sms", "whatsapp"), fail=False):
        self.channels, self.fail, self.calls = channels, fail, []

    def send(self, channel, to, body):
        self.calls.append((channel, to, body))
        if self.fail:
            raise RuntimeError("boom")


@pytest.fixture
def sender(client):
    fake = FakeSender()
    app.dependency_overrides[notify.get_sender] = lambda: fake
    return fake


def approved(client, admin, make_dish, body, *, phone="050-123 4567", opt_in=True, lang="he"):
    body["customer"]["phone"] = phone
    o = put_item(client, new(client, body), make_dish()).json()
    r = client.post(
        f"/api/orders/{o['id']}/submit?lang={lang}",
        json={"version": o["version"], "sms_opt_in": opt_in},
        headers=hdr(o),
    )
    assert r.status_code == 200, r.text
    return admin.post(f"/api/admin/orders/{o['id']}/approve", json={}).json()


def advance(admin, o):
    r = admin.post(ADV.format(o["id"]), json={"version": o["version"]})
    assert r.status_code == 200, r.text
    return r.json()


def to_delivery_dispatch(admin, db, o):
    db.execute(text("UPDATE orders SET fulfillment_type = 'delivery', delivery_address = 'x'"))
    db.commit()
    return advance(admin, advance(admin, o))  # approved -> in_kitchen -> out_for_delivery


def statuses(db):
    db.expire_all()
    rows = db.execute(text("SELECT kind, channel, status FROM notifications ORDER BY channel"))
    return [tuple(r) for r in rows]


def test_flying_lap_opt_in_once_per_channel(admin, client, make_dish, body, db, sender):
    o = approved(client, admin, make_dish, body, lang="ar")
    o = to_delivery_dispatch(admin, db, o)
    assert o["status"] == "out_for_delivery"
    assert [(c, to) for c, to, _ in sender.calls] == [("sms", "+972501234567"),
                                                      ("whatsapp", "+972501234567")]  # fmt: skip
    assert sender.calls[0][2] == notify.TEXTS["flying_lap"]["ar"]
    assert statuses(db) == [("flying_lap", "sms", "sent"), ("flying_lap", "whatsapp", "sent")]
    # Re-running the trigger (e.g. a retry) cannot resend.
    notify.notify(db, sender, "flying_lap", [uuid.UUID(o["id"])])
    assert len(sender.calls) == 2


def test_no_opt_in_sends_nothing(admin, client, make_dish, body, db, sender):
    o = approved(client, admin, make_dish, body, opt_in=False)
    to_delivery_dispatch(admin, db, o)
    assert sender.calls == [] and statuses(db) == []


def test_bad_phone_skipped(admin, client, make_dish, body, db, sender):
    o = approved(client, admin, make_dish, body, phone="12345")
    to_delivery_dispatch(admin, db, o)
    assert sender.calls == [] and statuses(db) == []


def test_safety_car_today_only_and_once(admin, client, make_dish, body, db, sender):
    today = dt.datetime.now(ZoneInfo("Asia/Jerusalem")).date()
    a = approved(client, admin, make_dish, body)  # approved, today
    b = approved(client, admin, make_dish, body)  # approved, stays in the future
    c = approved(client, admin, make_dish, body)  # pending_approval-like: cancelled below
    admin.post(f"/api/admin/orders/{c['id']}/cancel", json={"note": "x"})
    for o in (a, c):
        db.get(Order, uuid.UUID(o["id"])).event.event_date = today
    db.commit()
    assert admin.put("/api/admin/safety-car", json={"on": True}).status_code == 200
    assert {to for _, to, _ in sender.calls} == {"+972501234567"} and len(sender.calls) == 2
    assert sender.calls[0][2] == notify.TEXTS["safety_car"]["he"]
    assert admin.put("/api/admin/safety-car", json={"on": True}).status_code == 200
    admin.put("/api/admin/safety-car", json={"on": False})
    admin.put("/api/admin/safety-car", json={"on": True})
    assert len(sender.calls) == 2
    n = db.execute(text("SELECT count(*) FROM notifications")).scalar()
    assert n == 2 and b["id"]


def test_sender_failure_recorded_and_request_ok(admin, client, make_dish, body, db, sender):
    sender.fail = True
    o = approved(client, admin, make_dish, body)
    assert to_delivery_dispatch(admin, db, o)["status"] == "out_for_delivery"
    assert statuses(db) == [("flying_lap", "sms", "failed"), ("flying_lap", "whatsapp", "failed")]


def test_disabled_sender_logs_without_phone(admin, client, make_dish, body, db, caplog):
    app.dependency_overrides[notify.get_sender] = notify.DisabledSender
    caplog.set_level(logging.INFO)
    o = approved(client, admin, make_dish, body)
    to_delivery_dispatch(admin, db, o)
    assert "sms disabled" in caplog.text
    assert "1234567" not in caplog.text and statuses(db) == []
    assert admin.get("/api/admin/notify-status").json() == {"enabled": False}


def test_notify_status_enabled(admin, sender):
    assert admin.get("/api/admin/notify-status").json() == {"enabled": True}


def test_submit_stores_opt_in_and_lang(admin, client, make_dish, body, db):
    approved(client, admin, make_dish, body, lang="en")
    assert tuple(db.execute(text("SELECT sms_opt_in, lang FROM orders")).one()) == (True, "en")


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("050-123 4567", "+972501234567"),
        ("0501234567", "+972501234567"),
        ("+972 50-123-4567", "+972501234567"),
        ("+14155550123", None),
        ("+97205012345", None),  # trunk 0 kept by mistake
        ("+97221234567", None),  # landline: no SMS
        ("501234567", None),
        ("05012", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_phone(raw, want):
    assert notify.normalize_phone(raw) == want


def test_twilio_sender_fixed_url_and_sid(monkeypatch):
    sid = "AC" + "a" * 32
    seen = []

    def post(url, **kw):
        seen.append((url, kw))
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(notify.httpx, "post", post)
    t = notify.TwilioSender(sid, "tok", "+15005550006", "+15005550007")
    t.send("whatsapp", "+972501234567", "hi")
    t.send("sms", "+972501234567", "hi")
    assert seen[0][0] == f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    assert seen[0][1]["data"] == {"To": "whatsapp:+972501234567",
                                  "From": "whatsapp:+15005550007", "Body": "hi"}  # fmt: skip
    assert seen[1][1]["data"]["From"] == "+15005550006" and seen[1][1]["timeout"] == 5
    assert seen[0][1]["auth"] == (sid, "tok")
    assert notify.TwilioSender(sid, "t", None, "+1").channels == ("whatsapp",)
    for bad in ("", "AC123", "../x", "AC" + "A" * 32, "AC" + "a" * 32 + "/x"):
        with pytest.raises(ValueError):
            notify.TwilioSender(bad, "t", "+1", None)


def test_get_sender_env(monkeypatch):
    s = notify.get_settings()
    assert isinstance(notify.get_sender(), notify.DisabledSender)
    monkeypatch.setattr(s, "twilio_account_sid", "AC" + "b" * 32)
    monkeypatch.setattr(s, "twilio_auth_token", "tok")
    assert isinstance(notify.get_sender(), notify.DisabledSender)  # no sender number
    monkeypatch.setattr(s, "twilio_sms_from", "+15005550006")
    assert notify.get_sender().channels == ("sms",)


def test_budget_used_up_leaves_orders_unclaimed(
    admin, client, make_dish, body, db, sender, monkeypatch
):
    monkeypatch.setattr(notify, "BUDGET_S", -1)  # already past the deadline
    o = approved(client, admin, make_dish, body)
    to_delivery_dispatch(admin, db, o)
    assert sender.calls == [] and statuses(db) == []  # nothing claimed: still eligible later
