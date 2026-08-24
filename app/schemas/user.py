from datetime import datetime

from pydantic import Field, field_validator

from app.db.models.user import UserRole
from app.schemas.base import BasePydantic


class UserPydantic(BasePydantic):
    id: int
    login: str
    role: UserRole
    created_at: datetime
    updated_at: datetime


class UserWithRelationsPydantic(UserPydantic):
    sessions: list["UserSessionPydantic"] = Field(
        default_factory=list,
    )

    uploaded_videos: list["VideoPydantic"] = Field(
        default_factory=list,
    )

    video_views: list["VideoViewPydantic"] = Field(
        default_factory=list,
    )


class AddUserPydantic(BasePydantic):
    login: str = Field(
        min_length=3,
        max_length=64,
        examples=["student1"],
    )

    password: str = Field(
        min_length=8,
        max_length=72,
        examples=["student_password_123"],
    )

    @field_validator("login")
    @classmethod
    def validate_login(cls, value: str) -> str:
        value = value.strip().lower()

        if not value:
            raise ValueError("Логин не может быть пустым")

        normalized_value = value.replace("_", "").replace("-", "")

        if not normalized_value.isalnum():
            raise ValueError(
                "Логин может содержать буквы, цифры, _ и -"
            )

        return value