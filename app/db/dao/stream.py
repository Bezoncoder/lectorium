from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.stream import Stream, StreamStatus


class StreamDAO(BaseDAO[Stream]):
    model = Stream

    @classmethod
    async def get_with_course(
        cls,
        session: AsyncSession,
        stream_id: int,
    ) -> Stream | None:
        statement = (
            select(Stream)
            .where(Stream.id == stream_id)
            .options(selectinload(Stream.course))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_with_relations(
        cls,
        session: AsyncSession,
        stream_id: int,
    ) -> Stream | None:
        statement = (
            select(Stream)
            .where(Stream.id == stream_id)
            .options(
                selectinload(Stream.course),
                selectinload(Stream.lessons),
                selectinload(Stream.videos),
                selectinload(Stream.enrollments),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_by_course_id(
        cls,
        session: AsyncSession,
        course_id: int,
    ) -> Sequence[Stream]:
        statement = (
            select(Stream)
            .where(Stream.course_id == course_id)
            .order_by(
                Stream.starts_on.desc().nullslast(),
                Stream.title.asc(),
                Stream.id.asc(),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()

    @classmethod
    async def get_active_by_course_id(
        cls,
        session: AsyncSession,
        course_id: int,
    ) -> Sequence[Stream]:
        statement = (
            select(Stream)
            .where(
                Stream.course_id == course_id,
                Stream.status == StreamStatus.ACTIVE,
            )
            .order_by(
                Stream.starts_on.asc().nullslast(),
                Stream.id.asc(),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()