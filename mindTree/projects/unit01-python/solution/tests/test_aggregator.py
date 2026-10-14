import asyncio
from decimal import Decimal

import pytest

from quotes.aggregator import QuoteAggregator
from quotes.models import Quote
from quotes.suppliers import FakeSupplier


async def test_picks_cheapest_per_sku(
    cheap: FakeSupplier, pricey: FakeSupplier
) -> None:
    result = await QuoteAggregator([cheap, pricey]).best_quotes(["A", "B"])
    assert result.best["A"].supplier == "cheap"
    assert result.best["B"].supplier == "pricey"
    assert result.failures == []


async def test_unknown_sku_is_reported_not_raised(
    cheap: FakeSupplier,
) -> None:
    result = await QuoteAggregator([cheap]).best_quotes(["A", "ZZZ"])
    assert set(result.best) == {"A"}
    assert result.failures[0].sku == "ZZZ"


async def test_slow_supplier_times_out_without_blocking_others(
    cheap: FakeSupplier,
) -> None:
    slow = FakeSupplier("slow", {"A": Decimal("0.10")}, latency=5)
    aggregator = QuoteAggregator(
        [cheap, slow], timeout=0.05, retry_attempts=1
    )
    loop = asyncio.get_running_loop()
    start = loop.time()
    result = await aggregator.best_quotes(["A"])
    assert loop.time() - start < 1
    assert result.best["A"].supplier == "cheap"
    assert "timed out" in result.failures[0].reason


async def test_transient_failure_is_retried() -> None:
    flaky = FakeSupplier("flaky", {"A": Decimal("1")}, fail_times=1)
    result = await QuoteAggregator([flaky], retry_attempts=2).best_quotes(
        ["A"]
    )
    assert result.best["A"].supplier == "flaky"
    assert flaky.calls == 2


async def test_duplicate_skus_are_requested_once(
    cheap: FakeSupplier,
) -> None:
    await QuoteAggregator([cheap]).best_quotes(["A", "A", "A"])
    assert cheap.calls == 1


class CountingSupplier:
    """Records the maximum number of concurrent calls."""

    def __init__(self) -> None:
        self.name = "counting"
        self.active = 0
        self.peak = 0

    async def get_quote(self, sku: str) -> Quote:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return Quote(sku, self.name, Decimal("1"), 1)


async def test_concurrency_is_bounded() -> None:
    supplier = CountingSupplier()
    aggregator = QuoteAggregator([supplier], max_concurrency=3)
    await aggregator.best_quotes([f"SKU-{i}" for i in range(20)])
    assert supplier.peak == 3


def test_requires_a_supplier() -> None:
    with pytest.raises(ValueError):
        QuoteAggregator([])
