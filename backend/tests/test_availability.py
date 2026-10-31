import datetime as dt

from .test_security import error_code

SLOT = {"fulfillment_type": "pickup", "weekday": 1, "start_time": "10:00", "end_time": "12:00"}


def test_slot_end_must_be_after_start(admin):
    for end in ("10:00", "09:00"):
        response = admin.post("/api/admin/time-slots", json=SLOT | {"end_time": end})
        assert response.status_code == 422
        assert error_code(response) == "validation_error"
    ok = admin.post("/api/admin/time-slots", json=SLOT)
    assert ok.status_code == 201 and ok.json()["capacity"] is None


def test_slot_patch_rechecks_merged_times(admin):
    slot = admin.post("/api/admin/time-slots", json=SLOT).json()
    url = f"/api/admin/time-slots/{slot['id']}"
    assert admin.patch(url, json={"end_time": "09:00"}).status_code == 422
    assert admin.patch(url, json={"end_time": "13:00", "capacity": 4}).status_code == 200


def test_slot_validation(admin):
    assert admin.post("/api/admin/time-slots", json=SLOT | {"weekday": 7}).status_code == 422
    assert admin.post("/api/admin/time-slots", json=SLOT | {"capacity": -1}).status_code == 422
    assert admin.post("/api/admin/time-slots", json=SLOT | {"start_time": "x"}).status_code == 422


def test_availability_range(admin, client):
    inside, outside = (
        dt.date.today() + dt.timedelta(days=5),
        dt.date.today() + dt.timedelta(days=90),
    )
    for day in (inside, outside):
        admin.post("/api/admin/blocked-dates", json={"date": str(day), "reason": "holiday"})
    admin.post("/api/admin/time-slots", json=SLOT)
    admin.post("/api/admin/time-slots", json=SLOT | {"is_active": False})
    body = client.get("/api/availability").json()
    assert [b["date"] for b in body["blocked_dates"]] == [str(inside)]
    assert len(body["time_slots"]) == 1  # inactive slots are hidden
    wide = client.get(f"/api/availability?from={inside}&to={outside}").json()
    assert len(wide["blocked_dates"]) == 2


def test_availability_bad_range(client):
    assert client.get("/api/availability?from=2026-12-01&to=2026-11-01").status_code == 422
    assert client.get("/api/availability?from=2026-01-01&to=2028-01-01").status_code == 422
    assert client.get("/api/availability?from=bogus").status_code == 422


def test_delivery_zone_crud(admin):
    body = {"name": "Haifa", "fee": "25.00", "definition": {"cities": ["Haifa"]}}
    zone = admin.post("/api/admin/delivery-zones", json=body).json()
    assert zone["definition"] == {"cities": ["Haifa"]}
    url = f"/api/admin/delivery-zones/{zone['id']}"
    assert admin.patch(url, json={"fee": "-1"}).status_code == 422
    assert admin.patch(url, json={"name": None}).status_code == 422
    assert admin.patch(url, json={"fee": "30"}).json()["fee"] == "30.00"
    assert admin.post("/api/admin/delivery-zones", json=body | {"fee": "-5"}).status_code == 422
    assert admin.delete(url).status_code == 204
    assert admin.get("/api/admin/delivery-zones").json() == []


def test_blocked_date_delete(admin):
    row = admin.post("/api/admin/blocked-dates", json={"date": "2027-01-01"}).json()
    assert admin.delete(f"/api/admin/blocked-dates/{row['id']}").status_code == 204
    assert admin.delete(f"/api/admin/blocked-dates/{row['id']}").status_code == 404
    assert admin.post("/api/admin/blocked-dates", json={"date": "nope"}).status_code == 422
