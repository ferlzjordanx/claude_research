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
        # TODO(3a): CLOSED -> True. HALF_OPEN -> True for exactly one
        # probe (use self._probe_in_flight), False for the rest.
        # OPEN -> False. Read the state through self.state so the
        # OPEN -> HALF_OPEN timer is applied.
        raise NotImplementedError("TODO(3a)")

    def record_success(self) -> None:
        # TODO(3b): back to CLOSED, reset the failure count and the
        # probe flag.
        raise NotImplementedError("TODO(3b)")

    def record_failure(self) -> None:
        # TODO(3c): a failed probe in HALF_OPEN trips immediately.
        # In CLOSED, count consecutive failures and trip at
        # failure_threshold. Use self._trip().
        raise NotImplementedError("TODO(3c)")

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._clock()
        self._probe_in_flight = False
