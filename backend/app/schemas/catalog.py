import uuid
from decimal import Decimal
from typing import Annotated, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.catalog import AllergenStatus, KashrutClass, PricingUnit

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
OptName = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=200)]
Text = Annotated[str | None, StringConstraints(max_length=2000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NotNullPatch(BaseModel):
    """PATCH body: explicit null is allowed only for fields that are nullable in the DB."""

    not_null: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_null(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None and field in self.not_null:
                raise ValueError(f"{field} cannot be null")
        return self


# ---- categories
class CategoryIn(BaseModel):
    name_he: Name
    name_ar: OptName = None
    name_en: OptName = None
    sort_order: int = 0
    is_active: bool = True


class CategoryPatch(NotNullPatch):
    not_null: ClassVar[tuple[str, ...]] = ("name_he", "sort_order", "is_active")
    name_he: Name | None = None
    name_ar: OptName = None
    name_en: OptName = None
    sort_order: int | None = None
    is_active: bool | None = None


class CategoryOut(Out):
    id: uuid.UUID
    name: str = ""  # resolved for ?lang=, falls back to Hebrew
    name_he: str
    name_ar: str | None
    name_en: str | None
    sort_order: int
    is_active: bool


# ---- dishes
class DishIn(BaseModel):
    category_id: uuid.UUID
    name_he: Name
    name_ar: OptName = None
    name_en: OptName = None
    description_he: Text = None
    description_ar: Text = None
    description_en: Text = None
    pricing_unit: PricingUnit
    unit_price: Money
    unit_label: OptName = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    min_quantity: Money | None = None
    is_available: bool = True


class DishPatch(NotNullPatch):
    not_null: ClassVar[tuple[str, ...]] = (
        "category_id", "name_he", "pricing_unit", "unit_price", "currency", "is_available",
    )  # fmt: skip
    category_id: uuid.UUID | None = None
    name_he: Name | None = None
    name_ar: OptName = None
    name_en: OptName = None
    description_he: Text = None
    description_ar: Text = None
    description_en: Text = None
    pricing_unit: PricingUnit | None = None
    unit_price: Money | None = None
    unit_label: OptName = None
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    min_quantity: Money | None = None
    is_available: bool | None = None


class DietaryOut(Out):
    kashrut_class: KashrutClass | None = None
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None


class AllergenOut(BaseModel):
    allergen_id: int
    name: str
    status: AllergenStatus


class DishOut(Out):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str = ""
    description: str | None = None
    name_he: str
    name_ar: str | None
    name_en: str | None
    description_he: str | None
    description_ar: str | None
    description_en: str | None
    image_path: str | None
    pricing_unit: PricingUnit
    unit_price: Decimal
    unit_label: str | None
    currency: str
    min_quantity: Decimal | None
    is_available: bool
    dietary: DietaryOut = DietaryOut()  # no row -> all unknown (null)

    @field_validator("dietary", mode="before")
    @classmethod
    def _missing_dietary_row(cls, v):
        return v if v is not None else DietaryOut()


class DishDetailOut(DishOut):
    allergens: list[AllergenOut] = []


class AllergenStatusIn(BaseModel):
    allergen_id: int
    status: AllergenStatus


class DietaryIn(BaseModel):
    kashrut_class: KashrutClass | None = None
    is_vegetarian: bool | None = None
    is_vegan: bool | None = None
    allergens: list[AllergenStatusIn] = Field(default=[], max_length=50)
