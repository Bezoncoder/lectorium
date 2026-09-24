from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.course import Course
    from app.db.models.schedule_lesson import ScheduleLesson
    from app.db.models.stream_enrollment import StreamEnrollment
    from app.db.models.video import Video


class StreamStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    FINISHED = "finished"
    ARCHIVED = "archived"


class Stream(Base):
    __tablename__ = "streams"

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "title",
            name="uq_streams_course_title",
        ),
        UniqueConstraint(
            "id",
            "course_id",
            name="uq_streams_id_course_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    starts_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    ends_on: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Moscow",
    )

    telemost_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[StreamStatus] = mapped_column(
        Enum(StreamStatus),
        nullable=False,
        default=StreamStatus.DRAFT,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
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

    course: Mapped["Course"] = relationship(
        back_populates="streams",
    )

    lessons: Mapped[list["ScheduleLesson"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        order_by="ScheduleLesson.starts_at",
        lazy="selectin",
    )

    enrollments: Mapped[list["StreamEnrollment"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        lazy="selectin",
        overlaps="course,enrollments",
    )

    videos: Mapped[list["Video"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        lazy="selectin",
    )