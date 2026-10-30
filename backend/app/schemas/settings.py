from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.schemas.catalog import Out

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class SettingsIn(BaseModel):
    lead_time_days: Annotated[int, Field(ge=0, le=365)]
    min_food_total: Money
    delivery_base_fee: Money
    delivery_per_km: Money
    delivery_max_km: Annotated[Decimal, Field(ge=0, le=500, max_digits=6, decimal_places=2)]
    kitchen_address: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
    ]


class SettingsOut(Out, SettingsIn):
    kitchen_lat: float
    kitchen_lon: float


class PublicSettingsOut(BaseModel):
    lead_time_days: int
    min_food_total: Decimal
    max_km: Decimal


class DeliveryQuoteIn(BaseModel):
    address: Annotated[str, Field(min_length=1, max_length=500)]


class DeliveryQuoteOut(BaseModel):
    found: bool
    km: Decimal | None
    fee: Decimal | None
    max_km: Decimal
    too_far: bool
