import asyncio

from app.services.auth import UserService


async def create_student(
    login: str,
    password: str,
    course_id: int,
    stream_id: int | None = None,
) -> None:
    try:
        result = await UserService.create_student_and_enroll(
            login=login,
            password=password,
            course_id=course_id,
            stream_id=stream_id,
        )
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return

    if result is None:
        print(f"Пользователь '{login}' уже существует")
        return

    selected = (
        "автоматически"
        if result.stream_selected_automatically
        else "явно"
    )

    print(
        f"Студент создан: id={result.user.id}, "
        f"login={result.user.login}\n"
        f"Курс: {result.course.title} "
        f"(id={result.course.id})\n"
        f"Поток: {result.stream.title} "
        f"(id={result.stream.id}, выбран {selected})"
    )


if __name__ == "__main__":
    asyncio.run(
        create_student(
            login="student4",
            password="student4",
            course_id=2,
            stream_id=None,
        )
    )