from __future__ import annotations
import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp


logger = logging.getLogger(__name__)


class LectoriumError(Exception):
    """
    Ошибка при работе с API Lectorium.

    Используется для:
    - сетевых ошибок;
    - timeout;
    - HTTP 4xx и 5xx;
    - некорректных ответов API.

    Атрибуты:
        message: Человекочитаемое описание.
        status_code: HTTP-код, если сервер вернул ответ.
        detail: FastAPI `detail` либо текст ответа.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.status_code = status_code
        self.detail = detail

    def __str__(self) -> str:
        parts = [self.message]

        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")

        if self.detail and self.detail != self.message:
            parts.append(self.detail)

        return ": ".join(parts)


@dataclass(frozen=True, slots=True)
class CreatedStudent:
    """Результат успешного создания студента и зачисления в поток."""

    student_id: int
    login: str
    role: str

    course_id: int
    course_title: str

    stream_id: int
    stream_title: str
    stream_selection_source: str

    enrollment_id: int
    enrollment_status: str

    def __str__(self) -> str:
        return (
            "Студент успешно создан и зачислен:\n"
            f"ID студента: {self.student_id}\n"
            f"Логин: {self.login}\n"
            f"Курс: {self.course_title} (id={self.course_id})\n"
            f"Поток: {self.stream_title} (id={self.stream_id})\n"
            f"Выбор потока: {self.stream_selection_source}\n"
            f"Статус зачисления: {self.enrollment_status}"
        )


class Lectorium:
    """
    Асинхронный клиент Lectorium.

    Для создания клиента с проверенной авторизацией:

        lectorium = await Lectorium.create(
            login="admin",
            password="ADMIN_PASSWORD",
            base_url="https://lectorium.infrasharing.ru",
        )

    После завершения обязательно:

        await lectorium.close()

    Либо используйте async with:

        async with await Lectorium.create(...) as lectorium:
            ...
    """

    LOGIN_PATH = "/login"
    CREATE_STUDENT_PATH = "/admin/api/students"

    DEFAULT_TIMEOUT_SECONDS = 15.0
    DEFAULT_MAX_ATTEMPTS = 3
    RETRY_DELAY_SECONDS = 0.5

    def __init__(
        self,
        *,
        login: str,
        password: str,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        admin_login = login.strip()
        normalized_base_url = base_url.rstrip("/")

        if not admin_login:
            raise ValueError("Логин администратора не может быть пустым.")

        if not password:
            raise ValueError("Пароль администратора не может быть пустым.")

        if not normalized_base_url:
            raise ValueError("base_url не может быть пустым.")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds должен быть больше нуля."
            )

        if max_attempts < 1:
            raise ValueError(
                "max_attempts должен быть не меньше 1."
            )

        self._login = admin_login
        self._password = password
        self._base_url = normalized_base_url
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts

        self._session: aiohttp.ClientSession | None = None
        self._is_authenticated = False

    @classmethod
    async def create(
        cls,
        *,
        login: str,
        password: str,
        base_url: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> Lectorium:
        """
        Создаёт клиента, открывает HTTP-сессию и сразу проверяет вход admin.

        Если POST /login неуспешен, выбрасывает LectoriumError и
        закрывает созданную HTTP-сессию.
        """
        instance = cls(
            login=login,
            password=password,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )

        try:
            await instance._create_session()
            await instance.authenticate()
        except Exception:
            await instance.close()
            raise

        return instance

    async def __aenter__(self) -> Lectorium:
        """
        Поддержка async with.

        Если объект создан обычным конструктором, создаёт сессию и
        авторизуется при входе в контекст.
        """
        await self._get_or_create_session()
        await self.authenticate()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Закрывает aiohttp-сессию и освобождает соединения."""
        if self._session is not None and not self._session.closed:
            await self._session.close()

            logger.info(
                "HTTP-сессия Lectorium закрыта: base_url=%s",
                self._base_url,
            )

        self._session = None
        self._is_authenticated = False

    async def authenticate(self) -> None:
        """
        Выполняет POST /login и сохраняет cookie администратора.

        Успехом считаются HTTP 200, 302 и 303.
        """
        if self._is_authenticated:
            return

        logger.info(
            "Авторизация в Lectorium: base_url=%s, admin_login=%s",
            self._base_url,
            self._login,
        )

        status_code, response_body = await self._make_request(
            method="POST",
            path=self.LOGIN_PATH,
            data={
                "login": self._login,
                "password": self._password,
            },
            expected_statuses={200, 302, 303},
            retry_on_server_error=True,
            retry_on_network_error=True,
        )

        self._is_authenticated = True

        logger.info(
            "Администратор успешно авторизован: admin_login=%s",
            self._login,
        )

    async def create_student(
        self,
        *,
        student_login: str,
        student_password: str,
        course_id: int,
        stream_id: int | None = None,
    ) -> CreatedStudent:
        """
        Создаёт студента и зачисляет его в поток.

        Важно: POST создания студента не повторяется автоматически при
        сетевой ошибке, timeout или 5xx, чтобы не создать дубликат.

        При HTTP 401 выполняется повторная авторизация и повтор самого
        POST-запроса один раз: 401 означает, что endpoint не обработал
        запрос из-за отсутствующей или истекшей сессии.
        """
        self._validate_create_student_input(
            student_login=student_login,
            student_password=student_password,
            course_id=course_id,
            stream_id=stream_id,
        )

        normalized_student_login = student_login.strip()

        payload: dict[str, Any] = {
            "login": normalized_student_login,
            "password": student_password,
            "course_id": course_id,

        }

        if stream_id is not None:
            payload["stream_id"] = stream_id

        await self._get_or_create_session()
        await self.authenticate()

        logger.info(
            "Создание студента: student_login=%s, course_id=%s, stream_id=%s",
            normalized_student_login,
            course_id,
            stream_id,
        )

        try:
            status_code, response_body = await self._make_request(
                method="POST",
                path=self.CREATE_STUDENT_PATH,
                json_data=payload,
                expected_statuses={201},
                retry_on_server_error=False,
                retry_on_network_error=False,
            )
        except LectoriumError as exc:
            if exc.status_code != 401:
                raise

            logger.info(
                "Сессия администратора истекла. "
                "Выполняется повторный login."
            )

            self._is_authenticated = False
            await self.authenticate()

            status_code, response_body = await self._make_request(
                method="POST",
                path=self.CREATE_STUDENT_PATH,
                json_data=payload,
                expected_statuses={201},
                retry_on_server_error=False,
                retry_on_network_error=False,
            )

        response_data = self._parse_json_object(
            response_body=response_body,
        )

        created_student = self._parse_created_student(
            response_data=response_data,
        )

        logger.info(
            "Студент успешно создан: student_id=%s, student_login=%s, "
            "course_id=%s, stream_id=%s, enrollment_status=%s",
            created_student.student_id,
            created_student.login,
            created_student.course_id,
            created_student.stream_id,
            created_student.enrollment_status,
        )

        return created_student

    async def _create_session(self) -> aiohttp.ClientSession:
        """
        Создаёт внутреннюю aiohttp.ClientSession.

        Используется create() для гарантии, что сессия существует до
        проверки авторизации.
        """
        if self._session is not None and not self._session.closed:
            return self._session

        self._session = aiohttp.ClientSession(
            base_url=self._base_url,
            timeout=aiohttp.ClientTimeout(
                total=self._timeout_seconds,
            ),
            cookie_jar=aiohttp.CookieJar(),
            headers={
                "Accept": "application/json, text/plain, */*",
            },
        )

        self._is_authenticated = False

        logger.info(
            "Создана HTTP-сессия Lectorium: base_url=%s",
            self._base_url,
        )

        return self._session

    async def _get_or_create_session(self) -> aiohttp.ClientSession:
        """Возвращает открытую сессию или создаёт её лениво."""
        return await self._create_session()

    async def _make_request(
        self,
        *,
        method: str,
        path: str,
        expected_statuses: set[int],
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_redirects: bool = False,
        retry_on_network_error: bool = False,
        retry_on_server_error: bool = False,
    ) -> tuple[int, str]:
        """
        Делает HTTP-запрос к self._base_url + path.

        Делает максимум self._max_attempts попыток. По умолчанию это 3:
        - первая попытка;
        - первый retry;
        - второй retry.

        Повторяются только ошибки, которые разрешил вызывающий код:
        - timeout / aiohttp.ClientError — retry_on_network_error=True;
        - HTTP 5xx — retry_on_server_error=True.

        HTTP 4xx не повторяются: это бизнес-ошибка, неверные данные или
        проблемы авторизации, повтором они не исправляются.

        Для каждого endpoint-а вызывающий метод сам выбирает, безопасно ли
        повторять запрос. Для POST /admin/api/students retry отключён.
        """
        if not path.startswith("/"):
            raise ValueError(
                "path должен начинаться с '/', например '/login'."
            )

        if data is not None and json_data is not None:
            raise ValueError(
                "Нельзя передавать одновременно data и json_data."
            )

        session = await self._get_or_create_session()
        request_headers = headers or {}

        for attempt in range(1, self._max_attempts + 1):
            try:
                async with session.request(
                    method=method.upper(),
                    url=path,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    allow_redirects=allow_redirects,
                ) as response:
                    response_body = await response.text()

            except asyncio.TimeoutError as exc:
                if (
                    retry_on_network_error
                    and attempt < self._max_attempts
                ):
                    await self._sleep_before_retry(
                        attempt=attempt,
                        method=method,
                        path=path,
                        reason="timeout",
                    )
                    continue

                logger.warning(
                    "Timeout при запросе к Lectorium: "
                    "method=%s, path=%s, attempt=%s/%s",
                    method,
                    path,
                    attempt,
                    self._max_attempts,
                )

                raise LectoriumError(
                    "Превышено время ожидания при обращении к Lectorium."
                ) from exc

            except aiohttp.ClientError as exc:
                if (
                    retry_on_network_error
                    and attempt < self._max_attempts
                ):
                    await self._sleep_before_retry(
                        attempt=attempt,
                        method=method,
                        path=path,
                        reason=type(exc).__name__,
                    )
                    continue

                logger.exception(
                    "Ошибка сети при запросе к Lectorium: "
                    "method=%s, path=%s, attempt=%s/%s",
                    method,
                    path,
                    attempt,
                    self._max_attempts,
                )

                raise LectoriumError(
                    "Не удалось подключиться к Lectorium."
                ) from exc

            if (
                response.status >= 500
                and retry_on_server_error
                and attempt < self._max_attempts
            ):
                await self._sleep_before_retry(
                    attempt=attempt,
                    method=method,
                    path=path,
                    reason=f"HTTP {response.status}",
                )
                continue

            if response.status not in expected_statuses:
                detail = self._extract_error_detail(response_body)

                logger.warning(
                    "Ошибка ответа Lectorium: "
                    "method=%s, path=%s, status=%s, detail=%s",
                    method,
                    path,
                    response.status,
                    detail,
                )

                raise LectoriumError(
                    "Lectorium вернул ошибку.",
                    status_code=response.status,
                    detail=detail,
                )

            logger.debug(
                "Успешный ответ Lectorium: "
                "method=%s, path=%s, status=%s, attempt=%s/%s",
                method,
                path,
                response.status,
                attempt,
                self._max_attempts,
            )

            return response.status, response_body

        raise RuntimeError(
            "Внутренняя ошибка: _make_request завершился без результата."
        )

    async def _sleep_before_retry(
        self,
        *,
        attempt: int,
        method: str,
        path: str,
        reason: str,
    ) -> None:
        """
        Ждёт перед следующей попыткой.

        Задержка:
        - после первой неудачи: 0.5 секунды;
        - после второй неудачи: 1.0 секунда.
        """
        delay = self.RETRY_DELAY_SECONDS * attempt

        logger.warning(
            "Повтор запроса Lectorium через %.1f сек.: "
            "method=%s, path=%s, attempt=%s/%s, reason=%s",
            delay,
            method,
            path,
            attempt + 1,
            self._max_attempts,
            reason,
        )

        await asyncio.sleep(delay)

    @staticmethod
    def _validate_create_student_input(
        *,
        student_login: str,
        student_password: str,
        course_id: int,
        stream_id: int | None,
    ) -> None:
        if not student_login.strip():
            raise ValueError("Логин студента не может быть пустым.")

        if not student_password:
            raise ValueError("Пароль студента не может быть пустым.")

        if course_id <= 0:
            raise ValueError(
                "course_id должен быть положительным целым числом."
            )

        if stream_id is not None and stream_id <= 0:
            raise ValueError(
                "stream_id должен быть положительным целым числом или None."
            )

    @staticmethod
    def _parse_json_object(
        *,
        response_body: str,
    ) -> dict[str, Any]:
        """Проверяет, что успешный ответ API — JSON-объект."""
        try:
            parsed_data = json.loads(response_body)
        except json.JSONDecodeError as exc:
            logger.error(
                "Успешный ответ Lectorium не является JSON: response=%s",
                Lectorium._truncate_text(response_body),
            )

            raise LectoriumError(
                "Lectorium вернул успешный ответ, "
                "но тело не является JSON.",
                detail=Lectorium._truncate_text(response_body),
            ) from exc

        if not isinstance(parsed_data, dict):
            raise LectoriumError(
                "Lectorium вернул JSON неверной структуры: "
                "ожидался объект.",
                detail=Lectorium._truncate_text(response_body),
            )

        return parsed_data

    @staticmethod
    def _parse_created_student(
        *,
        response_data: dict[str, Any],
    ) -> CreatedStudent:
        """Парсит успешный ответ POST /admin/api/students."""
        try:
            user = response_data["user"]
            course = response_data["course"]
            stream = response_data["stream"]
            enrollment = response_data["enrollment"]

            if not all(
                isinstance(value, dict)
                for value in (user, course, stream, enrollment)
            ):
                raise TypeError(
                    "Поля user, course, stream и enrollment "
                    "должны быть JSON-объектами."
                )

            return CreatedStudent(
                student_id=int(user["id"]),
                login=str(user["login"]),
                role=str(user["role"]),
                course_id=int(course["id"]),
                course_title=str(course["title"]),
                stream_id=int(stream["id"]),
                stream_title=str(stream["title"]),
                stream_selection_source=str(
                    stream["selection_source"]
                ),
                enrollment_id=int(enrollment["id"]),
                enrollment_status=str(enrollment["status"]),
            )

        except (KeyError, TypeError, ValueError) as exc:
            logger.error(
                "Некорректная структура JSON create_student: %r",
                response_data,
            )

            raise LectoriumError(
                "API Lectorium вернул успешный ответ "
                "в неожиданном формате.",
                detail=Lectorium._truncate_text(str(response_data)),
            ) from exc

    @staticmethod
    def _extract_error_detail(response_body: str) -> str:
        """Извлекает поле `detail` из JSON-ошибки FastAPI."""
        try:
            response_data = json.loads(response_body)
        except json.JSONDecodeError:
            return Lectorium._truncate_text(response_body)

        if isinstance(response_data, dict):
            detail = response_data.get("detail")

            if isinstance(detail, str):
                return detail

            if detail is not None:
                return str(detail)

        return Lectorium._truncate_text(response_body)

    @staticmethod
    def _truncate_text(
        text: str,
        max_length: int = 500,
    ) -> str:
        """Ограничивает длину текста ответа для логов и ошибок."""
        normalized_text = text.strip()

        if not normalized_text:
            return "Ответ без тела."

        if len(normalized_text) > max_length:
            return f"{normalized_text[:max_length]}…"

        return normalized_text









