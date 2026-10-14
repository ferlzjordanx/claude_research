"""Resilient client for the payments service.

Every call gets: a timeout, retries with exponential backoff and full
jitter (only for retryable failures), the SAME Idempotency-Key on
every attempt, and a circuit breaker that fails fast when payments is
down.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx

from orders.breaker import CircuitBreaker

log = logging.getLogger("orders.payments_client")
Sleep = Callable[[float], Awaitable[None]]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class PaymentsUnavailable(Exception):
    """Outcome unknown or not attempted: try again later."""


class CircuitOpenError(PaymentsUnavailable):
    """The breaker is open: we did not even try."""


class PaymentRejected(Exception):
    """A final 4xx answer (declined, invalid): do not retry."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_s: float = 0.2
    max_delay_s: float = 2.0
    retry_after_cap_s: float = 5.0

    def backoff(self, attempt: int, rng: Callable[[], float]) -> float:
        """Full jitter: uniform(0, min(cap, base * 2**(attempt-1)))."""
        # TODO(1a): exponential ceiling, capped at max_delay_s, times
        # rng() (a float in [0, 1)). attempt starts at 1.
        raise NotImplementedError("TODO(1a)")


def is_retryable(
    response: httpx.Response | None, error: Exception | None
) -> bool:
    """Timeouts, connection errors, 5xx and 429. Never other 4xx."""
    # TODO(1b): an error is retryable if it is an httpx.TransportError
    # (timeouts and connection errors). A response is retryable if
    # its status is in RETRYABLE_STATUS.
    raise NotImplementedError("TODO(1b)")


def retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After", "")
    try:
        return max(0.0, float(value))
    except ValueError:
        return None  # HTTP-date form not supported here


class PaymentsClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        breaker: CircuitBreaker,
        policy: RetryPolicy | None = None,
        *,
        sleep: Sleep = asyncio.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._http = http
        self.breaker = breaker
        self.policy = policy or RetryPolicy()
        self._sleep = sleep
        self._rng = rng

    async def charge(
        self,
        idempotency_key: str,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """POST /payments. Returns the payment JSON on 200/201."""
        # TODO(2): the retry loop. For attempt 1..max_attempts:
        #  - ask self.breaker.allow_request(); if False raise
        #    CircuitOpenError (fail fast, no network call)
        #  - POST /payments with the SAME Idempotency-Key header on
        #    every attempt (merge it into `headers`)
        #  - catch httpx.HTTPError as the attempt's error
        #  - status < 400: breaker.record_success(), return json
        #  - not retryable (a 4xx): record_success() (payments is
        #    healthy, it said no) and raise PaymentRejected
        #  - 429: record_success(); sleep Retry-After seconds instead
        #    of the backoff; over retry_after_cap_s -> raise
        #    PaymentsUnavailable right away
        #  - other retryable failures: breaker.record_failure()
        #  - sleep self.policy.backoff(...) with self._sleep, but not
        #    after the last attempt
        # After the loop raise PaymentsUnavailable("gave up after N
        # attempts: <last error>").
        raise NotImplementedError("TODO(2)")


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text
