"""Persistence boundary. Unit 3 swaps this for SQLAlchemy/PostgreSQL."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Protocol

from app.models.customer import Customer, CustomerStatus


class CustomerRepository(Protocol):
    def add(
        self, name: str, email: str, company: str | None
    ) -> Customer: ...
    def get(self, customer_id: int) -> Customer | None: ...
    def get_by_email(self, email: str) -> Customer | None: ...
    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]: ...
    def update(self, customer: Customer) -> Customer: ...
    def delete(self, customer_id: int) -> bool: ...


class InMemoryCustomerRepository:
    """Thread-safe dict store; good for tests and the first iteration."""

    def __init__(self) -> None:
        self._rows: dict[int, Customer] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def add(self, name: str, email: str, company: str | None) -> Customer:
        with self._lock:
            now = datetime.now(UTC)
            customer = Customer(
                id=self._next_id,
                name=name,
                email=email,
                company=company,
                status=CustomerStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._rows[customer.id] = customer
            self._next_id += 1
            return customer

    def get(self, customer_id: int) -> Customer | None:
        return self._rows.get(customer_id)

    def get_by_email(self, email: str) -> Customer | None:
        return next(
            (c for c in self._rows.values() if c.email == email), None
        )

    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]:
        rows = sorted(self._rows.values(), key=lambda c: c.id)
        if query:
            q = query.lower()
            rows = [
                c
                for c in rows
                if q in c.name.lower() or q in (c.company or "").lower()
            ]
        return rows[offset : offset + limit], len(rows)

    def update(self, customer: Customer) -> Customer:
        with self._lock:
            self._rows[customer.id] = customer
            return customer

    def delete(self, customer_id: int) -> bool:
        with self._lock:
            return self._rows.pop(customer_id, None) is not None
