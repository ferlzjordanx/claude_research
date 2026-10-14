from __future__ import annotations

from sqlalchemy import String, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    quantity: Mapped[int] = mapped_column(default=0)


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        extra = {"poolclass": StaticPool} if url == "sqlite://" else {}
        return create_engine(
            url, connect_args={"check_same_thread": False}, **extra
        )
    # pre_ping drops dead pooled connections (DB failover, idle
    # timeouts in NAT gateways / RDS Proxy) before a request uses them.
    return create_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5
    )
