from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.base import BasePydantic


class CourseCreatePydantic(BasePydantic):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Название курса не может быть пустым")

        return value


class CourseUpdatePydantic(CourseCreatePydantic):
    pass


class CoursePydantic(BasePydantic):
    id: int
    title: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime