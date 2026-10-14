"""Deployment files are validated without a Docker daemon."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(
        (ROOT / "docker-compose.yml").read_text()
    )
    return data


def test_compose_runs_both_services() -> None:
    services = compose()["services"]
    assert set(services) == {"orders", "payments"}
    assert services["orders"]["ports"] == ["8000:8000"]
    assert services["payments"]["ports"] == ["8001:8001"]
    assert "payments.main:create_app" in services["payments"]["command"]
    assert "--factory" in services["orders"]["command"]


def test_orders_finds_payments_by_service_name() -> None:
    orders = compose()["services"]["orders"]
    env = orders["environment"]
    assert env["APP_PAYMENTS_URL"] == "http://payments:8001"
    assert orders["depends_on"]["payments"] == {
        "condition": "service_healthy"
    }


def test_every_service_has_a_healthcheck() -> None:
    for name, svc in compose()["services"].items():
        assert svc["healthcheck"]["test"][0] == "CMD", name


def test_dockerfile_runs_as_non_root() -> None:
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    assert lines[1].startswith("FROM python:3.12")
    assert "USER app" in lines


def test_every_file_fits_76_columns() -> None:
    skip = {
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip & set(path.parts):
            continue
        if path.suffix in {".db", ".pyc"}:
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            assert len(line) <= 76, f"{path.name}:{n}"
