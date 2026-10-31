import datetime as dt
from decimal import Decimal

from sqlalchemy import Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class BusinessSettings(Base):
    """Single row (id is always true)."""

    __tablename__ = "business_settings"
    id: Mapped[bool] = mapped_column(primary_key=True, default=True)
    lead_time_days: Mapped[int]
    edit_cutoff_hours: Mapped[int]
    min_food_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_base_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_max_km: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    kitchen_address: Mapped[str] = mapped_column(Text)
    kitchen_lat: Mapped[float]
    kitchen_lon: Mapped[float]


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"
    address_norm: Mapped[str] = mapped_column(Text, primary_key=True)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    found: Mapped[bool]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
