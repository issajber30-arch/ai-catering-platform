from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.leads import Lead


def list_leads(db: Session) -> list[Lead]:
    return list(db.scalars(select(Lead).order_by(Lead.created_at.desc())))


def add_all(db: Session, leads: list[Lead]) -> list[Lead]:
    db.add_all(leads)
    db.commit()
    for lead in leads:
        db.refresh(lead)
    return leads


def delete_demo(db: Session) -> int:
    deleted = db.execute(delete(Lead).where(Lead.is_demo)).rowcount
    db.commit()
    return deleted
