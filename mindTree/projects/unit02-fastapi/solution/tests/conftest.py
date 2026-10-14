from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        jwt_secret="test-secret-that-is-at-least-32-characters!",
        demo_users="admin:admin-pw:admin,viewer:viewer-pw:viewer",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # The context manager runs the lifespan (startup/shutdown).
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', 'admin-pw')}"}


@pytest.fixture
def viewer_headers(client: TestClient) -> dict[str, str]:
    token = login(client, "viewer", "viewer-pw")
    return {"Authorization": f"Bearer {token}"}
