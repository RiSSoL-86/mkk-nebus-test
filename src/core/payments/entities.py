from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from core.payments.choices import Currency, PaymentStatus


class PaymentData(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: Currency
    description: str = Field(max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentEntity(PaymentData):
    model_config = ConfigDict(frozen=True)

    payment_id: UUID
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None = None
    webhook_delivered_at: datetime | None = None
