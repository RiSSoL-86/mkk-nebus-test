from pydantic import BaseModel, Field

from app_settings.app import AppSettings
from app_settings.brokers import BrokersSettings
from app_settings.database import DatabaseSettings
from app_settings.processing import ProcessingSettings


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    brokers: BrokersSettings = Field(default_factory=BrokersSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)


settings = Settings()
