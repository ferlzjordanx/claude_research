"""Orders database: the orders service owns these tables alone."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    amount_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3))
    # pending -> paid | payment_failed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Generated once with the order and reused for every payment
    # attempt, including retries hours later.
    payment_key: Mapped[str] = mapped_column(String(64), unique=True)
    payment_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class OutboxRow(Base):
    """Events waiting to be published, written in the same
    transaction as the state change they describe."""

    __tablename__ = "outbox"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    aggregate_id: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[str] = mapped_column(Text)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        extra = {"poolclass": StaticPool} if url == "sqlite://" else {}
        return create_engine(
            url, connect_args={"check_same_thread": False}, **extra
        )
    return create_engine(url, pool_pre_ping=True)
