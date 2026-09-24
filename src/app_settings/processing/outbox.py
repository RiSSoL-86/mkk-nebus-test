from pydantic import Field

from app_settings.base import EnvironmentSettings


class OutboxSettings(EnvironmentSettings):
    """Outbox relay polling policy."""

    model_config = {"env_prefix": "OUTBOX_"}

    poll_interval_seconds: float = Field(default=0.5, ge=0)
    batch_size: int = Field(default=50, ge=1)
