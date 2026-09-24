from sqlalchemy import URL

from app_settings.base import EnvironmentSettings


class DatabaseSettings(EnvironmentSettings):
    model_config = {"env_prefix": "POSTGRES_"}

    db: str
    user: str
    password: str
    host: str
    port: int

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.db,
        )
