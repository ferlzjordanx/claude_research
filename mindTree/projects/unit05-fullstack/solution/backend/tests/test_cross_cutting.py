"""Frontend/backend coordination: request IDs, CORS, contract."""

from fastapi.testclient import TestClient


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    echoed = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"
    generated = client.get("/health")
    assert len(generated.headers["x-request-id"]) == 32


def test_malicious_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/health", headers={"X-Request-ID": "bad\nid with spaces"}
    )
    assert response.headers["x-request-id"] != "bad\nid with spaces"


def test_error_body_carries_request_id(client: TestClient) -> None:
    response = client.get(
        "/tickets", headers={"X-Request-ID": "trace-me-1"}
    )
    assert response.json()["request_id"] == "trace-me-1"


def test_cors_preflight_allows_spa_origin(client: TestClient) -> None:
    response = client.options(
        "/tickets",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/tickets",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_contract_matches_frontend_expectations(client: TestClient) -> None:
    """If a field the SPA relies on disappears, this fails in CI."""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    ticket = set(schemas["TicketOut"]["properties"])
    assert {
        "id",
        "title",
        "description",
        "priority",
        "status",
        "created_at",
    } <= ticket
    assert set(schemas["TicketCreate"]["properties"]) == {
        "title",
        "description",
        "priority",
    }
