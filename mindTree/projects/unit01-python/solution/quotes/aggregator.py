"""Concurrent quote aggregation with timeouts and bounded concurrency."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from quotes.errors import QuoteError, SupplierTimeoutError
from quotes.models import Quote, SupplierFailure
from quotes.retry import retry_async
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
        async with self._semaphore:
            try:
                async with asyncio.timeout(self._timeout):
                    return await supplier.get_quote(sku)
            except TimeoutError as exc:
                raise SupplierTimeoutError(
                    f"{supplier.name} timed out for {sku}"
                ) from exc

    async def _quote(
        self, supplier: SupplierClient, sku: str
    ) -> Quote | SupplierFailure:
        call = retry_async(attempts=self._retry_attempts, base_delay=0.05)(
            self._quote_once
        )
        try:
            return await call(supplier, sku)
        except QuoteError as exc:
            log.info("no quote from %s for %s: %s", supplier.name, sku, exc)
            return SupplierFailure(sku, supplier.name, str(exc))

    async def best_quotes(self, skus: Iterable[str]) -> AggregationResult:
        unique = list(dict.fromkeys(skus))  # dedupe, keep order
        # TaskGroup: if *we* have a bug (unexpected exception) all tasks
        # are cancelled. Expected supplier errors are converted to
        # SupplierFailure values inside _quote, so they never escape.
        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(self._quote(supplier, sku))
                for sku in unique
                for supplier in self._suppliers
            ]
        result = AggregationResult()
        for task in tasks:
            outcome = task.result()
            if isinstance(outcome, SupplierFailure):
                result.failures.append(outcome)
                continue
            current = result.best.get(outcome.sku)
            if current is None or outcome.unit_price < current.unit_price:
                result.best[outcome.sku] = outcome
        return result
