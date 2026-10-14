"""Outbox atomicity, relay, at-least-once delivery, idempotent
consumer."""

from typing import cast

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

import orders.service
from messaging.broker import InMemoryBroker, Message
from notifications.consumer import (
    NotificationRow,
    NotificationsBase,
    NotificationsConsumer,
    consume_once,
)
from orders.db import Base, OrderRow, OutboxRow, make_engine
from orders.outbox import TOPIC, relay_once
from orders.payments_client import PaymentsClient
from orders.service import OrderCreate, OrderService
from tests.conftest import FakeClock, OrdersFactory


def orders_db() -> sessionmaker[Session]:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def notifications_db() -> sessionmaker[Session]:
    engine = make_engine("sqlite://")
    NotificationsBase.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def count(sessions: sessionmaker[Session], model: type[object]) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


class SimulatedCrash(Exception):
    pass


def offline_service(sessions: sessionmaker[Session]) -> OrderService:
    # create_pending() never calls payments, so no client is needed.
    return OrderService(sessions, cast(PaymentsClient, None))


def paid_event(event_id: str = "evt-1", order_id: int = 1) -> Message:
    return Message(event_id, "OrderPaid", 1, {"order_id": order_id})


# ---- transactional outbox ----------------------------------------------


def test_order_and_outbox_row_commit_together() -> None:
    sessions = orders_db()
    service = offline_service(sessions)
    order = service.create_pending(
        OrderCreate(customer_id="c-1", amount_cents=100)
    )
    with sessions() as session:
        row = session.scalars(select(OutboxRow)).one()
    assert row.event_type == "OrderCreated"
    assert row.aggregate_id == str(order.id)
    assert row.published_at is None


def test_failure_mid_transaction_writes_neither(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sessions = orders_db()

    def boom(*args: object, **kwargs: object) -> OutboxRow:
        raise SimulatedCrash("crash between the two writes")

    monkeypatch.setattr(orders.service, "new_outbox_event", boom)
    service = offline_service(sessions)
    with pytest.raises(SimulatedCrash):
        service.create_pending(
            OrderCreate(customer_id="c-1", amount_cents=100)
        )
    assert count(sessions, OrderRow) == 0
    assert count(sessions, OutboxRow) == 0


# ---- relay -------------------------------------------------------------


async def test_relay_publishes_in_order_and_marks_sent(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    app, client = make_orders(httpx.ASGITransport(app=payments_app))
    await client.post(
        "/orders", json={"customer_id": "c-9", "amount_cents": 700}
    )
    broker = InMemoryBroker()
    assert relay_once(app.state.sessions, broker) == 2
    deliveries = broker.receive(TOPIC)
    assert [d.message.type for d in deliveries] == [
        "OrderCreated",
        "OrderPaid",
    ]
    with app.state.sessions() as session:
        sent = session.scalars(select(OutboxRow.published_at)).all()
    assert all(ts is not None for ts in sent)
    assert relay_once(app.state.sessions, broker) == 0  # nothing left


# ---- idempotent consumer ----------------------------------------------


def test_duplicate_delivery_is_processed_once() -> None:
    sessions = notifications_db()
    broker = InMemoryBroker()
    consumer = NotificationsConsumer(sessions)
    broker.publish(TOPIC, paid_event())
    broker.publish(TOPIC, paid_event())  # relay re-published it
    assert consume_once(broker, TOPIC, consumer) == 2  # both acked
    assert count(sessions, NotificationRow) == 1  # one email
    assert broker.pending(TOPIC) == 0


def test_lost_ack_redelivers_and_consumer_dedupes(
    clock: FakeClock,
) -> None:
    sessions = notifications_db()
    broker = InMemoryBroker(visibility_timeout_s=30, clock=clock)
    consumer = NotificationsConsumer(sessions)
    broker.publish(TOPIC, paid_event())

    first = broker.receive(TOPIC)
    assert consumer.handle(first[0].message) is True
    # ... the worker crashes before broker.ack(first[0]) ...
    assert broker.receive(TOPIC) == []  # invisible while in flight
    clock.advance(30)
    again = broker.receive(TOPIC)
    assert again[0].attempt == 2  # at-least-once: delivered twice
    assert consumer.handle(again[0].message) is False  # deduped
    broker.ack(again[0])
    assert count(sessions, NotificationRow) == 1


def test_poison_message_goes_to_dead_letters() -> None:
    sessions = notifications_db()
    broker = InMemoryBroker(max_deliveries=3)
    consumer = NotificationsConsumer(sessions)
    broker.publish(TOPIC, Message("evt-v2", "OrderPaid", 2, {}))
    for _ in range(4):
        consume_once(broker, TOPIC, consumer)
    assert [m.id for m in broker.dead_letters[TOPIC]] == ["evt-v2"]
    assert broker.pending(TOPIC) == 0
    assert count(sessions, NotificationRow) == 0


async def test_end_to_end_order_to_one_receipt(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    app, client = make_orders(httpx.ASGITransport(app=payments_app))
    await client.post(
        "/orders", json={"customer_id": "c-7", "amount_cents": 300}
    )
    broker: InMemoryBroker = app.state.broker
    relay_once(app.state.sessions, broker)
    # Simulate a relay crash before commit: publish everything again.
    with app.state.sessions.begin() as session:
        for row in session.scalars(select(OutboxRow)):
            row.published_at = None
    relay_once(app.state.sessions, broker)
    consume_once(broker, TOPIC, app.state.consumer)
    stats = (await client.get("/ops/events")).json()
    assert stats == {
        "outbox_pending": 0,
        "broker_pending": 0,
        "notifications_sent": 1,
        "dead_letters": 0,
    }
