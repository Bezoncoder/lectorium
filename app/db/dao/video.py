from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.video import Video


class VideoDAO(BaseDAO[Video]):
    model = Video

    @classmethod
    async def get_with_stream(
        cls,
        session: AsyncSession,
        video_id: int,
    ) -> Video | None:
        statement = (
            select(Video)
            .where(Video.id == video_id)
            .options(selectinload(Video.stream))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def find_by_stream_id(
        cls,
        session: AsyncSession,
        stream_id: int,
    ) -> Sequence[Video]:
        statement = (
            select(Video)
            .where(Video.stream_id == stream_id)
            .order_by(Video.created_at.desc(), Video.id.desc())
        )

        result = await session.execute(statement)

        return result.unique().scalars().all()