from getpass import getpass

import requests


# BASE_URL = "http://127.0.0.1:8000"

BASE_URL = "https://lectorium.infrasharing.ru"


def login_admin(
    client: requests.Session,
    login: str,
    password: str,
) -> None:
    response = client.post(
        f"{BASE_URL}/login",
        data={
            "login": login,
            "password": password,
        },
        allow_redirects=False,
        timeout=15,
    )

    if response.status_code not in (200, 302, 303):
        raise RuntimeError(
            "Не удалось войти как администратор:\n"
            f"HTTP {response.status_code}\n"
            f"{response.text}"
        )


def create_student(
    client: requests.Session,
    *,
    login: str,
    password: str,
    course_id: int,
    stream_id: int | None = None,
) -> dict:
    payload = {
        "login": login,
        "password": password,
        "course_id": course_id,
    }

    if stream_id is not None:
        payload["stream_id"] = stream_id

    response = client.post(
        f"{BASE_URL}/admin/api/students",
        json=payload,
        timeout=15,
    )

    if response.status_code != 201:
        raise RuntimeError(
            "Не удалось создать студента:\n"
            f"HTTP {response.status_code}\n"
            f"{response.text}"
        )

    return response.json()


def main() -> None:
    admin_login = input("Логин администратора: ").strip()
    admin_password = getpass("Пароль администратора: ")

    student_login = input("Логин нового студента: ").strip()
    student_password = getpass("Пароль нового студента: ")

    course_id = int(input("ID курса: ").strip())

    raw_stream_id = input(
        "ID потока (Enter для автоматического выбора): "
    ).strip()

    stream_id = int(raw_stream_id) if raw_stream_id else None

    with requests.Session() as client:
        login_admin(
            client,
            login=admin_login,
            password=admin_password,
        )

        result = create_student(
            client,
            login=student_login,
            password=student_password,
            course_id=course_id,
            stream_id=stream_id,
        )

    print("\nСтудент успешно создан и зачислен:")
    print(f"ID студента: {result['user']['id']}")
    print(f"Логин: {result['user']['login']}")
    print(
        f"Курс: {result['course']['title']} "
        f"(id={result['course']['id']})"
    )
    print(
        f"Поток: {result['stream']['title']} "
        f"(id={result['stream']['id']})"
    )
    print(
        "Выбор потока: "
        f"{result['stream']['selection_source']}"
    )
    print(
        "Статус зачисления: "
        f"{result['enrollment']['status']}"
    )


if __name__ == "__main__":
    main()