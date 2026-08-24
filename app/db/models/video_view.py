from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VideoView(Base):
    __tablename__ = "video_views"

    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "user_id",
            "view_date",
            name="uq_video_user_daily_view",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    watched_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
    )

    view_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    viewed_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="video_views",
        lazy="joined",
    )

    video: Mapped["Video"] = relationship(
        "Video",
        back_populates="views",
        lazy="joined",
    )