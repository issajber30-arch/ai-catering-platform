import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.ai import AiConversation, AiMessage
from app.models.orders import OrderStatus
from app.repositories import ai as repo
from app.services import orders

RATE_LIMIT = 30  # user messages per order per rolling hour
HISTORY_ROWS = 40  # budget: older rows are not sent to the model


def start(db: Session, order_id: uuid.UUID, token: str | None) -> AiConversation:
    """Checks token, draft status and the rate limit; returns the order's conversation."""
    order = orders.customer_order(db, order_id, token)
    if order.status != OrderStatus.draft:
        raise AppError(409, "Order can no longer be changed", code="invalid_transition")
    conv = repo.conversation(db, order_id, create=True)
    since = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
    if repo.user_messages_since(db, conv.id, since) >= RATE_LIMIT:
        raise AppError(429, "Too many messages. Please try again later.", code="rate_limited")
    return conv


def add(db: Session, conv_id: uuid.UUID, role: str, content, **usage) -> None:
    db.add(AiMessage(conversation_id=conv_id, role=role, content=content, **usage))
    db.commit()


def history(db: Session, conv_id: uuid.UUID) -> list[dict]:
    """API-format messages. Starts at a user text row so tool_use/tool_result pairs stay whole."""
    rows = repo.recent_messages(db, conv_id, HISTORY_ROWS)
    while rows and rows[0].role != "user":
        rows.pop(0)
    return [
        {
            "role": "assistant" if r.role == "assistant" else "user",
            "content": r.content["text"] if r.role == "user" else r.content,
        }
        for r in rows
    ]


def visible(db: Session, order_id, token) -> list[dict]:
    """What the customer sees: user and assistant text only (no tool traffic or thinking)."""
    orders.customer_order(db, order_id, token)
    conv = repo.conversation(db, order_id)
    out = []
    for r in repo.recent_messages(db, conv.id, 400) if conv else []:  # bounded
        if r.role == "user":
            text = r.content["text"]
        elif r.role == "assistant":
            text = "".join(b.get("text", "") for b in r.content if b.get("type") == "text")
        else:
            continue
        if text:
            out.append({"id": r.id, "role": r.role, "text": text, "created_at": r.created_at})
    return out
