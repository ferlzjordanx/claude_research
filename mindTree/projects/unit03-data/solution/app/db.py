"""Engine, connection pool and per-request sessions."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        kwargs: dict[str, object] = {
            "connect_args": {"check_same_thread": False}
        }
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # one shared in-memory DB
        engine = create_engine(url, echo=settings.sql_echo, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            # SQLite ignores foreign keys unless asked to enforce them.
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    # PostgreSQL: a bounded pool. pool_pre_ping discards dead
    # connections (e.g. after a DB failover) before handing them out.
    return create_engine(
        url,
        echo=settings.sql_echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_timeout=10,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit, which
    # is convenient when converting them to response models.
    return sessionmaker(engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One session per request; always closed (connection returned)."""
    session = factory()
    try:
        yield session
    finally:
        session.close()
