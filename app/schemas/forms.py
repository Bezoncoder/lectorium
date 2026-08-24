from pydantic import BaseModel, Field


class VideoViewCreate(BaseModel):
    watched_seconds: int = Field(
        ge=30,
        le=86_400,
    )