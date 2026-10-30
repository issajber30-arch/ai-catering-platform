import datetime as dt
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.ai import AiConversation, AiMessage, ChangeProposal, ProposalStatus


def conversation(db: Session, order_id: uuid.UUID, *, create: bool = False):
    conv = db.scalar(select(AiConversation).where(AiConversation.order_id == order_id))
    if conv is None and create:
        conv = AiConversation(order_id=order_id)
        db.add(conv)
        db.flush()
    return conv


def messages(db: Session, conversation_id: uuid.UUID) -> list[AiMessage]:
    q = select(AiMessage).where(AiMessage.conversation_id == conversation_id)
    return list(db.scalars(q.order_by(AiMessage.seq)))


def recent_messages(db: Session, conversation_id: uuid.UUID, limit: int) -> list[AiMessage]:
    q = select(AiMessage).where(AiMessage.conversation_id == conversation_id)
    return list(reversed(list(db.scalars(q.order_by(AiMessage.seq.desc()).limit(limit)))))


def user_messages_since(db: Session, conversation_id: uuid.UUID, since: dt.datetime) -> int:
    q = select(func.count()).where(
        AiMessage.conversation_id == conversation_id,
        AiMessage.role == "user",
        AiMessage.created_at > since,
    )
    return db.scalar(q) or 0


def proposals(db: Session, order_id: uuid.UUID, status: ProposalStatus | None):
    q = select(ChangeProposal).where(ChangeProposal.order_id == order_id)
    if status:
        q = q.where(ChangeProposal.status == status)
    return list(db.scalars(q.order_by(ChangeProposal.created_at.desc(), ChangeProposal.id)))


def proposal(db: Session, order_id: uuid.UUID, proposal_id: uuid.UUID, *, lock: bool = False):
    q = select(ChangeProposal).where(
        ChangeProposal.id == proposal_id, ChangeProposal.order_id == order_id
    )
    if lock:
        q = q.with_for_update().execution_options(populate_existing=True)
    return db.scalar(q)


def expire_pending(db: Session, order_id: uuid.UUID) -> None:
    db.execute(
        update(ChangeProposal)
        .where(ChangeProposal.order_id == order_id, ChangeProposal.status == ProposalStatus.pending)
        .values(status=ProposalStatus.expired, decided_at=func.now())
    )
