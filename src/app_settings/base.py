import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = os.getenv(
    key="ENV_FILE", default=str(Path(__file__).resolve().parents[1] / ".env")
)


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )
