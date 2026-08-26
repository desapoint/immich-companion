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
    immich_public_url: HttpUrl | None = None
    immich_api_key: SecretStr | None = None
    immich_api_key_file: Path | None = None
    immich_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    immich_retry_attempts: int = Field(default=3, ge=1, le=5)
    immich_retry_backoff_seconds: float = Field(default=0.15, ge=0, le=5)
    companion_database_url: SecretStr | None = None
    database_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    companion_test_state_file: Path | None = None
    allow_destructive_actions: bool = False
    action_max_targets: int = Field(default=5000, ge=1, le=50000)
    action_plan_ttl_seconds: int = Field(default=900, ge=30, le=86400)
    sync_batch_size: int = Field(default=250, ge=25, le=2000)
    sync_overlap_seconds: int = Field(default=300, ge=0, le=86400)
    sync_lease_seconds: int = Field(default=60, ge=15, le=900)
    sync_incremental_interval_seconds: int = Field(default=900, ge=30, le=86400)
    sync_full_interval_seconds: int = Field(default=604800, ge=300, le=604800)
    sync_max_attempts: int = Field(default=5, ge=1, le=10)
    sync_retry_backoff_seconds: float = Field(default=1.0, ge=0, le=60)

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

    @property
    def database_url(self) -> str | None:
        """Return the secret database URL for internal connection setup only."""

        if self.companion_database_url is None:
            return None
        return self.companion_database_url.get_secret_value()

    @property
    def sqlalchemy_database_url(self) -> str | None:
        """Return a SQLAlchemy psycopg URL without changing the stored secret."""

        database_url = self.database_url
        if database_url is None:
            return None
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        if database_url.startswith("postgres://"):
            return database_url.replace("postgres://", "postgresql+psycopg://", 1)
        return database_url


@lru_cache
def get_settings() -> Settings:
    """Load and cache environment-backed settings."""

    return Settings()
