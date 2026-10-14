"""Seed demo data: python -m app.seed"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, make_engine
from app.models import Customer, Product

PRODUCTS = [
    ("KB-01", "Mechanical keyboard", Decimal("89.00"), 25),
    ("MS-01", "Wireless mouse", Decimal("29.50"), 100),
    ("MN-27", "27-inch monitor", Decimal("249.99"), 5),
]


def seed(session: Session) -> None:
    if session.scalar(select(Product).limit(1)) is not None:
        return
    session.add_all(
        Product(sku=s, name=n, price=p, stock=q) for s, n, p, q in PRODUCTS
    )
    session.add(Customer(name="Jorge", email="jorge@example.com"))
    session.commit()


if __name__ == "__main__":
    engine = make_engine(get_settings())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
    print("seeded")
