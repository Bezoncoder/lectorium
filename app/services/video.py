from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.stream_enrollment import StreamEnrollmentDAO
from app.db.dao.video import VideoDAO
from app.db.models.course import Course
from app.db.models.stream import Stream
from app.db.models.stream_enrollment import EnrollmentStatus
from app.db.models.user import User, UserRole
from app.db.models.video import Video
from app.db.models.video_view import VideoView
from app.db.session import connection


MINIMUM_WATCH_SECONDS = 15


@dataclass(slots=True)
class UserVideoViewStatistics:
    views_count: int
    last_viewed_at: datetime | None
    max_watched_seconds: int | None


class VideoService:
    @staticmethod
    @connection
    async def get_all_for_stream(
        stream_id: int,
        *,
        session: AsyncSession,
    ) -> list[Video]:
        videos = await VideoDAO.find_by_stream_id(
            session=session,
            stream_id=stream_id,
        )

        return list(videos)

    @staticmethod
    @connection
    async def get_by_id(
        video_id: int,
        *,
        session: AsyncSession,
    ) -> Video | None:
        return await VideoDAO.get_with_stream(
            session=session,
            video_id=video_id,
        )

    @staticmethod
    @connection
    async def get_by_id_for_user(
        *,
        video_id: int,
        user_id: int,
        session: AsyncSession,
    ) -> Video | None:
        video = await VideoDAO.get_with_stream(
            session=session,
            video_id=video_id,
        )

        if video is None:
            return None

        user = await session.get(User, user_id)

        if user is None:
            return None

        # Администратор имеет доступ к любому видео всех потоков.
        if user.role == UserRole.ADMIN:
            return video

        enrollment = await StreamEnrollmentDAO.get_for_user_and_stream(
            session=session,
            user_id=user_id,
            stream_id=video.stream_id,
        )

        if enrollment is None:
            return None

        if enrollment.status not in (
            EnrollmentStatus.ACTIVE,
            EnrollmentStatus.COMPLETED,
        ):
            return None

        return video

    @staticmethod
    @connection
    async def get_stream_for_user_course(
        *,
        user_id: int,
        course_id: int,
        session: AsyncSession,
    ) -> Stream | None:
        user = await session.get(User, user_id)

        if user is None:
            return None

        # Для администратора каталог видео студента не используется.
        # Доступ к видео осуществляется через админ-маршруты потока.
        if user.role == UserRole.ADMIN:
            return None

        enrollment = await StreamEnrollmentDAO.get_for_user_and_course(
            session=session,
            user_id=user_id,
            course_id=course_id,
        )

        if enrollment is None:
            return None

        if enrollment.status not in (
            EnrollmentStatus.ACTIVE,
            EnrollmentStatus.COMPLETED,
        ):
            return None

        return enrollment.stream

    @staticmethod
    @connection
    async def create(
        *,
        stream_id: int,
        title: str,
        description: str | None,
        filename: str,
        original_filename: str,
        mime_type: str,
        size_bytes: int,
        uploaded_by_id: int,
        session: AsyncSession,
    ) -> Video:
        return await VideoDAO.add(
            session=session,
            stream_id=stream_id,
            title=title,
            description=description,
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            uploaded_by_id=uploaded_by_id,
        )

    @staticmethod
    @connection
    async def update(
        video_id: int,
        *,
        title: str,
        description: str | None,
        session: AsyncSession,
    ) -> Video | None:
        return await VideoDAO.update_one_by_id(
            session=session,
            data_id=video_id,
            values={
                "title": title,
                "description": description,
            },
        )

    @staticmethod
    @connection
    async def delete(
        video_id: int,
        *,
        session: AsyncSession,
    ) -> str | None:
        video = await session.get(Video, video_id)

        if video is None:
            return None

        filename = video.filename

        await session.delete(video)
        await session.commit()

        return filename

    @staticmethod
    @connection
    async def register_view(
        *,
        video_id: int,
        user_id: int,
        watched_seconds: int,
        session: AsyncSession,
    ) -> str:
        video = await VideoDAO.get_with_stream(
            session=session,
            video_id=video_id,
        )

        if video is None:
            return "not_found"

        user = await session.get(User, user_id)

        if user is None:
            return "forbidden"

        # Администратор может открыть видео для проверки,
        # но его просмотр не влияет на учебную статистику.
        if user.role == UserRole.ADMIN:
            return "admin_preview"

        enrollment = await StreamEnrollmentDAO.get_for_user_and_stream(
            session=session,
            user_id=user_id,
            stream_id=video.stream_id,
        )

        if (
            enrollment is None
            or enrollment.status
            not in (
                EnrollmentStatus.ACTIVE,
                EnrollmentStatus.COMPLETED,
            )
        ):
            return "forbidden"

        view = VideoView(
            video_id=video_id,
            user_id=user_id,
            watched_seconds=max(MINIMUM_WATCH_SECONDS, watched_seconds),
            view_date=datetime.utcnow().date(),
        )

        try:
            session.add(view)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return "already_registered"

        return "registered"

    @staticmethod
    @connection
    async def get_user_view_statistics(
        *,
        video_id: int,
        user_id: int,
        session: AsyncSession,
    ) -> UserVideoViewStatistics:
        statement = select(
            func.count(VideoView.id).label("views_count"),
            func.max(VideoView.viewed_at).label("last_viewed_at"),
            func.max(VideoView.watched_seconds).label(
                "max_watched_seconds"
            ),
        ).where(
            VideoView.video_id == video_id,
            VideoView.user_id == user_id,
            VideoView.watched_seconds >= MINIMUM_WATCH_SECONDS,
        )

        result = await session.execute(statement)
        data = result.mappings().one()

        return UserVideoViewStatistics(
            views_count=data["views_count"],
            last_viewed_at=data["last_viewed_at"],
            max_watched_seconds=data["max_watched_seconds"],
        )


