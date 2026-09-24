from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from core.payments.choices import PaymentStatus


class PaymentAccepted(BaseModel):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime
