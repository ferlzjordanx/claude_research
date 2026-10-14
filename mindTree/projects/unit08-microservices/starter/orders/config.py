"""Orders service settings (env vars with the APP_ prefix)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OrdersSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite:///./orders.db"
    payments_url: str = "http://127.0.0.1:8001"
    # Timeouts everywhere: never wait on a dependency forever.
    payments_timeout_s: float = Field(default=2.0, gt=0, le=30)
    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    retry_base_delay_s: float = Field(default=0.2, ge=0)
    retry_max_delay_s: float = Field(default=2.0, ge=0)
    # Do not sleep longer than this for a Retry-After header.
    retry_after_cap_s: float = Field(default=5.0, ge=0)
    breaker_failure_threshold: int = Field(default=5, ge=1)
    breaker_reset_timeout_s: float = Field(default=30.0, gt=0)
    # Demo worker: outbox relay + notifications consumer in-process.
    background_workers: bool = True
    worker_interval_s: float = Field(default=1.0, gt=0)
    notifications_database_url: str = "sqlite://"


@lru_cache
def get_orders_settings() -> OrdersSettings:
    return OrdersSettings()
