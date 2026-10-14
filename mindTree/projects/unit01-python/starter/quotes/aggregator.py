"""Concurrent quote aggregation with timeouts and bounded concurrency."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from quotes.models import Quote, SupplierFailure
from quotes.suppliers import SupplierClient

log = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    best: dict[str, Quote] = field(default_factory=dict)
    failures: list[SupplierFailure] = field(default_factory=list)


class QuoteAggregator:
    """Asks every supplier for every SKU and keeps the cheapest quote.

    * Each call is bounded by ``timeout`` seconds (asyncio.timeout).
    * At most ``max_concurrency`` calls are in flight (Semaphore).
    * Transient errors are retried; failures never abort other calls.
    """

    def __init__(
        self,
        suppliers: Sequence[SupplierClient],
        *,
        timeout: float = 1.0,
        max_concurrency: int = 10,
        retry_attempts: int = 3,
    ) -> None:
        if not suppliers:
            raise ValueError("at least one supplier is required")
        self._suppliers = list(suppliers)
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._retry_attempts = retry_attempts

    async def _quote_once(
        self, supplier: SupplierClient, sku: str
    ) -> Quote:
        # TODO: acquire the semaphore, wrap supplier.get_quote(sku) in
        # `async with asyncio.timeout(self._timeout)`, and convert the
        # built-in TimeoutError into SupplierTimeoutError (use `from`).
        raise NotImplementedError

    async def _quote(
        self, supplier: SupplierClient, sku: str
    ) -> Quote | SupplierFailure:
        # TODO: wrap _quote_once with retry_async(attempts=...) and turn
        # any QuoteError into a SupplierFailure value (do not raise).
        raise NotImplementedError

    async def best_quotes(self, skus: Iterable[str]) -> AggregationResult:
        # TODO:
        # 1. de-duplicate SKUs while keeping order
        # 2. start one task per (sku, supplier) inside asyncio.TaskGroup
        # 3. collect failures and keep the cheapest Quote per SKU
        raise NotImplementedError
