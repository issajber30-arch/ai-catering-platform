import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.api.catalog import Lang
from app.core.db import Db
from app.core.ratelimit import limit
from app.models.orders import EVENT_TYPES
from app.schemas.orders import (
    ItemIn,
    OrderCreate,
    OrderCreated,
    OrderOut,
    OrderPatch,
    PricingOut,
    RecommendationOut,
    SubmitIn,
)
from app.services import orders as service
from app.services.geo import Geocoder, get_geocoder

router = APIRouter(prefix="/api")
# Private link token issued once by POST /api/orders; wrong token and unknown id both give 404.
Token = Annotated[str | None, Header(alias="X-Order-Token")]
Geo = Annotated[Geocoder, Depends(get_geocoder)]


@router.get("/catalog/event-types")
def event_types() -> list[str]:
    # shortcut: constant list; move to the admin if the owner wants to edit it.
    return list(EVENT_TYPES)


@router.post("/orders", status_code=201, dependencies=[Depends(limit("orders", 10, 3600))])
def create_order(body: OrderCreate, db: Db, geocode: Geo, lang: Lang = "he") -> OrderCreated:
    return service.create_order(db, body, lang, geocode)


@router.get("/orders/{order_id}")
def get_order(order_id: uuid.UUID, db: Db, token: Token = None, lang: Lang = "he") -> OrderOut:
    return service.get_order(db, order_id, token, lang)


@router.patch("/orders/{order_id}")
def patch_order(
    order_id: uuid.UUID, body: OrderPatch, db: Db, geocode: Geo, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.patch_order(db, order_id, token, body, lang, geocode)


@router.put("/orders/{order_id}/items/{dish_id}")
def put_item(
    order_id: uuid.UUID, dish_id: uuid.UUID, body: ItemIn, db: Db, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.set_item(db, order_id, token, dish_id, body.quantity, body.version, lang)


@router.delete("/orders/{order_id}/items/{dish_id}")
def delete_item(
    order_id: uuid.UUID, dish_id: uuid.UUID, version: int, db: Db, token: Token = None,
    lang: Lang = "he",
) -> OrderOut:  # fmt: skip
    return service.remove_item(db, order_id, token, dish_id, version, lang)


@router.get("/orders/{order_id}/pricing")
def get_pricing(order_id: uuid.UUID, db: Db, token: Token = None, lang: Lang = "he") -> PricingOut:
    return service.get_pricing(db, order_id, token, lang)


@router.get("/orders/{order_id}/recommendations")
def get_recommendations(
    order_id: uuid.UUID, db: Db, token: Token = None
) -> list[RecommendationOut]:
    return service.recommendations(db, order_id, token)


@router.post("/orders/{order_id}/submit")
def submit_order(
    order_id: uuid.UUID, body: SubmitIn, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.submit(db, order_id, token, body.version, lang)


@router.post("/orders/{order_id}/reopen")
def reopen_order(
    order_id: uuid.UUID, body: SubmitIn, db: Db, token: Token = None, lang: Lang = "he"
) -> OrderOut:
    return service.reopen(db, order_id, token, body.version, lang)
