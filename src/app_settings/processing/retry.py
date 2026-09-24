from pydantic import Field

from app_settings.base import EnvironmentSettings


class RetrySettings(EnvironmentSettings):
    """Message-level processing retry/DLQ policy."""

    model_config = {"env_prefix": "RETRY_"}

    max_attempts: int = Field(default=3, ge=1)
    backoff_base_seconds: float = Field(default=2.0, ge=0)
