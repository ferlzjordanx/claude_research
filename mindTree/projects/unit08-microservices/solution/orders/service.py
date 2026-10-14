"""Order use cases: create (with outbox) and pay (via payments)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from common.problems import DomainError
from orders.db import OrderRow
from orders.outbox import new_outbox_event
from orders.payments_client import (
    CircuitOpenError,
    PaymentRejected,
    PaymentsClient,
    PaymentsUnavailable,
)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(min_length=1, max_length=64)
    amount_cents: int = Field(gt=0, le=10_000_000)
    currency: Literal["USD", "EUR"] = "USD"


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: str
    amount_cents: int
    currency: str
    status: str
    payment_id: str | None
    created_at: datetime


class OrderNotFound(DomainError):
    status_code = 404
    title = "Not found"


class OrderNotPayable(DomainError):
    status_code = 409
    title = "Order is not pending"


class PaymentsDown(DomainError):
    status_code = 503
    title = "Payments unavailable"


class OrderService:
    def __init__(
        self, sessions: sessionmaker[Session], payments: PaymentsClient
    ) -> None:
        self._sessions = sessions
        self._payments = payments

    def create_pending(self, data: OrderCreate) -> OrderRow:
        """Insert the order AND its OrderCreated event atomically."""
        with self._sessions.begin() as session:  # commit or rollback
            order = OrderRow(
                customer_id=data.customer_id,
                amount_cents=data.amount_cents,
                currency=data.currency,
                status="pending",
                payment_key=f"order-{uuid.uuid4().hex}",
            )
            session.add(order)
            session.flush()  # assigns order.id inside the transaction
            session.add(
                new_outbox_event(
                    str(order.id),
                    "OrderCreated",
                    {
                        "order_id": order.id,
                        "customer_id": order.customer_id,
                        "amount_cents": order.amount_cents,
                        "currency": order.currency,
                    },
                )
            )
        return order

    def get(self, order_id: int) -> OrderRow:
        with self._sessions() as session:
            order = session.get(OrderRow, order_id)
        if order is None:
            raise OrderNotFound(f"Order {order_id} not found.")
        return order

    async def pay(
        self, order_id: int, fault: str | None = None
    ) -> OrderRow:
        order = self.get(order_id)
        if order.status != "pending":
            raise OrderNotPayable(f"Order {order_id} is {order.status}.")
        body = {
            "order_id": order.id,
            "amount_cents": order.amount_cents,
            "currency": order.currency,
        }
        headers = {"X-Fault": fault} if fault else None
        try:
            payment = await self._payments.charge(
                order.payment_key, body, headers
            )
        except CircuitOpenError as exc:
            reset = int(self._payments.breaker.reset_timeout_s)
            raise self._down(order, str(exc), retry_after=reset) from exc
        except PaymentsUnavailable as exc:
            raise self._down(order, str(exc), retry_after=5) from exc
        except PaymentRejected as exc:
            if exc.status_code == 409:  # same key still in progress
                raise self._down(order, exc.detail, 2) from exc
            return self._finish(
                order_id,
                "payment_failed",
                None,
                "PaymentFailed",
                {"reason": exc.detail},
            )
        return self._finish(
            order_id,
            "paid",
            str(payment["payment_id"]),
            "OrderPaid",
            {"payment_id": payment["payment_id"]},
        )

    def _finish(
        self,
        order_id: int,
        status: str,
        payment_id: str | None,
        event_type: str,
        extra: dict[str, object],
    ) -> OrderRow:
        """Update status and write the event in ONE transaction."""
        with self._sessions.begin() as session:
            order = session.get_one(OrderRow, order_id)
            if order.status != "pending":  # a concurrent call won
                return order
            order.status = status
            order.payment_id = payment_id
            session.add(
                new_outbox_event(
                    str(order_id),
                    event_type,
                    {"order_id": order_id, **extra},
                )
            )
        return order

    @staticmethod
    def _down(
        order: OrderRow, reason: str, retry_after: int
    ) -> PaymentsDown:
        # The order exists and stays pending. The caller (or a
        # reconciliation job) can POST /orders/{id}/pay later with
        # the same payment key: no double charge.
        return PaymentsDown(
            f"Payment not confirmed: {reason}",
            order_id=order.id,
            order_status="pending",
            headers={"Retry-After": str(retry_after)},
        )
