from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from core.common.broker.consumer import BaseConsumer
from core.common.broker.producer import BaseProducer


class BaseBroker(ABC):
    """Message bus connection that owns its producer and consumer."""

    producer: BaseProducer
    consumer: BaseConsumer

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def setup(self) -> None: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def __aenter__(self) -> Self: ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
