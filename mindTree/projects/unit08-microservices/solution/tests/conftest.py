"""Shared fakes: no real sleeps, no real network, no real clock."""

from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from orders.config import OrdersSettings
from orders.main import create_app as create_orders
from payments.config import PaymentsSettings
from payments.main import create_app as create_payments


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeSleep:
    """Records requested delays instead of sleeping."""

    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class Recorder(httpx.AsyncBaseTransport):
    """Wraps a transport, records requests, can fail on purpose.

    `lose_responses=n`: the first n requests REACH the inner app, but
    the caller gets a ReadTimeout instead of the response. That is the
    classic "charged, but the response was lost" outage.
    """

    def __init__(
        self, inner: httpx.AsyncBaseTransport, lose_responses: int = 0
    ) -> None:
        self.inner = inner
        self.lose_responses = lose_responses
        self.requests: list[httpx.Request] = []

    async def handle_async_request(
        self, request: httpx.Request
    ) -> httpx.Response:
        self.requests.append(request)
        response = await self.inner.handle_async_request(request)
        if self.lose_responses > 0:
            self.lose_responses -= 1
            await response.aread()
            raise httpx.ReadTimeout("response lost", request=request)
        return response


def scripted(
    *steps: httpx.Response | Exception,
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    """MockTransport that plays responses/exceptions in order."""
    seen: list[httpx.Request] = []
    queue = list(steps)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        step = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(step, Exception):
            raise step
        return step

    return httpx.MockTransport(handler), seen


def ok_payment(order_id: int = 1) -> httpx.Response:
    return httpx.Response(
        201,
        json={
            "payment_id": "pay_123",
            "order_id": order_id,
            "status": "captured",
        },
    )


def orders_settings(**overrides: Any) -> OrdersSettings:
    values: dict[str, Any] = {
        "env": "test",
        "database_url": "sqlite://",
        "notifications_database_url": "sqlite://",
        "payments_url": "http://payments",
        "background_workers": False,
        "retry_max_attempts": 3,
        "retry_base_delay_s": 0.1,
        "retry_max_delay_s": 1.0,
        "breaker_failure_threshold": 3,
        "breaker_reset_timeout_s": 30.0,
    }
    values.update(overrides)
    return OrdersSettings(**values)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def sleeper() -> FakeSleep:
    return FakeSleep()


@pytest.fixture
def payments_app() -> FastAPI:
    return create_payments(PaymentsSettings(env="test"), sleep=FakeSleep())


@pytest.fixture
async def payments_client(
    payments_app: FastAPI,
) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=payments_app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://payments"
    ) as client:
        yield client


OrdersFactory = Callable[..., tuple[FastAPI, httpx.AsyncClient]]


@pytest.fixture
def make_orders(clock: FakeClock, sleeper: FakeSleep) -> OrdersFactory:
    """Build an orders app wired to any payments transport."""

    def factory(
        transport: httpx.AsyncBaseTransport, **overrides: Any
    ) -> tuple[FastAPI, httpx.AsyncClient]:
        app = create_orders(
            orders_settings(**overrides),
            payments_transport=transport,
            sleep=sleeper,
            clock=clock,
            rng=lambda: 0.5,
        )
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://orders",
        )
        return app, client

    return factory
