from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_customer_summary(client: TestClient) -> None:
    # Customer 3 has (3 % 4) + 1 = 4 orders: 3000+3100+3200+3300.
    body = client.get("/customers/3/summary").json()
    assert body == {
        "customer_id": 3,
        "name": "Customer 003",
        "order_count": 4,
        "total_cents": 12600,
    }


def test_unknown_customer_is_problem_json_with_request_id(
    client: TestClient,
) -> None:
    response = client.get(
        "/customers/999/summary", headers={"X-Request-ID": "req-12345678"}
    )
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["request_id"] == "req-12345678"
