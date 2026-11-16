import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CHAR, Numeric, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Order matters: the first entry is the regression's reference level (lead_model.py).
LEAD_SOURCES = ("instagram", "google", "referral", "whatsapp", "phone", "other")
LEAD_STATUSES = ("new", "contacted", "won", "lost")


class Lead(Base):
    """A potential customer. Name/contact/notes are stored but never fed to the model or the AI."""

    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    full_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(Text)
    event_date: Mapped[dt.date]
    guests: Mapped[int]
    source: Mapped[str] = mapped_column(Text)
    returning_customer: Mapped[bool] = mapped_column(default=False, server_default=false())
    used_assistant: Mapped[bool] = mapped_column(default=False, server_default=false())
    requested_quote: Mapped[bool] = mapped_column(default=False, server_default=false())
    budget_per_guest: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), default="ILS", server_default="ILS")
    status: Mapped[str] = mapped_column(Text, default="new", server_default="new")
    is_demo: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
