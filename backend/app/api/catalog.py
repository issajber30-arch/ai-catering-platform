import datetime as dt
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.db import Db
from app.models.catalog import KashrutClass
from app.repositories import catalog as repo
from app.schemas.catalog import CategoryOut, DishDetailOut, DishOut
from app.schemas.logistics import AvailabilityOut
from app.services import availability
from app.services import catalog as service

router = APIRouter(prefix="/api")
Lang = Literal["he", "ar", "en"]


@router.get("/catalog/categories")
def categories(db: Db, lang: Lang = "he") -> list[CategoryOut]:
    return [service.category_out(c, lang) for c in repo.list_categories(db, active_only=True)]


@router.get("/catalog/dishes")
def dishes(
    db: Db,
    category_id: uuid.UUID | None = None,
    vegan: bool | None = None,
    vegetarian: bool | None = None,
    kashrut: KashrutClass | None = None,
    lang: Lang = "he",
) -> list[DishOut]:
    found = repo.list_dishes(
        db, public=True, category_id=category_id, vegan=vegan, vegetarian=vegetarian,
        kashrut=kashrut,
    )  # fmt: skip
    return [service.dish_out(d, lang) for d in found]


@router.get("/catalog/dishes/{dish_id}")
def dish(dish_id: uuid.UUID, db: Db, lang: Lang = "he") -> DishDetailOut:
    return service.dish_detail(db, dish_id, lang, public=True)


@router.get("/availability")
def get_availability(
    db: Db,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> AvailabilityOut:
    return availability.availability(db, start, end)
