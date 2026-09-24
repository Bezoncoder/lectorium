import asyncio

from app.services.auth import UserService


async def create_student(
    login: str,
    password: str,
) -> None:
    student = await UserService.create_student(
        login=login,
        password=password,
    )

    if student is None:
        print(f"Пользователь '{login}' уже существует")
        return

    print(
        f"Студент создан: "
        f"id={student.id}, "
        f"login={student.login}"
    )


if __name__ == "__main__":
    asyncio.run(
        create_student(
            login="student5",
            password="student5",
        )
    )