from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(50), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))


class TicketRow(Base):
    __tablename__ = "tickets"
    __table_args__ = (Index("ix_tickets_owner_status", "owner", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open")
    owner: Mapped[str] = mapped_column(ForeignKey("users.username"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    # AI triage result. ai_status: pending | done | fallback
    ai_status: Mapped[str] = mapped_column(String(10), default="pending")
    ai_category: Mapped[str | None] = mapped_column(String(20))
    ai_priority: Mapped[str | None] = mapped_column(String(10))
    ai_summary: Mapped[str | None] = mapped_column(String(300))
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    ai_needs_human: Mapped[bool] = mapped_column(Boolean, default=True)


class ReplyRow(Base):
    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[str]] = mapped_column(JSON, default=list)
    # draft (AI-written, not visible to the requester) | sent
    status: Mapped[str] = mapped_column(String(10), default="draft")
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(50))
    approved_by: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )


class OrderRow(Base):
    """Read-only copy of the customer's orders (the assistant's tool)."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    customer: Mapped[str] = mapped_column(
        ForeignKey("users.username"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    eta: Mapped[str | None] = mapped_column(String(20))


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        extra = {"poolclass": StaticPool} if url == "sqlite://" else {}
        return create_engine(
            url, connect_args={"check_same_thread": False}, **extra
        )
    return create_engine(url, pool_pre_ping=True, pool_size=5)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()
