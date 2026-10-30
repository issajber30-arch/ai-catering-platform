import datetime as dt
import hashlib
import hmac
import secrets
import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.catalog import Dish, DishCategory, KashrutClass
from app.models.logistics import FulfillmentType, TimeSlot
from app.models.orders import Customer, Event, Order, OrderItem, OrderStatus, QuantityRule
from app.repositories import catalog as crepo
from app.repositories import logistics as lrepo
from app.repositories import orders as repo
from app.repositories import settings as srepo
from app.schemas.orders import (
    ItemOut,
    OrderCreate,
    OrderCreated,
    OrderOut,
    OrderPatch,
    OrderSummary,
    PricingOut,
    QuantityRuleIn,
    RecommendationOut,
)
from app.services import geo, pricing, quantities
from app.services.catalog import need
from app.services.settings import num


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _not_found() -> AppError:
    return AppError(404, "Order not found")


def customer_order(db: Session, order_id: uuid.UUID, token: str | None, *, lock: bool = False):
    """Wrong token and unknown id look the same, so ids cannot be probed."""
    order = repo.get_order(db, order_id, lock=lock)
    if order is None or not token or not hmac.compare_digest(order.access_token_hash, _hash(token)):
        raise _not_found()
    return order


def _draft(db: Session, order_id: uuid.UUID, token: str | None, version: int) -> Order:
    order = customer_order(db, order_id, token, lock=True)
    if order.status != OrderStatus.draft:
        raise AppError(409, "Order can no longer be changed", code="invalid_transition")
    if order.version != version:
        raise AppError(409, "Order was changed elsewhere", code="order_version_conflict")
    return order


def _at(day: dt.date, time: dt.time) -> dt.datetime:
    return dt.datetime.combine(day, time, tzinfo=ZoneInfo(get_settings().business_timezone))


def check_logistics(db: Session, event_date, ftype, slot_id, address) -> TimeSlot:
    """Weekday convention: TimeSlot.weekday follows date.weekday(), Monday=0 .. Sunday=6."""
    today = dt.datetime.now(ZoneInfo(get_settings().business_timezone)).date()
    if event_date < today:
        raise AppError(422, "Event date is in the past")
    lead = srepo.get(db).lead_time_days
    if event_date < today + dt.timedelta(days=lead):
        raise AppError(422, f"Events need at least {lead} days' notice")
    if lrepo.blocked_between(db, event_date, event_date):
        raise AppError(422, "Event date is not available")
    slot = crepo.get(db, TimeSlot, slot_id) if slot_id else None
    if slot is None or not slot.is_active or slot.fulfillment_type != ftype:
        raise AppError(422, "Time slot is not available for this fulfillment type")
    if slot.weekday is not None and slot.weekday != event_date.weekday():
        raise AppError(422, "Time slot is not offered on that weekday")
    if _at(event_date, slot.start_time) <= dt.datetime.now(dt.UTC):
        raise AppError(422, "Time slot has already started")
    if ftype == FulfillmentType.delivery:
        if not address:
            raise AppError(422, "Delivery needs an address")
    return slot


def _delivery(db: Session, geocode, ftype, address) -> dict:
    """Order columns for the delivery distance and fee; pickup clears them."""
    if ftype != FulfillmentType.delivery:
        return dict(delivery_km=None, delivery_lat=None, delivery_lon=None, delivery_fee=None,
                    delivery_fee_estimated=False)  # fmt: skip
    s = srepo.get(db)
    q = geo.quote(db, geocode, address, s)
    if q.too_far:
        raise AppError(
            422, f"Delivery isn't available this far (max {num(s.delivery_max_km)} km); "
            "choose pickup."
        )  # fmt: skip
    return dict(delivery_km=q.km, delivery_lat=q.lat, delivery_lon=q.lon, delivery_fee=q.fee,
                delivery_fee_estimated=not q.found)  # fmt: skip


def create_order(db: Session, body: OrderCreate, lang: str, geocode) -> OrderCreated:
    # shortcut: no rate limit on order creation; add at proxy/app before public launch (Phase 6).
    slot = check_logistics(
        db, body.event.event_date, body.fulfillment_type, body.time_slot_id,
        body.delivery_address,
    )  # fmt: skip
    fields = _delivery(db, geocode, body.fulfillment_type, body.delivery_address)
    customer = Customer(**body.customer.model_dump())
    db.add(customer)
    db.flush()
    event = Event(customer_id=customer.id, **body.event.model_dump())
    db.add(event)
    db.flush()
    token = secrets.token_urlsafe(32)
    delivery = body.fulfillment_type == FulfillmentType.delivery
    order = _save(
        db,
        Order(
            customer_id=customer.id,
            event_id=event.id,
            access_token_hash=_hash(token),
            fulfillment_type=body.fulfillment_type,
            time_slot_id=slot.id,
            requested_at=_at(event.event_date, slot.start_time),
            delivery_address=body.delivery_address if delivery else None,
            delivery_zone_id=body.delivery_zone_id if delivery else None,
            currency=get_settings().default_currency,
            **fields,
        ),
    )
    return OrderCreated(**order_out(order, lang).model_dump(), access_token=token)


