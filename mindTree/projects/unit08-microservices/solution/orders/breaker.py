"""A small circuit breaker with an injectable clock.

CLOSED ──(failures >= threshold)──► OPEN
  ▲                                   │ reset_timeout elapses
  │ probe succeeds                    ▼
  └────────────────────────────── HALF_OPEN
               probe fails ──► OPEN again (timer restarts)
"""

import time
from collections.abc import Callable
from enum import StrEnum

Clock = Callable[[], float]


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout_s: float = 30.0,
        clock: Clock = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self._clock = clock
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> BreakerState:
        # OPEN turns into HALF_OPEN lazily, when someone looks.
        if (
            self._state is BreakerState.OPEN
            and self._clock() - self._opened_at >= self.reset_timeout_s
        ):
            self._state = BreakerState.HALF_OPEN
            self._probe_in_flight = False
        return self._state

    def allow_request(self) -> bool:
        """Ask before every call. False means: fail fast."""
        state = self.state
        if state is BreakerState.CLOSED:
            return True
        if state is BreakerState.HALF_OPEN and not self._probe_in_flight:
            self._probe_in_flight = True  # exactly one trial call
            return True
        return False

    def record_success(self) -> None:
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._probe_in_flight = False

    def record_failure(self) -> None:
        if self.state is BreakerState.HALF_OPEN:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()
        self._probe_in_flight = False
