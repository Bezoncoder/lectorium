from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "Lectorium"
    debug: bool = False

    secret_key: str

    db_user: str
    db_password: str
    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str

    video_dir: Path = PROJECT_DIR / "video"

    session_cookie_name: str = "lectorium_session"
    session_ttl_days: int = 7
    cookie_secure: bool = False

    max_video_size_mb: int = 2048

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_db_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        database = quote_plus(self.db_name)

        return (
            f"postgresql+asyncpg://{user}:{password}@"
            f"{self.db_host}:{self.db_port}/{database}"
        )

    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024


settings = Settings()