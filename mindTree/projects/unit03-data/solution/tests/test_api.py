from fastapi.testclient import TestClient


def order(
    client: TestClient, *lines: tuple[str, int], customer_id: int = 1
):
    return client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "lines": [{"sku": s, "quantity": q} for s, q in lines],
        },
    )


def test_health_checks_database(client: TestClient) -> None:
    assert client.get("/health").json()["database"] == "up"


def test_create_customer_and_duplicate_email(client: TestClient) -> None:
    body = {"name": "Ada", "email": "Ada@Example.com"}
    first = client.post("/customers", json=body)
    assert first.status_code == 201
    assert first.json()["email"] == "ada@example.com"
    second = client.post("/customers", json=body)
    assert second.status_code == 409


def test_product_read_is_cached(client: TestClient) -> None:
    first = client.get("/products/KB-01")
    second = client.get("/products/KB-01")
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert second.json()["stock"] == 25


def test_place_order_decrements_stock_and_totals(
    client: TestClient,
) -> None:
    response = order(client, ("KB-01", 2), ("MS-01", 1))
    assert response.status_code == 201
    body = response.json()
    assert body["total"] == "207.50"  # 2*89.00 + 29.50
    assert client.get("/products/KB-01").json()["stock"] == 23


def test_duplicate_skus_in_one_order_are_merged(client: TestClient) -> None:
    response = order(client, ("MS-01", 1), ("MS-01", 2))
    assert response.status_code == 201
    assert response.json()["lines"] == [
        {"sku": "MS-01", "quantity": 3, "unit_price": "29.50"}
    ]


def test_insufficient_stock_rolls_back_everything(
    client: TestClient,
) -> None:
    # KB-01 succeeds first (sorted order), then MN-27 fails: the KB-01
    # decrement must be rolled back too.
    response = order(client, ("MN-27", 6), ("KB-01", 1))
    assert response.status_code == 409
    assert response.json()["title"] == "Insufficient stock"
    assert client.get("/products/KB-01").json()["stock"] == 25
    assert client.get("/customers/1/orders").json() == []


def test_cache_is_invalidated_after_order(client: TestClient) -> None:
    assert client.get("/products/MN-27").json()["stock"] == 5
    assert order(client, ("MN-27", 2)).status_code == 201
    after = client.get("/products/MN-27")
    assert after.headers["x-cache"] == "MISS"
    assert after.json()["stock"] == 3


def test_unknown_sku_and_customer(client: TestClient) -> None:
    assert order(client, ("NOPE", 1)).status_code == 422
    assert order(client, ("KB-01", 1), customer_id=999).status_code == 404


def test_order_validation(client: TestClient) -> None:
    assert order(client).status_code == 422  # no lines
    assert order(client, ("KB-01", 0)).status_code == 422


def test_list_orders_newest_first(client: TestClient) -> None:
    order(client, ("KB-01", 1))
    order(client, ("MS-01", 1))
    orders = client.get("/customers/1/orders").json()
    assert [o["lines"][0]["sku"] for o in orders] == ["MS-01", "KB-01"]
    assert client.get("/customers/999/orders").status_code == 404
