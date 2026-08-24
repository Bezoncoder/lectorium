from datetime import datetime

from app.schemas.base import BasePydantic


class VideoStatisticsPydantic(BasePydantic):
    video_id: int
    title: str
    total_views: int
    unique_viewers: int
    last_viewed_at: datetime | None


class VideoViewerStatisticsPydantic(BasePydantic):
    login: str
    views_count: int
    last_viewed_at: datetime
    max_watched_seconds: int