class StatisticsService:
    @staticmethod
    @connection
    async def get_all(
        *,
        session: AsyncSession,
    ):
        statement = (
            select(
                Video.id.label("video_id"),
                Course.id.label("course_id"),
                Course.title.label("course_title"),
                Stream.id.label("stream_id"),
                Stream.title.label("stream_title"),
                Video.title.label("title"),
                func.count(VideoView.id).label("total_views"),
                func.count(
                    distinct(VideoView.user_id),
                ).label("unique_viewers"),
                func.max(
                    VideoView.viewed_at,
                ).label("last_viewed_at"),
            )
            .join(Stream, Stream.id == Video.stream_id)
            .join(Course, Course.id == Stream.course_id)
            .outerjoin(
                VideoView,
                VideoView.video_id == Video.id,
            )
            .group_by(
                Video.id,
                Course.id,
                Course.title,
                Stream.id,
                Stream.title,
                Video.title,
            )
            .order_by(
                Course.title.asc(),
                Stream.starts_on.desc().nullslast(),
                Video.created_at.desc(),
            )
        )

        result = await session.execute(statement)

        return result.mappings().all()

    @staticmethod
    @connection
    async def get_video_viewers(
        video_id: int,
        *,
        session: AsyncSession,
    ):
        statement = (
            select(
                User.login.label("login"),
                func.count(VideoView.id).label("views_count"),
                func.max(VideoView.viewed_at).label("last_viewed_at"),
                func.max(
                    VideoView.watched_seconds,
                ).label("max_watched_seconds"),
            )
            .join(
                VideoView,
                VideoView.user_id == User.id,
            )
            .where(VideoView.video_id == video_id)
            .group_by(User.id, User.login)
            .order_by(func.max(VideoView.viewed_at).desc())
        )

        result = await session.execute(statement)

        return result.mappings().all()