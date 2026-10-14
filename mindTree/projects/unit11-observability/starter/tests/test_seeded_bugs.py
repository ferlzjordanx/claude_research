"""One test per production bug from the scenario. All must pass."""

import asyncio
import time
from typing import Any

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.config import Settings
from app.main import create_app


def test_revenue_report_has_no_n_plus_one(client: TestClient) -> None:
    statements: list[str] = []

    def count(*args: Any) -> None:
        statements.append(args[2])  # (conn, cursor, statement, ...)

    engine = client.app.state.engine  # type: ignore[attr-defined]
    event.listen(engine, "before_cursor_execute", count)
    try:
        rows = client.get("/reports/revenue").json()
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert len(rows) == 25
    assert len(statements) <= 2, statements
    # Customer 23: 4 orders, 23000 + 23100 + 23200 + 23300.
    assert rows[0] == {
        "customer_id": 23,
        "name": "Customer 023",
        "order_count": 4,
        "total_cents": 92600,
    }


async def test_export_does_not_block_the_event_loop(
    settings: Settings,
) -> None:
    delay, n = 0.2, 5
    app = create_app(
        settings.model_copy(update={"render_delay_seconds": 0.2})
    )
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://t") as ac,
    ):
        start = time.perf_counter()
        results = await asyncio.gather(
            *(ac.get("/reports/export") for _ in range(n))
        )
        elapsed = time.perf_counter() - start
    assert all(r.status_code == 200 for r in results)
    assert results[0].text.startswith("customer_id,name")
    # Blocking: ~n * delay = 1.0 s. Non-blocking: ~1 x delay.
    assert elapsed < delay * n * 0.6, f"took {elapsed:.2f}s"


def test_fx_client_has_a_timeout(
    client: TestClient, settings: Settings
) -> None:
    timeout = client.app.state.fx.http.timeout  # type: ignore[attr-defined]
    assert timeout.read == settings.fx_timeout_seconds
    assert timeout.connect is not None


def test_fx_timeout_maps_to_504_problem_json(
    client: TestClient, fx_mock: respx.MockRouter
) -> None:
    fx_mock.get("/rates").mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.get("/reports/revenue-fx?currency=EUR")
    assert response.status_code == 504
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["title"] == "Gateway Timeout"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_fx_server_error_maps_to_502(
    client: TestClient, fx_mock: respx.MockRouter
) -> None:
    fx_mock.get("/rates").mock(return_value=httpx.Response(503))
    response = client.get("/reports/revenue-fx?currency=EUR")
    assert response.status_code == 502
