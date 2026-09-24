from uuid import UUID

from pydantic import BaseModel


class PaymentNewEvent(BaseModel):
    """Payload of the `payments.new` outbox event."""

    payment_id: UUID
