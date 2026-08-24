"""Validated application settings with safe defaults."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    companion_env: str = "development"
    companion_version: str = "0.1.0"
    companion_frontend_dir: Path | None = None
    immich_url: HttpUrl | None = None
    immich_api_key: SecretStr | None = None
    immich_api_key_file: Path | None = None
    immich_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    companion_database_url: SecretStr | None = None
    database_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    companion_test_state_file: Path | None = None
    allow_destructive_actions: bool = False

    def resolve_immich_api_key(self) -> str | None:
        """Resolve a direct or file-backed API key without exposing it."""

        if self.immich_api_key is not None:
            value = self.immich_api_key.get_secret_value().strip()
            return value or None
        if self.immich_api_key_file is not None and self.immich_api_key_file.is_file():
            value = self.immich_api_key_file.read_text(encoding="utf-8").strip()
            return value or None
        return None

    @property
    def immich_configured(self) -> bool:
        """Return whether both required Immich connection values exist."""

        return self.immich_url is not None and self.resolve_immich_api_key() is not None


@lru_cache
def get_settings() -> Settings:
    """Load and cache environment-backed settings."""

    return Settings()
