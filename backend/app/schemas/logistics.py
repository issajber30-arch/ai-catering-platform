import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import BaseModel, Field, StringConstraints

from app.models.logistics import FulfillmentType
from app.schemas.catalog import NotNullPatch, Out

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Weekday = Annotated[int | None, Field(ge=0, le=6)]


class ZoneIn(BaseModel):
    name: Name
    fee: Money
    definition: dict = Field(default={}, max_length=50)
    is_active: bool = True


class ZonePatch(NotNullPatch):
    not_null: ClassVar[tuple[str, ...]] = ("name", "fee", "definition", "is_active")
    name: Name | None = None
    fee: Money | None = None
    definition: dict | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class ZoneOut(Out):
    id: uuid.UUID
    name: str
    fee: Decimal
    definition: dict
    is_active: bool


class SlotIn(BaseModel):
    fulfillment_type: FulfillmentType
    weekday: Weekday = None
    start_time: dt.time
    end_time: dt.time
    capacity: Annotated[int | None, Field(ge=0, le=100000)] = None
    is_active: bool = True


class SlotPatch(NotNullPatch):
    not_null: ClassVar[tuple[str, ...]] = (
        "fulfillment_type",
        "start_time",
        "end_time",
        "is_active",
    )
    fulfillment_type: FulfillmentType | None = None
    weekday: Weekday = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    capacity: Annotated[int | None, Field(ge=0, le=100000)] = None
    is_active: bool | None = None


class SlotOut(Out):
    id: uuid.UUID
    fulfillment_type: FulfillmentType
    weekday: int | None
    start_time: dt.time
    end_time: dt.time
    capacity: int | None
    is_active: bool


class BlockedIn(BaseModel):
    date: dt.date
    reason: Annotated[str | None, StringConstraints(max_length=500)] = None


class BlockedOut(Out):
    id: uuid.UUID
    date: dt.date
    reason: str | None


class AvailabilityOut(BaseModel):
    blocked_dates: list[BlockedOut]
    time_slots: list[SlotOut]
