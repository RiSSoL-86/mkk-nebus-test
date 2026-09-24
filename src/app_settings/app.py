from pydantic import Field, SecretStr

from app_settings.base import EnvironmentSettings


class AppSettings(EnvironmentSettings):
    project_name: str = "MKK Nebus Payments"
    debug: bool = False
    api_key: SecretStr = Field(min_length=1)
