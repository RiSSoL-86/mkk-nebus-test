from urllib.parse import quote

from pydantic import Field, SecretStr

from app_settings.base import EnvironmentSettings


class RabbitMQSettings(EnvironmentSettings):
    model_config = {"env_prefix": "RABBITMQ_"}

    user: str = Field(validation_alias="RABBITMQ_DEFAULT_USER")
    password: SecretStr = Field(validation_alias="RABBITMQ_DEFAULT_PASS")
    host: str
    port: int = Field(ge=1, le=65535)
    prefetch_count: int = Field(default=10, ge=1)
    connect_attempts: int = Field(default=10, ge=1)
    connect_retry_delay_seconds: float = Field(default=3.0, ge=0)

    @property
    def url(self) -> SecretStr:
        user = quote(string=self.user, safe="")
        password = quote(string=self.password.get_secret_value(), safe="")
        host = f"[{self.host}]" if ":" in self.host else self.host
        vhost = quote(string="/", safe="")
        return SecretStr(
            secret_value=f"amqp://{user}:{password}@{host}:{self.port}/{vhost}"
        )
