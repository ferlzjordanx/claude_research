"""Settings loaded from environment variables (12-factor config)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    # SecretStr hides the value in repr/logs. No default: the app must
    # not start with a missing or weak signing key.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "customers-api"
    jwt_audience: str = "customers-api-clients"
    access_token_minutes: int = Field(default=30, ge=1, le=24 * 60)
    demo_users: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
