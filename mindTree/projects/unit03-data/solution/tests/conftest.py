"""Tests run on in-memory SQLite by default. Set TEST_DATABASE_URL to
a PostgreSQL URL to run the same suite (plus concurrency tests) there."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app
from app.seed import seed

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")
IS_POSTGRES = TEST_DB_URL.startswith("postgresql")


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DB_URL, redis_url="")


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    engine = make_engine(settings)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    app = create_app(settings, create_schema=False)
    with TestClient(app) as test_client:
        # Share the test engine so the app sees the seeded data
        # (essential for in-memory SQLite).
        app.state.engine.dispose()
        from app.db import make_session_factory

        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        yield test_client
