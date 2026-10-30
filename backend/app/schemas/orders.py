import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.catalog import PricingUnit
from app.models.logistics import FulfillmentType
from app.models.orders import EVENT_TYPES, OrderStatus
from app.schemas.catalog import Name, Out

Guests = Annotated[int, Field(ge=0, le=100000)]
Quantity = Annotated[Decimal, Field(gt=0, le=100000, max_digits=10, decimal_places=2)]
Serving = Annotated[Decimal, Field(ge=0, le=100000, max_digits=10, decimal_places=3)]
Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.\S+$")
]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Note = Annotated[str, StringConstraints(max_length=1000)]


class CustomerIn(BaseModel):
    full_name: Name
    email: Email | None = None
    phone: Phone | None = None

    @model_validator(mode="after")
    def _contact(self):
        if not (self.email or self.phone):
            raise ValueError("email or phone is required")
        return self


class EventIn(BaseModel):
    event_type: Literal[*EVENT_TYPES]
    event_date: dt.date
    adults: Guests
    children: Guests
    vegetarian_guests: Guests = 0
    vegan_guests: Guests = 0
    restricted_guests: Guests = 0
    dietary_notes: Annotated[str | None, StringConstraints(max_length=2000)] = None

    @model_validator(mode="after")
    def _subsets(self):
        total = self.adults + self.children
        if total <= 0:
            raise ValueError("at least one guest is required")
        if max(self.vegetarian_guests, self.vegan_guests, self.restricted_guests) > total:
            raise ValueError("dietary guest counts cannot exceed adults + children")
        return self


class OrderCreate(BaseModel):
    customer: CustomerIn
    event: EventIn
    fulfillment_type: FulfillmentType
    time_slot_id: uuid.UUID
    delivery_address: Address | None = None
    delivery_zone_id: uuid.UUID | None = None


class OrderPatch(BaseModel):
    """Only the fields that are sent change; `event`, if sent, replaces the whole event."""

    version: int
    event: EventIn | None = None
    fulfillment_type: FulfillmentType | None = None
    time_slot_id: uuid.UUID | None = None
    delivery_address: Address | None = None
    delivery_zone_id: uuid.UUID | None = None


class ItemIn(BaseModel):
    quantity: Quantity
    version: int


class SubmitIn(BaseModel):
    version: int


class DecisionIn(BaseModel):
    note: Note | None = None


class CancelIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class ItemOut(BaseModel):
    dish_id: uuid.UUID
    name: str
    pricing_unit: PricingUnit
    unit: str | None
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal


class CustomerOut(Out):
    full_name: str
    email: str | None
    phone: str | None


class EventOut(Out):
    event_type: str
    event_date: dt.date
    adults: int
    children: int
    vegetarian_guests: int
    vegan_guests: int
    restricted_guests: int
    dietary_notes: str | None


class PricingOut(BaseModel):
    items: list[ItemOut]
    subtotal: Decimal
    delivery_fee: Decimal | None  # null: address not found, fee confirmed by the business
    total: Decimal
    currency: str


class OrderOut(PricingOut):
    id: uuid.UUID
    status: OrderStatus
    version: int
    customer: CustomerOut
    event: EventOut
    fulfillment_type: FulfillmentType
    time_slot_id: uuid.UUID | None
    requested_at: dt.datetime
    delivery_address: str | None
    delivery_zone_id: uuid.UUID | None
    submitted_at: dt.datetime | None
    decided_at: dt.datetime | None
    decision_note: str | None
    cancelled_at: dt.datetime | None
    cancel_note: str | None
    warnings: list[str]
    delivery_km: Decimal | None
    delivery_fee_estimated: bool


class OrderCreated(OrderOut):
    access_token: str  # returned only once, on creation


class OrderSummary(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    customer_name: str
    event_type: str
    event_date: dt.date
    guests: int
    total: Decimal | None
    currency: str
    submitted_at: dt.datetime | None
    created_at: dt.datetime


class RecommendationOut(BaseModel):
    dish_id: uuid.UUID
    category_id: uuid.UUID
    recommended: Decimal | None
    reason: str | None


class QuantityRuleIn(BaseModel):
    per_adult: Serving
    per_child: Serving
    round_step: Annotated[Decimal, Field(gt=0, le=100000, max_digits=10, decimal_places=3)] = (
        Decimal(1)
    )


class QuantityRuleOut(Out):
    category_id: uuid.UUID
    per_adult: Decimal
    per_child: Decimal
    round_step: Decimal
