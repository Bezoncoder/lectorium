from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.schedule_lesson import ScheduleLesson


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="BootCamp",
    )

    dates: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )

    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="МСК",
    )

    telemost_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    lessons: Mapped[list["ScheduleLesson"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="ScheduleLesson.starts_at",
        lazy="selectin",
    )