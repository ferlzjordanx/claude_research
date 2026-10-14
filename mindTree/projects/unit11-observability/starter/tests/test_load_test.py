import httpx
from fastapi import FastAPI

from scripts.load_test import percentile, run_load, summarize


def test_percentile_nearest_rank() -> None:
    values = [float(v) for v in range(1, 101)]  # 1..100
    assert percentile(values, 50) == 50.0
    assert percentile(values, 95) == 95.0
    assert percentile(values, 99) == 99.0
    assert percentile([], 99) == 0.0


def test_summary_error_rate() -> None:
    summary = summarize([10.0, 20.0, 30.0, 40.0], errors=1, wall_s=1.0)
    assert summary.error_rate == 0.25
    assert summary.max_ms == 40.0
    assert "p95=" in str(summary)


async def test_run_load_against_the_app(app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://t") as ac,
    ):
        summary = await run_load(ac, "/reports/revenue", 20, 5)
    assert summary.requests == 20
    assert summary.errors == 0