def _save(db: Session, order: Order) -> Order:
    return repo.get_order(db, crepo.save(db, order).id)


def _priced(order: Order, lang: str) -> PricingOut:
    draft = order.status == OrderStatus.draft
    items = sorted(order.items, key=lambda i: i.dish.name_he)
    if draft:
        delivery = order.fulfillment_type == FulfillmentType.delivery
        fee = order.delivery_fee  # computed from distance when the order was last saved
        if delivery and order.delivery_km is None and not order.delivery_fee_estimated:
            fee = order.zone.fee if order.zone else None  # older orders priced by zone
        t = pricing.price(
            [pricing.Line(i.quantity, i.dish.unit_price, i.dish.currency) for i in items], fee
        )
        rows = [
            (i, i.dish.pricing_unit, i.dish.unit_price, lt)
            for i, lt in zip(items, t.line_totals, strict=True)
        ]
        totals = (
            t.subtotal, None if order.delivery_fee_estimated else t.delivery_fee, t.total,
            t.currency or order.currency,
        )  # fmt: skip
    else:
        rows = [
            (i, i.snapshot_pricing_unit, i.snapshot_unit_price, i.snapshot_line_total)
            for i in items
        ]
        totals = (order.subtotal, order.delivery_fee, order.total, order.currency)
    out = []
    for i, unit, price, line in rows:
        name = getattr(i.dish, f"name_{lang}") or i.dish.name_he
        if not draft and lang == "he":
            name = i.snapshot_name
        out.append(ItemOut(
            dish_id=i.dish_id, name=name, pricing_unit=unit, unit=i.dish.unit_label,
            unit_price=price, quantity=i.quantity, line_total=line,
        ))  # fmt: skip
    return PricingOut(items=out, subtotal=totals[0], delivery_fee=totals[1], total=totals[2],
                      currency=totals[3])  # fmt: skip


def _warnings(order: Order) -> list[str]:
    kinds = {i.dish.dietary.kashrut_class for i in order.items if i.dish.dietary}  # null = unknown
    both = KashrutClass.meat in kinds and KashrutClass.dairy in kinds
    return ["mixes_meat_dairy"] if both else []


def order_out(order: Order, lang: str = "he") -> OrderOut:
    return OrderOut(
        **_priced(order, lang).model_dump(),
        warnings=_warnings(order), delivery_km=order.delivery_km,
        delivery_fee_estimated=order.delivery_fee_estimated,
        id=order.id, status=order.status, version=order.version, customer=order.customer,
        event=order.event, fulfillment_type=order.fulfillment_type,
        time_slot_id=order.time_slot_id, requested_at=order.requested_at,
        delivery_address=order.delivery_address, delivery_zone_id=order.delivery_zone_id,
        submitted_at=order.submitted_at, decided_at=order.decided_at,
        decision_note=order.decision_note,
    )  # fmt: skip


def get_order(db: Session, order_id, token, lang: str) -> OrderOut:
    return order_out(customer_order(db, order_id, token), lang)


def get_pricing(db: Session, order_id, token, lang: str) -> PricingOut:
    return _priced(customer_order(db, order_id, token), lang)


def patch_order(db: Session, order_id, token, body: OrderPatch, lang: str, geocode) -> OrderOut:
    current = customer_order(db, order_id, token)
    sent = body.model_fields_set
    event = body.event.model_dump() if body.event else {}
    ftype = body.fulfillment_type or current.fulfillment_type
    address = body.delivery_address if "delivery_address" in sent else current.delivery_address
    zone_id = body.delivery_zone_id if "delivery_zone_id" in sent else current.delivery_zone_id
    changed = ftype != current.fulfillment_type or address != current.delivery_address
    # Geocode before taking the row lock: the lookup can take seconds and commits its cache,
    # which would release the lock. Any change in between bumps the version, so _draft catches it.
    fields = _delivery(db, geocode, ftype, address) if changed else {}
    order = _draft(db, order_id, token, body.version)
    slot = check_logistics(
        db, event.get("event_date", order.event.event_date), ftype,
        body.time_slot_id or order.time_slot_id, address,
    )  # fmt: skip
    for k, v in event.items():
        setattr(order.event, k, v)
    delivery = ftype == FulfillmentType.delivery
    order.fulfillment_type, order.time_slot_id = ftype, slot.id
    order.delivery_address = address if delivery else None
    order.delivery_zone_id = zone_id if delivery else None
    for k, v in fields.items():
        setattr(order, k, v)
    order.requested_at = _at(order.event.event_date, slot.start_time)
    order.version += 1
    return order_out(_save(db, order), lang)


