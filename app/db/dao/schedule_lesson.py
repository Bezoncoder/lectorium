from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.schedule_lesson import ScheduleLesson


class ScheduleLessonDAO(BaseDAO[ScheduleLesson]):
    model = ScheduleLesson

    @classmethod
    async def get_by_course_id(
        cls,
        session: AsyncSession,
        course_id: int,
    ) -> Sequence[ScheduleLesson]:
        statement = (
            select(ScheduleLesson)
            .where(ScheduleLesson.course_id == course_id)
            .options(selectinload(ScheduleLesson.video))
            .order_by(
                ScheduleLesson.starts_at.asc(),
                ScheduleLesson.sort_order.asc(),
                ScheduleLesson.id.asc(),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()

    @classmethod
    async def get_with_video_by_id(
        cls,
        session: AsyncSession,
        lesson_id: int,
    ) -> ScheduleLesson | None:
        statement = (
            select(ScheduleLesson)
            .where(ScheduleLesson.id == lesson_id)
            .options(selectinload(ScheduleLesson.video))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def clear_by_course_id(
        cls,
        session: AsyncSession,
        course_id: int,
    ) -> None:
        try:
            statement = delete(ScheduleLesson).where(
                ScheduleLesson.course_id == course_id
            )

            await session.execute(statement)
            await session.commit()
        except Exception:
            await session.rollback()
            raise