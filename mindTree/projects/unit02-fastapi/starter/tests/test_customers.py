from fastapi.testclient import TestClient

Headers = dict[str, str]


def create(client: TestClient, headers: Headers, **overrides: str) -> dict:
    body = {"name": "Ada Lovelace", "email": "ada@example.com"} | overrides
    response = client.post("/customers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_201_with_location(
    client: TestClient, admin_headers: Headers
) -> None:
    response = client.post(
        "/customers",
        json={"name": "  Ada  ", "email": "ADA@Example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/customers/{body['id']}"
    assert body["name"] == "Ada"  # whitespace stripped
    assert body["email"] == "ada@example.com"  # normalised
    assert body["status"] == "active"


def test_duplicate_email_is_409_problem_json(
    client: TestClient, admin_headers: Headers
) -> None:
    create(client, admin_headers)
    response = client.post(
        "/customers",
        json={"name": "Other", "email": "ada@example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Conflict"


def test_get_and_404(
    client: TestClient, admin_headers: Headers, viewer_headers: Headers
) -> None:
    created = create(client, admin_headers)
    ok = client.get(f"/customers/{created['id']}", headers=viewer_headers)
    assert ok.status_code == 200
    missing = client.get("/customers/999", headers=viewer_headers)
    assert missing.status_code == 404
    assert missing.json()["status"] == 404


def test_list_paginates_and_filters(
    client: TestClient, admin_headers: Headers
) -> None:
    for i in range(5):
        create(
            client,
            admin_headers,
            name=f"User {i}",
            email=f"u{i}@example.com",
            company="Globex" if i % 2 else "Acme",
        )
    page = client.get(
        "/customers?limit=2&offset=1", headers=admin_headers
    ).json()
    assert page["total"] == 5
    assert [c["name"] for c in page["items"]] == ["User 1", "User 2"]
    filtered = client.get("/customers?q=globex", headers=admin_headers)
    assert filtered.json()["total"] == 2


def test_patch_updates_only_sent_fields(
    client: TestClient, admin_headers: Headers
) -> None:
    created = create(client, admin_headers, company="Acme")
    response = client.patch(
        f"/customers/{created['id']}",
        json={"status": "inactive"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "inactive"
    assert body["company"] == "Acme"
    assert body["updated_at"] >= created["updated_at"]


# TODO: test_patch_cannot_steal_another_email (expect 409)


def test_delete_then_404(
    client: TestClient, admin_headers: Headers
) -> None:
    created = create(client, admin_headers)
    path = f"/customers/{created['id']}"
    assert client.delete(path, headers=admin_headers).status_code == 204
    assert client.delete(path, headers=admin_headers).status_code == 404


def test_health_needs_no_auth(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_documents_the_contract(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert "/customers/{customer_id}" in spec["paths"]
    assert "CustomerCreate" in spec["components"]["schemas"]
