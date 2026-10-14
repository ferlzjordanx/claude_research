"""Core product rules carried over from Unit 5, plus AI triage."""

from fastapi.testclient import TestClient

from app.ai.fake import FakeLLM
from app.ai.llm import LLMRateLimited, LLMTimeout
from tests.conftest import ClientFactory, auth, new_ticket


def test_requesters_only_see_their_own_tickets(client: TestClient) -> None:
    new_ticket(client, "alice", "Parcel late")
    bobs = new_ticket(client, "bob", "Invoice wrong")
    mine = client.get("/tickets", headers=auth(client, "alice")).json()
    assert [t["title"] for t in mine["items"]] == ["Parcel late"]
    peek = client.get(
        f"/tickets/{bobs['id']}", headers=auth(client, "alice")
    )
    assert peek.status_code == 404


def test_only_agents_change_status(client: TestClient) -> None:
    ticket = new_ticket(client, "alice", "Parcel late")
    path = f"/tickets/{ticket['id']}"
    body = {"status": "closed"}
    assert (
        client.patch(path, json=body, headers=auth(client, "alice"))
    ).status_code == 403
    assert (
        client.patch(path, json=body, headers=auth(client, "agent"))
    ).status_code == 200


def test_triage_is_saved_and_shown_to_agents_only(
    client: TestClient,
) -> None:
    ticket = new_ticket(
        client, "alice", "Parcel late", "Tracking shows a delay, eta?"
    )
    assert ticket["ai"] is None  # requester view hides internal AI data
    agent_view = client.get(
        f"/tickets/{ticket['id']}", headers=auth(client, "agent")
    ).json()
    assert agent_view["ai"]["status"] == "done"
    assert agent_view["ai"]["category"] == "delivery"
    assert agent_view["ai"]["needs_human"] is False


def test_llm_outage_never_blocks_ticket_creation(
    make_client: ClientFactory,
) -> None:
    llm = FakeLLM(failures=[LLMTimeout("t")] * 3)
    client = make_client(llm)
    new_ticket(client, "alice", "Parcel late")
    view = client.get("/tickets", headers=auth(client, "agent")).json()
    ai = view["items"][0]["ai"]
    assert ai == {
        "status": "fallback",
        "category": None,
        "priority": None,
        "summary": None,
        "confidence": None,
        "needs_human": True,
    }
    assert llm.calls == 3  # 1 try + 2 bounded retries, then fallback


def test_transient_error_is_retried(make_client: ClientFactory) -> None:
    llm = FakeLLM(failures=[LLMRateLimited("429")])
    client = make_client(llm)
    new_ticket(client, "alice", "Charged twice", "refund please")
    ai = client.get("/tickets", headers=auth(client, "agent")).json()[
        "items"
    ][0]["ai"]
    assert ai["status"] == "done"
    assert ai["category"] == "billing"


def test_business_rule_overrides_model(client: TestClient) -> None:
    new_ticket(
        client, "alice", "Orders I did not place", "Looks like fraud"
    )
    ai = client.get("/tickets", headers=auth(client, "agent")).json()[
        "items"
    ][0]["ai"]
    assert ai["priority"] == "high"
    assert ai["needs_human"] is True


def test_retriage_is_agent_only(make_client: ClientFactory) -> None:
    llm = FakeLLM(failures=[LLMTimeout("t")] * 3)
    client = make_client(llm)
    ticket = new_ticket(client, "alice", "Parcel late, eta?")
    path = f"/tickets/{ticket['id']}/retriage"
    assert (
        client.post(path, headers=auth(client, "alice")).status_code == 403
    )
    again = client.post(path, headers=auth(client, "agent")).json()
    assert again["ai"]["status"] == "done"
