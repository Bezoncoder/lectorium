from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dao.video import VideoDAO
from app.db.models.user import User
from app.db.models.video import Video
from app.db.models.video_view import VideoView
from app.db.session import connection


class VideoService:
    @staticmethod
    @connection
    async def get_all(
        *,
        session: AsyncSession,
    ) -> list[Video]:
        videos = await VideoDAO.find_all(
            session=session,
            order_by=Video.created_at.desc(),
        )

        return list(videos)

    @staticmethod
    @connection
    async def get_by_id(
        video_id: int,
        *,
        session: AsyncSession,
    ) -> Video | None:
        return await VideoDAO.get_by_id(
            session=session,
            data_id=video_id,
        )

    @staticmethod
    @connection
    async def create(
        *,
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
    ) -> bool:
        video = await session.get(Video, video_id)

        if video is None:
            return False

        view = VideoView(
            video_id=video_id,
            user_id=user_id,
            watched_seconds=max(30, watched_seconds),
            view_date=datetime.utcnow().date(),
        )

        try:
            session.add(view)
            await session.commit()
        except IntegrityError:
            await session.rollback()

        return True


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
                Video.title.label("title"),
                func.count(VideoView.id).label("total_views"),
                func.count(
                    distinct(VideoView.user_id),
                ).label("unique_viewers"),
                func.max(
                    VideoView.viewed_at,
                ).label("last_viewed_at"),
            )
            .outerjoin(
                VideoView,
                VideoView.video_id == Video.id,
            )
            .group_by(Video.id, Video.title)
            .order_by(Video.created_at.desc())
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
                func.max(
                    VideoView.viewed_at,
                ).label("last_viewed_at"),
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