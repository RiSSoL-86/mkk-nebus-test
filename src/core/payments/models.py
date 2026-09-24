from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import CheckConstraint, DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.common.models import BaseModel
from core.payments.choices import Currency, PaymentStatus


class Payment(BaseModel):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[Currency] = mapped_column(
        Enum(
            Currency,
            name="payment_currency",
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    description: Mapped[str] = mapped_column(String(2000))
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=PaymentStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    webhook_url: Mapped[str] = mapped_column(String(2083))
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    webhook_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
