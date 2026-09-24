from pydantic import Field

from app_settings.base import EnvironmentSettings


class GatewaySettings(EnvironmentSettings):
    """Emulated payment gateway behaviour."""

    model_config = {"env_prefix": "GATEWAY_"}

    min_delay_seconds: float = Field(default=2.0, ge=0)
    max_delay_seconds: float = Field(default=5.0, ge=0)
    success_rate: float = Field(default=0.9, ge=0, le=1)
