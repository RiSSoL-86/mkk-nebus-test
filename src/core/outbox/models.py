from datetime import datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.common.models import BaseModel


class OutboxEvent(BaseModel):
    __tablename__ = "outbox"
    __table_args__ = (
        Index(
            "ix_outbox_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
