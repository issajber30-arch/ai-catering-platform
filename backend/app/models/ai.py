import datetime as dt
import enum
import uuid
from decimal import Decimal

from sqlalchemy import FetchedValue, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.catalog import pg_enum


class ProposalStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    failed = "failed"


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class AiMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_conversations.id"))
    seq: Mapped[int] = mapped_column(server_default=FetchedValue())  # identity, DB-assigned
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[dict | list] = mapped_column(JSONB)
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    cache_read_tokens: Mapped[int | None]
    cache_creation_tokens: Mapped[int | None]
    stop_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class ChangeProposal(Base):
    __tablename__ = "ai_change_proposals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_conversations.id"))
    base_order_version: Mapped[int]
    changes: Mapped[list] = mapped_column(JSONB)
    diff: Mapped[list] = mapped_column(JSONB)
    rationale: Mapped[str | None] = mapped_column(Text)
    price_before: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_after: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[ProposalStatus] = mapped_column(
        pg_enum(ProposalStatus, "proposal_status"), default=ProposalStatus.pending
    )
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[dt.datetime | None]
    executed_at: Mapped[dt.datetime | None]
