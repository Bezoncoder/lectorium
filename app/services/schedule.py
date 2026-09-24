from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.course import CourseDAO
from app.db.dao.schedule_lesson import ScheduleLessonDAO
from app.db.dao.stream import StreamDAO
from app.db.dao.video import VideoDAO
from app.db.models.course import Course
from app.db.models.schedule_lesson import ScheduleLesson
from app.db.models.stream import Stream, StreamStatus
from app.db.models.video import Video
from app.db.session import connection
from app.schemas.course import (
    CourseCreatePydantic,
    CourseUpdatePydantic,
)
from app.schemas.schedule_lesson import (
    ScheduleLessonCreatePydantic,
    ScheduleLessonUpdatePydantic,
)
from app.schemas.stream import StreamCreatePydantic, StreamUpdatePydantic


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
    async def get_courses_for_admin(
        *,
        session: AsyncSession,
    ) -> list[Course]:
        courses = await CourseDAO.find_all_with_streams(session=session)

        return list(courses)

    @staticmethod
    @connection
    async def get_course_with_streams(
        course_id: int,
        *,
        session: AsyncSession,
    ) -> Course | None:
        return await CourseDAO.get_with_streams(
            session=session,
            course_id=course_id,
        )

    @staticmethod
    @connection
    async def create_course(
        *,
        title: str,
        description: str | None,
        is_active: bool,
        session: AsyncSession,
    ) -> Course:
        data = CourseCreatePydantic(
            title=title,
            description=description,
            is_active=is_active,
        )

        return await CourseDAO.add(
            session=session,
            **data.model_dump(),
        )

    @staticmethod
    @connection
    async def update_course(
        course_id: int,
        *,
        title: str,
        description: str | None,
        is_active: bool,
        session: AsyncSession,
    ) -> Course | None:
        data = CourseUpdatePydantic(
            title=title,
            description=description,
            is_active=is_active,
        )

        return await CourseDAO.update_one_by_id(
            session=session,
            data_id=course_id,
            values=data,
        )

    @staticmethod
    @connection
    async def create_stream(
        course_id: int,
        *,
        title: str,
        starts_on: str | None,
        ends_on: str | None,
        timezone: str,
        telemost_url: str | None,
        status: str,
        session: AsyncSession,
    ) -> Stream | None:
        course = await CourseDAO.get_by_id(
            session=session,
            data_id=course_id,
        )

        if course is None:
            return None

        data = StreamCreatePydantic(
            title=title,
            starts_on=starts_on or None,
            ends_on=ends_on or None,
            timezone=timezone,
            telemost_url=telemost_url,
            status=StreamStatus(status),
        )

        return await StreamDAO.add(
            session=session,
            course_id=course_id,
            **data.model_dump(),
        )

    @staticmethod
    @connection
    async def update_stream(
        stream_id: int,
        *,
        title: str,
        starts_on: str | None,
        ends_on: str | None,
        timezone: str,
        telemost_url: str | None,
        status: str,
        session: AsyncSession,
    ) -> Stream | None:
        data = StreamUpdatePydantic(
            title=title,
            starts_on=starts_on or None,
            ends_on=ends_on or None,
            timezone=timezone,
            telemost_url=telemost_url,
            status=StreamStatus(status),
        )

        return await StreamDAO.update_one_by_id(
            session=session,
            data_id=stream_id,
            values=data,
        )

    @staticmethod
    @connection
    async def get_stream_admin_page_data(
        stream_id: int,
        *,
        session: AsyncSession,
    ) -> tuple[Stream | None, list[ScheduleLesson], list[Video]]:
        stream = await StreamDAO.get_with_course(
            session=session,
            stream_id=stream_id,
        )

        if stream is None:
            return None, [], []

        lessons = list(
            await ScheduleLessonDAO.get_by_stream_id(
                session=session,
                stream_id=stream_id,
            )
        )

        videos = list(
            await VideoDAO.find_by_stream_id(
                session=session,
                stream_id=stream_id,
            )
        )

        return stream, lessons, videos

    @staticmethod
    @connection
    async def create_lesson(
        stream_id: int,
        *,
        title: str,
        starts_at: str,
        video_id: str | None,
        session: AsyncSession,
    ) -> ScheduleLesson | None:
        stream = await StreamDAO.get_by_id(
            session=session,
            data_id=stream_id,
        )

        if stream is None:
            return None

        lessons = await ScheduleLessonDAO.get_by_stream_id(
            session=session,
            stream_id=stream_id,
        )

        selected_video_id = int(video_id) if video_id else None

        await ScheduleService._validate_video_for_stream(
            session=session,
            stream_id=stream_id,
            video_id=selected_video_id,
        )

        data = ScheduleLessonCreatePydantic(
            title=title.strip(),
            starts_at=ScheduleService.parse_moscow_datetime(starts_at),
            video_id=selected_video_id,
            sort_order=len(lessons) + 1,
        )

        return await ScheduleLessonDAO.add(
            session=session,
            stream_id=stream_id,
            **data.model_dump(),
        )

    @staticmethod
    @connection
    async def update_lesson(
        stream_id: int,
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

        if lesson is None or lesson.stream_id != stream_id:
            return None

        selected_video_id = int(video_id) if video_id else None

        await ScheduleService._validate_video_for_stream(
            session=session,
            stream_id=stream_id,
            video_id=selected_video_id,
        )

        data = ScheduleLessonUpdatePydantic(
            title=title.strip(),
            starts_at=ScheduleService.parse_moscow_datetime(starts_at),
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
        stream_id: int,
        lesson_id: int,
        *,
        session: AsyncSession,
    ) -> bool:
        lesson = await ScheduleLessonDAO.get_by_id(
            session=session,
            data_id=lesson_id,
        )

        if lesson is None or lesson.stream_id != stream_id:
            return False

        return await ScheduleLessonDAO.delete_by_id(
            session=session,
            data_id=lesson_id,
        )

    @staticmethod
    @connection
    async def clear_lessons(
        stream_id: int,
        *,
        session: AsyncSession,
    ) -> bool:
        stream = await StreamDAO.get_by_id(
            session=session,
            data_id=stream_id,
        )

        if stream is None:
            return False

        await ScheduleLessonDAO.clear_by_stream_id(
            session=session,
            stream_id=stream_id,
        )

        return True

    @staticmethod
    async def _validate_video_for_stream(
        *,
        session: AsyncSession,
        stream_id: int,
        video_id: int | None,
    ) -> None:
        if video_id is None:
            return

        video = await VideoDAO.get_by_id(
            session=session,
            data_id=video_id,
        )

        if video is None:
            raise ValueError("Видео не найдено")

        if video.stream_id != stream_id:
            raise ValueError(
                "Видео принадлежит другому потоку"
            )