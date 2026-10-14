from fastapi.testclient import TestClient

from tests.conftest import sample


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_post_intake_returns_201_with_provenance(
    client: TestClient,
) -> None:
    resp = client.post(
        "/intake",
        json={"text": sample("02_web_form.txt"), "channel": "web_form"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "auto_accepted"
    assert body["fields"]["phone"]["source"] == "deterministic"
    assert body["fields"]["patient_name"]["source"] == "llm"


def test_intake_input_is_validated(client: TestClient) -> None:
    assert client.post("/intake", json={"text": ""}).status_code == 422
    resp = client.post("/intake", json={"text": "hi", "extra": 1})
    assert resp.status_code == 422


def test_review_endpoints_and_error_codes(client: TestClient) -> None:
    sid = client.post(
        "/intake", json={"text": sample("06_future_dob.txt")}
    ).json()["id"]
    queue = client.get("/review-queue").json()
    assert [s["id"] for s in queue] == [sid]

    bad = client.post(
        f"/review/{sid}/approve",
        json={"reviewer": "desk.jo", "corrections": {"phone": "123"}},
    )
    assert bad.status_code == 422
    assert "phone" in bad.json()["issues"]

    ok = client.post(
        f"/review/{sid}/approve",
        json={
            "reviewer": "desk.jo",
            "corrections": {"date_of_birth": "1962-11-02"},
        },
    )
    assert ok.status_code == 200
    again = client.post(
        f"/review/{sid}/reject",
        json={"reviewer": "desk.jo", "reason": "too late"},
    )
    assert again.status_code == 409
    assert client.get("/review-queue").json() == []
    assert client.get("/intake/999").status_code == 404


def test_audit_endpoint_lists_entries(client: TestClient) -> None:
    sid = client.post(
        "/intake", json={"text": sample("01_clean_email.txt")}
    ).json()["id"]
    audit = client.get(f"/intake/{sid}/audit").json()
    assert [(a["actor"], a["action"]) for a in audit] == [
        ("system", "auto_accept")
    ]
