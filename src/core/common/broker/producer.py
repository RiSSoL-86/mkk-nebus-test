from abc import ABC, abstractmethod
from typing import Any


class BaseProducer(ABC):
    """Broker-agnostic payment event sender."""

    @abstractmethod
    async def publish(
        self, payload: dict[str, Any], event_type: str
    ) -> None: ...

    @abstractmethod
    async def retry(self, payload: dict[str, Any], attempt: int) -> None: ...

    @abstractmethod
    async def dead_letter(
        self, payload: dict[str, Any], attempt: int
    ) -> None: ...
