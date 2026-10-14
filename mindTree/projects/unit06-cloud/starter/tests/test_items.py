from fastapi.testclient import TestClient


def test_create_list_and_get_item(client: TestClient) -> None:
    created = client.post(
        "/items", json={"sku": "BOLT-M6", "name": "Bolt", "quantity": 40}
    )
    assert created.status_code == 201
    item = created.json()
    assert item["sku"] == "BOLT-M6" and item["quantity"] == 40

    listed = client.get("/items").json()
    assert [i["sku"] for i in listed] == ["BOLT-M6"]
    assert client.get(f"/items/{item['id']}").json() == item


def test_missing_item_is_404(client: TestClient) -> None:
    assert client.get("/items/999").status_code == 404


def test_duplicate_sku_is_409(client: TestClient) -> None:
    body = {"sku": "NUT-M6", "name": "Nut"}
    assert client.post("/items", json=body).status_code == 201
    assert client.post("/items", json=body).status_code == 409


def test_invalid_item_is_422(client: TestClient) -> None:
    bad = {"sku": "", "name": "x", "quantity": -1}
    assert client.post("/items", json=bad).status_code == 422
