import logging
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

ModelType = TypeVar("ModelType", bound=DeclarativeBase)

logger = logging.getLogger(__name__)


class BaseDAO(Generic[ModelType]):
    model: type[ModelType]

    @classmethod
    async def add(
        cls,
        session: AsyncSession,
        **values: Any,
    ) -> ModelType:
        instance = cls.model(**values)

        try:
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
        except SQLAlchemyError:
            await session.rollback()
            logger.exception(
                "Ошибка добавления записи в %s",
                cls.model.__tablename__,
            )
            raise

        return instance

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        data_id: int,
    ) -> ModelType | None:
        return await session.get(cls.model, data_id)

    @classmethod
    async def get_one_or_none(
        cls,
        session: AsyncSession,
        **filters: Any,
    ) -> ModelType | None:
        statement = select(cls.model).filter_by(**filters)
        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def find_all(
        cls,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int | None = None,
        order_by: Any | None = None,
        **filters: Any,
    ) -> Sequence[ModelType]:
        statement = select(cls.model).filter_by(**filters)

        if order_by is not None:
            statement = statement.order_by(order_by)

        statement = statement.offset(offset)

        if limit is not None:
            statement = statement.limit(limit)

        result = await session.execute(statement)

        return result.unique().scalars().all()

    @classmethod
    async def update_one_by_id(
        cls,
        session: AsyncSession,
        data_id: int,
        values: BaseModel | dict[str, Any],
    ) -> ModelType | None:
        record = await session.get(cls.model, data_id)

        if record is None:
            return None

        values_dict = cls._get_values_dict(values)

        try:
            cls._apply_values(record, values_dict)
            await session.commit()
            await session.refresh(record)
        except SQLAlchemyError:
            await session.rollback()
            logger.exception(
                "Ошибка обновления id=%s в %s",
                data_id,
                cls.model.__tablename__,
            )
            raise

        return record

    @classmethod
    async def delete_by_id(
        cls,
        session: AsyncSession,
        data_id: int,
    ) -> bool:
        record = await session.get(cls.model, data_id)

        if record is None:
            return False

        try:
            await session.delete(record)
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.exception(
                "Ошибка удаления id=%s из %s",
                data_id,
                cls.model.__tablename__,
            )
            raise

        return True

    @classmethod
    async def count(
        cls,
        session: AsyncSession,
        **filters: Any,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(cls.model)
            .filter_by(**filters)
        )

        result = await session.execute(statement)

        return result.scalar_one()

    @classmethod
    def _get_values_dict(
        cls,
        values: BaseModel | dict[str, Any],
    ) -> dict[str, Any]:
        if isinstance(values, BaseModel):
            return values.model_dump(exclude_unset=True)

        return values.copy()

    @classmethod
    def _apply_values(
        cls,
        record: ModelType,
        values: dict[str, Any],
    ) -> None:
        allowed_fields = {
            column.name
            for column in cls.model.__table__.columns
        }

        unknown_fields = set(values) - allowed_fields

        if unknown_fields:
            raise ValueError(
                f"Неизвестные поля: {', '.join(sorted(unknown_fields))}"
            )

        for key, value in values.items():
            setattr(record, key, value)