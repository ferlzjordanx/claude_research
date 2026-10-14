"""Settings loaded from environment variables (12-factor config)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    # Both are injected at build time (Dockerfile ARG -> ENV) so a
    # running pod can prove exactly which commit it was built from.
    version: str = "0.0.0-dev"
    git_sha: str = "unknown"


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
