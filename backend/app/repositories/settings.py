from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.settings import BusinessSettings, GeocodeCache


def get(db: Session) -> BusinessSettings:
    return db.get_one(BusinessSettings, True)


def cached(db: Session, key: str) -> GeocodeCache | None:
    return db.get(GeocodeCache, key)


def cache(db: Session, key: str, point: tuple[float, float] | None) -> None:
    # shortcut: no eviction; add a TTL/size cap if unique-address volume grows (Phase 6).
    lat, lon = point or (None, None)
    db.execute(
        insert(GeocodeCache)
        .values(address_norm=key, lat=lat, lon=lon, found=point is not None)
        .on_conflict_do_nothing()
    )
    db.commit()
