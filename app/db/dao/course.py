from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.course import Course


class CourseDAO(BaseDAO[Course]):
    model = Course

    @classmethod
    async def get_current(
        cls,
        session: AsyncSession,
    ) -> Course | None:
        statement = (
            select(Course)
            .options(selectinload(Course.lessons))
            .order_by(Course.id.asc())
            .limit(1)
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()