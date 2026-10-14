"""Retries, backoff, timeouts and the circuit breaker."""

import httpx
import pytest

from orders.breaker import BreakerState, CircuitBreaker
from orders.payments_client import (
    CircuitOpenError,
    PaymentRejected,
    PaymentsClient,
    PaymentsUnavailable,
    RetryPolicy,
)
from tests.conftest import FakeClock, FakeSleep, ok_payment, scripted

BODY = {"order_id": 1, "amount_cents": 100, "currency": "USD"}


def make_client(
    transport: httpx.AsyncBaseTransport,
    sleeper: FakeSleep,
    breaker: CircuitBreaker | None = None,
    attempts: int = 3,
) -> PaymentsClient:
    http = httpx.AsyncClient(
        transport=transport, base_url="http://payments"
    )
    return PaymentsClient(
        http,
        breaker or CircuitBreaker(failure_threshold=100),
        RetryPolicy(attempts, base_delay_s=0.1, max_delay_s=1.0),
        sleep=sleeper,
        rng=lambda: 0.5,
    )


# ---- backoff -------------------------------------------------------


def test_full_jitter_backoff_grows_and_is_capped() -> None:
    policy = RetryPolicy(base_delay_s=0.1, max_delay_s=1.0)
    ceilings = [policy.backoff(n, lambda: 1.0) for n in range(1, 7)]
    assert ceilings == pytest.approx([0.1, 0.2, 0.4, 0.8, 1.0, 1.0])
    # Full jitter: anywhere between 0 and the ceiling.
    assert policy.backoff(3, lambda: 0.0) == 0.0
    assert policy.backoff(3, lambda: 0.25) == pytest.approx(0.1)


# ---- retries -------------------------------------------------------


async def test_retries_5xx_then_succeeds(sleeper: FakeSleep) -> None:
    transport, seen = scripted(
        httpx.Response(503), httpx.Response(502), ok_payment()
    )
    client = make_client(transport, sleeper)
    result = await client.charge("order-key-0001", BODY)
    assert result["payment_id"] == "pay_123"
    assert len(seen) == 3
    # rng=0.5 -> half of each ceiling (0.1, 0.2)
    assert sleeper.calls == pytest.approx([0.05, 0.1])


async def test_same_idempotency_key_on_every_attempt(
    sleeper: FakeSleep,
) -> None:
    transport, seen = scripted(
        httpx.ConnectError("refused"), httpx.Response(500), ok_payment()
    )
    await make_client(transport, sleeper).charge("order-key-0002", BODY)
    keys = {r.headers["Idempotency-Key"] for r in seen}
    assert keys == {"order-key-0002"}


@pytest.mark.parametrize("status", [400, 402, 404, 422])
async def test_no_retry_on_4xx(sleeper: FakeSleep, status: int) -> None:
    transport, seen = scripted(
        httpx.Response(status, json={"detail": "nope"})
    )
    with pytest.raises(PaymentRejected) as info:
        await make_client(transport, sleeper).charge("order-key-03", BODY)
    assert info.value.status_code == status
    assert len(seen) == 1 and sleeper.calls == []


async def test_429_honors_retry_after(sleeper: FakeSleep) -> None:
    transport, seen = scripted(
        httpx.Response(429, headers={"Retry-After": "2"}), ok_payment()
    )
    await make_client(transport, sleeper).charge("order-key-0004", BODY)
    assert sleeper.calls == [2.0]
    assert len(seen) == 2


async def test_retry_after_over_cap_gives_up(sleeper: FakeSleep) -> None:
    transport, seen = scripted(
        httpx.Response(429, headers={"Retry-After": "600"})
    )
    with pytest.raises(PaymentsUnavailable):
        await make_client(transport, sleeper).charge("order-key-05", BODY)
    assert len(seen) == 1 and sleeper.calls == []


async def test_timeouts_are_retried_then_reported(
    sleeper: FakeSleep,
) -> None:
    transport, seen = scripted(httpx.ReadTimeout("slow"))
    with pytest.raises(PaymentsUnavailable, match="ReadTimeout"):
        await make_client(transport, sleeper).charge("order-key-06", BODY)
    assert len(seen) == 3  # max_attempts, no more
    assert len(sleeper.calls) == 2  # no sleep after the last attempt


# ---- circuit breaker ---------------------------------------------------


def test_breaker_opens_after_threshold(clock: FakeClock) -> None:
    breaker = CircuitBreaker(3, reset_timeout_s=30, clock=clock)
    for _ in range(2):
        breaker.record_failure()
    assert breaker.state is BreakerState.CLOSED
    breaker.record_failure()
    assert breaker.state is BreakerState.OPEN
    assert breaker.allow_request() is False


def test_success_resets_consecutive_failures(clock: FakeClock) -> None:
    breaker = CircuitBreaker(3, reset_timeout_s=30, clock=clock)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state is BreakerState.CLOSED


def test_half_open_allows_one_probe_and_closes(clock: FakeClock) -> None:
    breaker = CircuitBreaker(1, reset_timeout_s=30, clock=clock)
    breaker.record_failure()
    clock.advance(29.9)
    assert breaker.state is BreakerState.OPEN
    clock.advance(0.1)
    assert breaker.state is BreakerState.HALF_OPEN
    assert breaker.allow_request() is True  # the probe
    assert breaker.allow_request() is False  # everyone else waits
    breaker.record_success()
    assert breaker.state is BreakerState.CLOSED
    assert breaker.allow_request() is True


def test_failed_probe_reopens_and_restarts_timer(clock: FakeClock) -> None:
    breaker = CircuitBreaker(1, reset_timeout_s=30, clock=clock)
    breaker.record_failure()
    clock.advance(30)
    assert breaker.allow_request() is True
    breaker.record_failure()
    assert breaker.state is BreakerState.OPEN
    clock.advance(29)
    assert breaker.state is BreakerState.OPEN


async def test_open_breaker_fails_fast_without_network(
    clock: FakeClock, sleeper: FakeSleep
) -> None:
    breaker = CircuitBreaker(2, reset_timeout_s=30, clock=clock)
    transport, seen = scripted(httpx.Response(503))
    client = make_client(transport, sleeper, breaker, attempts=5)
    with pytest.raises(CircuitOpenError):
        await client.charge("order-key-0007", BODY)
    assert len(seen) == 2  # tripped mid-retry, stopped calling
    with pytest.raises(CircuitOpenError):
        await client.charge("order-key-0008", BODY)
    assert len(seen) == 2  # not a single extra request
