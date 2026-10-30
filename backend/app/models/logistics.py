import datetime as dt
import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Numeric, SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FulfillmentType(enum.StrEnum):
    pickup = "pickup"
    delivery = "delivery"


class DeliveryZone(Base):
    __tablename__ = "delivery_zones"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(Text)
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    definition: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)


class TimeSlot(Base):
    __tablename__ = "time_slots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        SAEnum(FulfillmentType, name="fulfillment_type", create_type=False)
    )
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    start_time: Mapped[dt.time]
    end_time: Mapped[dt.time]
    capacity: Mapped[int | None]
    is_active: Mapped[bool] = mapped_column(default=True)


class BlockedDate(Base):
    __tablename__ = "blocked_dates"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    date: Mapped[dt.date] = mapped_column(unique=True)
    reason: Mapped[str | None] = mapped_column(Text)
