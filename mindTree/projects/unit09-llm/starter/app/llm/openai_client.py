"""OpenAI adapter: Responses API + structured outputs.

[Provider-specific] Verified against `openai` 3.31:
- `AsyncOpenAI(api_key=..., max_retries=...)`
- `await client.responses.parse(model=, instructions=, input=,
  text_format=PydanticModel, max_output_tokens=, store=, timeout=)`
  returns a `ParsedResponse` whose `.output_parsed` is the validated
  object (None if incomplete or refused), `.usage.input_tokens`,
  `.usage.output_tokens` and `.model`.
- The SDK turns `text_format` into
  `text={"format": {"type": "json_schema", "strict": true, ...}}`.
- System prompt goes in `instructions=`; user text in `input=`.
"""

import time

import openai
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


def _retry_after(exc: openai.APIStatusError) -> float | None:
    value = exc.response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def map_error(exc: Exception) -> LLMError:
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeout("openai: request timed out")
    if isinstance(exc, openai.APIConnectionError):
        return LLMUnavailable("openai: connection error", True)
    if isinstance(exc, openai.RateLimitError):
        return LLMRateLimited("openai: 429", _retry_after(exc))
    if isinstance(exc, openai.APIStatusError):
        code = exc.status_code
        return LLMUnavailable(f"openai: HTTP {code}", code >= 500)
    if isinstance(exc, ValidationError):
        return LLMInvalidOutput(
            f"openai: schema validation failed ({exc.error_count()} errors)"
        )
    return LLMUnavailable(f"openai: {type(exc).__name__}", False)


class OpenAILLM:
    def __init__(self, client: openai.AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    def from_key(cls, api_key: str, model: str) -> "OpenAILLM":
        client = openai.AsyncOpenAI(api_key=api_key, max_retries=0)
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
            response = await self._client.responses.parse(
                model=self._model,
                instructions=system,
                input=user,
                text_format=schema,
                max_output_tokens=max_tokens,
                # Do not keep ticket text on the provider side
                # longer than needed (PII). Default is to store.
                store=False,
                timeout=timeout_s,
            )
        except Exception as exc:
            raise map_error(exc) from exc
        latency_ms = (time.perf_counter() - start) * 1000
        raw_usage = response.usage
        usage = (
            Usage(raw_usage.input_tokens, raw_usage.output_tokens)
            if raw_usage is not None
            else Usage()
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMInvalidOutput(
                f"openai: no parsed output (status={response.status})",
                usage,
            )
        return LLMResult(parsed, usage, response.model, latency_ms)
