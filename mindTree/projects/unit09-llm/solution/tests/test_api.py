import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.llm import build_llm
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLM
from app.main import create_app
from app.triage import PROMPT_VERSION
from tests.conftest import valid


def client_for(
    settings: Settings, llm: FakeLLM | None = None
) -> TestClient:
    return TestClient(create_app(settings, llm=llm))


def test_triage_endpoint_returns_result_and_meta(
    settings: Settings,
) -> None:
    with client_for(settings, FakeLLM.scripted([valid()])) as client:
        response = client.post("/triage", json={"text": "Charged twice"})

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["category"] == "billing"
    meta = body["meta"]
    assert meta["prompt_version"] == PROMPT_VERSION
    assert meta["model"] == "fake-model"
    assert meta["input_tokens"] == 120
    assert meta["output_tokens"] == 40
    assert meta["cost_estimate_usd"] == 0.0
    assert meta["fallback_used"] is False


def test_default_fake_provider_works_without_keys(
    settings: Settings,
) -> None:
    with client_for(settings) as client:
        response = client.post(
            "/triage", json={"text": "Production API is down!"}
        )
        health = client.get("/health").json()

    assert response.status_code == 200
    assert response.json()["result"]["priority"] in {"high", "urgent"}
    assert health == {"status": "ok", "provider": "fake"}


def test_provider_failure_returns_200_with_fallback(
    settings: Settings,
) -> None:
    llm = FakeLLM.scripted([LLMUnavailable("401", retryable=False)])
    with client_for(settings, llm) as client:
        response = client.post("/triage", json={"text": "Hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["fallback_used"] is True
    assert body["result"]["needs_human"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": "x" * 8001},
        {"text": "ok", "priority": "urgent"},  # extra field
        {},
    ],
)
def test_invalid_input_is_rejected(
    settings: Settings, payload: dict[str, object]
) -> None:
    llm = FakeLLM()
    with client_for(settings, llm) as client:
        response = client.post("/triage", json=payload)

    assert response.status_code == 422
    assert llm.calls == []  # no tokens spent on bad input


def test_max_length_input_is_accepted(settings: Settings) -> None:
    with client_for(settings) as client:
        response = client.post("/triage", json={"text": "a" * 8000})
    assert response.status_code == 200


def test_settings_require_keys_for_real_providers() -> None:
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
        Settings(llm_provider="anthropic", _env_file=None)
    with pytest.raises(ValidationError, match="OPENAI_MODEL"):
        Settings(llm_provider="openai", openai_api_key="k", _env_file=None)


def test_build_llm_selects_provider() -> None:
    anthropic_settings = Settings(
        llm_provider="anthropic", anthropic_api_key="k", _env_file=None
    )
    openai_settings = Settings(
        llm_provider="openai",
        openai_api_key="k",
        openai_model="example-model-2026",
        _env_file=None,
    )
    assert build_llm(anthropic_settings).model == "claude-opus-5-5"
    assert build_llm(openai_settings).model == "example-model-2026"
    # SecretStr keeps the key out of repr() and logs.
    assert "k'" not in repr(anthropic_settings.anthropic_api_key)
