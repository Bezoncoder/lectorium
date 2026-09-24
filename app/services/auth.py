from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.dao.stream import StreamDAO
from app.db.dao.stream_enrollment import StreamEnrollmentDAO
from app.db.dao.user import UserDAO
from app.db.models.course import Course
from app.db.models.stream import Stream, StreamStatus
from app.db.models.stream_enrollment import (
    EnrollmentStatus,
    StreamEnrollment,
)
from app.db.models.user import User, UserRole
from app.db.models.user_session import UserSession
from app.db.session import connection


@dataclass(slots=True)
class StudentEnrollmentResult:
    user: User
    course: Course
    stream: Stream
    enrollment: StreamEnrollment
    stream_selected_automatically: bool


class UserService:
    @staticmethod
    @connection
    async def authenticate(
        login: str,
        password: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        user = await UserDAO.get_one_or_none(
            session=session,
            login=login.strip().lower(),
        )

        if user is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    @staticmethod
    @connection
    async def create_student(
        login: str,
        password: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        normalized_login = login.strip().lower()

        existing_user = await UserDAO.get_one_or_none(
            session=session,
            login=normalized_login,
        )

        if existing_user is not None:
            return None

        student = User(
            login=normalized_login,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
        )

        try:
            session.add(student)
            await session.commit()
            await session.refresh(student)
        except IntegrityError:
            await session.rollback()
            return None

        return student

    @staticmethod
    @connection
    async def create_student_and_enroll(
        *,
        login: str,
        password: str,
        course_id: int,
        stream_id: int | None,
        session: AsyncSession,
    ) -> StudentEnrollmentResult | None:
        normalized_login = login.strip().lower()

        existing_user = await UserDAO.get_one_or_none(
            session=session,
            login=normalized_login,
        )

        if existing_user is not None:
            return None

        course = await session.get(Course, course_id)

        if course is None:
            raise ValueError("Курс не найден")

        (
            selected_stream,
            selected_automatically,
        ) = await UserService._resolve_stream(
            session=session,
            course_id=course_id,
            stream_id=stream_id,
        )

        student = User(
            login=normalized_login,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
        )

        enrollment = StreamEnrollment(
            user=student,
            course_id=course_id,
            stream_id=selected_stream.id,
            status=EnrollmentStatus.ACTIVE,
        )

        try:
            session.add_all((student, enrollment))
            await session.commit()
            await session.refresh(student)
            await session.refresh(enrollment)
        except IntegrityError:
            await session.rollback()
            return None

        return StudentEnrollmentResult(
            user=student,
            course=course,
            stream=selected_stream,
            enrollment=enrollment,
            stream_selected_automatically=selected_automatically,
        )

    @staticmethod
    @connection
    async def enroll_existing_student(
        *,
        user_id: int,
        course_id: int,
        stream_id: int | None,
        session: AsyncSession,
    ) -> StudentEnrollmentResult | None:
        user = await session.get(User, user_id)

        if user is None or user.role != UserRole.STUDENT:
            return None

        course = await session.get(Course, course_id)

        if course is None:
            raise ValueError("Курс не найден")

        existing_enrollment = (
            await StreamEnrollmentDAO.get_for_user_and_course(
                session=session,
                user_id=user_id,
                course_id=course_id,
            )
        )

        if existing_enrollment is not None:
            raise ValueError(
                "Студент уже назначен в поток этого курса"
            )

        (
            selected_stream,
            selected_automatically,
        ) = await UserService._resolve_stream(
            session=session,
            course_id=course_id,
            stream_id=stream_id,
        )

        enrollment = StreamEnrollment(
            user_id=user.id,
            course_id=course_id,
            stream_id=selected_stream.id,
            status=EnrollmentStatus.ACTIVE,
        )

        try:
            session.add(enrollment)
            await session.commit()
            await session.refresh(enrollment)
        except IntegrityError:
            await session.rollback()
            raise ValueError(
                "Не удалось назначить студента в поток"
            ) from None

        return StudentEnrollmentResult(
            user=user,
            course=course,
            stream=selected_stream,
            enrollment=enrollment,
            stream_selected_automatically=selected_automatically,
        )

    @staticmethod
    @connection
    async def find_student_by_login(
        login: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        return await UserDAO.find_student_by_login(
            session=session,
            login=login.strip().lower(),
        )
    @staticmethod
    @connection
    async def get_student_by_id(
        user_id: int,
        *,
        session: AsyncSession,
    ) -> User | None:
        student = await UserDAO.get_with_enrollments(
            session=session,
            user_id=user_id,
        )

        if student is None or student.role != UserRole.STUDENT:
            return None

        return student

    @staticmethod
    @connection
    async def change_student_password(
        *,
        user_id: int,
        new_password: str,
        session: AsyncSession,
    ) -> bool:
        user = await session.get(User, user_id)

        if user is None or user.role != UserRole.STUDENT:
            return False

        user.password_hash = hash_password(new_password)

        try:
            await session.execute(
                delete(UserSession).where(
                    UserSession.user_id == user_id
                )
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise

        return True

    @staticmethod
    async def _resolve_stream(
        *,
        session: AsyncSession,
        course_id: int,
        stream_id: int | None,
    ) -> tuple[Stream, bool]:
        if stream_id is not None:
            stream = await StreamDAO.get_with_course(
                session=session,
                stream_id=stream_id,
            )

            if stream is None:
                raise ValueError("Поток не найден")

            if stream.course_id != course_id:
                raise ValueError(
                    "Поток не принадлежит указанному курсу"
                )

            if stream.status != StreamStatus.ACTIVE:
                raise ValueError(
                    "В указанный поток нельзя зачислить студента"
                )

            return stream, False

        stream = await UserService._find_nearest_active_stream(
            session=session,
            course_id=course_id,
        )

        if stream is None:
            raise ValueError(
                "Для курса нет активного или ближайшего потока"
            )

        return stream, True

    @staticmethod
    async def _find_nearest_active_stream(
        *,
        session: AsyncSession,
        course_id: int,
    ) -> Stream | None:
        streams = await StreamDAO.get_active_by_course_id(
            session=session,
            course_id=course_id,
        )

        today = date.today()

        current_streams = [
            stream
            for stream in streams
            if (
                stream.starts_on is not None
                and stream.starts_on <= today
                and (
                    stream.ends_on is None
                    or stream.ends_on >= today
                )
            )
        ]

        if current_streams:
            return sorted(
                current_streams,
                key=lambda stream: (
                    stream.starts_on or date.min,
                    stream.id,
                ),
            )[0]

        future_streams = [
            stream
            for stream in streams
            if (
                stream.starts_on is not None
                and stream.starts_on > today
            )
        ]

        if future_streams:
            return sorted(
                future_streams,
                key=lambda stream: (
                    stream.starts_on or date.max,
                    stream.id,
                ),
            )[0]

        open_streams = [
            stream
            for stream in streams
            if stream.starts_on is None
        ]

        if open_streams:
            return sorted(
                open_streams,
                key=lambda stream: stream.id,
            )[0]

        return None


class SessionService:
    @staticmethod
    @connection
    async def create(
        user_id: int,
        ip_address: str | None,
        user_agent: str | None,
        *,
        session: AsyncSession,
    ) -> str:
        token = generate_session_token()
        now = datetime.utcnow()

        user_session = UserSession(
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=now + timedelta(
                days=settings.session_ttl_days,
            ),
            last_used_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.add(user_session)
        await session.commit()

        return token

    @staticmethod
    @connection
    async def get_user_by_token(
        token: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        now = datetime.utcnow()
        token_hash = hash_session_token(token)

        statement = (
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(
                UserSession.token_hash == token_hash,
                UserSession.expires_at > now,
            )
        )

        result = await session.execute(statement)
        user = result.unique().scalar_one_or_none()

        if user is None:
            return None

        await session.execute(
            update(UserSession)
            .where(UserSession.token_hash == token_hash)
            .values(last_used_at=now)
        )
        await session.commit()

        return user

    @staticmethod
    @connection
    async def delete(
        token: str,
        *,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            delete(UserSession).where(
                UserSession.token_hash == hash_session_token(token),
            )
        )
        await session.commit()