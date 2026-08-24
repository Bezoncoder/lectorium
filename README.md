# Lectorium

**Lectorium** — асинхронный веб-сервис для учебных видео.

Стек: FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, PostgreSQL, asyncpg, Jinja2, aiofiles и Docker Compose.

В сервисе есть две роли:

- **student** — просматривает видео и статистику;
- **admin** — имеет права student, а также добавляет, редактирует и удаляет видео.

Видео сохраняются на диск сервера в каталоге `video/`. Метаданные, пользователи, серверные сессии и статистика просмотров хранятся в PostgreSQL.

---

## Возможности

- Авторизация по `login` и `password` с cookie-сессиями.
- Server-side sessions в таблице `user_sessions`.
- Роли `student` и `admin`.
- Асинхронная работа с PostgreSQL через SQLAlchemy и `asyncpg`.
- Миграции БД через Alembic.
- Асинхронная загрузка видео через `aiofiles`.
- UUID-имена файлов на диске; оригинальное имя хранится только для отображения.
- Поддерживаемые форматы: MP4, WebM, OGG.
- Учёт просмотра после 30 секунд.
- Не более одного засчитанного просмотра одного видео от одного пользователя в день.
- Общая статистика и список пользователей, смотревших видео.
- HTML-интерфейс на Jinja2.
- PostgreSQL хранит данные в локальной папке проекта `postgres_data/`.

---

## Структура проекта

```text
lectorium/
├── app/
│   ├── api/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── statistics.py
│   │   └── videos.py
│   ├── core/
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   └── security.py
│   ├── db/
│   │   ├── dao/
│   │   ├── models/
│   │   ├── base.py
│   │   └── session.py
│   ├── schemas/
│   ├── services/
│   ├── static/
│   ├── templates/
│   └── main.py
├── migration/
│   └── versions/
├── scripts/
│   ├── create_admin.py
│   └── create_student.py
├── video/
├── postgres_data/
├── .env
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Требования

Для запуска через Docker:

- Docker Engine;
- Docker Compose v2.

Для локальной разработки без Docker для приложения:

- Python 3.12+;
- PostgreSQL в Docker или установленный отдельно;
- виртуальное окружение Python.

Проверка Docker:

```bash
docker --version
docker compose version
```

---

## Конфигурация

### `.env` для локального запуска

Создайте файл конфигурации:

```bash
cp .env.example .env
```

Пример `.env` для запуска приложения и Alembic **на хостовой машине**:

```env
APP_NAME=Lectorium
DEBUG=true

SECRET_KEY=replace_with_a_long_random_secret

DB_USER=lectorium
DB_PASSWORD=lectorium_password
DB_HOST=127.0.0.1
DB_PORT=15432
DB_NAME=lectorium

VIDEO_DIR=video

SESSION_COOKIE_NAME=lectorium_session
SESSION_TTL_DAYS=7
COOKIE_SECURE=false

MAX_VIDEO_SIZE_MB=2048
```

`DB_PORT=15432` указан потому, что в `docker-compose.yml` PostgreSQL публикуется на хост по адресу `15432`, а внутри контейнера продолжает использовать порт `5432`.

Сгенерировать безопасный `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### `.env.docker` для контейнера приложения

Если приложение запускается внутри Docker, оно должно обращаться к PostgreSQL по имени Compose-сервиса `postgres`, а не по `127.0.0.1`.

Создайте `.env.docker`:

```env
APP_NAME=Lectorium
DEBUG=false

SECRET_KEY=replace_with_a_long_random_secret

DB_USER=lectorium
DB_PASSWORD=lectorium_password
DB_HOST=postgres
DB_PORT=5432
DB_NAME=lectorium

VIDEO_DIR=/app/video

SESSION_COOKIE_NAME=lectorium_session
SESSION_TTL_DAYS=7
COOKIE_SECURE=true

MAX_VIDEO_SIZE_MB=2048
```

> Для локального HTTP-запуска без TLS ставьте `COOKIE_SECURE=false`. В production за Nginx/HTTPS ставьте `COOKIE_SECURE=true`.

---

## Docker Compose

Пример `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:17
    container_name: lectorium_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: lectorium
      POSTGRES_USER: lectorium
      POSTGRES_PASSWORD: lectorium_password
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "15432:5432"
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "pg_isready -U lectorium -d lectorium"
        ]
      interval: 5s
      timeout: 5s
      retries: 20

  app:
    build: .
    container_name: lectorium_app
    restart: unless-stopped
    env_file:
      - .env.docker
    ports:
      - "8000:8000"
    volumes:
      - ./video:/app/video
    depends_on:
      postgres:
        condition: service_healthy
```

`./postgres_data:/var/lib/postgresql/data` — bind mount. Поэтому физические данные PostgreSQL появятся в `postgres_data/` в корне проекта.

Добавьте в `.gitignore`:

```gitignore
.env
.env.docker
postgres_data/
video/*
!video/.gitkeep
```

Не редактируйте файлы внутри `postgres_data/` вручную: это внутренние файлы PostgreSQL.

