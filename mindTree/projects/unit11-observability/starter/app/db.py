"""SQLAlchemy models, engine, seed data and the session dependency."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import ForeignKey, String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # PII: stored, but never logged and never put in a metric label.
    email: Mapped[str] = mapped_column(String(200))
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"), index=True
    )
    amount_cents: Mapped[int]
    customer: Mapped[Customer] = relationship(back_populates="orders")


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        # A file DB gets one connection per thread from the pool.
        # (A single shared in-memory connection breaks under
        # concurrent requests: the load test finds that quickly.)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True, pool_size=10)


def seed(factory: sessionmaker[Session], customers: int) -> None:
    """Deterministic data: customer n has (n % 4) + 1 orders."""
    with factory.begin() as session:
        if session.get(Customer, 1) is not None:
            return
        for n in range(1, customers + 1):
            customer = Customer(
                id=n, name=f"Customer {n:03d}", email=f"c{n}@example.com"
            )
            customer.orders = [
                Order(amount_cents=1000 * n + 100 * k)
                for k in range((n % 4) + 1)
            ]
            session.add(customer)


def get_session(request: Request) -> Iterator[Session]:
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        yield session
