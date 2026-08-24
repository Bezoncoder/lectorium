from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.dao.user import UserDAO
from app.db.models.user import User, UserRole
from app.db.models.user_session import UserSession
from app.db.session import connection


class UserService:
    @staticmethod
    @connection
    async def authenticate(
        login: str,
        password: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        user = await UserDAO.get_one_or_none(
            session=session,
            login=login,
        )

        if user is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    @staticmethod
    @connection
    async def create_student(
        login: str,
        password: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        existing_user = await UserDAO.get_one_or_none(
            session=session,
            login=login,
        )

        if existing_user is not None:
            return None

        student = User(
            login=login,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
        )

        try:
            session.add(student)
            await session.commit()
            await session.refresh(student)
        except IntegrityError:
            await session.rollback()
            return None

        return student


class SessionService:
    @staticmethod
    @connection
    async def create(
        user_id: int,
        ip_address: str | None,
        user_agent: str | None,
        *,
        session: AsyncSession,
    ) -> str:
        token = generate_session_token()
        now = datetime.utcnow()

        user_session = UserSession(
            user_id=user_id,
            token_hash=hash_session_token(token),
            expires_at=now + timedelta(
                days=settings.session_ttl_days,
            ),
            last_used_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        session.add(user_session)
        await session.commit()

        return token

    @staticmethod
    @connection
    async def get_user_by_token(
        token: str,
        *,
        session: AsyncSession,
    ) -> User | None:
        now = datetime.utcnow()
        token_hash = hash_session_token(token)

        statement = (
            select(User)
            .join(UserSession, UserSession.user_id == User.id)
            .where(
                UserSession.token_hash == token_hash,
                UserSession.expires_at > now,
            )
        )

        result = await session.execute(statement)
        user = result.unique().scalar_one_or_none()

        if user is None:
            return None

        await session.execute(
            update(UserSession)
            .where(UserSession.token_hash == token_hash)
            .values(last_used_at=now)
        )
        await session.commit()

        return user

    @staticmethod
    @connection
    async def delete(
        token: str,
        *,
        session: AsyncSession,
    ) -> None:
        await session.execute(
            delete(UserSession).where(
                UserSession.token_hash == hash_session_token(token),
            )
        )
        await session.commit()