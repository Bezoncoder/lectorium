import argparse
import asyncio
import getpass

from app.core.security import hash_password
from app.db.dao.user import UserDAO
from app.db.models.user import UserRole
from app.db.session import async_session_maker


async def create_admin(
    login: str,
    password: str,
) -> None:
    async with async_session_maker() as session:
        existing_user = await UserDAO.get_one_or_none(
            session=session,
            login=login,
        )

        if existing_user is not None:
            print(f"Пользователь '{login}' уже существует")
            return

        admin = await UserDAO.add(
            session=session,
            login=login,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )

        print(
            f"Администратор создан: "
            f"id={admin.id}, "
            f"login={admin.login}, "
            f"role={admin.role.value}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Создание администратора Lectorium",
    )

    parser.add_argument(
        "--login",
        required=True,
        help="Логин нового администратора",
    )

    parser.add_argument(
        "--password",
        required=False,
        help=(
            "Пароль администратора. "
            "Не рекомендуется: он попадёт в историю shell."
        ),
    )

    return parser.parse_args()


def validate_login(login: str) -> str:
    login = login.strip().lower()

    if len(login) < 3 or len(login) > 64:
        raise SystemExit(
            "Логин должен содержать от 3 до 64 символов"
        )

    normalized_login = login.replace("_", "").replace("-", "")

    if not normalized_login.isalnum():
        raise SystemExit(
            "Логин может содержать только буквы, цифры, _ и -"
        )

    return login


def get_password(password_from_args: str | None) -> str:
    if password_from_args is not None:
        password = password_from_args
    else:
        print("Пароль должен содержать минимум 8 символов.")
        password = getpass.getpass("Введите пароль администратора: ")
        password_repeat = getpass.getpass("Повторите пароль: ")

        if password != password_repeat:
            raise SystemExit("Пароли не совпадают")

    if len(password) < 8:
        raise SystemExit(
            "Пароль должен содержать минимум 8 символов"
        )

    if len(password.encode("utf-8")) > 72:
        raise SystemExit(
            "Пароль не должен превышать 72 байта в UTF-8"
        )

    return password


def main() -> None:
    args = parse_args()

    login = validate_login(args.login)
    password = get_password(args.password)

    asyncio.run(
        create_admin(
            login=login,
            password=password,
        )
    )


if __name__ == "__main__":
    main()