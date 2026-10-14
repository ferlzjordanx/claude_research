from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.config import Settings


def test_login_returns_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/auth/token", data={"username": "admin", "password": "admin-pw"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60


def test_wrong_password_and_unknown_user_look_identical(
    client: TestClient,
) -> None:
    wrong = client.post(
        "/auth/token", data={"username": "admin", "password": "nope"}
    )
    unknown = client.post(
        "/auth/token", data={"username": "ghost", "password": "nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get("/customers").status_code == 401


def test_tampered_token_is_401(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    headers = {"Authorization": admin_headers["Authorization"] + "x"}
    assert client.get("/customers", headers=headers).status_code == 401


def test_expired_token_is_401(
    client: TestClient, settings: Settings
) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": past,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    response = client.get(
        "/customers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# TODO: test_token_for_other_audience_is_401 - sign a token whose aud
# is "some-other-api" and assert the API rejects it with 401.


def test_viewer_cannot_create(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/customers",
        json={"name": "A", "email": "a@example.com"},
        headers=viewer_headers,
    )
    assert response.status_code == 403
