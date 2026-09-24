from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.schedule_lesson import ScheduleLessonDAO
from app.db.dao.stream_enrollment import StreamEnrollmentDAO
from app.db.models.course import Course
from app.db.models.schedule_lesson import ScheduleLesson
from app.db.models.stream import Stream
from app.db.models.stream_enrollment import StreamEnrollment
from app.db.models.video_view import VideoView
from app.db.session import connection


MOSCOW_TZ = ZoneInfo("Europe/Moscow")
MINIMUM_WATCH_SECONDS = 15

MONTH_NAMES = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


@dataclass(slots=True)
class CabinetProgress:
    completed: int
    total: int
    remaining: int
    percent: int


@dataclass(slots=True)
class CabinetLesson:
    id: int
    title: str
    video_id: int | None
    starts_at: datetime
    date_day: str
    date_month: str
    date_label: str
    time_label: str
    status: str


@dataclass(slots=True)
class CabinetCourseCard:
    course: Course
    stream: Stream
    enrollment: StreamEnrollment
    progress: CabinetProgress
    next_lesson: CabinetLesson | None


@dataclass(slots=True)
class CabinetData:
    course: Course
    stream: Stream
    enrollment: StreamEnrollment
    lessons: list[CabinetLesson]
    next_lesson: CabinetLesson | None
    progress: CabinetProgress


class CabinetService:
    @staticmethod
    @connection
    async def get_my_courses(
        user_id: int,
        *,
        session: AsyncSession,
    ) -> list[CabinetCourseCard]:
        enrollments = await StreamEnrollmentDAO.get_accessible_for_user(
            session=session,
            user_id=user_id,
        )

        cards: list[CabinetCourseCard] = []

        for enrollment in enrollments:
            if enrollment.course is None or enrollment.stream is None:
                continue

            dashboard = await CabinetService._build_dashboard(
                session=session,
                enrollment=enrollment,
            )

            cards.append(
                CabinetCourseCard(
                    course=dashboard.course,
                    stream=dashboard.stream,
                    enrollment=dashboard.enrollment,
                    progress=dashboard.progress,
                    next_lesson=dashboard.next_lesson,
                )
            )

        return cards

    @staticmethod
    @connection
    async def get_course_dashboard(
        user_id: int,
        course_id: int,
        *,
        session: AsyncSession,
    ) -> CabinetData | None:
        enrollment = await StreamEnrollmentDAO.get_for_user_and_course(
            session=session,
            user_id=user_id,
            course_id=course_id,
        )

        if enrollment is None:
            return None

        if enrollment.course is None or enrollment.stream is None:
            return None

        if enrollment.status.value not in ("active", "completed"):
            return None

        return await CabinetService._build_dashboard(
            session=session,
            enrollment=enrollment,
        )

    @staticmethod
    async def _build_dashboard(
        *,
        session: AsyncSession,
        enrollment: StreamEnrollment,
    ) -> CabinetData:
        if enrollment.course is None or enrollment.stream is None:
            raise ValueError("В зачислении отсутствуют курс или поток")

        lessons = list(
            await ScheduleLessonDAO.get_by_stream_id(
                session=session,
                stream_id=enrollment.stream_id,
            )
        )

        watched_video_ids = await CabinetService._get_watched_video_ids(
            session=session,
            user_id=enrollment.user_id,
            stream_id=enrollment.stream_id,
        )

        now = datetime.now(MOSCOW_TZ)

        cabinet_lessons = [
            CabinetService._to_cabinet_lesson(
                lesson=lesson,
                watched_video_ids=watched_video_ids,
                now=now,
            )
            for lesson in lessons
        ]

        completed = sum(
            lesson.status == "completed"
            for lesson in cabinet_lessons
        )
        total = len(cabinet_lessons)
        remaining = max(total - completed, 0)
        percent = completed * 100 // total if total else 0

        next_lesson = next(
            (
                lesson
                for lesson in cabinet_lessons
                if lesson.starts_at > now
            ),
            None,
        )

        return CabinetData(
            course=enrollment.course,
            stream=enrollment.stream,
            enrollment=enrollment,
            lessons=cabinet_lessons,
            next_lesson=next_lesson,
            progress=CabinetProgress(
                completed=completed,
                total=total,
                remaining=remaining,
                percent=percent,
            ),
        )

    @staticmethod
    async def _get_watched_video_ids(
        *,
        session: AsyncSession,
        user_id: int,
        stream_id: int,
    ) -> set[int]:
        statement = (
            select(distinct(VideoView.video_id))
            .join(VideoView.video)
            .where(
                VideoView.user_id == user_id,
                VideoView.watched_seconds >= MINIMUM_WATCH_SECONDS,
                VideoView.video.has(stream_id=stream_id),
            )
        )

        result = await session.execute(statement)

        return set(result.scalars().all())

    @staticmethod
    def _to_cabinet_lesson(
        *,
        lesson: ScheduleLesson,
        watched_video_ids: set[int],
        now: datetime,
    ) -> CabinetLesson:
        starts_at = lesson.starts_at

        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=MOSCOW_TZ)
        else:
            starts_at = starts_at.astimezone(MOSCOW_TZ)

        if lesson.video_id in watched_video_ids:
            status = "completed"
        elif lesson.video_id is not None:
            status = "available"
        elif starts_at > now:
            status = "upcoming"
        else:
            status = "pending"

        return CabinetLesson(
            id=lesson.id,
            title=lesson.title,
            video_id=lesson.video_id,
            starts_at=starts_at,
            date_day=str(starts_at.day),
            date_month=MONTH_NAMES[starts_at.month],
            date_label=(
                f"{starts_at.day} "
                f"{MONTH_NAMES[starts_at.month]} "
                f"{starts_at.year}"
            ),
            time_label=starts_at.strftime("%H:%M"),
            status=status,
        )