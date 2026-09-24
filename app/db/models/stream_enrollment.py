from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.course import Course
    from app.db.models.stream import Stream
    from app.db.models.user import User


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StreamEnrollment(Base):
    __tablename__ = "stream_enrollments"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "course_id",
            name="uq_stream_enrollments_user_course",
        ),
        UniqueConstraint(
            "user_id",
            "stream_id",
            name="uq_stream_enrollments_user_stream",
        ),
        ForeignKeyConstraint(
            ["stream_id", "course_id"],
            ["streams.id", "streams.course_id"],
            name="fk_stream_enrollments_stream_course",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    stream_id: Mapped[int] = mapped_column(
        nullable=False,
        index=True,
    )

    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus),
        nullable=False,
        default=EnrollmentStatus.ACTIVE,
        index=True,
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(
        back_populates="enrollments",
    )

    course: Mapped["Course"] = relationship(
        back_populates="enrollments",
        overlaps="enrollments,stream",
    )

    stream: Mapped["Stream"] = relationship(
        back_populates="enrollments",
        overlaps="course,enrollments",
    )