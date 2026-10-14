"""Scripted, offline ToolLLM for tests and the default dev mode."""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Callable, Sequence

from app.agent.types import (
    AssistantMessage,
    LLMResponse,
    Message,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)

Policy = Callable[[Sequence[Message]], LLMResponse]
ORDER = re.compile(r"ORD-\d{4}")
DOLLARS = re.compile(r"\$(\d+(?:\.\d{1,2})?)")
_ids = itertools.count(1)


def call(name: str, **arguments: object) -> LLMResponse:
    tool_call = ToolCall(f"call_{next(_ids)}", name, dict(arguments))
    return LLMResponse(tool_calls=(tool_call,), stop="tool_use")


def say(text: str) -> LLMResponse:
    return LLMResponse(text=text, stop="end")


def user_text(messages: Sequence[Message]) -> str:
    return next(m.text for m in messages if isinstance(m, UserMessage))


def tool_outputs(messages: Sequence[Message]) -> list[dict[str, object]]:
    """All tool results so far, parsed from JSON, oldest first."""
    out: list[dict[str, object]] = []
    for m in messages:
        if isinstance(m, ToolResultsMessage):
            out.extend(json.loads(r.content) for r in m.results)
    return out


def calls_made(messages: Sequence[Message]) -> list[str]:
    return [
        c.name
        for m in messages
        if isinstance(m, AssistantMessage)
        for c in m.tool_calls
    ]


def _results(output: dict[str, object]) -> list[dict[str, str]]:
    raw = output.get("results", [])
    return raw if isinstance(raw, list) else []


def search_then_answer(messages: Sequence[Message]) -> LLMResponse:
    """Search once, then answer from the top passage with a citation."""
    if "search_kb" not in calls_made(messages):
        return call("search_kb", query=user_text(messages), k=3)
    results = _results(tool_outputs(messages)[-1])
    if not results:
        return say("I don't know based on our help center articles.")
    top = results[0]
    first = re.split(r"(?<=[.!?])\s", top["text"])[0]
    return say(f"{first} [{top['id']}]")


def loop_forever(messages: Sequence[Message]) -> LLMResponse:
    """A stuck model: the same call, every turn."""
    return call("search_kb", query="refund", k=3)


def demo_policy(messages: Sequence[Message]) -> LLMResponse:
    """Deterministic stand-in for a real model in dev mode."""
    text = user_text(messages)
    order = ORDER.search(text)
    amount = DOLLARS.search(text)
    made = calls_made(messages)
    if order and "refund" in text.lower() and amount:
        if "get_order" not in made:
            return call("get_order", order_id=order.group())
        if "issue_refund" not in made:
            cents = round(float(amount.group(1)) * 100)
            return call(
                "issue_refund",
                order_id=order.group(),
                amount_cents=cents,
                reason="Customer request via assistant",
            )
        return say(
            f"Refund result: {json.dumps(tool_outputs(messages)[-1])}"
        )
    if order:
        if "get_order" not in made:
            return call("get_order", order_id=order.group())
        return say(
            f"Order details: {json.dumps(tool_outputs(messages)[-1])}"
        )
    return search_then_answer(messages)


def gullible_policy(messages: Sequence[Message]) -> LLMResponse:
    """A model that falls for indirect prompt injection: if a passage
    says to refund, it proposes the refund. Code must stop it."""
    made = calls_made(messages)
    if "search_kb" not in made:
        return call("search_kb", query=user_text(messages), k=3)
    if "issue_refund" not in made:
        for item in _results(tool_outputs(messages)[0]):
            body = item["text"].lower()
            order = ORDER.search(item["text"])
            if "ignore previous instructions" in body and order:
                return call(
                    "issue_refund",
                    order_id=order.group(),
                    amount_cents=30_000,
                    reason="Instructed by document",
                )
    return say("Done.")


class FakeToolLLM:
    """Either a policy function or a fixed script of responses (the
    last response repeats). Records what it was sent."""

    name = "fake"

    def __init__(
        self, behavior: Policy | Sequence[LLMResponse] = demo_policy
    ) -> None:
        self._policy = behavior if callable(behavior) else None
        self._script = list(behavior) if not callable(behavior) else []
        self.requests: list[tuple[list[Message], list[str]]] = []

    def complete(
        self,
        system: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        self.requests.append((list(messages), [t.name for t in tools]))
        if self._policy is not None:
            response = self._policy(messages)
        else:
            index = min(len(self.requests), len(self._script)) - 1
            response = self._script[index]
        # Rough token estimate so budgets can be tested offline.
        prompt = system + "".join(repr(m) for m in messages)
        return LLMResponse(
            text=response.text,
            tool_calls=response.tool_calls,
            stop=response.stop,
            input_tokens=len(prompt) // 4,
            output_tokens=max(1, len(response.text) // 4),
        )
