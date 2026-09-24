from abc import ABC, abstractmethod
from typing import Any


class BaseService[ResultT](ABC):
    """Application service implementing a single use case."""

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> ResultT: ...
