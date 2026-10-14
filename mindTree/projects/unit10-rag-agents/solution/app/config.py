"""Settings loaded from environment variables (12-factor config)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    provider: Literal["fake", "anthropic", "openai"] = "fake"
    anthropic_model: str = "claude-opus-5-5"
    # No default model name: take it from OpenAI's models page.
    openai_model: str = ""
    llm_timeout_s: float = Field(default=30.0, gt=0)
    max_output_tokens: int = Field(default=2048, ge=64)

    kb_dir: Path = ROOT / "data" / "kb"
    chunk_max_chars: int = Field(default=600, ge=100)
    chunk_overlap: int = Field(default=80, ge=0)
    # Below this best rerank score the assistant abstains.
    min_relevance: float = Field(default=0.5, ge=0, le=1)

    approval_threshold_cents: int = Field(default=5000, ge=0)
    max_refund_cents: int = Field(default=50000, ge=1)

    agent_max_turns: int = Field(default=6, ge=1, le=50)
    agent_max_tool_calls: int = Field(default=10, ge=1)
    agent_timeout_s: float = Field(default=30.0, gt=0)
    agent_max_tokens: int = Field(default=50_000, ge=1000)

    demo_tokens: str = ""

    @model_validator(mode="after")
    def _provider_needs_model(self) -> Settings:
        if self.provider == "openai" and not self.openai_model:
            raise ValueError("APP_OPENAI_MODEL is required for openai")
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
