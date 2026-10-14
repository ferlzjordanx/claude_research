# Unit 8 Project — Orders + Payments (Resilient Microservices)

Two FastAPI services that survive a payments outage without charging
anyone twice:

- **payments** (`:8001`): `POST /payments` requires an
  `Idempotency-Key`. Same key + same body replays the stored answer;
  same key + different body is 422. Fault injection rehearses
  outages (`X-Fault` header or `APP_FAULT_*` settings).
- **orders** (`:8000`): `POST /orders` writes the order and an outbox
  event in one transaction, then charges through a client with a
  timeout, retries (exponential backoff + full jitter, `Retry-After`
  on 429), one idempotency key for every attempt, and a circuit
  breaker that returns 503 problem+json fast when payments is down.
- **outbox relay + notifications consumer**: the relay publishes
  outbox rows to an in-memory, at-least-once broker; the consumer
  dedupes by event id, so a duplicate delivery sends one receipt.

```
client ─► orders ──timeout/retry/breaker──► payments
            │ same tx                        Idempotency-Key store
            ▼                                + ledger of charges
          outbox ─relay─► broker ─► notifications (dedupe by id)
```

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

Tests wire orders to payments in-process (`httpx.ASGITransport`) or
to `httpx.MockTransport`, with a fake clock and a fake sleep: no
network, no real waiting.

## Verify by hand

```bash
J='Content-Type: application/json'
D='{"customer_id":"c-1","amount_cents":2500}'
curl -s -XPOST :8000/orders -H "$J" -d "$D"          # paid
curl -si -XPOST :8000/orders -H "$J" -d "$D" \
     -H 'X-Fault: error'                  # 503 + order_id, pending
curl -s -XPOST :8000/orders/2/pay        # paid (same payment key)
curl -s :8001/payments?order_id=2        # exactly one charge
curl -s :8000/health/ready               # circuit state, outbox
curl -s :8000/ops/events                 # relay + consumer counts
```

Two `X-Fault: error` orders (3 attempts each, threshold 5) trip the
breaker: the next order fails in milliseconds with
`detail: ... circuit is open`, and `/health/ready` stays 200
(payments being down must not take orders out of the load balancer).
