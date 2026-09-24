from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from core.common.models import BaseModel


class BaseRepository[ModelT: BaseModel, IdT]:
    """Generic data-access layer."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, pk: IdT) -> ModelT | None:
        """Return a single entity by primary key, or None if absent."""
        return await self.session.get(entity=self.model, ident=pk)

    async def create(self, data: dict[str, Any]) -> ModelT:
        """Persist a new entity built from `data` and return it."""
        entity = self.model(**data)
        self.session.add(instance=entity)
        await self.session.flush()
        return entity

    async def update(self, pk: IdT, data: dict[str, Any]) -> ModelT | None:
        """Apply `data` to the entity with `pk`; None if it is absent."""
        entity = await self.get(pk=pk)
        if entity is None:
            return None
        for field, value in data.items():
            setattr(entity, field, value)
        await self.session.flush()
        return entity

    async def delete(self, pk: IdT) -> None:
        """Delete the entity with `pk` if it exists."""
        entity = await self.get(pk=pk)
        if entity is not None:
            await self.session.delete(instance=entity)
            await self.session.flush()

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[ModelT], int]:
        """Return a page of all entities together with the total count."""
        return await self._paginate(limit=limit, offset=offset)

    async def _paginate(
        self,
        *where: ColumnElement[bool],
        options: Sequence[ExecutableOption] = (),
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[ModelT], int]:
        """Return a filtered page with stable ordering and its total count."""
        stmt = (
            select(self.model)
            .where(*where)
            .options(*options)
            .order_by(
                self.model.created_at, *self.model.__mapper__.primary_key
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(statement=stmt)
        entities = result.scalars().all()

        count_stmt = select(func.count()).select_from(self.model).where(*where)
        total = await self.session.scalar(statement=count_stmt) or 0

        return entities, total
