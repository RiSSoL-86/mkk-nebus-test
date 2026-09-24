from pydantic import BaseModel, Field

from app_settings.brokers.rabbitmq import RabbitMQSettings

__all__ = ["BrokersSettings", "RabbitMQSettings"]


class BrokersSettings(BaseModel):
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
