"""Adapters tested two ways, both offline:

1. Duck-typed stub clients: check the exact arguments we pass and
   how we map responses and exceptions.
2. The real SDK client with an in-memory HTTP transport
   (httpx2.MockTransport, the HTTP library both SDKs use): checks
   the JSON the SDK would actually send. No network.
"""

import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import openai
import pytest
from pydantic import BaseModel, ValidationError

from app.llm.anthropic_client import AnthropicLLM
from app.llm.anthropic_client import map_error as map_anthropic
from app.llm.base import (
    LLMInvalidOutput,
    LLMRateLimited,
    LLMTimeout,
    LLMUnavailable,
    Usage,
)
from app.llm.openai_client import OpenAILLM
from app.llm.openai_client import map_error as map_openai
from app.triage import TriageResult
from tests.conftest import valid

REQ = httpx2.Request("POST", "https://api.example.test/v1")


def status_error(cls: type[Exception], code: int, **headers: str) -> Any:
    response = httpx2.Response(code, headers=headers, request=REQ)
    return cls("boom", response=response, body=None)


def validation_error() -> ValidationError:
    try:
        TriageResult.model_validate({"category": "nope"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


# ---------------------------------------------------------- Anthropic


class StubMessages:
    """Mimics `client.messages` / `client.responses`: one .parse()."""

    def __init__(self, result: Any) -> None:
        self.result = result
        self.kwargs: dict[str, Any] = {}

    async def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def anthropic_response(parsed: BaseModel | None) -> SimpleNamespace:
    return SimpleNamespace(
        parsed_output=parsed,
        usage=SimpleNamespace(input_tokens=321, output_tokens=54),
        model="claude-opus-5-5",
        stop_reason="end_turn" if parsed else "max_tokens",
    )


def anthropic_llm(result: Any) -> tuple[AnthropicLLM, StubMessages]:
    messages = StubMessages(result)
    client: Any = SimpleNamespace(messages=messages)  # duck-typed
    return AnthropicLLM(client, "claude-opus-5-5"), messages


async def test_anthropic_request_shape_and_usage() -> None:
    parsed = TriageResult.model_validate(valid())
    llm, stub = anthropic_llm(anthropic_response(parsed))

    res = await llm.complete_structured(
        system="SYS",
        user="USER",
        schema=TriageResult,
        max_tokens=500,
        timeout_s=9,
    )

    assert stub.kwargs == {
        "model": "claude-opus-5-5",
        "max_tokens": 500,
        "system": "SYS",  # top-level, not a message
        "messages": [{"role": "user", "content": "USER"}],
        "output_format": TriageResult,
        "timeout": 9,
    }
    assert res.parsed == parsed
    assert res.usage == Usage(321, 54)
    assert res.model == "claude-opus-5-5"


async def test_anthropic_missing_parsed_output_is_invalid() -> None:
    llm, _ = anthropic_llm(anthropic_response(None))
    with pytest.raises(LLMInvalidOutput) as info:
        await llm.complete_structured(
            system="s", user="u", schema=TriageResult
        )
    assert "max_tokens" in str(info.value)
    assert info.value.usage == Usage(321, 54)


@pytest.mark.parametrize(
    ("exc", "expected", "retryable"),
    [
        (anthropic.APITimeoutError(REQ), LLMTimeout, None),
        (anthropic.APIConnectionError(request=REQ), LLMUnavailable, True),
        (
            status_error(anthropic.OverloadedError, 529),
            LLMUnavailable,
            True,
        ),
        (
            status_error(anthropic.InternalServerError, 500),
            LLMUnavailable,
            True,
        ),
        (
            status_error(anthropic.AuthenticationError, 401),
            LLMUnavailable,
            False,
        ),
        (status_error(anthropic.NotFoundError, 404), LLMUnavailable, False),
        (validation_error(), LLMInvalidOutput, None),
    ],
)
async def test_anthropic_exception_mapping(
    exc: Exception, expected: type, retryable: bool | None
) -> None:
    llm, _ = anthropic_llm(exc)
    with pytest.raises(expected) as info:
        await llm.complete_structured(
            system="s", user="u", schema=TriageResult
        )
    assert info.value.__cause__ is exc  # original kept for debugging
    if retryable is not None:
        assert info.value.retryable is retryable


def test_anthropic_rate_limit_reads_retry_after() -> None:
    exc = status_error(
        anthropic.RateLimitError, 429, **{"retry-after": "7"}
    )
    mapped = map_anthropic(exc)
    assert isinstance(mapped, LLMRateLimited)
    assert mapped.retry_after == 7.0


def anthropic_reply(text: str) -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 11, "output_tokens": 7},
    }


