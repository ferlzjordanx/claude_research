"""Pick the LLM provider from settings (APP_LLM_PROVIDER)."""

from app.config import Settings
from app.llm.base import LLMClient


def build_llm(settings: Settings) -> LLMClient:
    # Settings already validated that keys/models are present.
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_client import AnthropicLLM

        assert settings.anthropic_api_key is not None
        return AnthropicLLM.from_key(
            settings.anthropic_api_key.get_secret_value(),
            settings.anthropic_model,
        )
    if settings.llm_provider == "openai":
        from app.llm.openai_client import OpenAILLM

        assert settings.openai_api_key is not None
        return OpenAILLM.from_key(
            settings.openai_api_key.get_secret_value(),
            settings.openai_model,
        )
    from app.llm.fake import FakeLLM

    return FakeLLM()
