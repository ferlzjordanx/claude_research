"""12-factor config: every setting comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    environment: str = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # In Kubernetes this arrives from a Secret, never a ConfigMap.
    database_url: str = "sqlite:///./inventory.db"
    # Dev/demo convenience. Production runs Alembic migrations as a
    # separate Job before the rollout instead.
    create_schema: bool = True
    version: str = "1.0.0"
    # Baked into the image at build time (Dockerfile ARG GIT_SHA).
    git_sha: str = "unknown"


@lru_cache
def get_settings() -> Settings:
    return Settings()
