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
    version: str = "0.0.0-dev"
    git_sha: str = "local"
    log_json: bool = True

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "acme-support"
    jwt_audience: str = "acme-support-spa"
    access_token_minutes: int = 30

    database_url: str = "sqlite:///./support.db"
    create_schema: bool = True  # dev/test; prod runs Alembic
    cors_origins: list[str] = ["http://localhost:5173"]
    demo_users: str = ""

    # AI layer. "fake" runs offline and deterministically (default).
    llm_provider: Literal["fake", "anthropic", "openai"] = "fake"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"
    openai_api_key: SecretStr | None = None
    openai_model: str = ""  # required when llm_provider=openai
    llm_timeout_s: float = 20.0
    llm_max_retries: int = 2
    llm_retry_base_s: float = 0.5
    agent_max_turns: int = 6
    kb_dir: str = "data/kb"


@lru_cache
def get_settings() -> Settings:
    return Settings()
