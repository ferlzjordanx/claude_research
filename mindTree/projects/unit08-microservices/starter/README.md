# Unit 8 Starter — Orders + Payments (Resilient Microservices)

Two FastAPI services and an async side channel. The wiring, routes,
schemas, broker, relay, Dockerfile and compose file already work.
What is missing is the logic that makes the system survive a
payments outage without charging anyone twice.

```
client ─► orders ──timeout/retry/breaker──► payments
            │ same tx                        Idempotency-Key store
            ▼                                + ledger of charges
          outbox ─relay─► broker ─► notifications (dedupe by id)
```

## Your tasks

`grep -rn "TODO(" --include=*.py .` lists them all.

| # | File | Task |
|---|------|------|
| 1 | `orders/payments_client.py` | full-jitter backoff; retryable? |
| 2 | `orders/payments_client.py` | retry loop: same key, 429, breaker |
| 3 | `orders/breaker.py` | closed/open/half-open transitions |
| 4 | `payments/store.py` | idempotency: claim, replay, mismatch |
| 5 | `orders/service.py` | order + outbox row in one transaction |
| 6 | `notifications/consumer.py` | dedupe by event id |

Order that works well: 4 (`pytest -q tests/test_payments.py`),
1 and 3 (`pytest -q tests/test_resilience.py -k "backoff or
breaker"`), 2 (`pytest -q tests/test_resilience.py`), 5, 6, then
the whole suite. Done when all 43 tests pass and
`ruff check . && ruff format --check . && mypy` is clean.

At the start, 33 tests fail and 10 pass (deployment files,
validation, missing-key, throttle and dead-letter tests do not
depend on your code).

## Run locally (two terminals)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn payments.main:create_app --factory --port 8001
uvicorn orders.main:create_app --factory --port 8000
```

Or with Docker: `docker compose up --build`.

## Test

```bash
pytest -q && ruff check . && ruff format --check . && mypy
```

Tests use `httpx.ASGITransport` (orders calls the real payments app
in-process) or `httpx.MockTransport` (scripted failures), plus a
fake clock and a fake sleep. Nothing waits for real.

## Verify by hand (after the TODOs)

```bash
J='Content-Type: application/json'
D='{"customer_id":"c-1","amount_cents":2500}'
curl -s -XPOST :8000/orders -H "$J" -d "$D"          # paid
curl -si -XPOST :8000/orders -H "$J" -d "$D" \
     -H 'X-Fault: error'                  # 503 + order_id, pending
curl -s -XPOST :8000/orders/2/pay        # paid (same payment key)
curl -s :8001/payments?order_id=2        # exactly one charge
curl -s :8000/health/ready               # circuit state, outbox
```
