"""Integration tests: real HTTP stack, real SQL (in-memory SQLite)."""

from fastapi.testclient import TestClient

from tests.conftest import auth


def new_ticket(
    client: TestClient, user: str, title: str = "Printer jam"
) -> dict:
    response = client.post(
        "/tickets",
        json={"title": title, "priority": "high"},
        headers=auth(client, user),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_comes_from_token_not_body(client: TestClient) -> None:
    response = client.post(
        "/tickets",
        json={"title": "Hack", "owner": "bob"},
        headers=auth(client, "alice"),
    )
    assert response.status_code == 422  # extra field rejected
    ticket = new_ticket(client, "alice")
    assert ticket["owner"] == "alice"


def test_requesters_only_see_their_own_tickets(client: TestClient) -> None:
    new_ticket(client, "alice", "Alice ticket")
    bobs = new_ticket(client, "bob", "Bob ticket")

    alice_view = client.get(
        "/tickets", headers=auth(client, "alice")
    ).json()
    assert [t["title"] for t in alice_view["items"]] == ["Alice ticket"]

    # Object-level authorization: guessing an ID does not work (404).
    peek = client.get(
        f"/tickets/{bobs['id']}", headers=auth(client, "alice")
    )
    assert peek.status_code == 404

    agent_view = client.get(
        "/tickets", headers=auth(client, "agent")
    ).json()
    assert agent_view["total"] == 2


def test_only_agents_change_status(client: TestClient) -> None:
    ticket = new_ticket(client, "alice")
    path = f"/tickets/{ticket['id']}"
    denied = client.patch(
        path, json={"status": "closed"}, headers=auth(client, "alice")
    )
    assert denied.status_code == 403
    assert denied.json()["title"] == "Forbidden"
    ok = client.patch(
        path, json={"status": "closed"}, headers=auth(client, "agent")
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "closed"


def test_filter_by_status(client: TestClient) -> None:
    first = new_ticket(client, "alice", "One")
    new_ticket(client, "alice", "Two")
    client.patch(
        f"/tickets/{first['id']}",
        json={"status": "in_progress"},
        headers=auth(client, "agent"),
    )
    page = client.get(
        "/tickets?status=in_progress", headers=auth(client, "agent")
    ).json()
    assert [t["title"] for t in page["items"]] == ["One"]


def test_validation_errors_are_problem_details(client: TestClient) -> None:
    response = client.post(
        "/tickets", json={"title": "ab"}, headers=auth(client, "alice")
    )
    assert response.status_code == 422
    body = response.json()
    assert body["errors"][0]["loc"] == ["body", "title"]
    assert body["request_id"]


def test_me_returns_role(client: TestClient) -> None:
    me = client.get("/me", headers=auth(client, "agent")).json()
    assert me == {"username": "agent", "role": "agent"}


def test_unauthenticated_is_401_problem(client: TestClient) -> None:
    response = client.get("/tickets")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["status"] == 401
