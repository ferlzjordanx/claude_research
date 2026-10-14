"""Anthropic adapter: Messages API + structured outputs.

[Provider-specific] Verified against `anthropic` 1.13:
- `AsyncAnthropic(api_key=..., max_retries=...)`
- `await client.messages.parse(model=, max_tokens=, system=,
  messages=, output_format=PydanticModel, timeout=)` returns a
  `ParsedMessage` whose `.parsed_output` is the validated object
  (None on refusal / max_tokens), `.usage.input_tokens`,
  `.usage.output_tokens` and `.model`.
- The SDK turns `output_format` into
  `output_config={"format": {"type": "json_schema", ...}}`.
- System prompt is a top-level `system=` argument, not a message.
"""

import time

import anthropic
from pydantic import ValidationError

from app.llm.base import (
    LLMError,
    LLMInvalidOutput,
    LLMRateLimited,
    LLMResult,
    LLMTimeout,
    LLMUnavailable,
    T,
    Usage,
)


def _retry_after(exc: anthropic.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def map_error(exc: Exception) -> LLMError:
    """Translate SDK exceptions into the app's error types.

    Order matters: APITimeoutError is a subclass of
    APIConnectionError, and RateLimitError / OverloadedError are
    subclasses of APIStatusError.
    """
    if isinstance(exc, anthropic.APITimeoutError):
        return LLMTimeout("anthropic: request timed out")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMUnavailable("anthropic: connection error", True)
    if isinstance(exc, anthropic.RateLimitError):
        return LLMRateLimited("anthropic: 429", _retry_after(exc))
    if isinstance(exc, anthropic.APIStatusError):
        # 529 overloaded and 5xx are worth retrying; 4xx are not.
        code = exc.status_code
        return LLMUnavailable(f"anthropic: HTTP {code}", code >= 500)
    if isinstance(exc, ValidationError):
        return LLMInvalidOutput(
            f"anthropic: schema validation failed "
            f"({exc.error_count()} errors)"
        )
    return LLMUnavailable(f"anthropic: {type(exc).__name__}", False)


class AnthropicLLM:
    def __init__(
        self, client: anthropic.AsyncAnthropic, model: str
    ) -> None:
        # Typed as the real SDK client so mypy checks every call
        # below; tests inject a duck-typed stub instead.
        self._client = client
        self._model = model

    @classmethod
    def from_key(cls, api_key: str, model: str) -> "AnthropicLLM":
        # max_retries=0: the service owns the retry policy. Leaving
        # SDK retries on as well multiplies attempts (and cost).
        client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=0)
        return cls(client, model)

    @property
    def model(self) -> str:
        return self._model

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 1024,
        timeout_s: float = 20.0,
    ) -> LLMResult[T]:
        start = time.perf_counter()
        try:
            response = await self._client.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                timeout=timeout_s,
            )
        except Exception as exc:  # mapped, never swallowed
            raise map_error(exc) from exc
        latency_ms = (time.perf_counter() - start) * 1000
        usage = Usage(
            response.usage.input_tokens, response.usage.output_tokens
        )
        parsed = response.parsed_output
        if parsed is None:
            raise LLMInvalidOutput(
                f"anthropic: no parsed output "
                f"(stop_reason={response.stop_reason})",
                usage,
            )
        return LLMResult(parsed, usage, response.model, latency_ms)
