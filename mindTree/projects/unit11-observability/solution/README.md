# Unit 11 Project — Instrumented Orders API

A FastAPI reporting service over SQLAlchemy/SQLite that calls an
external FX-rate service, fully instrumented:

- JSON logs with `request_id`, `trace_id`, `span_id` and redaction;
- Prometheus RED metrics at `/metrics`, labeled by route template;
- OpenTelemetry traces: auto server spans + manual service, DB and
  outbound-call spans, W3C `traceparent` in and out;
- the four production bugs from the unit's scenario, fixed and
  guarded by tests (blocking call in `async def`, N+1 queries, no
  outbound timeout, high-cardinality metric labels).

```
client ─► RequestId ─► Metrics ─► routes ─► ReportService ─► SQLite
            │ logs        │ /metrics             └─► FxClient ─► FX
            └──────── OTel server span (outermost) ───── spans ──┘
```

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory          # :8000/docs
# second terminal: the fake FX dependency
uvicorn scripts.fake_fx:app --port 9000
```

Endpoints: `/customers/{id}/summary`, `/reports/revenue`,
`/reports/revenue-fx?currency=EUR`, `/reports/export` (CSV),
`/metrics`, `/health`.

## Test

```bash
pytest -q && ruff check . && ruff format --check . && mypy
```

Expected: **22 passed**.

## Verify by hand

```bash
python -m scripts.load_test \
    --url http://127.0.0.1:8000/reports/export \
    --requests 100 --concurrency 20
curl -s localhost:8000/metrics | grep http_request_duration
FAKE_FX_DELAY=5 uvicorn scripts.fake_fx:app --port 9000  # then:
curl -i "localhost:8000/reports/revenue-fx?currency=EUR"  # 504
```

Set `APP_OTEL_EXPORTER=otlp` and `OTEL_EXPORTER_OTLP_ENDPOINT` to
send traces to an OpenTelemetry Collector, Jaeger, Tempo or a vendor.
See `RUNBOOK.md` for symptom-driven debugging steps.
