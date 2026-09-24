from datetime import date, datetime

from pydantic import Field, field_validator, model_validator

from app.db.models.stream import StreamStatus
from app.schemas.base import BasePydantic


class StreamCreatePydantic(BasePydantic):
    title: str = Field(min_length=1, max_length=255)
    starts_on: date | None = None
    ends_on: date | None = None
    timezone: str = Field(min_length=1, max_length=64)
    telemost_url: str | None = Field(default=None, max_length=2_000)
    status: StreamStatus = StreamStatus.DRAFT

    @field_validator("title", "timezone")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Поле не может быть пустым")

        return value

    @field_validator("telemost_url")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()

        return value or None

    @model_validator(mode="after")
    def validate_dates(self) -> "StreamCreatePydantic":
        if (
            self.starts_on is not None
            and self.ends_on is not None
            and self.ends_on < self.starts_on
        ):
            raise ValueError(
                "Дата окончания потока не может быть раньше даты начала"
            )

        return self


class StreamUpdatePydantic(StreamCreatePydantic):
    pass


class StreamPydantic(BasePydantic):
    id: int
    course_id: int
    title: str
    starts_on: date | None
    ends_on: date | None
    timezone: str
    telemost_url: str | None
    status: StreamStatus
    created_at: datetime
    updated_at: datetime