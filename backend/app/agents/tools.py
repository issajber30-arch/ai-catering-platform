"""Assistant tools: thin wrappers over services. The order id is bound by the server (Ctx) and is
never a tool argument. Results are JSON; untrusted text is labelled with its source."""

import json
import logging
import uuid
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.catalog import KashrutClass
from app.schemas.ai import ProposeArgs
from app.schemas.catalog import DishOut
from app.services import catalog, orders, proposals

log = logging.getLogger(__name__)


@dataclass
class Ctx:
    db: Session
    order_id: uuid.UUID
    conversation_id: uuid.UUID
    lang: str = "he"
    created: list = field(default_factory=list)  # proposals made during this turn


def w(text: str | None, source: str) -> dict | None:
    """Untrusted text, labelled so the model can tell data from instructions."""
    return None if text is None else {"text": text, "source": source}


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class DishesArgs(_Args):
    category_id: uuid.UUID | None
    vegetarian: bool | None
    vegan: bool | None
    kashrut: KashrutClass | None


class DishArgs(_Args):
    dish_id: uuid.UUID


def _dish(d: DishOut) -> dict:
    return {
        "id": d.id, "category_id": d.category_id, "name": w(d.name, "catalog"),
        "description": w(d.description, "catalog"), "pricing_unit": d.pricing_unit,
        "unit_label": w(d.unit_label, "catalog"), "unit_price": d.unit_price,
        "currency": d.currency, "min_quantity": d.min_quantity,
        # null = unknown, not "no"
        "dietary": {"kashrut_class": d.dietary.kashrut_class,
                    "is_vegetarian": d.dietary.is_vegetarian, "is_vegan": d.dietary.is_vegan},
    }  # fmt: skip


def _items(o) -> list[dict]:
    return [
        {"dish_id": i.dish_id, "name": w(i.name, "catalog"), "quantity": i.quantity,
         "pricing_unit": i.pricing_unit, "unit_price": i.unit_price, "line_total": i.line_total}
        for i in o.items
    ]  # fmt: skip


def get_menu_categories(c: Ctx, _: NoArgs):
    return [
        {"id": x.id, "name": w(x.name, "catalog")} for x in catalog.active_categories(c.db, c.lang)
    ]


def get_available_dishes(c: Ctx, a: DishesArgs):
    found = catalog.available_dishes(
        c.db, c.lang, category_id=a.category_id, vegetarian=a.vegetarian, vegan=a.vegan,
        kashrut=a.kashrut,
    )  # fmt: skip
    return [_dish(d) for d in found]


def get_dish_details(c: Ctx, a: DishArgs):
    d = catalog.dish_detail(c.db, a.dish_id, c.lang, public=True)
    return _dish(d) | {
        "allergens": [{"allergen": w(x.name, "catalog"), "status": x.status} for x in d.allergens]
    }


def get_current_order(c: Ctx, _: NoArgs):
    # Deliberately a whitelist: no name, contact details, address or decision note.
    o = orders.bound_order(c.db, c.order_id, c.lang)
    e = o.event
    return {
        "version": o.version, "status": o.status, "fulfillment_type": o.fulfillment_type,
        "event": {
            "event_type": e.event_type, "event_date": e.event_date, "adults": e.adults,
            "children": e.children, "vegetarian_guests": e.vegetarian_guests,
            "vegan_guests": e.vegan_guests, "restricted_guests": e.restricted_guests,
            "dietary_notes": w(e.dietary_notes, "customer_entered"),
        },
        "items": _items(o), "subtotal": o.subtotal, "delivery_fee": o.delivery_fee,
        "total": o.total, "currency": o.currency, "warnings": o.warnings,
    }  # fmt: skip


def get_order_pricing(c: Ctx, _: NoArgs):
    o = orders.bound_order(c.db, c.order_id, c.lang)
    return {  # delivery_fee null = to be confirmed by CaterKing
        "items": _items(o), "subtotal": o.subtotal, "delivery_fee": o.delivery_fee,
        "total": o.total, "currency": o.currency,
    }  # fmt: skip


