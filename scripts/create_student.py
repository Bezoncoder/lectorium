import asyncio

from app.core.security import hash_password
from app.db.dao.user import UserDAO
from app.db.models.user import UserRole
from app.db.session import async_session_maker

"""

python -m scripts.create_student

"""


async def create_student():
    login = "student"
    password = "student"

    async with async_session_maker() as session:
        exists = await UserDAO.get_one_or_none(
            session=session,
            login=login,
        )

        if exists:
            print(f"Пользователь {login} уже существует")
            return

        student = await UserDAO.add(
            session=session,
            login=login,
            password_hash=hash_password(password),
            role=UserRole.STUDENT,
        )

        print(
            f"Студент создан: id={student.id}, "
            f"login={student.login}, role={student.role.value}"
        )


if __name__ == "__main__":
    asyncio.run(create_student())