# Unit 11 Starter — Instrumented Orders API (with seeded bugs)

A FastAPI reporting service over SQLAlchemy/SQLite that calls an
external FX-rate service. It "works", but the customer says it gets
slow every afternoon. It contains four real production bugs and
half-finished observability. The tests are the spec.

```
client ─► RequestId ─► Metrics ─► routes ─► ReportService ─► SQLite
            │ logs        │ /metrics             └─► FxClient ─► FX
            └──────── OTel server span (outermost) ───── spans ──┘
```

## Your tasks

Find them with `grep -rn "TODO(" app`.

| # | File | Task |
|---|------|------|
| 1 | `app/observability/logging.py` | JSON formatter fields + redaction |
| 2 | `app/observability/logging.py` | stamp request/trace/span IDs |
| 3 | `app/observability/metrics.py` | BUG: label by route template |
| 4 | `app/services.py` | DB span + service span with attributes |
| 5 | `app/services.py` | BUG: N+1 queries -> one aggregate |
| 6 | `app/routes.py` | BUG: blocking call inside `async def` |
| 7 | `app/fx.py` | BUG: outbound client without timeout |
| 8 | `app/fx.py` | map timeouts/errors to 504/502 |

Starting state: **12 failed, 10 passed**. Done when `pytest -q`
shows **22 passed** and `ruff check .`, `ruff format --check .` and
`mypy` are clean. Suggested order: reproduce first (below), then
1-2 (you need logs to debug), 4 (traces), 3, then the bugs 5-8.

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory          # :8000/docs
uvicorn scripts.fake_fx:app --port 9000        # second terminal
```

## Reproduce the slowness before fixing anything

```bash
python -m scripts.load_test \
    --url http://127.0.0.1:8000/reports/export \
    --requests 50 --concurrency 10
# note p50/p95: requests queue behind each other (TODO 6)
curl -s localhost:8000/metrics | grep http_requests_total
# one series per customer ID (TODO 3)
py-spy dump --pid $(pgrep -f "uvicorn app.main")
# MainThread stuck in time.sleep inside render_report
```

Record the numbers. After the fixes, run the same commands again:
the before/after comparison is your evidence for the customer.
