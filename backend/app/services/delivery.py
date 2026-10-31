from sqlalchemy.orm import Session

from app.models.logistics import DeliveryZone
from app.repositories import catalog as repo
from app.services.catalog import need, update


def create_zone(db: Session, data: dict) -> DeliveryZone:
    return repo.save(db, DeliveryZone(**data))


def update_zone(db: Session, zone_id, data: dict) -> DeliveryZone:
    return update(db, need(db, DeliveryZone, zone_id, "Delivery zone"), data)
