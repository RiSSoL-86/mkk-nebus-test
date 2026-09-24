from pydantic import Field

from app_settings.base import EnvironmentSettings


class WebhookSettings(EnvironmentSettings):
    """Webhook request settings."""

    model_config = {"env_prefix": "WEBHOOK_"}

    timeout_seconds: float = Field(default=5.0, ge=0)