# from __future__ import annotations


#
# import asyncio
# import json
# import logging
# from dataclasses import dataclass
# from typing import Any
#
# import aiohttp
#
#
"""
    Использование в TG_Bot

    @router.message(Command("create_student"))
    async def handler(message: Message) -> None:
        lectorium = Lectorium(
            login="admin",
            password="ADMIN_PASSWORD",
            base_url="http://127.0.0.1:8000",
        )

        try:
            student = await lectorium.create_student(
                student_login="test",
                student_password="StrongPassword123",
                course_id=1,
                stream_id=None,
            )
        except Lectorium.LectoriumError as exc:
            await message.answer(
                f"Не удалось создать студента:\n{exc}"
            )
        finally:
            await lectorium.close()


"""
#
# logger = logging.getLogger(__name__)
#
#
# @dataclass(frozen=True, slots=True)
# class CreatedStudent:
#     """
#     Результат успешного создания студента и его зачисления в поток.
#     """
#
#     student_id: int
#     login: str
#     role: str
#
#     course_id: int
#     course_title: str
#
#     stream_id: int
#     stream_title: str
#     stream_selection_source: str
#
#     enrollment_id: int
#     enrollment_status: str
#
#     def __str__(self) -> str:
#         return (
#             "Студент успешно создан и зачислен:\n"
#             f"ID студента: {self.student_id}\n"
#             f"Логин: {self.login}\n"
#             f"Курс: {self.course_title} (id={self.course_id})\n"
#             f"Поток: {self.stream_title} (id={self.stream_id})\n"
#             f"Выбор потока: {self.stream_selection_source}\n"
#             f"Статус зачисления: {self.enrollment_status}"
#         )
#
#
# class Lectorium:
#     """
#     Асинхронный клиент API Lectorium на aiohttp.
#
#     Жизненный цикл:
#     - __init__(): сохраняет настройки, HTTP-сессию не создаёт;
#     - create_student(): лениво создаёт сессию и при необходимости логинится;
#     - close(): закрывает aiohttp.ClientSession;
#     - async with: поддерживается, но не обязателен.
#
#     Пример без async with:
#
#         lectorium = Lectorium(
#             login="admin",
#             password="ADMIN_PASSWORD",
#             base_url="http://127.0.0.1:8000",
#         )
#
#         try:
#             student = await lectorium.create_student(
#                 student_login="test",
#                 student_password="StrongPassword123",
#                 course_id=1,
#             )
#         finally:
#             await lectorium.close()
#
#     Пример с async with:
#
#         async with Lectorium(
#             login="admin",
#             password="ADMIN_PASSWORD",
#             base_url="http://127.0.0.1:8000",
#         ) as lectorium:
#             student = await lectorium.create_student(
#                 student_login="test",
#                 student_password="StrongPassword123",
#                 course_id=1,
#             )
#     """
#
#     LOGIN_PATH = "/login"
#     CREATE_STUDENT_PATH = "/admin/api/students"
#
#     class LectoriumError(Exception):
#         """
#         Единое исключение клиента Lectorium.
#
#         Атрибуты:
#             message: Понятное описание ошибки.
#             status_code: HTTP-код, если сервер успел ответить.
#             detail: FastAPI detail или ограниченный текст ответа.
#         """
#
#         def __init__(
#             self,
#             message: str,
#             *,
#             status_code: int | None = None,
#             detail: str | None = None,
#         ) -> None:
#             super().__init__(message)
#
#             self.message = message
#             self.status_code = status_code
#             self.detail = detail
#
#         def __str__(self) -> str:
#             parts = [self.message]
#
#             if self.status_code is not None:
#                 parts.append(f"HTTP {self.status_code}")
#
#             if self.detail and self.detail != self.message:
#                 parts.append(self.detail)
#
#             return ": ".join(parts)
#
#     def __init__(
#         self,
#         *,
#         login: str,
#         password: str,
#         base_url: str,
#         timeout_seconds: float = 15.0,
#     ) -> None:
#         admin_login = login.strip()
#         normalized_base_url = base_url.rstrip("/")
#
#         if not admin_login:
#             raise ValueError("Логин администратора не может быть пустым.")
#
#         if not password:
#             raise ValueError("Пароль администратора не может быть пустым.")
#
#         if not normalized_base_url:
#             raise ValueError("base_url не может быть пустым.")
#
#         if timeout_seconds <= 0:
#             raise ValueError(
#                 "timeout_seconds должен быть больше нуля."
#             )
#
#         self._login = admin_login
#         self._password = password
#         self._base_url = normalized_base_url
#         self._timeout_seconds = timeout_seconds
#
#         self._session: aiohttp.ClientSession | None = None
#         self._is_authenticated = False
#
#     async def __aenter__(self) -> Lectorium:
#         """
#         Не открывает сессию заранее.
#
#         Сессия будет создана только при первом HTTP-запросе.
#         """
#         return self
#
#     async def __aexit__(
#         self,
#         exc_type: type[BaseException] | None,
#         exc_value: BaseException | None,
#         traceback: Any,
#     ) -> None:
#         await self.close()
#
#     async def close(self) -> None:
#         """
#         Закрывает сессию и освобождает сетевые ресурсы.
#
#         Метод безопасен при повторном вызове.
#         """
#         if self._session is not None and not self._session.closed:
#             await self._session.close()
#
#             logger.info(
#                 "HTTP-сессия Lectorium закрыта: base_url=%s",
#                 self._base_url,
#             )
#
#         self._session = None
#         self._is_authenticated = False
#
#     async def authenticate(self) -> None:
#         """
#         Авторизует администратора через POST /login.
#
#         Сессия создаётся автоматически при первом вызове.
#
#         Cookie, полученная от Lectorium, остаётся в ClientSession и будет
#         использована в POST /admin/api/students.
#
#         Повторный login не выполняется, пока _is_authenticated=True.
#         """
#         session = await self._get_or_create_session()
#
#         if self._is_authenticated:
#             return
#
#         logger.info(
#             "Авторизация в Lectorium: base_url=%s, admin_login=%s",
#             self._base_url,
#             self._login,
#         )
#
#         try:
#             async with session.post(
#                 self.LOGIN_PATH,
#                 data={
#                     "login": self._login,
#                     "password": self._password,
#                 },
#                 allow_redirects=False,
#             ) as response:
#                 response_body = await response.text()
#
#                 if response.status not in (200, 302, 303):
#                     detail = self._extract_error_detail(response_body)
#
#                     logger.warning(
#                         "Ошибка авторизации Lectorium: "
#                         "status=%s, admin_login=%s, detail=%s",
#                         response.status,
#                         self._login,
#                         detail,
#                     )
#
#                     raise self.LectoriumError(
#                         "Не удалось войти как администратор.",
#                         status_code=response.status,
#                         detail=detail,
#                     )
#
#         except asyncio.TimeoutError as exc:
#             logger.warning(
#                 "Timeout при авторизации: "
#                 "base_url=%s, admin_login=%s",
#                 self._base_url,
#                 self._login,
#             )
#
#             raise self.LectoriumError(
#                 "Превышено время ожидания при авторизации в Lectorium."
#             ) from exc
#
#         except aiohttp.ClientError as exc:
#             logger.exception(
#                 "Ошибка сети при авторизации: "
#                 "base_url=%s, admin_login=%s",
#                 self._base_url,
#                 self._login,
#             )
#
#             raise self.LectoriumError(
#                 "Не удалось подключиться к Lectorium при авторизации."
#             ) from exc
#
#         self._is_authenticated = True
#
#         logger.info(
#             "Администратор успешно авторизован: admin_login=%s",
#             self._login,
#         )
#
#     async def create_student(
#         self,
#         *,
#         student_login: str,
#         student_password: str,
#         course_id: int,
#         stream_id: int | None = None,
#     ) -> CreatedStudent:
#         """
#         Создаёт студента и зачисляет его на курс/поток.
#
#         При stream_id=None:
#         - stream_id не передаётся в JSON;
#         - сервер автоматически выбирает активный текущий или ближайший
#           будущий поток;
#         - в результате будет selection_source="auto".
#
#         При stream_id=<id>:
#         - сервер зачисляет в указанный поток;
#         - в результате будет selection_source="requested".
#
#         Если сервер вернул 401:
#         1. клиент сбрасывает локальный флаг авторизации;
#         2. повторно авторизуется;
#         3. повторяет создание студента ровно один раз.
#
#         Повтор выполняется только для HTTP 401. Для timeout, сетевых
#         ошибок и 5xx автоматический retry не выполняется, чтобы не
#         создать студента дважды при неопределённом результате запроса.
#         """
#         normalized_student_login = student_login.strip()
#
#         self._validate_create_student_input(
#             student_login=normalized_student_login,
#             student_password=student_password,
#             course_id=course_id,
#             stream_id=stream_id,
#         )
#
#         payload: dict[str, Any] = {
#             "login": normalized_student_login,
#             "password": student_password,
#             "course_id": course_id,
#         }
#
#         if stream_id is not None:
#             payload["stream_id"] = stream_id
#
#         logger.info(
#             "Создание студента: student_login=%s, course_id=%s, stream_id=%s",
#             normalized_student_login,
#             course_id,
#             stream_id,
#         )
#
#         await self.authenticate()
#
#         status_code, response_body = await self._post_create_student(
#             payload=payload,
#         )
#
#         if status_code == 401:
#             logger.info(
#                 "Сессия Lectorium недействительна. "
#                 "Выполняется повторная авторизация."
#             )
#
#             self._is_authenticated = False
#
#             await self.authenticate()
#
#             status_code, response_body = await self._post_create_student(
#                 payload=payload,
#             )
#
#         self._raise_for_create_student_error(
#             status_code=status_code,
#             response_body=response_body,
#         )
#
#         response_data = self._parse_json_object(
#             response_body=response_body,
#         )
#
#         created_student = self._parse_created_student(
#             response_data=response_data,
#         )
#
#         logger.info(
#             "Студент успешно создан: student_id=%s, "
#             "student_login=%s, course_id=%s, stream_id=%s, "
#             "selection_source=%s, enrollment_id=%s, "
#             "enrollment_status=%s",
#             created_student.student_id,
#             created_student.login,
#             created_student.course_id,
#             created_student.stream_id,
#             created_student.stream_selection_source,
#             created_student.enrollment_id,
#             created_student.enrollment_status,
#         )
#
#         return created_student
#
#     async def _get_or_create_session(self) -> aiohttp.ClientSession:
#         """
#         Возвращает существующую открытую сессию или создаёт новую.
#
#         Это и есть ленивая инициализация: в __init__ HTTP-сессия не
#         создаётся; она появляется только перед первым HTTP-запросом.
#         """
#         if self._session is not None and not self._session.closed:
#             return self._session
#
#         self._session = aiohttp.ClientSession(
#             base_url=self._base_url,
#             timeout=aiohttp.ClientTimeout(
#                 total=self._timeout_seconds,
#             ),
#             cookie_jar=aiohttp.CookieJar(),
#             headers={
#                 "Accept": "application/json, text/plain, */*",
#             },
#         )
#
#         self._is_authenticated = False
#
#         logger.info(
#             "Создана HTTP-сессия Lectorium: base_url=%s",
#             self._base_url,
#         )
#
#         return self._session
#
#     async def _post_create_student(
#         self,
#         *,
#         payload: dict[str, Any],
#     ) -> tuple[int, str]:
#         """
#         Отправляет один POST /admin/api/students.
#
#         Не выполняет retry и не разбирает HTTP-статус — это делает
#         create_student(), чтобы контролировать единственную попытку
#         переавторизации после HTTP 401.
#         """
#         session = await self._get_or_create_session()
#
#         try:
#             async with session.post(
#                 self.CREATE_STUDENT_PATH,
#                 json=payload,
#             ) as response:
#                 return response.status, await response.text()
#
#         except asyncio.TimeoutError as exc:
#             logger.warning(
#                 "Timeout при запросе создания студента."
#             )
#
#             raise self.LectoriumError(
#                 "Превышено время ожидания при создании студента."
#             ) from exc
#
#         except aiohttp.ClientError as exc:
#             logger.exception(
#                 "Ошибка сети при запросе создания студента."
#             )
#
#             raise self.LectoriumError(
#                 "Не удалось подключиться к Lectorium "
#                 "при создании студента."
#             ) from exc
#
#     @staticmethod
#     def _validate_create_student_input(
#         *,
#         student_login: str,
#         student_password: str,
#         course_id: int,
#         stream_id: int | None,
#     ) -> None:
#         """Проверяет базные значения до выполнения HTTP-запроса."""
#         if not student_login:
#             raise ValueError("Логин студента не может быть пустым.")
#
#         if not student_password:
#             raise ValueError("Пароль студента не может быть пустым.")
#
#         if course_id <= 0:
#             raise ValueError(
#                 "course_id должен быть положительным целым числом."
#             )
#
#         if stream_id is not None and stream_id <= 0:
#             raise ValueError(
#                 "stream_id должен быть положительным целым числом или None."
#             )
#
#     def _raise_for_create_student_error(
#         self,
#         *,
#         status_code: int,
#         response_body: str,
#     ) -> None:
#         """
#         Преобразует неуспешные HTTP-ответы API в LectoriumError.
#
#         Успех: HTTP 201 Created.
#
#         Известные бизнес-ошибки Lectorium:
#         - 409: пользователь с таким логином уже существует;
#         - 422: нет подходящего потока;
#         - 422: поток принадлежит другому курсу;
#         - 422: поток недоступен для зачисления.
#         """
#         if status_code == 201:
#             return
#
#         detail = self._extract_error_detail(response_body)
#
#         logger.warning(
#             "Ошибка создания студента: status=%s, detail=%s",
#             status_code,
#             detail,
#         )
#
#         if status_code == 401:
#             self._is_authenticated = False
#
#             raise self.LectoriumError(
#                 "Сессия администратора недействительна или истекла.",
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         if status_code == 403:
#             raise self.LectoriumError(
#                 "У пользователя нет прав администратора.",
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         if status_code == 404:
#             raise self.LectoriumError(
#                 "Endpoint создания студента не найден. "
#                 "Проверьте base_url и путь API.",
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         if status_code == 409:
#             raise self.LectoriumError(
#                 "Пользователь с таким логином уже существует.",
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         if status_code == 422:
#             raise self.LectoriumError(
#                 self._get_422_error_message(detail),
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         if status_code >= 500:
#             raise self.LectoriumError(
#                 "Внутренняя ошибка сервера Lectorium.",
#                 status_code=status_code,
#                 detail=detail,
#             )
#
#         raise self.LectoriumError(
#             "Lectorium вернул неожиданный HTTP-ответ.",
#             status_code=status_code,
#             detail=detail,
#         )
#
#     @staticmethod
#     def _get_422_error_message(detail: str) -> str:
#         """
#         Преобразует известные detail-сообщения от backend в понятный текст.
#         """
#         messages = {
#             "Для курса нет активного или ближайшего потока": (
#                 "Для выбранного курса нет активного текущего "
#                 "или ближайшего будущего потока."
#             ),
#             "Поток не принадлежит указанному курсу": (
#                 "Указанный поток не принадлежит выбранному курсу."
#             ),
#             "В указанный поток нельзя зачислить студента": (
#                 "В указанный поток нельзя зачислить студента."
#             ),
#         }
#
#         return messages.get(
#             detail,
#             "Данные создания студента не прошли проверку API.",
#         )
#
#     @staticmethod
#     def _parse_json_object(
#         *,
#         response_body: str,
#     ) -> dict[str, Any]:
#         """
#         Разбирает успешный API-ответ как JSON-объект.
#         """
#         try:
#             parsed_data = json.loads(response_body)
#         except json.JSONDecodeError as exc:
#             logger.error(
#                 "Успешный ответ Lectorium не является JSON: response=%s",
#                 Lectorium._truncate_text(response_body),
#             )
#
#             raise Lectorium.LectoriumError(
#                 "Lectorium вернул успешный ответ, "
#                 "но его тело не является JSON.",
#                 detail=Lectorium._truncate_text(response_body),
#             ) from exc
#
#         if not isinstance(parsed_data, dict):
#             logger.error(
#                 "JSON-ответ Lectorium имеет неверный тип: "
#                 "type=%s, data=%r",
#                 type(parsed_data).__name__,
#                 parsed_data,
#             )
#
#             raise Lectorium.LectoriumError(
#                 "Lectorium вернул JSON неверной структуры: "
#                 "ожидался объект.",
#                 detail=Lectorium._truncate_text(response_body),
#             )
#
#         return parsed_data
#
#     @staticmethod
#     def _parse_created_student(
#         *,
#         response_data: dict[str, Any],
#     ) -> CreatedStudent:
#         """
#         Разбирает успешный ответ backend:
#
#         {
#           "user": {
#             "id": 3,
#             "login": "test",
#             "role": "student"
#           },
#           "course": {
#             "id": 1,
#             "title": "BootCamp"
#           },
#           "stream": {
#             "id": 1,
#             "title": "Осень 2026",
#             "selection_source": "auto"
#           },
#           "enrollment": {
#             "id": 1,
#             "status": "active"
#           }
#         }
#         """
#         try:
#             user = response_data["user"]
#             course = response_data["course"]
#             stream = response_data["stream"]
#             enrollment = response_data["enrollment"]
#
#             if not isinstance(user, dict):
#                 raise TypeError("Поле user должно быть объектом.")
#
#             if not isinstance(course, dict):
#                 raise TypeError("Поле course должно быть объектом.")
#
#             if not isinstance(stream, dict):
#                 raise TypeError("Поле stream должно быть объектом.")
#
#             if not isinstance(enrollment, dict):
#                 raise TypeError("Поле enrollment должно быть объектом.")
#
#             return CreatedStudent(
#                 student_id=int(user["id"]),
#                 login=str(user["login"]),
#                 role=str(user["role"]),
#                 course_id=int(course["id"]),
#                 course_title=str(course["title"]),
#                 stream_id=int(stream["id"]),
#                 stream_title=str(stream["title"]),
#                 stream_selection_source=str(
#                     stream["selection_source"]
#                 ),
#                 enrollment_id=int(enrollment["id"]),
#                 enrollment_status=str(enrollment["status"]),
#             )
#
#         except (KeyError, TypeError, ValueError) as exc:
#             logger.error(
#                 "Некорректная структура JSON create_student: %r",
#                 response_data,
#             )
#
#             raise Lectorium.LectoriumError(
#                 "API Lectorium вернул успешный ответ "
#                 "в неожиданном формате.",
#                 detail=Lectorium._truncate_text(str(response_data)),
#             ) from exc
#
#     @staticmethod
#     def _extract_error_detail(
#         response_body: str,
#     ) -> str:
#         """
#         Извлекает `detail` из JSON-ответа FastAPI.
#
#         Например:
#             {"detail": "Поток не принадлежит указанному курсу"}
#         """
#         try:
#             response_data = json.loads(response_body)
#         except json.JSONDecodeError:
#             return Lectorium._truncate_text(response_body)
#
#         if isinstance(response_data, dict):
#             detail = response_data.get("detail")
#
#             if isinstance(detail, str):
#                 return detail
#
#             if detail is not None:
#                 return str(detail)
#
#         return Lectorium._truncate_text(response_body)
#
#     @staticmethod
#     def _truncate_text(
#         text: str,
#         max_length: int = 500,
#     ) -> str:
#         """
#         Ограничивает размер response body для исключений и логов.
#
#         Пароли и request body в логи не передаются.
#         """
#         normalized_text = text.strip()
#
#         if not normalized_text:
#             return "Ответ без тела."
#
#         if len(normalized_text) > max_length:
#             return f"{normalized_text[:max_length]}…"
#
#         return normalized_text
#
#
async def main():
    lectorium = Lectorium(
        login="admin",
        password="1q2w3e4r",
        base_url="https://lectorium.infrasharing.ru/",
    )

    try:
        student = await lectorium.create_student(
            student_login="test14",
            student_password="testtest",
            course_id=1,
            stream_id=None,
        )
        print(student)

    except Exception as exc:
        pass
    finally:
        await lectorium.close()


if __name__=="__main__":

    asyncio.run(main())