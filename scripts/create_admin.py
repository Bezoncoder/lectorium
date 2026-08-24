import asyncio

from app.core.security import hash_password
from app.db.dao.user import UserDAO
from app.db.models.user import UserRole
from app.db.session import async_session_maker

"""

python -m scripts.create_admin    

"""


async def create_admin():
    login = "admin"
    password = "admin"

    async with async_session_maker() as session:
        exists = await UserDAO.get_one_or_none(
            session=session,
            login=login,
        )

        if exists:
            print(f"Пользователь {login} уже существует")
            return

        admin = await UserDAO.add(
            session=session,
            login=login,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )

        print(
            f"Админ создан: id={admin.id}, "
            f"login={admin.login}, "
            f"role={admin.role.value}"
        )


if __name__ == "__main__":
    asyncio.run(create_admin())