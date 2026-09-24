from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dao.base import BaseDAO
from app.db.models.user import User, UserRole


class UserDAO(BaseDAO[User]):
    model = User

    @classmethod
    async def find_student_by_login(
        cls,
        session: AsyncSession,
        login: str,
    ) -> User | None:
        statement = (
            select(User)
            .where(
                User.login == login,
                User.role == UserRole.STUDENT,
            )
            .options(selectinload(User.enrollments))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()

    @classmethod
    async def get_with_enrollments(
        cls,
        session: AsyncSession,
        user_id: int,
    ) -> User | None:
        statement = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.enrollments))
        )

        result = await session.execute(statement)

        return result.unique().scalar_one_or_none()