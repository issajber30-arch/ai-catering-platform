import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.ai import ProposalStatus
from app.schemas.orders import Quantity


class ChatIn(BaseModel):
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class _Change(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddItem(_Change):
    op: Literal["add_item"]
    dish_id: uuid.UUID
    quantity: Quantity


class SetQuantity(_Change):
    op: Literal["set_quantity"]
    dish_id: uuid.UUID
    quantity: Quantity


class RemoveItem(_Change):
    op: Literal["remove_item"]
    dish_id: uuid.UUID


Change = Annotated[AddItem | SetQuantity | RemoveItem, Field(discriminator="op")]


class ProposeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: Annotated[list[Change], Field(min_length=1, max_length=20)]
    rationale: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
    ]


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    base_order_version: int
    changes: list[dict]
    diff: list[dict]  # [{dish_id, name, current, proposed}], null = not in the order
    rationale: str | None
    price_before: Decimal
    price_after: Decimal
    status: ProposalStatus
    created_at: dt.datetime
    decided_at: dt.datetime | None
    executed_at: dt.datetime | None


class ChatOut(BaseModel):
    reply: str
    proposals: list[ProposalOut]


class MessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    text: str
    created_at: dt.datetime
