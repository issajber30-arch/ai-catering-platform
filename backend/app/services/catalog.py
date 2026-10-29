from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.catalog import Dish, DishCategory
from app.repositories import catalog as repo
from app.schemas.catalog import (
    CategoryOut,
    DietaryIn,
    DishDetailOut,
    DishOut,
)

LANGS = ("he", "ar", "en")


def localize(out, lang: str):
    """Fill name/description for lang, falling back to Hebrew (the required language)."""
    out.name = getattr(out, f"name_{lang}") or out.name_he
    if hasattr(out, "description"):
        out.description = getattr(out, f"description_{lang}") or out.description_he
    return out


def category_out(c: DishCategory, lang: str = "he") -> CategoryOut:
    return localize(CategoryOut.model_validate(c), lang)


def dish_out(d: Dish, lang: str = "he") -> DishOut:
    return localize(DishOut.model_validate(d), lang)


def dish_detail(db: Session, dish_id, lang: str, public: bool) -> DishDetailOut:
    dish = repo.get_dish(db, dish_id)
    if dish is None or (public and not dish.is_available):
        raise AppError(404, "Dish not found")
    out = localize(DishDetailOut.model_validate(dish), lang)
    out.allergens = [
        {"allergen_id": a.id, "name": a.name, "status": s}
        for a, s in repo.allergens_with_status(db, dish_id)
    ]
    return out


def need(db: Session, model, obj_id, label: str):
    obj = repo.get(db, model, obj_id)
    if obj is None:
        raise AppError(404, f"{label} not found")
    return obj


def create_category(db: Session, data: dict) -> DishCategory:
    return repo.save(db, DishCategory(**data))


def update(db: Session, obj, data: dict):
    for k, v in data.items():
        setattr(obj, k, v)
    return repo.save(db, obj)


def delete_category(db: Session, category_id) -> None:
    cat = need(db, DishCategory, category_id, "Category")
    if repo.category_has_dishes(db, category_id):
        raise AppError(409, "Category still has dishes")
    repo.remove(db, cat)


def create_dish(db: Session, data: dict) -> Dish:
    need(db, DishCategory, data["category_id"], "Category")
    data["currency"] = data["currency"] or get_settings().default_currency
    return repo.save(db, Dish(**data))


def update_dish(db: Session, dish_id, data: dict) -> Dish:
    dish = need(db, Dish, dish_id, "Dish")
    if "category_id" in data:
        need(db, DishCategory, data["category_id"], "Category")
    return update(db, dish, data)


def set_dietary(db: Session, dish_id, body: DietaryIn) -> DishDetailOut:
    need(db, Dish, dish_id, "Dish")
    allergens = {a.allergen_id: a.status for a in body.allergens}
    if len(allergens) != len(body.allergens):
        raise AppError(422, "Duplicate allergen")
    if repo.allergen_ids(db, list(allergens)) != set(allergens):
        raise AppError(422, "Unknown allergen id")
    fields = body.model_dump(exclude={"allergens"})
    try:
        repo.replace_dietary(db, dish_id, fields, allergens)
    except IntegrityError:
        db.rollback()
        raise AppError(409, "Dish was changed concurrently") from None
    return dish_detail(db, dish_id, "he", public=False)
