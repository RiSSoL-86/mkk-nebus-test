from app_settings.brokers.rabbitmq import RabbitMQSettings


def test_url_quotes_credentials_and_vhost():
    broker = RabbitMQSettings(
        RABBITMQ_DEFAULT_USER="us@er",
        RABBITMQ_DEFAULT_PASS="pa:ss/word",
        host="rabbitmq",
        port=5672,
    )

    url = broker.url.get_secret_value()

    assert url == "amqp://us%40er:pa%3Ass%2Fword@rabbitmq:5672/%2F"


def test_url_brackets_ipv6_host():
    broker = RabbitMQSettings(
        RABBITMQ_DEFAULT_USER="user",
        RABBITMQ_DEFAULT_PASS="pass",
        host="::1",
        port=5672,
    )

    url = broker.url.get_secret_value()

    assert url.startswith("amqp://user:pass@[::1]:5672/")
