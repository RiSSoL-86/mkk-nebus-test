from faststream import FastStream

from core.brokers.rabbitmq import RabbitMQBroker
from services.payment_processor.handlers import PaymentNewHandler

broker = RabbitMQBroker()
handler = PaymentNewHandler(producer=broker.producer)
broker.consumer.subscribe(handler=handler.handle)
app = FastStream(broker.raw_broker)


@app.on_startup
async def connect() -> None:
    await broker.connect()


@app.after_startup
async def setup() -> None:
    await broker.setup()
