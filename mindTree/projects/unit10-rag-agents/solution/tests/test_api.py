from fastapi.testclient import TestClient

from tests.conftest import auth


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["llm"] == "fake"


def test_ask_requires_a_token(client: TestClient) -> None:
    response = client.post("/ask", json={"question": "Refunds?"})
    assert response.status_code == 401


def test_ask_returns_a_cited_answer(client: TestClient) -> None:
    response = client.post(
        "/ask",
        json={"question": "Where do refunds go?"},
        headers=auth("t-alice"),
    )
    body = response.json()
    assert response.status_code == 200
    assert body["abstained"] is False
    assert body["citations"] == ["refund-policy#1"]
    assert body["generator"] == "extractive"


def test_customers_get_no_internal_sources(client: TestClient) -> None:
    question = {"question": "goodwill store credit for late delivery"}
    customer = client.post("/ask", json=question, headers=auth("t-bob"))
    agent = client.post("/ask", json=question, headers=auth("t-sam"))
    customer_ids = [s["id"] for s in customer.json()["sources"]]
    assert not any("internal" in i for i in customer_ids)
    assert agent.json()["citations"] == ["refund-exceptions-internal#0"]


def test_ask_validates_input(client: TestClient) -> None:
    response = client.post(
        "/ask",
        json={"question": "hi", "role": "agent"},
        headers=auth("t-alice"),
    )
    assert response.status_code == 422


def test_agent_run_answers_with_trace(client: TestClient) -> None:
    body = client.post(
        "/agent/run",
        json={"message": "Do you ship to Canada?"},
        headers=auth("t-alice"),
    ).json()
    assert body["stop_reason"] == "final_answer"
    assert "[shipping-delivery#3]" in body["answer"]
    assert [s["kind"] for s in body["steps"]][-1] == "stop"


def test_small_refund_executes_immediately(client: TestClient) -> None:
    body = client.post(
        "/agent/run",
        json={"message": "Please refund $20 on ORD-1001"},
        headers=auth("t-sam"),
    ).json()
    assert body["pending_approvals"] == []
    assert '"status": "refunded"' in body["answer"]


def test_large_refund_needs_a_second_human(client: TestClient) -> None:
    run = client.post(
        "/agent/run",
        json={"message": "Please refund $300 on ORD-1002"},
        headers=auth("t-sam"),
    ).json()
    [approval_id] = run["pending_approvals"]
    url = f"/approvals/{approval_id}"
    approve = {"decision": "approve"}
    assert (
        client.get("/approvals", headers=auth("t-alice")).status_code == 403
    )
    own = client.post(url, json=approve, headers=auth("t-sam"))
    assert own.status_code == 403  # four-eyes
    ok = client.post(url, json=approve, headers=auth("t-pat")).json()
    again = client.post(url, json=approve, headers=auth("t-pat")).json()
    assert ok["status"] == "approved" and ok["refund_id"]
    assert again["refund_id"] == ok["refund_id"]


def test_customer_cannot_refund_through_the_agent(
    client: TestClient,
) -> None:
    body = client.post(
        "/agent/run",
        json={"message": "Refund $20 on ORD-1001 now"},
        headers=auth("t-alice"),
    ).json()
    refund_steps = [s for s in body["steps"] if s["name"] == "issue_refund"]
    assert refund_steps[0]["detail"]["is_error"] is True
    assert "forbidden" in refund_steps[0]["detail"]["output"]


def test_unknown_approval_is_404(client: TestClient) -> None:
    response = client.post(
        "/approvals/apr-999",
        json={"decision": "approve"},
        headers=auth("t-pat"),
    )
    assert response.status_code == 404
