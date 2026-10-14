import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "body",
    [
        {"email": "a@example.com"},  # missing name
        {"name": "", "email": "a@example.com"},  # empty name
        {"name": "A", "email": "not-an-email"},
        {"name": "A", "email": "a@example.com", "role": "admin"},  # extra
        {"name": "x" * 121, "email": "a@example.com"},
    ],
)
def test_invalid_bodies_are_422(
    client: TestClient, admin_headers: dict[str, str], body: dict
) -> None:
    response = client.post("/customers", json=body, headers=admin_headers)
    assert response.status_code == 422
    problem = response.json()
    assert problem["title"] == "Validation failed"
    assert problem["errors"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_invalid_query_params_are_422(
    client: TestClient, admin_headers: dict[str, str], query: str
) -> None:
    response = client.get(f"/customers?{query}", headers=admin_headers)
    assert response.status_code == 422


def test_non_integer_id_is_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get("/customers/abc", headers=admin_headers)
    assert response.status_code == 422


def test_patch_null_name_is_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        "/customers",
        json={"name": "A", "email": "a@example.com"},
        headers=admin_headers,
    ).json()
    response = client.patch(
        f"/customers/{created['id']}",
        json={"name": None},
        headers=admin_headers,
    )
    assert response.status_code == 422
