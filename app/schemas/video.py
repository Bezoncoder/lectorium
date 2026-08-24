from datetime import datetime

from pydantic import Field

from app.schemas.base import BasePydantic


class VideoPydantic(BasePydantic):
    id: int
    title: str
    description: str | None
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    uploaded_by_id: int
    created_at: datetime
    updated_at: datetime


class VideoCreatePydantic(BasePydantic):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)


class VideoUpdatePydantic(BasePydantic):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)