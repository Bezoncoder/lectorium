## Инструкция: создание студента через API с `requests`

Эта инструкция показывает, как создать нового студента через API Lectorium и сразу назначить его на курс и поток.

Скрипт делает следующее:

1. Входит в Lectorium под администратором.
2. Получает cookie-сессию администратора.
3. Создаёт нового студента через защищённый API.
4. Назначает студента на выбранный курс.
5. Назначает студента в конкретный поток либо автоматически выбирает подходящий активный поток.

## Требования

Перед запуском убедитесь, что:

- приложение запущено по адресу `http://127.0.0.1:8000`;
- существует пользователь с ролью `admin`;
- существует нужный курс;
- у курса есть хотя бы один поток со статусом **«Активен»**, если поток будет подбираться автоматически;
- в виртуальном окружении установлен пакет `requests`.

В текущем `requirements.txt` пакет `requests` может отсутствовать. Установите его:

```bash
pip install requests
```

Чтобы зависимость сохранилась для будущих установок, добавьте в `requirements.txt`:

```text
requests>=2.31.0
```

## Создайте скрипт

Создайте файл:

```text
scripts/api_create_student_example.py
```

Вставьте в него следующий код:

```python
from getpass import getpass

import requests


BASE_URL = "http://127.0.0.1:8000"


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
```

## Запуск

Запустите скрипт из корня проекта:

```bash
python -m scripts.api_create_student_example
```

Скрипт последовательно запросит:

```text
Логин администратора:
Пароль администратора:
Логин нового студента:
Пароль нового студента:
ID курса:
ID потока (Enter для автоматического выбора):
```

Пароли не отображаются в терминале при вводе, потому что используется `getpass()`.


## Ниже готовый пример для **другого Python-проекта**. 

Вызовите одну функцию, передав логин и пароль администратора, логин и пароль нового студента, а также ID курса; поток можно передать явно или оставить `None` для автоматического выбора.

### Готовый модуль

Создайте в другом проекте файл, например:

```text
lectorium_client.py
```

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class LectoriumApiError(Exception):
    pass


@dataclass(slots=True)
class CreatedStudent:
    user_id: int
    login: str
    course_id: int
    course_title: str
    stream_id: int
    stream_title: str
    stream_selection_source: str
    enrollment_id: int
    enrollment_status: str