def get_quantity_recommendations(c: Ctx, _: NoArgs):
    return [r.model_dump() for r in orders.bound_recommendations(c.db, c.order_id)]


def propose_order_change(c: Ctx, a: ProposeArgs):
    p = proposals.create(c.db, c.order_id, c.conversation_id, a, c.lang)
    c.created.append(p)
    return {
        "proposal_id": p.id, "status": "pending", "applied": False,
        "diff": [d | {"name": w(d["name"], "catalog")} for d in p.diff],
        "price_before": p.price_before, "price_after": p.price_after,
        "next": "Not applied. The customer must press Approve on the proposal card.",
    }  # fmt: skip


def _schema(properties: dict | None = None) -> dict:
    props = properties or {}
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}  # fmt: skip


_QTY = {"type": "number", "description": "Quantity in the dish's own unit (trays, kg, items)"}
_ID = {"type": "string", "description": "Dish id returned by a tool"}


def _change(op: str, *fields: str) -> dict:
    props = {"op": {"type": "string", "enum": [op]}, "dish_id": _ID}
    if "quantity" in fields:
        props["quantity"] = _QTY
    return _schema(props)


# name -> (description, input schema, args model, handler)
_REGISTRY = {
    "get_menu_categories": ("List the active menu categories.", _schema(), NoArgs,
                            get_menu_categories),
    "get_available_dishes": (
        "List dishes that can be ordered, optionally filtered. Use null for no filter. "
        "Dietary values that are null are unknown, not false.",
        _schema({
            "category_id": {"type": ["string", "null"]},
            "vegetarian": {"type": ["boolean", "null"]},
            "vegan": {"type": ["boolean", "null"]},
            "kashrut": {
                "anyOf": [{"type": "string", "enum": ["meat", "dairy", "pareve"]}, {"type": "null"}]
            },
        }),
        DishesArgs, get_available_dishes,
    ),
    "get_dish_details": ("One dish with its allergen statuses (contains, free or unknown).",
                         _schema({"dish_id": _ID}), DishArgs, get_dish_details),
    "get_current_order": ("The customer's draft order: event, items, totals, version.",
                          _schema(), NoArgs, get_current_order),
    "get_order_pricing": ("Backend-computed itemised pricing of the current order.",
                          _schema(), NoArgs, get_order_pricing),
    "get_quantity_recommendations": (
        "Backend-computed recommended quantities for the current order's dishes.",
        _schema(), NoArgs, get_quantity_recommendations),
    "propose_order_change": (
        "Propose adding dishes, changing quantities or removing dishes. This does NOT change the "
        "order: the customer must approve the proposal card. Prices are computed by the backend.",
        _schema({
            "changes": {"type": "array", "items": {"anyOf": [
                _change("add_item", "quantity"),
                _change("set_quantity", "quantity"),
                _change("remove_item"),
            ]}},
            "rationale": {"type": "string", "description": "One or two sentences for the customer"},
        }),
        ProposeArgs, propose_order_change,
    ),
}  # fmt: skip

# Sorted by name and built once: a deterministic tools block keeps the prompt cache valid.
TOOLS = [
    {"name": n, "description": d, "input_schema": s, "strict": True}
    for n, (d, s, _, _) in sorted(_REGISTRY.items())
]


def run(c: Ctx, name: str, raw) -> tuple[str, bool]:
    """Returns (JSON text, is_error). Arguments are re-validated; errors go back to the model."""
    try:
        if name not in _REGISTRY:
            raise AppError(422, f"Unknown tool {name}")
        _, _, model, handler = _REGISTRY[name]
        result = handler(c, model.model_validate(raw))
        return json.dumps(result, ensure_ascii=False, sort_keys=True, default=str), False
    except ValidationError as e:
        c.db.rollback()
        problems = [f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()]
        return json.dumps({"error": "Invalid arguments", "problems": problems}), True
    except AppError as e:
        c.db.rollback()
        log.info("tool %s failed order=%s status=%s", name, c.order_id, e.status)
        return json.dumps({"error": e.message}), True
