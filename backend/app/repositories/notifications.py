import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.orders import Notification, Order, OrderStatus


def claim(db: Session, order_id: uuid.UUID, kind: str, channel: str) -> bool:
    """Insert the 'sending' row; False if this (order, kind, channel) was already claimed."""
    result = db.execute(
        insert(Notification.__table__)
        .values(order_id=order_id, kind=kind, channel=channel, status="sending")
        .on_conflict_do_nothing()
        .returning(Notification.__table__.c.order_id)
    )
    claimed = result.first() is not None
    db.commit()
    return claimed


def finish(db: Session, order_id: uuid.UUID, kind: str, channel: str, status: str) -> None:
    db.execute(
        update(Notification)
        .where(Notification.order_id == order_id, Notification.kind == kind)
        .where(Notification.channel == channel)
        .values(status=status)
    )
    db.commit()


def get_order(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.get(Order, order_id)  # no row lock: callers run after their commit


def active_order_ids(db: Session, day: dt.date) -> list[uuid.UUID]:
    from app.models.orders import Event

    q = select(Order.id).join(Event, Order.event_id == Event.id)
    q = q.where(Order.status.in_((OrderStatus.approved, OrderStatus.in_kitchen)))
    return list(db.scalars(q.where(Event.event_date == day)))
