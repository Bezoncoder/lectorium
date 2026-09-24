from datetime import datetime

from pydantic import Field

from app.schemas.base import BasePydantic


class ScheduleLessonCreatePydantic(BasePydantic):
    title: str = Field(min_length=1, max_length=500)
    starts_at: datetime
    video_id: int | None = Field(default=None, gt=0)
    sort_order: int = Field(ge=0)


class ScheduleLessonUpdatePydantic(ScheduleLessonCreatePydantic):
    pass