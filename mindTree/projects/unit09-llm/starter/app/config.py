"""Settings loaded from environment variables (12-factor config)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# EXAMPLE prices, USD per 1M tokens: (input, output). They are here
# to show the mechanics of cost tracking, NOT as a price list. Check
# the provider's pricing page and override with APP_PRICES.
EXAMPLE_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "fake-model": (0.0, 0.0),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    # "fake" runs with no key and no network: the default.
    llm_provider: Literal["fake", "anthropic", "openai"] = "fake"

    # SecretStr hides the value in repr() and logs.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    openai_api_key: SecretStr | None = None
    # No default on purpose: pick an ID from OpenAI's models page.
    openai_model: str = ""

    llm_timeout_s: float = Field(default=20.0, gt=0, le=120)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    llm_backoff_base_s: float = Field(default=0.5, ge=0)
    max_output_tokens: int = Field(default=1024, ge=64, le=8192)
    confidence_threshold: float = Field(default=0.6, ge=0, le=1)
    prices: dict[str, tuple[float, float]] = Field(
        default_factory=lambda: dict(EXAMPLE_PRICES)
    )

    @model_validator(mode="after")
    def _provider_is_configured(self) -> "Settings":
        # Fail at startup, not on the first customer request.
        if self.llm_provider == "anthropic":
            if not _has_value(self.anthropic_api_key):
                raise ValueError("APP_ANTHROPIC_API_KEY is required")
        if self.llm_provider == "openai":
            if not _has_value(self.openai_api_key):
                raise ValueError("APP_OPENAI_API_KEY is required")
            if not self.openai_model:
                raise ValueError("APP_OPENAI_MODEL is required")
        return self

    @property
    def active_model(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        if self.llm_provider == "openai":
            return self.openai_model
        return "fake-model"


def _has_value(secret: SecretStr | None) -> bool:
    return secret is not None and bool(secret.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
