"""OpenAI Responses API adapter [Provider-specific].

Wire format (openai 3.31, Responses API, function calling):
  tools:    {"type": "function", "name", "description",
            "parameters", "strict": True}
  request:  input items; a prior call is echoed back as
            {"type": "function_call", "call_id", "name",
            "arguments": "<json string>"}; its result as
            {"type": "function_call_output", "call_id", "output"}
  response: response.output items of type "function_call" (with
            call_id and JSON-string arguments) or "message"
            (content parts of type "output_text")
There is no is_error flag: errors travel inside the output JSON.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from app.agent.types import (
    AssistantMessage,
    LLMResponse,
    LLMStop,
    Message,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)


def to_openai_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "strict": True,
        }
        for t in tools
    ]


def to_openai_input(messages: Sequence[Message]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m, UserMessage):
            items.append({"role": "user", "content": m.text})
        elif isinstance(m, AssistantMessage):
            if m.text:
                items.append({"role": "assistant", "content": m.text})
            items.extend(
                {
                    "type": "function_call",
                    "call_id": c.id,
                    "name": c.name,
                    "arguments": json.dumps(c.arguments),
                }
                for c in m.tool_calls
            )
        elif isinstance(m, ToolResultsMessage):
            items.extend(
                {
                    "type": "function_call_output",
                    "call_id": r.call_id,
                    "output": r.content,
                }
                for r in m.results
            )
    return items


def _parse_arguments(raw: str) -> dict[str, object]:
    """Arguments arrive as a JSON string. Bad JSON becomes an args
    dict that fails validation, so the model gets a tool error."""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"_invalid_json": raw}
    return value if isinstance(value, dict) else {"_invalid_json": raw}


def from_openai_response(response: Any) -> LLMResponse:
    texts: list[str] = []
    calls: list[ToolCall] = []
    refused = False
    for item in response.output:
        if item.type == "function_call":
            calls.append(
                ToolCall(
                    item.call_id,
                    item.name,
                    _parse_arguments(item.arguments),
                )
            )
        elif item.type == "message":
            for part in item.content:
                if part.type == "output_text":
                    texts.append(part.text)
                elif part.type == "refusal":
                    refused = True
    status = response.status or ""
    stop: LLMStop
    if refused:
        stop = "refusal"
    elif status == "incomplete":
        stop = "max_tokens"
    elif calls:
        stop = "tool_use"
    else:
        stop = "end"
    usage = response.usage
    return LLMResponse(
        text="".join(texts),
        tool_calls=tuple(calls),
        stop=stop,
        input_tokens=usage.input_tokens if usage else 0,
        output_tokens=usage.output_tokens if usage else 0,
        raw_stop=status,
    )


class OpenAIToolLLM:
    name = "openai"

    def __init__(
        self, client: Any, model: str, max_output_tokens: int = 2048
    ) -> None:
        if not model:
            raise ValueError("Set APP_OPENAI_MODEL to a model ID.")
        self.client = client  # openai.OpenAI (or a stub in tests)
        self.model = model
        self.max_output_tokens = max_output_tokens

    @classmethod
    def from_env(
        cls, model: str, max_output_tokens: int, timeout_s: float
    ) -> OpenAIToolLLM:
        import openai  # imported lazily: optional dependency

        # Reads OPENAI_API_KEY from the environment.
        client = openai.OpenAI(timeout=timeout_s, max_retries=2)
        return cls(client, model, max_output_tokens)

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "instructions": system,
            "input": to_openai_input(messages),
            "max_output_tokens": self.max_output_tokens,
        }
        if tools:
            kwargs["tools"] = to_openai_tools(tools)
        return from_openai_response(self.client.responses.create(**kwargs))
