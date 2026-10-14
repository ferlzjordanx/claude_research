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
    # The pilot's main tuning knob. Raise it and more goes to humans;
    # lower it and more is auto-accepted. Agreed with the customer in
    # requirements.md (NFR-3), not picked by the engineer alone.
    auto_accept_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    # True: the LLM also extracts fields the regexes found, so the
    # merge step can detect disagreements. False: cheaper, fewer
    # tokens, but conflicts are never seen.
    llm_cross_check: bool = True
    # Only the fake ships here. The Anthropic/OpenAI adapters from
    # Unit 9 would add "anthropic" | "openai" (see README).
    extractor: Literal["fake"] = "fake"
    max_text_chars: int = Field(default=20_000, ge=100)


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
