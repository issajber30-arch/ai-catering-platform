from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.settings import BusinessSettings
from app.repositories import settings as repo
from app.services import geo
from app.services.catalog import update as save


def get(db: Session) -> BusinessSettings:
    return repo.get(db)


def num(d: Decimal) -> str:
    text = f"{d:f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def update(db: Session, data: dict, geocode: geo.Geocoder) -> BusinessSettings:
    s = repo.get(db)
    if data["kitchen_address"] != s.kitchen_address:
        point = geo.locate(db, geocode, data["kitchen_address"])
        if point is None:
            raise AppError(422, "Kitchen address could not be found")
        data = data | {"kitchen_lat": point[0], "kitchen_lon": point[1]}
    return save(db, s, data)
