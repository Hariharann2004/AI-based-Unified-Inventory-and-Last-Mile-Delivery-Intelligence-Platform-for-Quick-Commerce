from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """Runtime configuration loaded from UID_* environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="UID_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=5000, ge=1, le=65535)
    cors_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    model_directory: Path = PROJECT_ROOT / "models"
    artifact_manifest: Path = PROJECT_ROOT / "artifacts" / "manifest.json"
    artifact_base_url: str | None = None
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'platform.db'}"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return tuple(origin.strip() for origin in value.split(",") if origin.strip())
        return value

    @field_validator("model_directory", mode="before")
    @classmethod
    def resolve_model_directory(cls, value):
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @field_validator("artifact_manifest", mode="before")
    @classmethod
    def resolve_artifact_manifest(cls, value):
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