def set_item(db: Session, order_id, token, dish_id, quantity: Decimal, version, lang):
    order = _draft(db, order_id, token, version)
    dish = need(db, Dish, dish_id, "Dish")
    if not dish.is_available:
        raise AppError(422, "Dish is not available")
    if dish.min_quantity is not None and quantity < dish.min_quantity:
        raise AppError(422, f"Minimum quantity for this dish is {dish.min_quantity}")
    others = [
        pricing.Line(i.quantity, i.dish.unit_price, i.dish.currency)
        for i in order.items
        if i.dish_id != dish_id
    ]
    pricing.price([*others, pricing.Line(quantity, dish.unit_price, dish.currency)])
    if item := repo.get_item(order, dish_id):
        item.quantity = quantity
    else:
        order.items.append(OrderItem(dish_id=dish_id, quantity=quantity))
    order.version += 1
    return order_out(_save(db, order), lang)


def remove_item(db: Session, order_id, token, dish_id, version, lang) -> OrderOut:
    order = _draft(db, order_id, token, version)
    item = repo.get_item(order, dish_id)
    if item is None:
        raise AppError(404, "Item not found")
    order.items.remove(item)
    order.version += 1
    return order_out(_save(db, order), lang)


def recommendations(db: Session, order_id, token) -> list[RecommendationOut]:
    order = customer_order(db, order_id, token)
    selected = [
        quantities.Selected(i.dish_id, i.dish.category_id, i.dish.pricing_unit) for i in order.items
    ]
    rules = {
        cid: quantities.Rule(r.per_adult, r.per_child, r.round_step)
        for cid, r in repo.rules_by_category(db).items()
    }
    found = quantities.recommend(order.event.adults, order.event.children, selected, rules)
    return [RecommendationOut(**vars(r)) for r in found]


def submit(db: Session, order_id, token, version, lang) -> OrderOut:
    order = _draft(db, order_id, token, version)
    if not order.items:
        raise AppError(422, "Order has no items")
    if any(not i.dish.is_available for i in order.items):
        raise AppError(422, "Some dishes are no longer available")
    if any(
        i.dish.min_quantity is not None and i.quantity < i.dish.min_quantity for i in order.items
    ):
        raise AppError(422, "Some dishes are below their minimum quantity")
    check_logistics(
        db, order.event.event_date, order.fulfillment_type, order.time_slot_id,
        order.delivery_address,
    )  # fmt: skip
    priced = _priced(order, lang)
    minimum = srepo.get(db).min_food_total
    if priced.subtotal < minimum:  # delivery fee is not counted
        raise AppError(422, f"Food total must reach ₪{num(minimum)}")
    lines = {line.dish_id: line for line in priced.items}
    for item in order.items:
        line = lines[item.dish_id]
        item.snapshot_name = item.dish.name_he
        item.snapshot_pricing_unit = line.pricing_unit
        item.snapshot_unit_price = line.unit_price
        item.snapshot_line_total = line.line_total
    order.subtotal, order.delivery_fee, order.total = (
        priced.subtotal,
        priced.delivery_fee,
        priced.total,
    )  # fmt: skip
    order.currency = priced.currency
    order.status = OrderStatus.pending_approval
    order.submitted_at = dt.datetime.now(dt.UTC)
    order.version += 1
    return order_out(_save(db, order), lang)


# ---- owner
def list_orders(db: Session, status: OrderStatus | None) -> list[OrderSummary]:
    return [
        OrderSummary(
            id=o.id, status=o.status, customer_name=o.customer.full_name,
            event_type=o.event.event_type, event_date=o.event.event_date,
            guests=o.event.adults + o.event.children, total=o.total, currency=o.currency,
            submitted_at=o.submitted_at, created_at=o.created_at,
        )
        for o in repo.list_orders(db, status)
    ]  # fmt: skip


def admin_order(db: Session, order_id) -> OrderOut:
    order = repo.get_order(db, order_id)
    if order is None:
        raise _not_found()
    return order_out(order)


def decide(db: Session, order_id, status: OrderStatus, note: str | None) -> OrderOut:
    order = repo.get_order(db, order_id, lock=True)
    if order is None:
        raise _not_found()
    if order.status != OrderStatus.pending_approval:
        raise AppError(
            409, "Only orders awaiting approval can be decided", code="invalid_transition"
        )
    order.status, order.decision_note = status, note
    order.decided_at = dt.datetime.now(dt.UTC)
    order.version += 1
    return order_out(_save(db, order))


def put_rule(db: Session, category_id, body: QuantityRuleIn) -> QuantityRule:
    need(db, DishCategory, category_id, "Category")
    rule = repo.get_rule(db, category_id) or QuantityRule(category_id=category_id)
    for k, v in body.model_dump().items():
        setattr(rule, k, v)
    return crepo.save(db, rule)


def delete_rule(db: Session, category_id) -> None:
    rule = repo.get_rule(db, category_id)
    if rule is None:
        raise AppError(404, "Quantity rule not found")
    crepo.remove(db, rule)
