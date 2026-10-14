"""Orders -> payments, wired in-process with httpx.ASGITransport."""

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from orders.db import OutboxRow
from tests.conftest import FakeClock, OrdersFactory, Recorder, scripted

ORDER = {"customer_id": "c-42", "amount_cents": 2500, "currency": "USD"}


def events(app: FastAPI) -> list[str]:
    with app.state.sessions() as session:
        rows = session.scalars(
            select(OutboxRow).order_by(OutboxRow.created_at)
        ).all()
        return [r.event_type for r in rows]


async def test_order_is_paid_and_events_recorded(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    app, client = make_orders(httpx.ASGITransport(app=payments_app))
    response = await client.post("/orders", json=ORDER)
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "paid"
    assert order["payment_id"].startswith("pay_")
    assert events(app) == ["OrderCreated", "OrderPaid"]


async def test_declined_payment_marks_order_failed(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    app, client = make_orders(httpx.ASGITransport(app=payments_app))
    response = await client.post(
        "/orders", json={**ORDER, "amount_cents": 500_000}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "payment_failed"
    assert events(app) == ["OrderCreated", "PaymentFailed"]


async def test_lost_response_retry_does_not_double_charge(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    """Regression test for 'customers were charged twice'."""
    recorder = Recorder(
        httpx.ASGITransport(app=payments_app), lose_responses=1
    )
    _, client = make_orders(recorder)
    response = await client.post("/orders", json=ORDER)
    assert response.json()["status"] == "paid"
    assert len(recorder.requests) == 2  # it really did retry
    keys = {r.headers["Idempotency-Key"] for r in recorder.requests}
    assert len(keys) == 1  # with the same key
    order_id = response.json()["id"]
    assert len(payments_app.state.ledger.list(order_id)) == 1


async def test_outage_returns_503_and_later_payment_succeeds(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    _, client = make_orders(
        httpx.ASGITransport(app=payments_app),
        breaker_failure_threshold=10,
    )
    down = await client.post(
        "/orders", json=ORDER, headers={"X-Fault": "error"}
    )
    assert down.status_code == 503
    assert down.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert "Retry-After" in down.headers
    problem = down.json()
    assert problem["order_status"] == "pending"
    order_id = problem["order_id"]

    later = await client.post(f"/orders/{order_id}/pay")
    assert later.status_code == 200
    assert later.json()["status"] == "paid"
    assert len(payments_app.state.ledger.list(order_id)) == 1
    again = await client.post(f"/orders/{order_id}/pay")
    assert again.status_code == 409  # already paid


async def test_timeouts_leave_order_pending(
    make_orders: OrdersFactory,
) -> None:
    transport, seen = scripted(httpx.ReadTimeout("payments is slow"))
    _, client = make_orders(transport)
    response = await client.post("/orders", json=ORDER)
    assert response.status_code == 503
    assert "ReadTimeout" in response.json()["detail"]
    assert len(seen) == 3
    order = await client.get(f"/orders/{response.json()['order_id']}")
    assert order.json()["status"] == "pending"


async def test_circuit_opens_fails_fast_then_recovers(
    make_orders: OrdersFactory,
    payments_app: FastAPI,
    clock: FakeClock,
) -> None:
    recorder = Recorder(httpx.ASGITransport(app=payments_app))
    _, client = make_orders(recorder)  # threshold 3, 3 attempts
    first = await client.post(
        "/orders", json=ORDER, headers={"X-Fault": "error"}
    )
    assert first.status_code == 503
    assert len(recorder.requests) == 3

    fast = await client.post("/orders", json=ORDER)
    assert fast.status_code == 503
    assert "circuit is open" in fast.json()["detail"]
    assert fast.headers["Retry-After"] == "30"
    assert len(recorder.requests) == 3  # payments was not called

    ready = await client.get("/health/ready")
    assert ready.status_code == 200  # still ready: no cascade
    assert ready.json()["payments_circuit"] == "open"

    clock.advance(30)  # reset timeout -> half-open -> one probe
    probe = await client.post(f"/orders/{fast.json()['order_id']}/pay")
    assert probe.json()["status"] == "paid"
    ready = await client.get("/health/ready")
    assert ready.json()["payments_circuit"] == "closed"


async def test_validation_and_not_found_are_problem_json(
    make_orders: OrdersFactory, payments_app: FastAPI
) -> None:
    _, client = make_orders(httpx.ASGITransport(app=payments_app))
    bad = await client.post("/orders", json={**ORDER, "amount_cents": 0})
    assert bad.status_code == 422
    missing = await client.get("/orders/999")
    assert missing.status_code == 404
    assert missing.json()["title"] == "Not found"
