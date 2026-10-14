"""Deterministic offline LLM: default provider, tests and demos.

It behaves like a (simple) model so the whole product runs without
API keys, and it can be scripted to fail in every way a real
provider fails.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

from pydantic import BaseModel

from app.ai.llm import (
    Chat,
    LLMInvalidOutput,
    Structured,
    ToolCall,
    ToolSpec,
    Turn,
    Usage,
)
from app.schemas import Category, Priority, TriageResult

ORDER_ID = re.compile(r"\bORD-\d{3,}\b")
KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.DELIVERY: ("late", "delay", "where is", "tracking", "eta"),
    Category.BILLING: ("charged", "refund", "invoice", "payment"),
    Category.DAMAGE: ("damaged", "broken", "crushed", "leaking"),
    Category.ACCOUNT: ("password", "login", "account", "address"),
}


def heuristic_triage(text: str) -> TriageResult:
    low = text.lower()
    scores = {
        cat: sum(word in low for word in words)
        for cat, words in KEYWORDS.items()
    }
    best = max(scores, key=lambda c: scores[c])
    category = best if scores[best] else Category.OTHER
    urgent = any(w in low for w in ("urgent", "asap", "today"))
    priority = Priority.HIGH if urgent else Priority.MEDIUM
    summary = " ".join(text.split())[:120]
    confidence = 0.9 if scores[best] >= 2 else 0.7 if scores[best] else 0.4
    return TriageResult(
        category=category,
        priority=priority,
        summary=summary or "(empty)",
        confidence=confidence,
    )


class FakeLLM:
    name = "fake"

    def __init__(
        self,
        failures: list[Exception] | None = None,
        loop_forever: bool = False,
    ) -> None:
        # Exceptions raised by the next calls, in order (then succeed).
        self.failures = list(failures or [])
        self.loop_forever = loop_forever
        self.calls = 0

    def _maybe_fail(self) -> None:
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)

    async def structured[T: BaseModel](
        self, system: str, user: str, schema: type[T]
    ) -> Structured[T]:
        self._maybe_fail()
        if schema is not TriageResult:
            raise LLMInvalidOutput(f"fake cannot produce {schema}")
        value = heuristic_triage(user)
        usage = Usage(len(user) // 4 + len(system) // 4, 40)
        return Structured(cast(T, value), usage, "fake-1")

    def chat(self, system: str, user: str) -> Chat:
        return FakeChat(self, user)


class FakeChat:
    """Search the KB, look up an order if one is mentioned, answer."""

    def __init__(self, llm: FakeLLM, user: str) -> None:
        self._llm = llm
        self._user = user
        self._turn = 0
        self._results: dict[str, Any] = {}

    async def step(self, tools: list[ToolSpec]) -> Turn:
        self._llm._maybe_fail()
        self._turn += 1
        usage = Usage(200, 50)
        if self._llm.loop_forever:
            call = ToolCall(f"c{self._turn}", "search_kb", {"query": "x"})
            return Turn("", [call], usage)
        if self._turn == 1:
            calls = [
                ToolCall("c1", "search_kb", {"query": self._question()})
            ]
            order = ORDER_ID.search(self._user)
            if order:
                calls.append(
                    ToolCall("c2", "get_order", {"order_id": order[0]})
                )
            return Turn("", calls, usage)
        return Turn(self._answer(), [], usage)

    def add_tool_results(self, results: list[tuple[ToolCall, str]]) -> None:
        for call, output in results:
            self._results[call.name] = json.loads(output)

    def _question(self) -> str:
        for line in self._user.splitlines():
            if line.startswith("Ticket:"):
                return line.removeprefix("Ticket:").strip()[:200]
        return self._user[:200]

    def _answer(self) -> str:
        parts = ["Hello, thanks for contacting Acme Logistics."]
        order = self._results.get("get_order", {})
        if "status" in order:
            parts.append(
                f"Order {order['id']} is currently {order['status']}"
                + (f" with ETA {order['eta']}." if order["eta"] else ".")
            )
        hits = self._results.get("search_kb", [])
        if hits:
            top = hits[0]
            first = top["text"].split(". ")[0].rstrip(".")
            parts.append(f"{first}. [{top['id']}]")
        else:
            parts.append("I have escalated your question to a specialist.")
        return " ".join(parts)
