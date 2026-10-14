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
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "support-desk"
    jwt_audience: str = "support-desk-spa"
    access_token_minutes: int = 30
    database_url: str = "sqlite:///./support.db"
    # Exact origins only: "*" plus credentials is rejected by browsers
    # and would be unsafe.
    cors_origins: list[str] = ["http://localhost:5173"]
    demo_users: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