async def test_anthropic_real_sdk_wire_format() -> None:
    sent: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.update(json.loads(request.content))
        return httpx2.Response(
            200, json=anthropic_reply(json.dumps(valid()))
        )

    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(
            transport=httpx2.MockTransport(handler)
        ),
    )
    res = await AnthropicLLM(client, "claude-opus-5-5").complete_structured(
        system="SYS", user="USER", schema=TriageResult
    )

    assert sent["system"] == "SYS"
    assert sent["messages"] == [{"role": "user", "content": "USER"}]
    fmt = sent["output_config"]["format"]
    assert fmt["type"] == "json_schema"
    assert set(fmt["schema"]["required"]) == set(TriageResult.model_fields)
    assert res.usage == Usage(11, 7)


async def test_anthropic_real_sdk_429_maps_to_rate_limited() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            429,
            headers={"retry-after": "3"},
            json={
                "type": "error",
                "error": {
                    "type": "rate_limit_error",
                    "message": "slow down",
                },
            },
        )

    client = anthropic.AsyncAnthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultAsyncHttpxClient(
            transport=httpx2.MockTransport(handler)
        ),
    )
    llm = AnthropicLLM(client, "claude-opus-5-5")
    with pytest.raises(LLMRateLimited) as info:
        await llm.complete_structured(
            system="s", user="u", schema=TriageResult
        )
    assert info.value.retry_after == 3.0


# ------------------------------------------------------------- OpenAI


def openai_response(parsed: BaseModel | None) -> SimpleNamespace:
    return SimpleNamespace(
        output_parsed=parsed,
        usage=SimpleNamespace(input_tokens=200, output_tokens=30),
        model="example-model-2026",
        status="completed" if parsed else "incomplete",
    )


def openai_llm(result: Any) -> tuple[OpenAILLM, StubMessages]:
    responses = StubMessages(result)  # same .parse() shape
    client: Any = SimpleNamespace(responses=responses)
    return OpenAILLM(client, "example-model-2026"), responses


async def test_openai_request_shape_and_usage() -> None:
    parsed = TriageResult.model_validate(valid())
    llm, stub = openai_llm(openai_response(parsed))

    res = await llm.complete_structured(
        system="SYS",
        user="USER",
        schema=TriageResult,
        max_tokens=500,
        timeout_s=9,
    )

    assert stub.kwargs == {
        "model": "example-model-2026",
        "instructions": "SYS",  # system prompt lives here
        "input": "USER",
        "text_format": TriageResult,
        "max_output_tokens": 500,
        "store": False,
        "timeout": 9,
    }
    assert res.usage == Usage(200, 30)
    assert res.model == "example-model-2026"


async def test_openai_incomplete_is_invalid() -> None:
    llm, _ = openai_llm(openai_response(None))
    with pytest.raises(LLMInvalidOutput, match="incomplete"):
        await llm.complete_structured(
            system="s", user="u", schema=TriageResult
        )


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (openai.APITimeoutError(REQ), LLMTimeout),
        (openai.APIConnectionError(request=REQ), LLMUnavailable),
        (status_error(openai.RateLimitError, 429), LLMRateLimited),
        (status_error(openai.InternalServerError, 503), LLMUnavailable),
        (status_error(openai.BadRequestError, 400), LLMUnavailable),
        (validation_error(), LLMInvalidOutput),
    ],
)
async def test_openai_exception_mapping(
    exc: Exception, expected: type
) -> None:
    llm, _ = openai_llm(exc)
    with pytest.raises(expected):
        await llm.complete_structured(
            system="s", user="u", schema=TriageResult
        )


def test_openai_retryable_flags() -> None:
    server = map_openai(status_error(openai.InternalServerError, 503))
    client = map_openai(status_error(openai.BadRequestError, 400))
    assert isinstance(server, LLMUnavailable) and server.retryable
    assert isinstance(client, LLMUnavailable) and not client.retryable


async def test_openai_real_sdk_wire_format() -> None:
    sent: dict[str, Any] = {}
    body = {
        "id": "resp_test",
        "object": "response",
        "created_at": 1,
        "model": "example-model-2026",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "annotations": [],
                        "text": json.dumps(valid()),
                    }
                ],
            }
        ],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.update(json.loads(request.content))
        return httpx2.Response(200, json=body)

    client = openai.AsyncOpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=openai.DefaultAsyncHttpxClient(
            transport=httpx2.MockTransport(handler)
        ),
    )
    res = await OpenAILLM(client, "example-model-2026").complete_structured(
        system="SYS", user="USER", schema=TriageResult
    )

    assert sent["instructions"] == "SYS"
    assert sent["input"] == "USER"
    assert sent["store"] is False
    fmt = sent["text"]["format"]
    assert fmt["type"] == "json_schema" and fmt["strict"] is True
    assert res.parsed.category == "billing"
    assert res.usage == Usage(5, 3)


def test_real_clients_construct_without_network() -> None:
    assert AnthropicLLM.from_key("k", "claude-opus-5-5").model == (
        "claude-opus-5-5"
    )
    assert OpenAILLM.from_key("k", "example-model-2026").model == (
        "example-model-2026"
    )
