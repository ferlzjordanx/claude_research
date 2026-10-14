"""Fault injection: rehearse outages before they happen for real.

Settings apply to every request (an outage). The X-Fault header
applies to one request (a demo or a test):

  error         503 before charging (nothing happened)
  throttle      429 with Retry-After: 1 (back off, then retry)
  slow          sleep before answering (client timeouts fire)
  after-charge  charge succeeds, then 500 (the response is "lost")
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from enum import StrEnum

from common.problems import DomainError

Sleep = Callable[[float], Awaitable[None]]


class FaultMode(StrEnum):
    ERROR = "error"
    THROTTLE = "throttle"
    SLOW = "slow"
    AFTER_CHARGE = "after-charge"


class InjectedOutage(DomainError):
    status_code = 503
    title = "Service unavailable (injected)"


class InjectedThrottle(DomainError):
    status_code = 429
    title = "Too many requests (injected)"


class InjectedCrash(DomainError):
    status_code = 500
    title = "Internal server error (injected)"


class FaultInjector:
    SLOW_MS = 5_000

    def __init__(
        self,
        error_rate: float = 0.0,
        latency_ms: int = 0,
        rng: Callable[[], float] = random.random,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.error_rate = error_rate
        self.latency_ms = latency_ms
        self._rng = rng
        self._sleep = sleep

    async def before_charge(self, mode: FaultMode | None) -> None:
        delay_ms = self.latency_ms
        if mode is FaultMode.SLOW:
            delay_ms = max(delay_ms, self.SLOW_MS)
        if delay_ms:
            await self._sleep(delay_ms / 1000)
        if mode is FaultMode.THROTTLE:
            raise InjectedThrottle(
                "Slow down.", headers={"Retry-After": "1"}
            )
        if mode is FaultMode.ERROR or self._rng() < self.error_rate:
            raise InjectedOutage("Payments is having a bad day.")

    def after_charge(self, mode: FaultMode | None) -> None:
        if mode is FaultMode.AFTER_CHARGE:
            raise InjectedCrash("Charged, but the response was lost.")