def create_lectorium_student(
    *,
    base_url: str,
    admin_login: str,
    admin_password: str,
    student_login: str,
    student_password: str,
    course_id: int,
    stream_id: int | None = None,
    timeout: int = 15,
) -> CreatedStudent:
    """
    Создаёт студента в Lectorium и зачисляет его на курс.

    Если stream_id не передан, Lectorium автоматически выбирает
    текущий или ближайший активный поток указанного курса.
    """
    base_url = base_url.rstrip("/")

    payload: dict[str, Any] = {
        "login": student_login,
        "password": student_password,
        "course_id": course_id,
    }

    if stream_id is not None:
        payload["stream_id"] = stream_id

    with requests.Session() as client:
        try:
            login_response = client.post(
                f"{base_url}/login",
                data={
                    "login": admin_login,
                    "password": admin_password,
                },
                allow_redirects=False,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise LectoriumApiError(
                f"Не удалось подключиться к Lectorium: {exc}"
            ) from exc

        if login_response.status_code not in (200, 302, 303):
            raise LectoriumApiError(
                "Не удалось авторизоваться в Lectorium как администратор: "
                f"HTTP {login_response.status_code}; "
                f"{login_response.text}"
            )

        try:
            create_response = client.post(
                f"{base_url}/admin/api/students",
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise LectoriumApiError(
                f"Не удалось отправить запрос создания студента: {exc}"
            ) from exc

    if create_response.status_code != 201:
        try:
            error_message = create_response.json().get(
                "detail",
                create_response.text,
            )
        except ValueError:
            error_message = create_response.text

        raise LectoriumApiError(
            "Не удалось создать студента в Lectorium: "
            f"HTTP {create_response.status_code}; "
            f"{error_message}"
        )

    data = create_response.json()

    return CreatedStudent(
        user_id=data["user"]["id"],
        login=data["user"]["login"],
        course_id=data["course"]["id"],
        course_title=data["course"]["title"],
        stream_id=data["stream"]["id"],
        stream_title=data["stream"]["title"],
        stream_selection_source=data["stream"]["selection_source"],
        enrollment_id=data["enrollment"]["id"],
        enrollment_status=data["enrollment"]["status"],
    )
```

### Использование в другом проекте

Например, в файле:

```text
main.py
```

```python
from lectorium_client import (
    LectoriumApiError,
    create_lectorium_student,
)


try:
    student = create_lectorium_student(
        base_url="http://127.0.0.1:8000",
        admin_login="admin",
        admin_password="ADMIN_PASSWORD",
        student_login="new_student_01",
        student_password="StudentPassword123",
        course_id=2,
        stream_id=None,
    )
except LectoriumApiError as exc:
    print(f"Ошибка Lectorium: {exc}")
else:
    print("Студент создан:")
    print(f"ID: {student.user_id}")
    print(f"Логин: {student.login}")
    print(f"Курс: {student.course_title} (id={student.course_id})")
    print(f"Поток: {student.stream_title} (id={student.stream_id})")
    print(f"Выбор потока: {student.stream_selection_source}")
    print(f"Статус доступа: {student.enrollment_status}")
```

## Вызов функции

### Автоматический подбор потока

```python
student = create_lectorium_student(
    base_url="http://127.0.0.1:8000",
    admin_login="admin",
    admin_password="ADMIN_PASSWORD",
    student_login="student_from_crm",
    student_password="StrongPassword123",
    course_id=2,
)
```

Здесь `stream_id` не указан. Lectorium выберет текущий активный поток, а если такого нет — ближайший будущий активный поток.

### Явный поток

```python
student = create_lectorium_student(
    base_url="http://127.0.0.1:8000",
    admin_login="admin",
    admin_password="ADMIN_PASSWORD",
    student_login="student_group_a",
    student_password="StrongPassword123",
    course_id=2,
    stream_id=5,
)
```

В этом случае студент будет назначен строго в поток `5`, если он относится к курсу `2` и имеет статус `active`.

## Что нужно установить

В другом проекте:

```bash
pip install requests
```

## Важные правила

- Передавайте секреты через переменные окружения или секрет-хранилище, а не храните пароль администратора прямо в Git.
- В production используйте `https://`, а не `http://`.
- Функция открывает временную сессию, входит администратором, создаёт студента и автоматически закрывает HTTP-сессию.
- При дубликате логина функция выбросит `LectoriumApiError` с HTTP-кодом `409`.
- Если подходящего активного потока нет, функция выбросит ошибку с HTTP-кодом `422`.

## Как узнать ID курса

Администратор может увидеть ID курса в адресной строке браузера.

Например, если открыт адрес:

```text
http://127.0.0.1:8000/admin/courses/2
```

то:

```text
ID курса: 2
```

## Как узнать ID потока

Откройте нужный поток в админке. Если адрес выглядит так:

```text
http://127.0.0.1:8000/admin/streams/5
```

то:

```text
ID потока: 5
```

## Автоматический выбор потока

Если при вопросе:

```text
ID потока (Enter для автоматического выбора):
```

просто нажать `Enter`, скрипт не отправит `stream_id`.

Сервер автоматически выберет поток для указанного курса:

1. Сначала ищет активный поток, который проходит сейчас.
2. Если текущего потока нет — выбирает ближайший будущий активный поток.
3. Если потоков с датами нет — выбирает активный поток без даты начала.
4. Если подходящего активного потока нет — студент не будет создан.

Для автоматического выбора у потока должен быть статус:

```text
Активен
```

## Явный выбор потока

Если студент должен попасть в конкретную группу, введите ID потока:

```text
ID потока (Enter для автоматического выбора): 5
```

Сервер проверит:

- поток существует;
- поток принадлежит выбранному курсу;
- поток имеет статус `active`;
- студент с таким логином ещё не существует.

## Успешный результат

Пример вывода:

```text
Студент успешно создан и зачислен:
ID студента: 15
Логин: student_api_01
Курс: Python Backend (id=2)
Поток: Осень 2026 · группа А (id=5)
Выбор потока: auto
Статус зачисления: active
```

Значение:

```text
Выбор потока: auto
```

означает, что поток выбрала система автоматически.

Значение:

```text
Выбор потока: requested
```

означает, что ID потока был передан вручную.

## Возможные ошибки

### Неверный логин или пароль администратора

Пример:

```text
Не удалось войти как администратор:
HTTP 400
...
```

Проверьте учётные данные администратора.

### Логин студента уже существует

Пример:

```text
Не удалось создать студента:
HTTP 409
{"detail":"Пользователь с таким логином уже существует"}
```

Выберите другой логин или найдите существующего студента в админке и назначьте ему дополнительный курс вручную.

### У курса нет активного потока

Пример:

```text
Не удалось создать студента:
HTTP 422
{"detail":"Для курса нет активного или ближайшего потока"}
```

Решение:

```text
Курсы
→ нужный курс
→ нужный поток
→ Настройки потока
→ Статус: Активен
→ Сохранить поток
```

После этого снова запустите скрипт.

### Поток не относится к указанному курсу

Пример:

```text
HTTP 422
{"detail":"Поток не принадлежит указанному курсу"}
```

Проверьте `course_id` и `stream_id` в административных URL.

### Поток не активен

Пример:

```text
HTTP 422
{"detail":"В указанный поток нельзя зачислить студента"}
```

Переведите поток в статус **«Активен»** или не указывайте `stream_id`, чтобы система выбрала другой подходящий поток.

## Что создаётся в базе

После успешного запуска создаются две связанные записи:

```text
users
└── stream_enrollments
```

То есть студент создаётся и сразу получает доступ к одному потоку выбранного курса.

```text
User
└── StreamEnrollment
    ├── course_id
    ├── stream_id
    └── status = active
```

Студент сможет войти по своему логину и паролю, увидеть курс в личном кабинете, открыть расписание назначенного потока и смотреть только доступные ему видеозаписи.