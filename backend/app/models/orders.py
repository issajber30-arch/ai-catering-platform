import datetime as dt
import enum
import uuid
from decimal import Decimal

from sqlalchemy import CHAR, ForeignKey, Numeric, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.catalog import Dish, PricingUnit, pg_enum
from app.models.logistics import DeliveryZone, FulfillmentType

# shortcut: event types are a constant; move them to an owner-editable table if asked.
EVENT_TYPES = ("birthday", "family_celebration", "bar_bat_mitzvah", "shabbat", "other")


class OrderStatus(enum.StrEnum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    full_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    event_type: Mapped[str] = mapped_column(Text)
    event_date: Mapped[dt.date]
    adults: Mapped[int]
    children: Mapped[int]
    vegetarian_guests: Mapped[int] = mapped_column(default=0)
    vegan_guests: Mapped[int] = mapped_column(default=0)
    restricted_guests: Mapped[int] = mapped_column(default=0)
    dietary_notes: Mapped[str | None] = mapped_column(Text)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    snapshot_name: Mapped[str | None] = mapped_column(Text)
    snapshot_pricing_unit: Mapped[PricingUnit | None] = mapped_column(
        pg_enum(PricingUnit, "pricing_unit")
    )
    snapshot_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    snapshot_line_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    dish: Mapped[Dish] = relationship()


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"), default=OrderStatus.draft
    )
    version: Mapped[int] = mapped_column(default=1)
    access_token_hash: Mapped[str] = mapped_column(Text)
    fulfillment_type: Mapped[FulfillmentType] = mapped_column(
        SAEnum(FulfillmentType, name="fulfillment_type", create_type=False)
    )
    time_slot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("time_slots.id"))
    requested_at: Mapped[dt.datetime]
    delivery_address: Mapped[str | None] = mapped_column(Text)
    delivery_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_zones.id"))
    currency: Mapped[str] = mapped_column(CHAR(3))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    delivery_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    submitted_at: Mapped[dt.datetime | None]
    decided_at: Mapped[dt.datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    customer: Mapped[Customer] = relationship()
    event: Mapped[Event] = relationship()
    zone: Mapped[DeliveryZone | None] = relationship()
    items: Mapped[list[OrderItem]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class QuantityRule(Base):
    __tablename__ = "quantity_rules"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dish_categories.id"), unique=True)
    per_adult: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    per_child: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    round_step: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal(1))
