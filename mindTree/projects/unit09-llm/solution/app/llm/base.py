"""Provider-neutral LLM port: one Protocol, one result, four errors.

The rest of the app depends on this module only. Each provider
adapter (Anthropic, OpenAI, Fake) maps its SDK's objects and
exceptions onto these types, so retries, fallbacks and tests never
see an SDK-specific class.
"""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True)
class LLMResult[R: BaseModel]:
    parsed: R  # already validated against the Pydantic schema
    usage: Usage
    model: str  # the model that actually answered
    latency_ms: float


class LLMError(Exception):
    """Base class. Carries usage when tokens were spent anyway."""

    def __init__(self, message: str, usage: Usage | None = None):
        super().__init__(message)
        self.usage = usage or Usage()


class LLMTimeout(LLMError):
    """No answer within the deadline. Transient: retry."""


class LLMRateLimited(LLMError):
    """HTTP 429. Transient: retry after `retry_after` seconds."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMInvalidOutput(LLMError):
    """The model answered, but not with a valid object. Repair once."""


class LLMUnavailable(LLMError):
    """Provider failed. 5xx/529/network are retryable; 4xx are not
    (bad key, bad model ID, bad request): retrying cannot help."""

    def __init__(self, message: str, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class LLMClient(Protocol):
    """What the service needs from any model provider."""

    @property
    def model(self) -> str: ...

    async def complete_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        max_tokens: int = 1024,
        timeout_s: float = 20.0,
    ) -> LLMResult[T]: ...
