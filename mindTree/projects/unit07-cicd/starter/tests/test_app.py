import pytest
from fastapi.testclient import TestClient

from app.config import Settings


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_build_metadata(client: TestClient) -> None:
    body = client.get("/version").json()
    assert body == {
        "version": "1.4.0",
        "git_sha": "abc1234def",
        "env": "test",
    }


def test_settings_read_app_prefixed_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_GIT_SHA", "feedface")
    monkeypatch.setenv("APP_VERSION", "2.0.0")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert (settings.git_sha, settings.version) == ("feedface", "2.0.0")


def test_quote_applies_volume_discount(client: TestClient) -> None:
    response = client.get(
        "/quote", params={"unit_price": "19.99", "quantity": 12}
    )
    assert response.status_code == 200
    assert response.json() == {"total": "227.89", "currency": "USD"}


def test_quote_rejects_bad_input(client: TestClient) -> None:
    response = client.get(
        "/quote", params={"unit_price": "-1", "quantity": 0}
    )
    assert response.status_code == 422
