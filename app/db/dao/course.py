from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.course import Course


class CourseDAO(BaseDAO[Course]):
    model = Course

    @classmethod
    async def get_with_streams(
        cls,
        session: AsyncSession,
        course_id: int,
    ) -> Course | None:
        statement = (
            select(Course)
            .where(Course.id == course_id)
            .options(selectinload(Course.streams))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def find_all_with_streams(
        cls,
        session: AsyncSession,
        *,
        only_active: bool = False,
    ) -> Sequence[Course]:
        statement = select(Course).options(selectinload(Course.streams))

        if only_active:
            statement = statement.where(Course.is_active.is_(True))

        statement = statement.order_by(Course.title.asc(), Course.id.asc())

        result = await session.execute(statement)

        return result.unique().scalars().all()