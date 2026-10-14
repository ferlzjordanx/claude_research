"""Orders service: creates orders and charges them through payments.

Run: uvicorn orders.main:create_app --factory --port 8000
"""

import asyncio
import contextlib
import logging
import random
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

from common.problems import register_error_handlers
from messaging.broker import InMemoryBroker
from notifications.consumer import (
    NotificationRow,
    NotificationsBase,
    NotificationsConsumer,
    consume_once,
)
from orders.breaker import CircuitBreaker, Clock
from orders.config import OrdersSettings, get_orders_settings
from orders.db import Base, make_engine
from orders.outbox import TOPIC, pending_count, relay_once
from orders.payments_client import PaymentsClient, RetryPolicy, Sleep
from orders.service import OrderCreate, OrderOut, OrderService

log = logging.getLogger("orders")


def create_app(
    settings: OrdersSettings | None = None,
    *,
    payments_transport: httpx.AsyncBaseTransport | None = None,
    sleep: Sleep | None = None,
    clock: Clock | None = None,
    rng: Callable[[], float] | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_orders_settings()

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    # Demo only: in production notifications is its own deployment
    # with its own database, reading from SQS/Kafka/RabbitMQ.
    n_engine = make_engine(settings.notifications_database_url)
    NotificationsBase.metadata.create_all(n_engine)
    n_sessions = sessionmaker(n_engine, expire_on_commit=False)
    broker = InMemoryBroker()
    consumer = NotificationsConsumer(n_sessions)

    breaker = CircuitBreaker(
        settings.breaker_failure_threshold,
        settings.breaker_reset_timeout_s,
        clock=clock or time.monotonic,
    )
    http = httpx.AsyncClient(
        base_url=settings.payments_url,
        timeout=httpx.Timeout(settings.payments_timeout_s),
        transport=payments_transport,
    )
    payments = PaymentsClient(
        http,
        breaker,
        RetryPolicy(
            settings.retry_max_attempts,
            settings.retry_base_delay_s,
            settings.retry_max_delay_s,
            settings.retry_after_cap_s,
        ),
        sleep=sleep or asyncio.sleep,
        rng=rng or random.random,
    )
    service = OrderService(sessions, payments)

    async def worker() -> None:
        while True:
            try:
                relay_once(sessions, broker)
                consume_once(broker, TOPIC, consumer)
            except Exception:
                log.exception("background worker iteration failed")
            await asyncio.sleep(settings.worker_interval_s)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = None
        if settings.background_workers:
            task = asyncio.create_task(worker())
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await http.aclose()

    app = FastAPI(title="Orders", version="1.0.0", lifespan=lifespan)
    register_error_handlers(app)
    app.state.sessions, app.state.broker = sessions, broker
    app.state.breaker, app.state.consumer = breaker, consumer
    app.state.n_sessions = n_sessions
    demo_faults = settings.env != "prod"

    # Route handlers are async because they await payments. The SQL
    # calls are short and sync here; under load use an async engine
    # (or run_in_threadpool) so they do not block the event loop.
    @app.post("/orders", status_code=201)
    async def create_order(
        body: OrderCreate,
        x_fault: Annotated[str | None, Header()] = None,
    ) -> OrderOut:
        order = service.create_pending(body)
        paid = await service.pay(order.id, x_fault if demo_faults else None)
        return OrderOut.model_validate(paid)

    @app.post("/orders/{order_id}/pay")
    async def retry_payment(
        order_id: int,
        x_fault: Annotated[str | None, Header()] = None,
    ) -> OrderOut:
        paid = await service.pay(order_id, x_fault if demo_faults else None)
        return OrderOut.model_validate(paid)

    @app.get("/orders/{order_id}")
    async def get_order(order_id: int) -> OrderOut:
        return OrderOut.model_validate(service.get(order_id))

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness: the process is up. No dependency checks."""
        return {"status": "ok"}

    @app.get("/health/ready", response_model=None)
    async def ready() -> dict[str, object] | JSONResponse:
        """Readiness: OUR database must work. Payments being down
        does NOT make us unready, or one outage would drain every
        orders pod too (a cascading failure)."""
        try:
            with sessions() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            log.exception("readiness: database check failed")
            return JSONResponse(
                {"status": "unready", "database": "error"}, 503
            )
        return {
            "status": "ready",
            "database": "ok",
            "payments_circuit": breaker.state.value,
            "outbox_pending": pending_count(sessions),
        }

    @app.get("/ops/events")
    async def events() -> dict[str, int]:
        """Demo view of the async side of the system."""
        with n_sessions() as session:
            sent = session.scalar(
                select(func.count()).select_from(NotificationRow)
            )
        return {
            "outbox_pending": pending_count(sessions),
            "broker_pending": broker.pending(TOPIC),
            "notifications_sent": sent or 0,
            "dead_letters": len(broker.dead_letters.get(TOPIC, [])),
        }

    return app
