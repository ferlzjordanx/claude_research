"""Supplier clients. The Protocol describes behaviour, not ancestry."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from quotes.errors import InvalidSkuError, TransientSupplierError
from quotes.models import Quote


class SupplierClient(Protocol):
    """Anything with a ``name`` and an async ``get_quote`` qualifies."""

    name: str

    async def get_quote(self, sku: str) -> Quote: ...


class FakeSupplier:
    """In-memory supplier used for demos and tests.

    ``latency`` simulates network delay. ``fail_times`` makes the first N
    calls raise a transient error, which lets tests exercise retries.
    """

    def __init__(
        self,
        name: str,
        prices: Mapping[str, Decimal],
        *,
        latency: float = 0.0,
        fail_times: int = 0,
    ) -> None:
        self.name = name
        self._prices = dict(prices)
        self._latency = latency
        self._failures_left = fail_times
        self.calls = 0

    async def get_quote(self, sku: str) -> Quote:
        self.calls += 1
        # asyncio.sleep yields to the event loop; time.sleep would block it.
        await asyncio.sleep(self._latency)
        if self._failures_left > 0:
            self._failures_left -= 1
            raise TransientSupplierError(f"{self.name} temporarily down")
        if sku not in self._prices:
            raise InvalidSkuError(f"{self.name} has no SKU {sku}")
        return Quote(
            sku=sku,
            supplier=self.name,
            unit_price=self._prices[sku],
            available=100,
        )
