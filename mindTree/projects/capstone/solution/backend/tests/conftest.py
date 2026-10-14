from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.ai.fake import FakeLLM
from app.config import Settings
from app.main import create_app

USERS = "agent:agent-pw:agent,alice:alice-pw:requester,bob:bob-pw:requester"


def make_settings() -> Settings:
    return Settings(
        env="test",
        log_json=False,
        jwt_secret="test-secret-test-secret-test-secret!!",
        database_url="sqlite://",
        cors_origins=["http://localhost:5173"],
        demo_users=USERS,
        llm_retry_base_s=0,
    )


ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client() -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def factory(llm: FakeLLM | None = None) -> TestClient:
        client = TestClient(create_app(make_settings(), llm or FakeLLM()))
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: ClientFactory) -> TestClient:
    return make_client()


def auth(client: TestClient, user: str) -> dict[str, str]:
    response = client.post(
        "/auth/token", data={"username": user, "password": f"{user}-pw"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def new_ticket(
    client: TestClient, user: str, title: str, description: str = ""
) -> dict[str, object]:
    response = client.post(
        "/tickets",
        json={"title": title, "description": description},
        headers=auth(client, user),
    )
    assert response.status_code == 201, response.text
    return dict(response.json())
