import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.models.leads import LEAD_SOURCES, LEAD_STATUSES
from app.models.orders import EVENT_TYPES
from app.schemas.catalog import NotNullPatch, Out

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]
Email = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Guests = Annotated[int, Field(ge=1, le=1000)]
Budget = Annotated[Decimal, Field(ge=0, le=100000, max_digits=10, decimal_places=2)]
EventType = Literal[*EVENT_TYPES]
Source = Literal[*LEAD_SOURCES]
Status = Literal[*LEAD_STATUSES]


def _not_past(v: dt.date | None) -> dt.date | None:
    if v is not None and v < dt.date.today():
        raise ValueError("event_date must be today or later")
    return v


class LeadIn(BaseModel):
    full_name: Name
    phone: Phone | None = None
    email: Email | None = None
    notes: Notes | None = None
    event_type: EventType
    event_date: dt.date
    guests: Guests
    source: Source
    returning_customer: bool = False
    used_assistant: bool = False
    requested_quote: bool = False
    budget_per_guest: Budget | None = None

    _date = field_validator("event_date")(_not_past)


class LeadPatch(NotNullPatch):
    not_null: ClassVar[tuple[str, ...]] = (
        "full_name", "event_type", "event_date", "guests", "source", "status",
        "returning_customer", "used_assistant", "requested_quote",
    )  # fmt: skip
    full_name: Name | None = None
    phone: Phone | None = None
    email: Email | None = None
    notes: Notes | None = None
    event_type: EventType | None = None
    event_date: dt.date | None = None
    guests: Guests | None = None
    source: Source | None = None
    returning_customer: bool | None = None
    used_assistant: bool | None = None
    requested_quote: bool | None = None
    budget_per_guest: Budget | None = None
    status: Status | None = None

    _date = field_validator("event_date")(_not_past)


class LeadOut(Out):
    id: uuid.UUID
    full_name: str
    phone: str | None
    email: str | None
    notes: str | None
    event_type: str
    event_date: dt.date
    guests: int
    source: str
    returning_customer: bool
    used_assistant: bool
    requested_quote: bool
    budget_per_guest: Decimal | None
    currency: str
    status: str
    is_demo: bool
    created_at: dt.datetime
    chance: float = 0.0
    raw_prediction: float = 0.0
    clipped: bool = False


class LeadDetailOut(LeadOut):
    average_chance: float
    breakdown: dict[str, float]


class ModelCardOut(BaseModel):
    r2: float
    clipped_share: float
    accuracy_at_50: float
    base_rate: float
    train_rows: int
    holdout_rows: int
    synthetic: bool


class DemoIn(BaseModel):
    n: Annotated[int, Field(ge=1, le=50)] = 12
