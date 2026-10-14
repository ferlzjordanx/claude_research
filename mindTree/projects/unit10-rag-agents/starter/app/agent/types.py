"""Provider-neutral message and tool-call types.

The agent loop only sees these. Adapters translate them to and from
each provider's wire format (Anthropic Messages, OpenAI Responses).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, object]  # JSON Schema (object)


@dataclass(frozen=True)
class ToolCall:
    id: str  # provider id: tool_use.id / function_call.call_id
    name: str
    arguments: dict[str, object]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: str  # JSON text: tool output is DATA for the model
    is_error: bool = False


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class AssistantMessage:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolResultsMessage:
    results: tuple[ToolResult, ...]


Message = UserMessage | AssistantMessage | ToolResultsMessage

# "tool_use": wants tools run; "end": final answer; the others mean
# the turn was cut short and its tool calls must NOT be executed.
LLMStop = Literal["tool_use", "end", "max_tokens", "refusal"]


@dataclass(frozen=True)
class LLMResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    stop: LLMStop = "end"
    input_tokens: int = 0
    output_tokens: int = 0
    raw_stop: str = field(default="", compare=False)


class ToolLLM(Protocol):
    """One model call. Implementations: FakeToolLLM,
    AnthropicToolLLM, OpenAIToolLLM."""

    name: str

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse: ...
