from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(
        env="test",
        jwt_secret="test-secret-test-secret-test-secret!!",
        database_url="sqlite://",
        cors_origins=["http://localhost:5173"],
        demo_users=(
            "agent:agent-pw:agent,alice:alice-pw:requester,"
            "bob:bob-pw:requester"
        ),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def auth(client: TestClient, user: str) -> dict[str, str]:
    response = client.post(
        "/auth/token", data={"username": user, "password": f"{user}-pw"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
