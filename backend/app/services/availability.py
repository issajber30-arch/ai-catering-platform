import datetime as dt

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.logistics import BlockedDate, TimeSlot
from app.repositories import catalog as repo
from app.repositories import logistics as lrepo
from app.schemas.logistics import AvailabilityOut
from app.services.catalog import need, update

MAX_RANGE_DAYS = 366


def check_slot(start: dt.time, end: dt.time) -> None:
    if end <= start:
        raise AppError(422, "end_time must be after start_time")


def create_slot(db: Session, data: dict) -> TimeSlot:
    check_slot(data["start_time"], data["end_time"])
    return repo.save(db, TimeSlot(**data))


def update_slot(db: Session, slot_id, data: dict) -> TimeSlot:
    slot = need(db, TimeSlot, slot_id, "Time slot")
    check_slot(data.get("start_time", slot.start_time), data.get("end_time", slot.end_time))
    return update(db, slot, data)


def block_date(db: Session, data: dict) -> BlockedDate:
    try:
        return repo.save(db, BlockedDate(**data))
    except IntegrityError:
        db.rollback()
        raise AppError(409, "Date is already blocked") from None


def availability(db: Session, start: dt.date | None, end: dt.date | None) -> AvailabilityOut:
    start = start or dt.date.today()
    end = end or start + dt.timedelta(days=60)
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise AppError(422, f"'to' must be on/after 'from', within {MAX_RANGE_DAYS} days")
    return AvailabilityOut(
        blocked_dates=lrepo.blocked_between(db, start, end),
        time_slots=lrepo.active_slots(db),
    )
