from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings(env="test", version="1.4.0", git_sha="abc1234def")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
