import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.db.models.course import Course
from app.db.models.schedule_lesson import ScheduleLesson
from app.db.models.stream import Stream, StreamStatus
from app.db.session import async_session_maker


MOSCOW_TZ = ZoneInfo("Europe/Moscow")

BOOTCAMP_COURSE = {
    "title": "BootCamp",
    "description": (
        "Практический курс по Python API, GitHub, S3, Spark "
        "и ClickHouse."
    ),
    "is_active": True,
}

BOOTCAMP_STREAM = {
    "title": "Осень 2026",
    "starts_on": date(2026, 9, 1),
    "ends_on": date(2026, 10, 29),
    "timezone": "Europe/Moscow",
    "telemost_url": None,
    "status": StreamStatus.ACTIVE,
}

BOOTCAMP_LESSONS = (
    (
        "2026-09-01 20:00",
        "Онбординг",
    ),
    (
        "2026-09-03 20:00",
        "#1 Python API",
    ),
    (
        "2026-09-08 20:00",
        "#1.2 GitHub",
    ),
    (
        "2026-09-10 20:00",
        "#2 API-S3",
    ),
    (
        "2026-09-15 20:00",
        "#3 Spark",
    ),
    (
        "2026-09-17 20:00",
        "#4 ClickHouse",
    ),
)


def parse_moscow_datetime(value: str) -> datetime:
    return datetime.strptime(
        value,
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=MOSCOW_TZ)


async def init_bootcamp() -> None:
    async with async_session_maker() as session:
        try:
            course_result = await session.execute(
                select(Course)
                .where(Course.title == BOOTCAMP_COURSE["title"])
            )
            course = course_result.scalar_one_or_none()

            if course is None:
                course = Course(**BOOTCAMP_COURSE)
                session.add(course)
                await session.flush()

                print(
                    f"Создан курс: {course.title} "
                    f"(id={course.id})"
                )
            else:
                print(
                    f"Курс уже существует: {course.title} "
                    f"(id={course.id})"
                )

            stream_result = await session.execute(
                select(Stream)
                .where(
                    Stream.course_id == course.id,
                    Stream.title == BOOTCAMP_STREAM["title"],
                )
            )
            stream = stream_result.scalar_one_or_none()

            if stream is None:
                stream = Stream(
                    course_id=course.id,
                    **BOOTCAMP_STREAM,
                )
                session.add(stream)
                await session.flush()

                print(
                    f"Создан поток: {stream.title} "
                    f"(id={stream.id})"
                )
            else:
                print(
                    f"Поток уже существует: {stream.title} "
                    f"(id={stream.id})"
                )

            lessons_result = await session.execute(
                select(ScheduleLesson.id)
                .where(ScheduleLesson.stream_id == stream.id)
                .limit(1)
            )

            first_lesson_id = lessons_result.scalar_one_or_none()

            if first_lesson_id is not None:
                print(
                    "Расписание потока уже заполнено. "
                    "Новые занятия не добавлены."
                )
                await session.commit()
                return

            lessons = [
                ScheduleLesson(
                    stream_id=stream.id,
                    starts_at=parse_moscow_datetime(starts_at),
                    title=title,
                    sort_order=position,
                )
                for position, (starts_at, title) in enumerate(
                    BOOTCAMP_LESSONS,
                    start=1,
                )
            ]

            session.add_all(lessons)
            await session.commit()

            print(
                "Создано занятий в расписании потока: "
                f"{len(lessons)}"
            )

        except Exception:
            await session.rollback()
            raise


if __name__ == "__main__":

    # alembic upgrade head
    # uvicorn app.main:app --reload

    asyncio.run(init_bootcamp())