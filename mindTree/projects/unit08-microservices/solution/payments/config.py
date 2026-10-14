"""Payments service settings (env vars with the APP_ prefix)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PaymentsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    # Fault injection to rehearse outages. Both default to "off".
    fault_error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    fault_latency_ms: int = Field(default=0, ge=0, le=60_000)
    # Allow the X-Fault header (demos/tests). Forced off in prod.
    fault_header_enabled: bool = True
    # Pretend the card issuer declines anything above this amount.
    decline_over_cents: int = Field(default=100_000, gt=0)


@lru_cache
def get_payments_settings() -> PaymentsSettings:
    return PaymentsSettings()
