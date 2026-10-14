"""Demo: python -m quotes SKU-1 SKU-2"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import asdict
from decimal import Decimal

from quotes.aggregator import QuoteAggregator
from quotes.pricing import BulkDiscount, FlatShipping, PriceCalculator
from quotes.suppliers import FakeSupplier
from quotes.utils import timed


async def main(skus: list[str]) -> int:
    suppliers = [
        FakeSupplier("acme", {"SKU-1": Decimal("9.50")}, latency=0.05),
        FakeSupplier(
            "globex",
            {"SKU-1": Decimal("9.10"), "SKU-2": Decimal("4.00")},
            latency=0.08,
            fail_times=1,
        ),
        FakeSupplier("slowco", {"SKU-2": Decimal("3.00")}, latency=5.0),
    ]
    aggregator = QuoteAggregator(suppliers, timeout=0.5, retry_attempts=2)
    calculator = PriceCalculator(
        [
            BulkDiscount(10, Decimal("5")),
            FlatShipping(Decimal("7"), Decimal("50")),
        ]
    )
    with timed("aggregation") as timing:
        result = await aggregator.best_quotes(skus)
    output = {
        "best": {
            sku: {
                "supplier": q.supplier,
                "unit_price": str(q.unit_price),
                "total_for_12": str(calculator.total(q.unit_price, 12)),
            }
            for sku, q in result.best.items()
        },
        "failures": [asdict(f) for f in result.failures],
        "seconds": round(timing["seconds"], 3),
    }
    print(json.dumps(output, indent=2))
    return 0 if result.best else 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s"
    )
    raise SystemExit(asyncio.run(main(sys.argv[1:] or ["SKU-1", "SKU-2"])))
