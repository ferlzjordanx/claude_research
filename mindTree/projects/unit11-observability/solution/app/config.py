"""Settings loaded from environment variables (12-factor config)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    service_name: str = "orders-api"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str = "sqlite:///./orders.db"
    seed_customers: int = Field(default=25, ge=0, le=10_000)
    fx_base_url: str = "http://127.0.0.1:9000"
    # Every outbound call needs a deadline. Never None.
    fx_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    # Simulated cost of the legacy (synchronous) report renderer.
    render_delay_seconds: float = Field(default=0.2, ge=0, le=10)
    otel_exporter: Literal["none", "console", "otlp"] = "none"
    # Head sampling: fraction of new traces to keep (1.0 = all).
    trace_sample_ratio: float = Field(default=1.0, ge=0, le=1)


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
