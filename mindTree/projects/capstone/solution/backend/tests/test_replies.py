"""AI drafts: grounded, scoped tools, bounded loop, human approval."""

from typing import Any

from fastapi.testclient import TestClient

from app.ai.fake import FakeLLM
from tests.conftest import ClientFactory, auth, new_ticket


def draft(client: TestClient, ticket_id: object) -> dict[str, Any]:
    response = client.post(
        f"/tickets/{ticket_id}/draft", headers=auth(client, "agent")
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_draft_is_grounded_and_uses_owner_order(client: TestClient) -> None:
    ticket = new_ticket(
        client, "alice", "Express parcel late", "Order ORD-1003 is late"
    )
    out = draft(client, ticket["id"])
    assert out["stop_reason"] == "answered"
    assert out["tool_calls"] == ["search_kb", "get_order"]
    reply = out["reply"]
    assert reply["status"] == "draft"
    assert reply["ai_generated"] is True
    assert "ORD-1003 is currently delayed" in reply["body"]
    assert reply["citations"]
    assert all(c in reply["body"] for c in reply["citations"])


def test_tool_cannot_read_another_customers_order(
    client: TestClient,
) -> None:
    # ORD-1002 belongs to bob; alice's ticket must not reveal it.
    ticket = new_ticket(client, "alice", "Where is ORD-1002?")
    body = draft(client, ticket["id"])["reply"]["body"]
    assert "delivered" not in body


def test_requester_never_sees_drafts(client: TestClient) -> None:
    ticket = new_ticket(client, "alice", "Parcel late, eta?")
    draft(client, ticket["id"])
    seen = client.get(
        f"/tickets/{ticket['id']}/replies", headers=auth(client, "alice")
    ).json()
    assert seen == []


def test_only_agents_draft_and_send(client: TestClient) -> None:
    ticket = new_ticket(client, "alice", "Parcel late, eta?")
    denied = client.post(
        f"/tickets/{ticket['id']}/draft", headers=auth(client, "alice")
    )
    assert denied.status_code == 403
    reply_id = draft(client, ticket["id"])["reply"]["id"]
    denied = client.post(
        f"/replies/{reply_id}/send", headers=auth(client, "alice")
    )
    assert denied.status_code == 403


def test_human_approval_sends_edited_text_once(client: TestClient) -> None:
    ticket = new_ticket(client, "alice", "Parcel late, eta?")
    reply_id = draft(client, ticket["id"])["reply"]["id"]
    sent = client.post(
        f"/replies/{reply_id}/send",
        json={"body": "Edited by a human."},
        headers=auth(client, "agent"),
    )
    assert sent.status_code == 200
    assert sent.json()["approved_by"] == "agent"
    again = client.post(
        f"/replies/{reply_id}/send", headers=auth(client, "agent")
    )
    assert again.status_code == 409
    seen = client.get(
        f"/tickets/{ticket['id']}/replies", headers=auth(client, "alice")
    ).json()
    assert [r["body"] for r in seen] == ["Edited by a human."]


def test_runaway_agent_is_stopped(make_client: ClientFactory) -> None:
    client = make_client(FakeLLM(loop_forever=True))
    ticket = new_ticket(client, "alice", "Parcel late")
    out = draft(client, ticket["id"])
    assert out["stop_reason"] == "repeated_call"
    assert out["reply"]["citations"] == []
    assert "specialist" in out["reply"]["body"]
