from datetime import datetime

from pydantic import Field

from app.db.models.stream_enrollment import EnrollmentStatus
from app.schemas.base import BasePydantic


class StreamEnrollmentCreatePydantic(BasePydantic):
    course_id: int = Field(gt=0)
    stream_id: int = Field(gt=0)


class StreamEnrollmentUpdatePydantic(BasePydantic):
    status: EnrollmentStatus


class StreamEnrollmentPydantic(BasePydantic):
    id: int
    user_id: int
    course_id: int
    stream_id: int
    status: EnrollmentStatus
    enrolled_at: datetime
    updated_at: datetime