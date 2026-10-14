"""Repositories: the only code that builds SQL for these tables."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload  # noqa: F401

from app.models import Customer, Order, OrderItem, Product  # noqa: F401


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, email: str) -> Customer:
        customer = Customer(name=name, email=email)
        self.session.add(customer)
        self.session.flush()  # INSERT now so the id is available
        return customer

    def get(self, customer_id: int) -> Customer | None:
        return self.session.get(Customer, customer_id)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_sku(self, sku: str) -> Product | None:
        return self.session.scalar(
            select(Product).where(Product.sku == sku)
        )

    def get_by_skus(self, skus: Iterable[str]) -> dict[str, Product]:
        rows = self.session.scalars(
            select(Product).where(Product.sku.in_(list(skus)))
        )
        return {p.sku: p for p in rows}


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_customer(
        self, customer_id: int, *, limit: int = 20
    ) -> Sequence[Order]:
        # TODO: select the customer's orders, newest first
        # (created_at DESC, id DESC), limited to `limit`, and eager-load
        # Order.items and OrderItem.product with selectinload so listing
        # N orders costs 3 queries, not 1 + N + N (test_repositories).
        raise NotImplementedError
