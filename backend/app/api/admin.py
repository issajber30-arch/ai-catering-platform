import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.core.db import Db
from app.core.errors import AppError
from app.core.security import require_admin
from app.core.storage import MAX_IMAGE_BYTES, detect_image, get_uploader
from app.models.catalog import Allergen, Dish, DishCategory
from app.models.logistics import BlockedDate, DeliveryZone, TimeSlot
from app.models.orders import OrderStatus, QuantityRule
from app.repositories import ai as ai_repo
from app.repositories import catalog as repo
from app.schemas.ai import ProposalOut
from app.schemas.catalog import (
    CategoryIn,
    CategoryOut,
    CategoryPatch,
    DietaryIn,
    DishDetailOut,
    DishIn,
    DishOut,
    DishPatch,
)
from app.schemas.logistics import (
    BlockedIn,
    BlockedOut,
    SlotIn,
    SlotOut,
    SlotPatch,
    ZoneIn,
    ZoneOut,
    ZonePatch,
)
from app.schemas.orders import (
    DecisionIn,
    OrderOut,
    OrderSummary,
    QuantityRuleIn,
    QuantityRuleOut,
)
from app.schemas.settings import SettingsIn, SettingsOut
from app.services import availability, delivery, geo
from app.services import catalog as service
from app.services import orders as order_service
from app.services import settings as settings_service

# One router-level dependency guards every admin route (a test enforces it).
router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@router.get("/categories")
def list_categories(db: Db) -> list[CategoryOut]:
    return [service.category_out(c) for c in repo.list_categories(db, active_only=False)]


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, db: Db) -> CategoryOut:
    return service.category_out(service.create_category(db, body.model_dump()))


@router.patch("/categories/{category_id}")
def patch_category(category_id: uuid.UUID, body: CategoryPatch, db: Db) -> CategoryOut:
    cat = service.need(db, DishCategory, category_id, "Category")
    return service.category_out(service.update(db, cat, body.model_dump(exclude_unset=True)))


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, db: Db) -> None:
    service.delete_category(db, category_id)


@router.get("/dishes")
def list_dishes(db: Db) -> list[DishOut]:
    return [service.dish_out(d) for d in repo.list_dishes(db, public=False)]


@router.post("/dishes", status_code=201)
def create_dish(body: DishIn, db: Db) -> DishDetailOut:
    dish = service.create_dish(db, body.model_dump())
    return service.dish_detail(db, dish.id, "he", public=False)


@router.get("/dishes/{dish_id}")
def get_dish(dish_id: uuid.UUID, db: Db) -> DishDetailOut:
    return service.dish_detail(db, dish_id, "he", public=False)


@router.patch("/dishes/{dish_id}")
def patch_dish(dish_id: uuid.UUID, body: DishPatch, db: Db) -> DishDetailOut:
    service.update_dish(db, dish_id, body.model_dump(exclude_unset=True))
    return service.dish_detail(db, dish_id, "he", public=False)


@router.delete("/dishes/{dish_id}", status_code=204)
def delete_dish(dish_id: uuid.UUID, db: Db) -> None:
    # Referenced by an order -> 409 from the IntegrityError handler; use is_available=false instead.
    repo.remove(db, service.need(db, Dish, dish_id, "Dish"))


@router.put("/dishes/{dish_id}/dietary")
def put_dietary(dish_id: uuid.UUID, body: DietaryIn, db: Db) -> DishDetailOut:
    return service.set_dietary(db, dish_id, body)


@router.post("/dishes/{dish_id}/image")
# Sync on purpose: the storage upload uses blocking httpx, so FastAPI runs it in the threadpool.
def upload_image(
    dish_id: uuid.UUID,
    file: UploadFile,
    db: Db,
    upload: Annotated[Callable[[bytes, str], str], Depends(get_uploader)],
) -> DishDetailOut:
    dish = service.need(db, Dish, dish_id, "Dish")
    data = file.file.read(MAX_IMAGE_BYTES + 1)  # bounded read: never buffer more than the cap
    if len(data) > MAX_IMAGE_BYTES:
        raise AppError(413, "Image must be 5 MB or smaller")
    kind = detect_image(data)
    if kind is None:
        raise AppError(415, "Only JPEG, PNG or WebP images are accepted")
    service.update(db, dish, {"image_path": upload(data, kind)})
    return service.dish_detail(db, dish_id, "he", public=False)


@router.get("/allergens")
def list_allergens(db: Db) -> list[dict]:
    return [{"id": a.id, "name": a.name} for a in repo.list_all(db, Allergen, Allergen.id)]


@router.get("/delivery-zones")
def list_zones(db: Db) -> list[ZoneOut]:
    return repo.list_all(db, DeliveryZone, DeliveryZone.name)


