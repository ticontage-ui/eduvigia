"""Configurações centralizadas do EduVigIA."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "EduVigIA")
    app_version: str = os.getenv("APP_VERSION", "2.0.0-F7-R1")
    environment: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://eduvigia:eduvigia@postgres:5432/eduvigia",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    mediamtx_api: str = os.getenv("MEDIAMTX_API", "http://mediamtx:9997")
    data_dir: str = os.getenv("EDUVIGIA_DATA_DIR", "/app/data")
    cors_origins: tuple[str, ...] = tuple(
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5177,http://127.0.0.1:5177",
        ).split(",")
        if item.strip()
    )


settings = Settings()