---

## Первый запуск на сервере

Все команды выполняются из корня проекта:

```bash
cd /path/to/lectorium
```

### 1. Создать каталоги данных

```bash
mkdir -p video postgres_data
```

- `video/` — загружаемые видеоролики;
- `postgres_data/` — данные PostgreSQL.

### 2. Настроить переменные окружения

```bash
cp .env.example .env
cp .env.example .env.docker
```

Затем отредактируйте `.env.docker` и обязательно задайте сильные значения:

```bash
nano .env.docker
```

В `.env.docker` укажите:

```env
DB_HOST=postgres
DB_PORT=5432
COOKIE_SECURE=true
```

### 3. Собрать и запустить контейнеры

```bash
sudo docker compose up -d --build
```

Команда:

- `up` создаёт и запускает сервисы;
- `-d` запускает их в фоне;
- `--build` пересобирает образ приложения из `Dockerfile`.

Проверить состояние:

```bash
sudo docker compose ps
```

Ожидается:

```text
lectorium_postgres   Up (healthy)
lectorium_app        Up
```

Посмотреть логи:

```bash
sudo docker compose logs -f postgres
sudo docker compose logs -f app
```

- `-f` непрерывно выводит новые строки лога;
- `Ctrl+C` завершает просмотр логов, но не останавливает контейнеры.

### 4. Применить миграции

Если начальная миграция уже хранится в репозитории:

```bash
sudo docker compose exec app alembic upgrade head
```

Команда `docker compose exec app ...` выполняет команду внутри запущенного контейнера `app`.

Если миграций ещё нет, сначала создайте первую ревизию:

```bash
sudo docker compose exec app alembic revision --autogenerate -m "Initial revision"
sudo docker compose exec app alembic upgrade head
```

Проверить версию миграции:

```bash
sudo docker compose exec app alembic current
```

Проверить таблицы PostgreSQL:

```bash
sudo docker compose exec postgres \
  psql -U lectorium -d lectorium -c "\dt"
```

### 5. Создать первого администратора

```bash
sudo docker compose exec -it app \
  python -m scripts.create_admin --login admin
```

Команда интерактивно запросит пароль и повтор пароля. Пароль не попадёт в историю shell и не будет виден в аргументах процессов.

Проверить пользователей:

```bash
sudo docker compose exec postgres \
  psql -U lectorium -d lectorium \
  -c "SELECT id, login, role, created_at FROM users ORDER BY id;"
```

### 6. Открыть сервис

```text
http://SERVER_IP:8000/login
```

Для production рекомендуется поставить Nginx перед приложением, настроить TLS-сертификат и открыть наружу только 80/443. Порт PostgreSQL `15432` не должен быть доступен из интернета.

---

## Локальная разработка

### Установить зависимости

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Запустить только PostgreSQL

```bash
sudo docker compose up -d postgres
```

Проверьте, что PostgreSQL готов:

```bash
sudo docker compose ps
```

### Настроить `.env`

Для запуска приложения локально используйте:

```env
DB_HOST=127.0.0.1
DB_PORT=15432
COOKIE_SECURE=false
```

### Применить миграции

```bash
alembic upgrade head
```

Создать новую миграцию после изменения SQLAlchemy-моделей:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

### Запустить FastAPI

```bash
uvicorn app.main:app --reload
```

- `--reload` автоматически перезапускает сервер после изменения Python-файлов;
- этот режим используется только в разработке.

Открыть в браузере:

```text
http://127.0.0.1:8000/login
```

Swagger / OpenAPI:

```text
http://127.0.0.1:8000/docs
```

---

## Создание пользователей

### Создать администратора локально

```bash
python -m scripts.create_admin --login admin
```

Скрипт интерактивно запросит пароль.

### Создать администратора в Docker

```bash
sudo docker compose exec -it app \
  python -m scripts.create_admin --login admin2
```

### Создать студента локально

```bash
python -m scripts.create_student
```

Если скрипт поддерживает аргументы, используйте:

```bash
python -m scripts.create_student --login student1
```

### Создать студента через HTTP API

```bash
curl -i \
  -X POST http://127.0.0.1:8000/add_user \
  -H "Content-Type: application/json" \
  -d '{
    "login": "student1",
    "password": "strong_student_password"
  }'
```

При успехе endpoint возвращает `201 Created` и создаёт пользователя с ролью `STUDENT`.

> `POST /add_user` публичный в текущей реализации. Перед production ограничьте создание пользователей: например, добавьте код приглашения, ограничение по сети или проверку прав администратора.

---

## API и страницы

### Авторизация

| Метод | Endpoint | Доступ | Назначение |
|---|---|---|---|
| `GET` | `/login` | Все | HTML-страница входа |
| `POST` | `/login` | Все | Проверить логин/пароль, создать cookie-сессию |
| `POST` | `/logout` | Авторизованные | Удалить текущую сессию и cookie |
| `POST` | `/add_user` | Все | Создать пользователя с ролью `student` |

#### `POST /add_user`

Request body:

