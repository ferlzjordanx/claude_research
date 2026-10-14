"""Anthropic Messages API adapter [Provider-specific].

Wire format (anthropic 1.13, Messages API):
  tools:    {"name", "description", "input_schema", "strict"}
  request:  assistant content blocks {"type": "tool_use", "id",
            "name", "input"}; results go back in a USER message as
            {"type": "tool_result", "tool_use_id", "content",
            "is_error"}
  response: content blocks of type "text" / "tool_use";
            stop_reason "tool_use" | "end_turn" | "max_tokens" |
            "refusal" | ...
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.agent.types import (
    LLMResponse,
    LLMStop,
    Message,
    ToolCall,
    ToolSpec,
)

DEFAULT_MODEL = "claude-opus-5-5"
STOP_MAP: dict[str, LLMStop] = {
    "tool_use": "tool_use",
    "end_turn": "end",
    "stop_sequence": "end",
    "max_tokens": "max_tokens",
    "model_context_window_exceeded": "max_tokens",
    "refusal": "refusal",
}


def to_anthropic_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.parameters,
            "strict": True,  # schema-valid inputs (we still validate)
        }
        for t in tools
    ]


def to_anthropic_messages(
    messages: Sequence[Message],
) -> list[dict[str, Any]]:
    """TODO(8): neutral messages -> Messages API dicts.
    UserMessage -> {"role": "user", "content": text}
    AssistantMessage -> {"role": "assistant", "content": [optional
      {"type": "text", "text"}, then per call {"type": "tool_use",
      "id", "name", "input"}]}
    ToolResultsMessage -> ONE {"role": "user", "content": [
      {"type": "tool_result", "tool_use_id", "content", "is_error"}
      per result]}
    Import UserMessage, AssistantMessage and ToolResultsMessage from
    app.agent.types and use isinstance() to tell them apart."""
    raise NotImplementedError("TODO(8)")


def from_anthropic_response(message: Any) -> LLMResponse:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in message.content:
        if block.type == "text":
            texts.append(block.text)
        elif block.type == "tool_use":
            calls.append(ToolCall(block.id, block.name, dict(block.input)))
    raw = message.stop_reason or ""
    return LLMResponse(
        text="".join(texts),
        tool_calls=tuple(calls),
        stop=STOP_MAP.get(raw, "end"),
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        raw_stop=raw,
    )


class AnthropicToolLLM:
    name = "anthropic"

    def __init__(
        self,
        client: Any,  # anthropic.Anthropic (or a stub in tests)
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
    ) -> None:
        self.client = client
        self.model = model
        self.max_tokens = max_tokens

    @classmethod
    def from_env(
        cls, model: str, max_tokens: int, timeout_s: float
    ) -> AnthropicToolLLM:
        import anthropic  # imported lazily: optional dependency

        # Reads ANTHROPIC_API_KEY from the environment.
        client = anthropic.Anthropic(timeout=timeout_s, max_retries=2)
        return cls(client, model, max_tokens)

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": to_anthropic_messages(messages),
        }
        if tools:
            kwargs["tools"] = to_anthropic_tools(tools)
        return from_anthropic_response(
            self.client.messages.create(**kwargs)
        )
