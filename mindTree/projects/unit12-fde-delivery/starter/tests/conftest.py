from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.extraction.llm import FakeExtractor
from app.fields import Field
from app.main import create_app
from app.models import Candidate
from app.repository import InMemoryRepository
from app.service import IntakeService

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
FROZEN_NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def sample(name: str) -> str:
    return (SAMPLES / name).read_text()


class StubExtractor:
    """Returns exactly the candidates a test scripts. Records calls."""

    def __init__(self, answers: Mapping[Field, Candidate]) -> None:
        self.answers = dict(answers)
        self.asked: list[list[Field]] = []

    def extract(
        self, text: str, fields: Sequence[Field]
    ) -> dict[Field, Candidate]:
        self.asked.append(list(fields))
        return {f: c for f, c in self.answers.items() if f in fields}


@pytest.fixture
def settings() -> Settings:
    return Settings(env="test", auto_accept_threshold=0.85)


@pytest.fixture
def service(settings: Settings) -> IntakeService:
    return IntakeService(
        InMemoryRepository(),
        FakeExtractor(),
        settings,
        clock=lambda: FROZEN_NOW,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings, clock=lambda: FROZEN_NOW)
    with TestClient(app) as test_client:
        yield test_client
