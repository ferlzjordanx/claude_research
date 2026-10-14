from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    database_url: str = "sqlite:///./orders.db"
    redis_url: str = ""
    cache_ttl_seconds: int = 60
    sql_echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
