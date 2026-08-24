from datetime import date, datetime

from pydantic import Field

from app.schemas.base import BasePydantic


class VideoViewPydantic(BasePydantic):
    id: int
    video_id: int
    user_id: int
    watched_seconds: int
    view_date: date
    viewed_at: datetime


class VideoViewCreatePydantic(BasePydantic):
    watched_seconds: int = Field(
        ge=15,
        le=86_400,
    )