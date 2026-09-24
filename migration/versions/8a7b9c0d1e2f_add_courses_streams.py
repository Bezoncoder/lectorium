"""add courses streams and enrollments

Revision ID: 8a7b9c0d1e2f
Revises: 5cfdf88aeac8
Create Date: 2026-09-24 19:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "8a7b9c0d1e2f"
down_revision: Union[str, Sequence[str], None] = "5cfdf88aeac8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


stream_status = postgresql.ENUM(
    "DRAFT",
    "ACTIVE",
    "FINISHED",
    "ARCHIVED",
    name="streamstatus",
    create_type=False,
)

enrollment_status = postgresql.ENUM(
    "ACTIVE",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
    name="enrollmentstatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()

    # Создаём PostgreSQL ENUM явно и только один раз.
    postgresql.ENUM(
        "DRAFT",
        "ACTIVE",
        "FINISHED",
        "ARCHIVED",
        name="streamstatus",
    ).create(bind, checkfirst=True)

    postgresql.ENUM(
        "ACTIVE",
        "BLOCKED",
        "COMPLETED",
        "CANCELLED",
        name="enrollmentstatus",
    ).create(bind, checkfirst=True)

    op.add_column(
        "courses",
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "courses",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.create_index(
        "ix_courses_is_active",
        "courses",
        ["is_active"],
        unique=False,
    )

    op.create_index(
        "ix_courses_title",
        "courses",
        ["title"],
        unique=True,
    )

    op.create_table(
        "streams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/Moscow",
        ),
        sa.Column("telemost_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            stream_status,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id",
            "title",
            name="uq_streams_course_title",
        ),
        sa.UniqueConstraint(
            "id",
            "course_id",
            name="uq_streams_id_course_id",
        ),
    )

    op.create_index(
        "ix_streams_course_id",
        "streams",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        "ix_streams_starts_on",
        "streams",
        ["starts_on"],
        unique=False,
    )
    op.create_index(
        "ix_streams_ends_on",
        "streams",
        ["ends_on"],
        unique=False,
    )
    op.create_index(
        "ix_streams_status",
        "streams",
        ["status"],
        unique=False,
    )

    op.create_table(
        "stream_enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            enrollment_status,
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stream_id", "course_id"],
            ["streams.id", "streams.course_id"],
            name="fk_stream_enrollments_stream_course",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "course_id",
            name="uq_stream_enrollments_user_course",
        ),
        sa.UniqueConstraint(
            "user_id",
            "stream_id",
            name="uq_stream_enrollments_user_stream",
        ),
    )

    op.create_index(
        "ix_stream_enrollments_user_id",
        "stream_enrollments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_stream_enrollments_course_id",
        "stream_enrollments",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        "ix_stream_enrollments_stream_id",
        "stream_enrollments",
        ["stream_id"],
        unique=False,
    )
    op.create_index(
        "ix_stream_enrollments_status",
        "stream_enrollments",
        ["status"],
        unique=False,
    )

    op.add_column(
        "schedule_lessons",
        sa.Column(
            "stream_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_schedule_lessons_stream_id",
        "schedule_lessons",
        ["stream_id"],
        unique=False,
    )

    op.add_column(
        "videos",
        sa.Column(
            "stream_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_videos_stream_id",
        "videos",
        ["stream_id"],
        unique=False,
    )

    bind.execute(
        sa.text(
            """
            INSERT INTO streams (
                course_id,
                title,
                timezone,
                telemost_url,
                status,
                created_at,
                updated_at
            )
            SELECT
                id,
                'Основной поток',
                COALESCE(NULLIF(timezone, ''), 'Europe/Moscow'),
                telemost_url,
                'ACTIVE',
                now(),
                now()
            FROM courses
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE schedule_lessons AS lesson
            SET stream_id = stream.id
            FROM streams AS stream
            WHERE lesson.course_id = stream.course_id
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE videos AS video
            SET stream_id = lesson.stream_id
            FROM schedule_lessons AS lesson
            WHERE lesson.video_id = video.id
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE videos AS video
            SET stream_id = stream.id
            FROM streams AS stream
            WHERE video.stream_id IS NULL
              AND stream.id = (
                  SELECT candidate.id
                  FROM streams AS candidate
                  ORDER BY candidate.id ASC
                  LIMIT 1
              )
            """
        )
    )

    op.alter_column(
        "schedule_lessons",
        "stream_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "videos",
        "stream_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "fk_schedule_lessons_stream_id",
        "schedule_lessons",
        "streams",
        ["stream_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_videos_stream_id",
        "videos",
        "streams",
        ["stream_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "schedule_lessons_course_id_fkey",
        "schedule_lessons",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_schedule_lessons_course_id",
        table_name="schedule_lessons",
    )

    op.drop_column("schedule_lessons", "course_id")

    op.drop_column("courses", "dates")
    op.drop_column("courses", "timezone")
    op.drop_column("courses", "telemost_url")

    op.alter_column(
        "courses",
        "is_active",
        server_default=None,
    )

    op.alter_column(
        "streams",
        "timezone",
        server_default=None,
    )

    op.alter_column(
        "streams",
        "status",
        server_default=None,
    )

    op.alter_column(
        "stream_enrollments",
        "status",
        server_default=None,
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "courses",
        sa.Column(
            "dates",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )

    op.add_column(
        "courses",
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="МСК",
        ),
    )

    op.add_column(
        "courses",
        sa.Column(
            "telemost_url",
            sa.Text(),
            nullable=True,
        ),
    )

    bind.execute(
        sa.text(
            """
            UPDATE courses AS course
            SET
                timezone = stream.timezone,
                telemost_url = stream.telemost_url
            FROM streams AS stream
            WHERE stream.course_id = course.id
              AND stream.title = 'Основной поток'
            """
        )
    )

    op.add_column(
        "schedule_lessons",
        sa.Column(
            "course_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    bind.execute(
        sa.text(
            """
            UPDATE schedule_lessons AS lesson
            SET course_id = stream.course_id
            FROM streams AS stream
            WHERE lesson.stream_id = stream.id
            """
        )
    )

    op.alter_column(
        "schedule_lessons",
        "course_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_foreign_key(
        "schedule_lessons_course_id_fkey",
        "schedule_lessons",
        "courses",
        ["course_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index(
        "ix_schedule_lessons_course_id",
        "schedule_lessons",
        ["course_id"],
        unique=False,
    )

    op.drop_constraint(
        "fk_schedule_lessons_stream_id",
        "schedule_lessons",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_schedule_lessons_stream_id",
        table_name="schedule_lessons",
    )

    op.drop_column("schedule_lessons", "stream_id")

    op.drop_constraint(
        "fk_videos_stream_id",
        "videos",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_videos_stream_id",
        table_name="videos",
    )

    op.drop_column("videos", "stream_id")

    op.drop_index(
        "ix_stream_enrollments_status",
        table_name="stream_enrollments",
    )
    op.drop_index(
        "ix_stream_enrollments_stream_id",
        table_name="stream_enrollments",
    )
    op.drop_index(
        "ix_stream_enrollments_course_id",
        table_name="stream_enrollments",
    )
    op.drop_index(
        "ix_stream_enrollments_user_id",
        table_name="stream_enrollments",
    )
    op.drop_table("stream_enrollments")

    op.drop_index("ix_streams_status", table_name="streams")
    op.drop_index("ix_streams_ends_on", table_name="streams")
    op.drop_index("ix_streams_starts_on", table_name="streams")
    op.drop_index("ix_streams_course_id", table_name="streams")
    op.drop_table("streams")

    op.drop_index("ix_courses_title", table_name="courses")
    op.drop_index("ix_courses_is_active", table_name="courses")
    op.drop_column("courses", "is_active")
    op.drop_column("courses", "description")

    op.alter_column(
        "courses",
        "dates",
        server_default=None,
    )

    op.alter_column(
        "courses",
        "timezone",
        server_default=None,
    )

    postgresql.ENUM(
        "ACTIVE",
        "BLOCKED",
        "COMPLETED",
        "CANCELLED",
        name="enrollmentstatus",
    ).drop(bind, checkfirst=True)

    postgresql.ENUM(
        "DRAFT",
        "ACTIVE",
        "FINISHED",
        "ARCHIVED",
        name="streamstatus",
    ).drop(bind, checkfirst=True)