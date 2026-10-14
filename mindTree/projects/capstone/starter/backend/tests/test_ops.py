"""Health, version, metrics, request IDs, CORS."""

from fastapi.testclient import TestClient

from tests.conftest import auth, new_ticket


def test_health_and_version(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "alive"}
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/version").json()["llm_provider"] == "fake"


def test_metrics_use_route_templates_and_count_llm_calls(
    client: TestClient,
) -> None:
    ticket = new_ticket(client, "alice", "Parcel late")
    client.get(f"/tickets/{ticket['id']}", headers=auth(client, "alice"))
    text = client.get("/metrics").text
    assert 'route="/tickets/{ticket_id}"' in text
    assert f'route="/tickets/{ticket["id"]}"' not in text
    assert 'llm_calls_total{operation="triage",outcome="ok"} 1.0' in text


def test_request_id_round_trip(client: TestClient) -> None:
    response = client.get("/tickets", headers={"X-Request-ID": "trace-1"})
    assert response.headers["x-request-id"] == "trace-1"
    assert response.json()["request_id"] == "trace-1"


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    ok = client.options(
        "/tickets",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert ok.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    bad = client.options(
        "/tickets",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in bad.headers
