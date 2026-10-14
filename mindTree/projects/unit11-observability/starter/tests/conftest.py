import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.config import Settings
from app.main import create_app
from app.observability.logging import ContextFilter, JsonFormatter

FX_URL = "http://fx.test"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,  # ignore a developer's local .env
        env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        fx_base_url=FX_URL,
        fx_timeout_seconds=0.5,
        render_delay_seconds=0.0,
        otel_exporter="none",
    )


@pytest.fixture
def spans() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def app(settings: Settings, spans: InMemorySpanExporter) -> FastAPI:
    return create_app(settings, span_exporter=spans)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:  # runs the lifespan
        yield test_client


@pytest.fixture
def fx_mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=FX_URL, assert_all_called=False) as mock:
        yield mock


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(JsonFormatter())
        self.addFilter(ContextFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def json_logs(client: TestClient) -> Iterator[list[str]]:
    """Formatted JSON lines, captured after the app configured logging."""
    handler = ListHandler()
    root = logging.getLogger()
    root.addHandler(handler)
    yield handler.lines
    root.removeHandler(handler)


def parse(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines]
