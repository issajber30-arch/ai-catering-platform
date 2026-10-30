import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.logistics import BlockedDate, TimeSlot


def blocked_between(db: Session, start: dt.date, end: dt.date):
    q = select(BlockedDate).where(BlockedDate.date.between(start, end)).order_by(BlockedDate.date)
    return list(db.scalars(q))


def active_slots(db: Session):
    q = select(TimeSlot).where(TimeSlot.is_active)
    return list(db.scalars(q.order_by(TimeSlot.weekday, TimeSlot.start_time)))
