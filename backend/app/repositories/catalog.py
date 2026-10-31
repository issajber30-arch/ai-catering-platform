import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import (
    Allergen,
    Dish,
    DishAllergen,
    DishCategory,
    DishDietary,
)


def get(db: Session, model, obj_id):
    return db.get(model, obj_id)


def list_all(db: Session, model, *order):
    return list(db.scalars(select(model).order_by(*order)))


def save(db: Session, obj):
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def remove(db: Session, obj) -> None:
    db.delete(obj)
    db.commit()


def list_categories(db: Session, active_only: bool):
    q = select(DishCategory).order_by(DishCategory.sort_order, DishCategory.name_he)
    return list(db.scalars(q.where(DishCategory.is_active) if active_only else q))


def category_has_dishes(db: Session, category_id: uuid.UUID) -> bool:
    return db.scalar(select(Dish.id).where(Dish.category_id == category_id).limit(1)) is not None


def list_dishes(db: Session, *, public: bool, category_id=None, vegan=None, vegetarian=None,
                kashrut=None):  # fmt: skip
    q = select(Dish).options(selectinload(Dish.dietary)).order_by(Dish.name_he)
    if public:
        q = q.where(Dish.is_available)
    if category_id:
        q = q.where(Dish.category_id == category_id)
    if vegan is not None or vegetarian is not None or kashrut is not None:
        q = q.join(DishDietary)  # inner join: dishes with unknown dietary never match a filter
        if vegan is not None:
            q = q.where(DishDietary.is_vegan == vegan)
        if vegetarian is not None:
            q = q.where(DishDietary.is_vegetarian == vegetarian)
        if kashrut is not None:
            q = q.where(DishDietary.kashrut_class == kashrut)
    return list(db.scalars(q))


def get_dish(db: Session, dish_id: uuid.UUID):
    return db.scalar(select(Dish).options(selectinload(Dish.dietary)).where(Dish.id == dish_id))


def allergens_with_status(db: Session, dish_id: uuid.UUID) -> list[tuple[Allergen, str]]:
    rows = db.execute(
        select(Allergen, DishAllergen.status)
        .outerjoin(
            DishAllergen,
            (DishAllergen.allergen_id == Allergen.id) & (DishAllergen.dish_id == dish_id),
        )
        .order_by(Allergen.id)
    )
    return [(a, s or "unknown") for a, s in rows]  # missing row = unknown


def allergen_ids(db: Session, ids: list[int]) -> set[int]:
    return set(db.scalars(select(Allergen.id).where(Allergen.id.in_(ids))))


def replace_dietary(db: Session, dish_id, fields: dict, allergens: dict[int, str]) -> None:
    row = db.get(DishDietary, dish_id) or DishDietary(dish_id=dish_id)
    for k, v in fields.items():
        setattr(row, k, v)
    db.add(row)
    for old in db.scalars(select(DishAllergen).where(DishAllergen.dish_id == dish_id)):
        db.delete(old)
    db.flush()
    db.add_all(DishAllergen(dish_id=dish_id, allergen_id=a, status=s) for a, s in allergens.items())
    db.commit()
