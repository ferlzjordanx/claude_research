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
        ceiling = min(
            self.max_delay_s, self.base_delay_s * 2.0 ** (attempt - 1)
        )
        return rng() * ceiling


def is_retryable(
    response: httpx.Response | None, error: Exception | None
) -> bool:
    """Timeouts, connection errors, 5xx and 429. Never other 4xx."""
    if error is not None:
        return isinstance(error, httpx.TransportError)
    assert response is not None
    return response.status_code in RETRYABLE_STATUS


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
        # One key for the whole logical operation, all attempts.
        send_headers = {
            **(headers or {}),
            "Idempotency-Key": idempotency_key,
        }
        last = "no attempt made"
        for attempt in range(1, self.policy.max_attempts + 1):
            if not self.breaker.allow_request():
                raise CircuitOpenError("payments circuit is open")
            response: httpx.Response | None = None
            error: Exception | None = None
            try:
                response = await self._http.post(
                    "/payments", json=body, headers=send_headers
                )
            except httpx.HTTPError as exc:
                error = exc

            if response is not None and response.status_code < 400:
                self.breaker.record_success()
                result: dict[str, Any] = response.json()
                return result
            if not is_retryable(response, error):
                # A clear 4xx means payments is healthy and said "no".
                self.breaker.record_success()
                assert response is not None
                raise PaymentRejected(
                    response.status_code, _detail(response)
                )

            delay = self.policy.backoff(attempt, self._rng)
            if response is not None and response.status_code == 429:
                # Throttling is back-pressure from a live service, not
                # a broken one: it must not trip the breaker.
                self.breaker.record_success()
                wait = retry_after_seconds(response)
                if wait is not None:
                    if wait > self.policy.retry_after_cap_s:
                        raise PaymentsUnavailable(
                            f"asked to wait {wait}s, over our cap"
                        )
                    delay = wait
            else:
                self.breaker.record_failure()
            last = (
                f"HTTP {response.status_code}"
                if response is not None
                else type(error).__name__
            )
            log.warning(
                "payments attempt %d/%d failed (%s) key=%s",
                attempt,
                self.policy.max_attempts,
                last,
                idempotency_key,
            )
            if attempt < self.policy.max_attempts:
                await self._sleep(delay)
        raise PaymentsUnavailable(
            f"gave up after {self.policy.max_attempts} attempts: {last}"
        )


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text
