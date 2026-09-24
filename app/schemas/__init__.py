from app.schemas.course import (
    CourseCreatePydantic,
    CoursePydantic,
    CourseUpdatePydantic,
)
from app.schemas.schedule_lesson import (
    ScheduleLessonCreatePydantic,
    ScheduleLessonUpdatePydantic,
)
from app.schemas.stream import (
    StreamCreatePydantic,
    StreamPydantic,
    StreamUpdatePydantic,
)
from app.schemas.stream_enrollment import (
    StreamEnrollmentCreatePydantic,
    StreamEnrollmentPydantic,
    StreamEnrollmentUpdatePydantic,
)
from app.schemas.user import (
    AddUserPydantic,
    AdminChangeStudentPasswordPydantic,
    AdminCreateStudentPydantic,
    AdminEnrollStudentPydantic,
    UserPydantic,
    UserWithRelationsPydantic,
)
from app.schemas.user_session import UserSessionPydantic
from app.schemas.video import (
    VideoCreatePydantic,
    VideoPydantic,
    VideoUpdatePydantic,
)
from app.schemas.video_view import (
    VideoViewCreatePydantic,
    VideoViewPydantic,
)

__all__ = (
    "AddUserPydantic",
    "AdminChangeStudentPasswordPydantic",
    "AdminCreateStudentPydantic",
    "AdminEnrollStudentPydantic",
    "CourseCreatePydantic",
    "CoursePydantic",
    "CourseUpdatePydantic",
    "ScheduleLessonCreatePydantic",
    "ScheduleLessonUpdatePydantic",
    "StreamCreatePydantic",
    "StreamEnrollmentCreatePydantic",
    "StreamEnrollmentPydantic",
    "StreamEnrollmentUpdatePydantic",
    "StreamPydantic",
    "StreamUpdatePydantic",
    "UserPydantic",
    "UserSessionPydantic",
    "UserWithRelationsPydantic",
    "VideoCreatePydantic",
    "VideoPydantic",
    "VideoUpdatePydantic",
    "VideoViewCreatePydantic",
    "VideoViewPydantic",
)