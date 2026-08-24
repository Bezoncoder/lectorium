from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


DATABASE_URL = settings.get_db_url()

engine = create_async_engine(
    url=DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=1800,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

P = ParamSpec("P")
T = TypeVar("T")


def connection(
    method: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    @wraps(method)
    async def wrapper(
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        async with async_session_maker() as session:
            try:
                return await method(
                    *args,
                    session=session,
                    **kwargs,
                )
            except Exception:
                await session.rollback()
                raise

    return wrapper