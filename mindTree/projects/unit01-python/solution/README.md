# Unit 1 Project — Async Supplier Quote Aggregator

Asks several suppliers for prices concurrently, with per-call timeouts,
bounded concurrency and retries on transient errors, then keeps the
cheapest quote per SKU and prices an order with composable rules.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m quotes SKU-1 SKU-2     # demo with fake suppliers
pytest -q                        # tests
ruff check . && mypy             # lint + strict type check
```
