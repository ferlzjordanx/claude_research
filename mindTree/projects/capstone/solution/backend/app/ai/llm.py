"""Provider-neutral LLM interface + Anthropic and OpenAI adapters.

The rest of the app only sees `LLM`, `Chat`, `ToolCall` and the error
types, so switching providers (or falling back) is configuration.
See Units 9-10 for the full treatment of both SDKs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic
import openai
from pydantic import BaseModel, ValidationError


class LLMError(Exception):
    """Base class: callers decide retry vs fallback by subtype."""


class LLMTimeout(LLMError):
    pass


class LLMRateLimited(LLMError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLMInvalidOutput(LLMError):
    pass


TRANSIENT = (LLMTimeout, LLMRateLimited, LLMUnavailable)


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class Structured[T: BaseModel]:
    value: T
    usage: Usage
    model: str


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    schema: dict[str, Any]  # JSON schema of the arguments


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(slots=True)
class Turn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class Chat(Protocol):
    """One conversation; the adapter keeps provider-specific history."""

    async def step(self, tools: list[ToolSpec]) -> Turn: ...

    def add_tool_results(
        self, results: list[tuple[ToolCall, str]]
    ) -> None: ...


class LLM(Protocol):
    name: str

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> Structured[T]: ...

    def chat(self, system: str, user: str) -> Chat: ...


# ---------------------------------------------------------------- Anthropic


def _map_anthropic(exc: Exception) -> LLMError:
    if isinstance(exc, anthropic.APITimeoutError):
        return LLMTimeout(str(exc))
    if isinstance(exc, anthropic.RateLimitError):
        return LLMRateLimited(str(exc))
    if isinstance(
        exc, anthropic.APIConnectionError | anthropic.InternalServerError
    ):
        return LLMUnavailable(str(exc))
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return LLMUnavailable(str(exc))  # includes 529 overloaded
    return LLMError(str(exc))


class AnthropicLLM:
    name = "anthropic"

    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        model: str,
        max_tokens: int = 2048,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> Structured[T]:
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
        except ValidationError as exc:
            raise LLMInvalidOutput(str(exc)) from exc
        except anthropic.APIError as exc:
            raise _map_anthropic(exc) from exc
        if response.parsed_output is None:
            raise LLMInvalidOutput(f"stop_reason={response.stop_reason}")
        usage = Usage(
            response.usage.input_tokens, response.usage.output_tokens
        )
        return Structured(response.parsed_output, usage, self._model)

    def chat(self, system: str, user: str) -> Chat:
        return _AnthropicChat(self, system, user)


class _AnthropicChat:
    def __init__(self, llm: AnthropicLLM, system: str, user: str) -> None:
        self._llm = llm
        self._system = system
        self._messages: list[dict[str, Any]] = [
            {"role": "user", "content": user}
        ]

    async def step(self, tools: list[ToolSpec]) -> Turn:
        try:
            response = await self._llm._client.messages.create(
                model=self._llm._model,
                max_tokens=self._llm._max_tokens,
                system=self._system,
                messages=self._messages,  # type: ignore[arg-type]
                tools=[
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.schema,
                        "strict": True,
                    }
                    for t in tools
                ],
            )
        except anthropic.APIError as exc:
            raise _map_anthropic(exc) from exc
        # Send the assistant content back unchanged (it can include
        # thinking blocks the API expects to see again).
        self._messages.append(
            {"role": "assistant", "content": response.content}
        )
        calls = [
            ToolCall(b.id, b.name, dict(b.input))
            for b in response.content
            if b.type == "tool_use"
        ]
        text = "".join(b.text for b in response.content if b.type == "text")
        usage = Usage(
            response.usage.input_tokens, response.usage.output_tokens
        )
        return Turn(text, calls, usage)

    def add_tool_results(self, results: list[tuple[ToolCall, str]]) -> None:
        self._messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": output,
                    }
                    for call, output in results
                ],
            }
        )


# ------------------------------------------------------------------ OpenAI


def _map_openai(exc: Exception) -> LLMError:
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeout(str(exc))
    if isinstance(exc, openai.RateLimitError):
        return LLMRateLimited(str(exc))
    if isinstance(
        exc, openai.APIConnectionError | openai.InternalServerError
    ):
        return LLMUnavailable(str(exc))
    return LLMError(str(exc))


class OpenAILLM:
    name = "openai"

    def __init__(
        self,
        client: openai.AsyncOpenAI,
        model: str,
        max_output_tokens: int = 2048,
    ) -> None:
        if not model:
            raise ValueError("APP_OPENAI_MODEL must be set")
        self._client = client
        self._model = model
        self._max = max_output_tokens

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> Structured[T]:
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=system,
                input=user,
                text_format=schema,
                max_output_tokens=self._max,
            )
        except ValidationError as exc:
            raise LLMInvalidOutput(str(exc)) from exc
        except openai.APIError as exc:
            raise _map_openai(exc) from exc
        if response.output_parsed is None:
            raise LLMInvalidOutput("no parsed output (refusal?)")
        u = response.usage
        usage = Usage(u.input_tokens, u.output_tokens) if u else Usage()
        return Structured(response.output_parsed, usage, self._model)

    def chat(self, system: str, user: str) -> Chat:
        return _OpenAIChat(self, system, user)


class _OpenAIChat:
    def __init__(self, llm: OpenAILLM, system: str, user: str) -> None:
        self._llm = llm
        self._system = system
        self._items: list[Any] = [{"role": "user", "content": user}]

    async def step(self, tools: list[ToolSpec]) -> Turn:
        try:
            response = await self._llm._client.responses.create(
                model=self._llm._model,
                instructions=self._system,
                input=self._items,
                max_output_tokens=self._llm._max,
                tools=[
                    {
                        "type": "function",
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.schema,
                        "strict": True,
                    }
                    for t in tools
                ],
            )
        except openai.APIError as exc:
            raise _map_openai(exc) from exc
        # Output items (function calls, reasoning) go back as input.
        self._items += response.output
        calls = [
            ToolCall(item.call_id, item.name, json.loads(item.arguments))
            for item in response.output
            if item.type == "function_call"
        ]
        u = response.usage
        usage = Usage(u.input_tokens, u.output_tokens) if u else Usage()
        return Turn(response.output_text, calls, usage)

    def add_tool_results(self, results: list[tuple[ToolCall, str]]) -> None:
        self._items += [
            {
                "type": "function_call_output",
                "call_id": call.id,
                "output": output,
            }
            for call, output in results
        ]
