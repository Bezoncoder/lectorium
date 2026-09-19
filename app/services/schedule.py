from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.course import CourseDAO
from app.db.dao.schedule_lesson import ScheduleLessonDAO
from app.db.dao.video import VideoDAO
from app.db.models.course import Course
from app.db.models.schedule_lesson import ScheduleLesson
from app.db.models.video import Video
from app.db.session import connection
from app.schemas.course import CourseUpdatePydantic
from app.schemas.schedule_lesson import (
    ScheduleLessonCreatePydantic,
    ScheduleLessonUpdatePydantic,
)


MOSCOW_TZ = ZoneInfo("Europe/Moscow")


class ScheduleService:
    @staticmethod
    def parse_moscow_datetime(raw_value: str) -> datetime:
        value = datetime.fromisoformat(raw_value)

        if value.tzinfo is None:
            return value.replace(tzinfo=MOSCOW_TZ)

        return value.astimezone(MOSCOW_TZ)

    @staticmethod
    @connection
    async def get_admin_page_data(
        *,
        session: AsyncSession,
    ) -> tuple[
        Course | None,
        list[ScheduleLesson],
        list[Video],
    ]:
        course = await CourseDAO.get_current(session)

        if course is None:
            return None, [], []

        lessons = list(
            await ScheduleLessonDAO.get_by_course_id(
                session=session,
                course_id=course.id,
            )
        )

        videos = list(
            await VideoDAO.find_all(
                session=session,
                order_by=Video.created_at.desc(),
            )
        )

        return course, lessons, videos

    @staticmethod
    @connection
    async def update_course(
        *,
        title: str,
        dates: str,
        timezone: str,
        telemost_url: str | None,
        session: AsyncSession,
    ) -> Course | None:
        course = await CourseDAO.get_current(session)

        if course is None:
            return None

        data = CourseUpdatePydantic(
            title=title.strip(),
            dates=dates.strip(),
            timezone=timezone.strip(),
            telemost_url=telemost_url.strip()
            if telemost_url
            else None,
        )

        return await CourseDAO.update_one_by_id(
            session=session,
            data_id=course.id,
            values=data,
        )

    @staticmethod
    @connection
    async def create_lesson(
        *,
        title: str,
        starts_at: str,
        video_id: str | None,
        session: AsyncSession,
    ) -> ScheduleLesson | None:
        course = await CourseDAO.get_current(session)

        if course is None:
            return None

        lessons = await ScheduleLessonDAO.get_by_course_id(
            session=session,
            course_id=course.id,
        )

        selected_video_id = int(video_id) if video_id else None

        data = ScheduleLessonCreatePydantic(
            title=title.strip(),
            starts_at=ScheduleService.parse_moscow_datetime(
                starts_at
            ),
            video_id=selected_video_id,
            sort_order=len(lessons) + 1,
        )

        return await ScheduleLessonDAO.add(
            session=session,
            course_id=course.id,
            **data.model_dump(),
        )

    @staticmethod
    @connection
    async def update_lesson(
        lesson_id: int,
        *,
        title: str,
        starts_at: str,
        video_id: str | None,
        sort_order: int,
        session: AsyncSession,
    ) -> ScheduleLesson | None:
        lesson = await ScheduleLessonDAO.get_with_video_by_id(
            session=session,
            lesson_id=lesson_id,
        )

        if lesson is None:
            return None

        selected_video_id = int(video_id) if video_id else None

        data = ScheduleLessonUpdatePydantic(
            title=title.strip(),
            starts_at=ScheduleService.parse_moscow_datetime(
                starts_at
            ),
            video_id=selected_video_id,
            sort_order=sort_order,
        )

        return await ScheduleLessonDAO.update_one_by_id(
            session=session,
            data_id=lesson_id,
            values=data,
        )

    @staticmethod
    @connection
    async def delete_lesson(
        lesson_id: int,
        *,
        session: AsyncSession,
    ) -> bool:
        return await ScheduleLessonDAO.delete_by_id(
            session=session,
            data_id=lesson_id,
        )

    @staticmethod
    @connection
    async def clear_lessons(
        *,
        session: AsyncSession,
    ) -> bool:
        course = await CourseDAO.get_current(session)

        if course is None:
            return False

        await ScheduleLessonDAO.clear_by_course_id(
            session=session,
            course_id=course.id,
        )

        return True