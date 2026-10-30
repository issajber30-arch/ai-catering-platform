import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, ForeignKey, Numeric, SmallInteger, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class PricingUnit(enum.StrEnum):
    per_guest = "per_guest"
    per_tray = "per_tray"
    per_weight = "per_weight"
    per_item = "per_item"


class KashrutClass(enum.StrEnum):
    meat = "meat"
    dairy = "dairy"
    pareve = "pareve"


class AllergenStatus(enum.StrEnum):
    contains = "contains"
    free = "free"
    unknown = "unknown"


def pg_enum(cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(cls, name=name, create_type=False)


class DishCategory(Base):
    __tablename__ = "dish_categories"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    name_he: Mapped[str] = mapped_column(Text)
    name_ar: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class Dish(Base):
    __tablename__ = "dishes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dish_categories.id"))
    name_he: Mapped[str] = mapped_column(Text)
    name_ar: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    description_he: Mapped[str | None] = mapped_column(Text)
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(Text)
    pricing_unit: Mapped[PricingUnit] = mapped_column(pg_enum(PricingUnit, "pricing_unit"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_label: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(CHAR(3))
    min_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_available: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    dietary: Mapped["DishDietary | None"] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class DishDietary(Base):
    __tablename__ = "dish_dietary"
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    kashrut_class: Mapped[KashrutClass | None] = mapped_column(
        pg_enum(KashrutClass, "kashrut_class")
    )
    is_vegetarian: Mapped[bool | None]
    is_vegan: Mapped[bool | None]
    verified_at: Mapped[datetime | None]


class Allergen(Base):
    __tablename__ = "allergens"
    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class DishAllergen(Base):
    __tablename__ = "dish_allergens"
    dish_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dishes.id"), primary_key=True)
    allergen_id: Mapped[int] = mapped_column(ForeignKey("allergens.id"), primary_key=True)
    status: Mapped[AllergenStatus] = mapped_column(pg_enum(AllergenStatus, "allergen_status"))
