from pydantic import Field

from app.schemas.base import BasePydantic


class CourseUpdatePydantic(BasePydantic):
    title: str = Field(min_length=1, max_length=255)
    dates: str = Field(min_length=1, max_length=255)
    timezone: str = Field(min_length=1, max_length=64)
    telemost_url: str | None = Field(
        default=None,
        max_length=2_000,
    )