@router.post("/delivery-zones", status_code=201)
def create_zone(body: ZoneIn, db: Db) -> ZoneOut:
    return delivery.create_zone(db, body.model_dump())


@router.patch("/delivery-zones/{zone_id}")
def patch_zone(zone_id: uuid.UUID, body: ZonePatch, db: Db) -> ZoneOut:
    return delivery.update_zone(db, zone_id, body.model_dump(exclude_unset=True))


@router.delete("/delivery-zones/{zone_id}", status_code=204)
def delete_zone(zone_id: uuid.UUID, db: Db) -> None:
    repo.remove(db, service.need(db, DeliveryZone, zone_id, "Delivery zone"))


@router.get("/time-slots")
def list_slots(db: Db) -> list[SlotOut]:
    return repo.list_all(db, TimeSlot, TimeSlot.weekday, TimeSlot.start_time)


@router.post("/time-slots", status_code=201)
def create_slot(body: SlotIn, db: Db) -> SlotOut:
    return availability.create_slot(db, body.model_dump())


@router.patch("/time-slots/{slot_id}")
def patch_slot(slot_id: uuid.UUID, body: SlotPatch, db: Db) -> SlotOut:
    return availability.update_slot(db, slot_id, body.model_dump(exclude_unset=True))


@router.delete("/time-slots/{slot_id}", status_code=204)
def delete_slot(slot_id: uuid.UUID, db: Db) -> None:
    repo.remove(db, service.need(db, TimeSlot, slot_id, "Time slot"))


@router.get("/blocked-dates")
def list_blocked(db: Db) -> list[BlockedOut]:
    return repo.list_all(db, BlockedDate, BlockedDate.date)


@router.post("/blocked-dates", status_code=201)
def create_blocked(body: BlockedIn, db: Db) -> BlockedOut:
    return availability.block_date(db, body.model_dump())


@router.delete("/blocked-dates/{blocked_id}", status_code=204)
def delete_blocked(blocked_id: uuid.UUID, db: Db) -> None:
    repo.remove(db, service.need(db, BlockedDate, blocked_id, "Blocked date"))


@router.get("/orders")
def list_orders(db: Db, status: OrderStatus | None = None) -> list[OrderSummary]:
    return order_service.list_orders(db, status)


@router.get("/orders/{order_id}")
def get_order(order_id: uuid.UUID, db: Db) -> OrderOut:
    return order_service.admin_order(db, order_id)


@router.get("/orders/{order_id}/assistant")
def order_assistant(order_id: uuid.UUID, db: Db) -> dict:
    # Counts + proposals only: chat text is deliberately hidden (owner-facing injection surface).
    order_service.admin_order(db, order_id)  # 404 for an unknown order
    conv = ai_repo.conversation(db, order_id)
    msgs = [
        m
        for m in (ai_repo.messages(db, conv.id) if conv else [])
        if m.role in ("user", "assistant")
    ]
    shown = [
        m
        for m in msgs
        if m.role == "user" or any(b.get("type") == "text" and b.get("text") for b in m.content)
    ]
    return {
        "message_count": len(shown),
        "last_message_at": shown[-1].created_at if shown else None,
        "proposals": [ProposalOut.model_validate(p) for p in ai_repo.proposals(db, order_id, None)],
    }


@router.post("/orders/{order_id}/approve")
def approve_order(order_id: uuid.UUID, db: Db, body: DecisionIn | None = None) -> OrderOut:
    return order_service.decide(db, order_id, OrderStatus.approved, (body or DecisionIn()).note)


@router.post("/orders/{order_id}/reject")
def reject_order(order_id: uuid.UUID, db: Db, body: DecisionIn | None = None) -> OrderOut:
    return order_service.decide(db, order_id, OrderStatus.rejected, (body or DecisionIn()).note)


@router.get("/quantity-rules")
def list_rules(db: Db) -> list[QuantityRuleOut]:
    return repo.list_all(db, QuantityRule, QuantityRule.category_id)


@router.put("/quantity-rules/{category_id}")
def put_rule(category_id: uuid.UUID, body: QuantityRuleIn, db: Db) -> QuantityRuleOut:
    return order_service.put_rule(db, category_id, body)


@router.delete("/quantity-rules/{category_id}", status_code=204)
def delete_rule(category_id: uuid.UUID, db: Db) -> None:
    order_service.delete_rule(db, category_id)


@router.get("/settings")
def get_settings(db: Db) -> SettingsOut:
    return settings_service.get(db)


@router.put("/settings")
def put_settings(
    body: SettingsIn, db: Db, geocode: Annotated[geo.Geocoder, Depends(geo.get_geocoder)]
) -> SettingsOut:
    return settings_service.update(db, body.model_dump(), geocode)
