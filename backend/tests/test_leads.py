import datetime as dt
import random

import pytest

from app.services import lead_model as lm

from .test_security import error_code

STRONG = {"event_type": "bar_bat_mitzvah", "guests": 120, "days_until_event": 40,
          "source": "referral", "returning_customer": True, "used_assistant": True,
          "requested_quote": True, "budget_per_guest": 150.0}  # fmt: skip
WEAK = {"event_type": "other", "guests": 15, "days_until_event": 2, "source": "instagram",
        "returning_customer": False, "used_assistant": False, "requested_quote": False,
        "budget_per_guest": None}  # fmt: skip


def lead_body(**over):
    body = {"full_name": "נועה לוי", "event_type": "birthday", "guests": 40, "source": "google",
            "event_date": (dt.date.today() + dt.timedelta(days=30)).isoformat()}  # fmt: skip
    return body | over


# ---- model
def test_ols_recovers_known_coefficients():
    rng = random.Random(1)  # noqa: S311
    rows = [lm.sample_features(rng) for _ in range(400)]
    # A target that is exactly linear in two encoded columns -> OLS must fit it perfectly.
    data = [(r, 0.1 + 0.3 * r["returning_customer"] + 0.002 * r["guests"]) for r in rows]
    model = lm.fit(data)
    for r, y in data[:20]:
        assert model.predict_raw(r) == pytest.approx(y, abs=1e-9)


def test_solve_rejects_singular():
    with pytest.raises(ValueError):
        lm._solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_scores_are_clipped_and_ordered():
    strong, weak = lm.score(STRONG), lm.score(WEAK)
    assert strong[0] > weak[0]
    for chance, raw, clipped in (strong, weak):
        assert 0.0 <= chance <= 1.0
        assert clipped == (not 0.0 <= raw <= 1.0)


def test_breakdown_sums_to_prediction():
    model, _ = lm.trained()
    for r in (STRONG, WEAK):
        parts = model.breakdown(r)
        assert set(parts) == set(lm.FIELDS)
        assert model.intercept + sum(parts.values()) == pytest.approx(model.predict_raw(r))


def test_soon_event_lowers_chance():
    model, _ = lm.trained()
    assert model.breakdown(WEAK)["days_until_event"] < 0
    assert lm.score(STRONG | {"days_until_event": 2})[1] < lm.score(STRONG)[1]


def test_model_card_is_honest():
    _, card = lm.trained()
    assert card["synthetic"] is True and card["holdout_rows"] == 400
    assert 0.2 < card["r2"] < 0.6
    assert card["clipped_share"] > 0  # the clip actually happens and is reported
    assert lm.trained() is lm.trained()  # fitted once per process


def test_far_and_past_dates_are_clamped():
    far, past = STRONG | {"days_until_event": 5000}, STRONG | {"days_until_event": -10}
    assert lm.score(far)[1] == pytest.approx(lm.score(STRONG | {"days_until_event": 365})[1])
    assert lm.score(past)[1] == pytest.approx(lm.score(STRONG | {"days_until_event": 0})[1])


# ---- API
def test_create_list_get_patch_delete(admin):
    made = admin.post("/api/admin/leads", json=lead_body(budget_per_guest="95.50"))
    assert made.status_code == 201, made.text
    lead = made.json()
    assert 0 <= lead["chance"] <= 1 and lead["status"] == "new" and lead["is_demo"] is False

    detail = admin.get(f"/api/admin/leads/{lead['id']}").json()
    assert set(detail["breakdown"]) == set(lm.FIELDS)
    assert detail["average_chance"] + sum(detail["breakdown"].values()) == pytest.approx(
        detail["raw_prediction"]
    )

    patched = admin.patch(f"/api/admin/leads/{lead['id']}", json={"status": "contacted"})
    assert patched.status_code == 200 and patched.json()["status"] == "contacted"
    assert [x["id"] for x in admin.get("/api/admin/leads").json()] == [lead["id"]]

    assert admin.delete(f"/api/admin/leads/{lead['id']}").status_code == 204
    missing = admin.get(f"/api/admin/leads/{lead['id']}")
    assert missing.status_code == 404 and error_code(missing) == "not_found"


def test_list_puts_open_leads_first_by_chance(admin):
    cold = admin.post("/api/admin/leads", json=lead_body(source="other", guests=5)).json()
    hot = admin.post("/api/admin/leads", json=lead_body(
        source="referral", returning_customer=True, requested_quote=True)).json()  # fmt: skip
    won = admin.post("/api/admin/leads", json=lead_body(source="referral")).json()
    admin.patch(f"/api/admin/leads/{won['id']}", json={"status": "won"})
    assert [x["id"] for x in admin.get("/api/admin/leads").json()] == [
        hot["id"], cold["id"], won["id"]]  # fmt: skip


@pytest.mark.parametrize("over", [
    {"guests": 0}, {"guests": 1001}, {"event_type": "wedding"}, {"source": "tiktok"},
    {"full_name": ""}, {"full_name": "x" * 201}, {"budget_per_guest": "-1"},
    {"event_date": (dt.date.today() - dt.timedelta(days=1)).isoformat()},
])  # fmt: skip
def test_invalid_leads_rejected_without_echo(admin, over):
    response = admin.post("/api/admin/leads", json=lead_body(**over))
    assert response.status_code == 422 and error_code(response) == "validation_error"
    assert "נועה" not in response.text


def test_patch_rejects_null_for_required(admin):
    lead = admin.post("/api/admin/leads", json=lead_body()).json()
    assert admin.patch(f"/api/admin/leads/{lead['id']}", json={"guests": None}).status_code == 422
    assert admin.patch(f"/api/admin/leads/{lead['id']}", json={"status": "x"}).status_code == 422


def test_demo_leads_add_and_clear(admin):
    real = admin.post("/api/admin/leads", json=lead_body()).json()
    demo = admin.post("/api/admin/leads/demo", json={"n": 5})
    assert demo.status_code == 201 and len(demo.json()) == 5
    assert all(x["is_demo"] and x["status"] == "new" for x in demo.json())
    assert admin.post("/api/admin/leads/demo", json={"n": 51}).status_code == 422
    assert admin.delete("/api/admin/leads/demo").json() == {"deleted": 5}
    assert [x["id"] for x in admin.get("/api/admin/leads").json()] == [real["id"]]


def test_model_card_route(admin):
    card = admin.get("/api/admin/leads/model").json()
    assert card["synthetic"] is True and card["train_rows"] == 2000


def test_leads_need_admin(client, make_token):
    assert client.get("/api/admin/leads").status_code == 401
    customer = {"Authorization": f"Bearer {make_token(role='customer')}"}
    assert client.get("/api/admin/leads", headers=customer).status_code == 403
