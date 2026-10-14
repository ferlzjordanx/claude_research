import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import make_engine
from app.logging_config import JsonFormatter
from app.main import create_app

# Opening a file in a directory that does not exist fails like an
# unreachable database server would.
DEAD_DB = "sqlite:////nonexistent-dir/inventory.db"


def test_live_is_ok(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_ready_checks_database(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_is_503_when_database_down(client: TestClient) -> None:
    client.app.state.engine = make_engine(DEAD_DB)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["database"] == "down"


def test_live_stays_ok_when_database_down() -> None:
    # The app must start (not crash-loop) and stay live; only
    # readiness reflects the dependency.
    settings = Settings(database_url=DEAD_DB, environment="test")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_ready_is_503_while_draining(client: TestClient) -> None:
    client.app.state.health.begin_drain()
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "draining"}
    # Liveness is unaffected: draining is not a reason to restart.
    assert client.get("/health/live").status_code == 200


def test_shutdown_marks_not_ready(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200
    # Leaving the context runs the lifespan shutdown (like SIGTERM).
    assert app.state.health.draining is True


def test_version_reports_build_metadata(client: TestClient) -> None:
    assert client.get("/version").json() == {
        "version": "9.9.9",
        "git_sha": "abc1234",
        "environment": "test",
    }


def test_settings_come_from_app_prefixed_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_GIT_SHA", "deadbee")
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.git_sha == "deadbee"
    assert settings.log_level == "DEBUG"


def test_logs_are_one_json_object_per_line() -> None:
    record = logging.LogRecord(
        "access", logging.INFO, __file__, 1, "request", None, None
    )
    record.status = 201
    line = JsonFormatter().format(record)
    data = json.loads(line)
    assert data["msg"] == "request"
    assert data["level"] == "INFO"
    assert data["status"] == 201
    assert "\n" not in line
