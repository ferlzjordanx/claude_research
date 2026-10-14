"""Repositories: the only code that builds SQL for these tables."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer, Order, OrderItem, Product


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
        stmt = (
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(limit)
            # Eager-load items and their products in 2 extra queries
            # total, instead of 1 query per order (the N+1 problem).
            .options(
                selectinload(Order.items).selectinload(OrderItem.product)
            )
        )
        return self.session.scalars(stmt).all()
