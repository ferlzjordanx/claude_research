"""FakeLLM: a scripted, offline LLMClient for tests, demos and CI.

Each call consumes one script step:
- a dict or BaseModel  -> validated against the schema (valid answer)
- a str                -> treated as raw model text; invalid JSON or
                          a schema mismatch raises LLMInvalidOutput
- an LLMError instance -> raised (timeout, 429, outage ...)
- HANG                 -> never returns (tests the service deadline)
When the script is empty, `responder` answers (default: a keyword
heuristic, so the app and the eval run with no key and no network).
"""

import asyncio
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMError, LLMInvalidOutput, LLMResult, T, Usage

HANG = object()
Step = BaseModel | dict[str, object] | str | LLMError | object
Responder = Callable[[str, str], Step]


@dataclass
class FakeCall:
    system: str
    user: str
    schema: str


def _ticket_text(user: str) -> str:
    match = re.search(r"<ticket>(.*?)</ticket>", user, re.DOTALL)
    return (match.group(1) if match else user).strip()


_RULES: list[tuple[str, str]] = [
    (r"invoice|refund|charge|payment|subscription", "billing"),
    (r"password|log ?in|sign in|account|2fa|locked", "account"),
    (r"feature|would be (nice|great)|please add", "feature"),
    (r"error|bug|crash|\bdown\b|outage|slow|\bapi\b", "technical"),
]


def keyword_responder(system: str, user: str) -> Step:
    """A deterministic stand-in for a model. Not smart, on purpose:
    it exercises the pipeline, it does not measure model quality."""
    text = _ticket_text(user).lower()
    category = next(
        (cat for pattern, cat in _RULES if re.search(pattern, text)),
        "other",
    )
    if category == "feature":
        category = "feature_request"
    priority = "medium"
    if re.search(r"urgent|asap|immediately|all users", text):
        priority = "urgent"
    elif re.search(r"\b(down|outage|cannot|can't)\b", text):
        priority = "high"
    elif category == "feature_request":
        priority = "low"
    confidence = 0.4 if category == "other" else 0.85
    summary = text[:120] or "empty ticket"
    return json.dumps(
        {
            "category": category,
            "priority": priority,
            "summary": summary,
            "needs_human": False,
            "confidence": confidence,
        }
    )


@dataclass
class FakeLLM:
    script: list[Step] = field(default_factory=list)
    responder: Responder = keyword_responder
    model_name: str = "fake-model"
    usage_per_call: Usage = field(default_factory=lambda: Usage(120, 40))
    calls: list[FakeCall] = field(default_factory=list)

    @classmethod
    def scripted(cls, steps: Iterable[Step]) -> "FakeLLM":
        return cls(script=list(steps))

    @property
    def model(self) -> str:
        return self.model_name

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 1024,
        timeout_s: float = 20.0,
    ) -> LLMResult[T]:
        self.calls.append(FakeCall(system, user, schema.__name__))
        step = self.script.pop(0) if self.script else None
        if step is None:
            step = self.responder(system, user)
        if step is HANG:
            await asyncio.sleep(3600)
        if isinstance(step, LLMError):
            raise step
        usage = self.usage_per_call
        try:
            if isinstance(step, str):
                parsed = schema.model_validate_json(step)
            elif isinstance(step, BaseModel):
                parsed = schema.model_validate(step.model_dump())
            else:
                parsed = schema.model_validate(step)
        except ValidationError as exc:
            # Tokens were spent even though the answer is unusable.
            raise LLMInvalidOutput(
                f"fake: {exc.error_count()} validation errors", usage
            ) from exc
        return LLMResult(parsed, usage, self.model_name, 5.0)