```json
{
  "login": "student1",
  "password": "strong_student_password"
}
```

Success response: `201 Created`.

```json
{
  "id": 2,
  "login": "student1",
  "role": "student",
  "created_at": "2026-08-24T15:00:00",
  "updated_at": "2026-08-24T15:00:00"
}
```

Ошибки:

| Код | Причина |
|---:|---|
| `409` | Логин уже существует |
| `422` | Некорректные `login` или `password` |

### Видео

| Метод | Endpoint | Доступ | Назначение |
|---|---|---|---|
| `GET` | `/` | Авторизованные | Каталог видео |
| `GET` | `/videos/{video_id}` | Авторизованные | Страница просмотра видео |
| `GET` | `/media/{video_id}` | Авторизованные | Защищённая раздача видеофайла |
| `POST` | `/videos/{video_id}/view` | Авторизованные | Зафиксировать просмотр после 30 секунд |

#### `POST /videos/{video_id}/view`

Request body:

```json
{
  "watched_seconds": 30
}
```

В базе создаётся запись `video_views`. Ограничение `(video_id, user_id, view_date)` гарантирует один зачёт просмотра в день для одного пользователя и конкретного видео.

### Администрирование видео

Все endpoints доступны только роли `admin`.

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/admin/videos` | Список роликов для управления |
| `GET` | `/admin/videos/new` | Страница загрузки нового видео |
| `POST` | `/admin/videos` | Загрузить файл и создать видео |
| `GET` | `/admin/videos/{video_id}/edit` | Страница редактирования |
| `POST` | `/admin/videos/{video_id}` | Изменить название и описание |
| `POST` | `/admin/videos/{video_id}/delete` | Удалить видео, связанные просмотры и файл |

`POST /admin/videos` принимает `multipart/form-data`:

```text
title=Основы FastAPI
description=Первый урок
video_file=lesson_01.mp4
```

Файл сохраняется как UUID:

```text
video/6ddaf91c807c47aa84883a4df5c840e1.mp4
```

### Статистика

Статистика доступна всем авторизованным пользователям.

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/statistics` | Общая статистика по всем видео |
| `GET` | `/statistics/videos/{video_id}` | Пользователи и просмотры конкретного видео |

### Технические endpoints

| Метод | Endpoint | Назначение |
|---|---|---|
| `GET` | `/health` | Проверка доступности приложения |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc |
| `GET` | `/openapi.json` | OpenAPI JSON |
| `GET` | `/static/{path}` | Статические файлы |

---

## Проверка PostgreSQL

Открыть `psql` в контейнере:

```bash
sudo docker compose exec postgres psql -U lectorium -d lectorium
```

Полезные SQL-команды:

```sql
-- Список таблиц
\dt

-- Пользователи
SELECT id, login, role, created_at
FROM users
ORDER BY id;

-- Видео
SELECT id, title, original_filename, size_bytes, created_at
FROM videos
ORDER BY id;

-- Просмотры
SELECT
    vv.id,
    u.login,
    v.title,
    vv.watched_seconds,
    vv.view_date,
    vv.viewed_at
FROM video_views AS vv
JOIN users AS u ON u.id = vv.user_id
JOIN videos AS v ON v.id = vv.video_id
ORDER BY vv.viewed_at DESC;

-- Выйти из psql
\q
```

---

## Полезные Docker-команды

```bash
# Запустить сервисы
sudo docker compose up -d

# Пересобрать образ и запустить сервисы
sudo docker compose up -d --build

# Остановить и удалить контейнеры/сеть, но оставить данные PostgreSQL
sudo docker compose down

# Остановить и удалить контейнеры, сеть и PostgreSQL data
sudo docker compose down -v

# Статус контейнеров
sudo docker compose ps

# Логи приложения
sudo docker compose logs -f app

# Логи PostgreSQL
sudo docker compose logs -f postgres

# Выполнить команду внутри app
sudo docker compose exec app <command>

# Перезапустить приложение
sudo docker compose restart app
```

> Поскольку PostgreSQL использует bind mount `./postgres_data`, команда `docker compose down -v` не удалит содержимое `postgres_data/`. Чтобы полностью удалить БД, остановите сервисы и удалите каталог вручную:
>
> ```bash
> sudo docker compose down
> sudo rm -rf postgres_data
> ```
>
> Это необратимо удалит все данные PostgreSQL.

---

## Production checklist

Перед публичным запуском:

- Используйте длинный уникальный `SECRET_KEY`.
- Установите `DEBUG=false`.
- Установите `COOKIE_SECURE=true`.
- Настройте Nginx/Caddy и HTTPS.
- Не публикуйте порт PostgreSQL наружу; при необходимости удалите секцию `ports` у сервиса `postgres`.
- Ограничьте или защитите `POST /add_user`.
- Добавьте CSRF-защиту на все изменяющие HTML POST-запросы.
- Настройте резервное копирование PostgreSQL и каталога `video/`.
- Установите лимиты размера запросов на reverse proxy.
- Регулярно применяйте миграции командой `alembic upgrade head`.

---

## Лицензия


