from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.stream import Stream
    from app.db.models.stream_enrollment import StreamEnrollment


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    streams: Mapped[list["Stream"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Stream.starts_on.desc()",
        lazy="selectin",
    )

    enrollments: Mapped[list["StreamEnrollment"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        lazy="selectin",
        overlaps="stream,enrollments",
    )