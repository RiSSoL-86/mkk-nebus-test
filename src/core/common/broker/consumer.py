from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

MessageHandler = Callable[[dict[str, Any], int], Awaitable[None]]


class BaseConsumer(ABC):
    """Delivers incoming payment events to a handler."""

    @abstractmethod
    def subscribe(self, handler: MessageHandler) -> None: ...
