from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.course import Course
from app.db.models.stream import Stream
from app.db.models.stream_enrollment import (
    EnrollmentStatus,
    StreamEnrollment,
)
from app.db.models.user import User


class StreamEnrollmentDAO(BaseDAO[StreamEnrollment]):
    model = StreamEnrollment

    @classmethod
    async def get_for_user_and_course(
        cls,
        session: AsyncSession,
        *,
        user_id: int,
        course_id: int,
    ) -> StreamEnrollment | None:
        statement = (
            select(StreamEnrollment)
            .where(
                StreamEnrollment.user_id == user_id,
                StreamEnrollment.course_id == course_id,
            )
            .options(
                selectinload(StreamEnrollment.course),
                selectinload(StreamEnrollment.stream),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_for_user_and_stream(
        cls,
        session: AsyncSession,
        *,
        user_id: int,
        stream_id: int,
    ) -> StreamEnrollment | None:
        statement = (
            select(StreamEnrollment)
            .where(
                StreamEnrollment.user_id == user_id,
                StreamEnrollment.stream_id == stream_id,
            )
            .options(
                selectinload(StreamEnrollment.course),
                selectinload(StreamEnrollment.stream),
            )
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_accessible_for_user(
        cls,
        session: AsyncSession,
        *,
        user_id: int,
    ) -> Sequence[StreamEnrollment]:
        statement = (
            select(StreamEnrollment)
            .join(Course, Course.id == StreamEnrollment.course_id)
            .join(Stream, Stream.id == StreamEnrollment.stream_id)
            .where(
                StreamEnrollment.user_id == user_id,
                StreamEnrollment.status.in_(
                    (
                        EnrollmentStatus.ACTIVE,
                        EnrollmentStatus.COMPLETED,
                    )
                ),
            )
            .options(
                selectinload(StreamEnrollment.course),
                selectinload(StreamEnrollment.stream),
            )
            .order_by(Course.title.asc(), Stream.starts_on.desc().nullslast())
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()

    @classmethod
    async def get_by_stream_id(
        cls,
        session: AsyncSession,
        stream_id: int,
    ) -> Sequence[StreamEnrollment]:
        statement = (
            select(StreamEnrollment)
            .join(User, User.id == StreamEnrollment.user_id)
            .where(StreamEnrollment.stream_id == stream_id)
            .options(selectinload(StreamEnrollment.user))
            .order_by(User.login.asc())
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()