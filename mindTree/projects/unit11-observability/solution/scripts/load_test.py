"""Tiny asyncio load generator: latency percentiles and error rate.

Usage:
    python -m scripts.load_test --url http://127.0.0.1:8000/reports/export
        [--requests 200] [--concurrency 20] [--timeout 10]

Not a replacement for k6/Locust; enough to reproduce "slow under
load" and to prove a fix (compare p95 before and after).
"""

import argparse
import asyncio
import math
import time
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Summary:
    requests: int
    errors: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    wall_s: float

    @property
    def error_rate(self) -> float:
        return self.errors / self.requests if self.requests else 0.0

    def __str__(self) -> str:
        rps = self.requests / self.wall_s if self.wall_s else 0.0
        return (
            f"requests={self.requests} errors={self.errors} "
            f"error_rate={self.error_rate:.1%} rps={rps:.1f}\n"
            f"p50={self.p50_ms:.1f}ms p95={self.p95_ms:.1f}ms "
            f"p99={self.p99_ms:.1f}ms max={self.max_ms:.1f}ms"
        )


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (pct in 0..100)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def summarize(
    latencies_ms: list[float], errors: int, wall_s: float
) -> Summary:
    return Summary(
        requests=len(latencies_ms),
        errors=errors,
        p50_ms=percentile(latencies_ms, 50),
        p95_ms=percentile(latencies_ms, 95),
        p99_ms=percentile(latencies_ms, 99),
        max_ms=max(latencies_ms, default=0.0),
        wall_s=wall_s,
    )


async def run_load(
    client: httpx.AsyncClient, url: str, total: int, concurrency: int
) -> Summary:
    """Send `total` GETs, at most `concurrency` at a time."""
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    errors = 0

    async def one() -> None:
        nonlocal errors
        async with semaphore:
            start = time.perf_counter()
            try:
                response = await client.get(url)
                if response.status_code >= 500:
                    errors += 1
            except httpx.HTTPError:
                errors += 1  # timeouts and connection errors count
            latencies.append((time.perf_counter() - start) * 1000)

    started = time.perf_counter()
    async with asyncio.TaskGroup() as group:
        for _ in range(total):
            group.create_task(one())
    return summarize(latencies, errors, time.perf_counter() - started)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        summary = await run_load(
            client, args.url, args.requests, args.concurrency
        )
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
