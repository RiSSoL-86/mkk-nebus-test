"""Create the payments and outbox tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "736dd32fea29"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create payment storage and the unpublished-event index.
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "currency",
            sa.Enum("RUB", "USD", "EUR", name="payment_currency"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "succeeded", "failed", name="payment_status"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("webhook_url", sa.String(length=2083), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "webhook_delivered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    # Remove payment storage and its enum types.
    op.drop_index(
        "ix_outbox_unpublished",
        table_name="outbox",
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.drop_table("outbox")
    op.drop_table("payments")
    sa.Enum(name="payment_status").drop(op.get_bind())
    sa.Enum(name="payment_currency").drop(op.get_bind())
