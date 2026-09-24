from pydantic import BaseModel, Field

from app_settings.processing.gateway import GatewaySettings
from app_settings.processing.outbox import OutboxSettings
from app_settings.processing.retry import RetrySettings
from app_settings.processing.webhook import WebhookSettings

__all__ = [
    "GatewaySettings",
    "OutboxSettings",
    "ProcessingSettings",
    "RetrySettings",
    "WebhookSettings",
]


class ProcessingSettings(BaseModel):
    gateway: GatewaySettings = Field(default_factory=GatewaySettings)
    webhook: WebhookSettings = Field(default_factory=WebhookSettings)
    outbox: OutboxSettings = Field(default_factory=OutboxSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)
