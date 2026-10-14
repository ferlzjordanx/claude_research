# Unit 11 — Observability, Debugging and Production Support

## 1. What This Unit Teaches

Shipping the feature is half of the FDE job. The other half starts when the customer says "it's slow" or "it's broken" and you have to find out why, on a system you may not have written, under pressure **[JD-Required: troubleshooting and debugging production systems, monitoring, logging, performance]**. This unit teaches you to make a service explain itself and to debug it with evidence instead of guesses:

- monitoring vs observability, and the signals: logs, metrics, traces, profiles;
- structured JSON logs with request and trace IDs, without PII or secrets;
- Prometheus metrics: counters, gauges, histograms, RED/USE, the four golden signals, and why label cardinality kills metric systems;
- distributed tracing with OpenTelemetry: spans, W3C `traceparent` propagation, auto-instrumentation, the Collector, sampling;
- SLIs, SLOs, error budgets and burn-rate alerts;
- a repeatable debugging method, profiling with `py-spy` and `cProfile`, and the classic Python/async performance bugs;
- incident response and blameless postmortems;
- what to observe in LLM features (tokens, cost, latency, prompt version, eval scores).

The project is an instrumented FastAPI service with four seeded production bugs. You find them with the signals, fix them, and prove each fix with a test.

## 2. Mental Model

```text
 Your service (FastAPI)                     Backends           People
 ┌──────────────────────────────┐
 │ request ─► RequestId (ID)    │  logs   ┌─────────────┐
 │         ─► Metrics (RED)     │ ──────► │ Loki / CW   │──┐
 │         ─► OTel server span  │ metrics │ Logs        │  │ dashboards
 │   route ─► service span      │ ──────► ├─────────────┤  ├──► alerts
 │         ─► DB span, HTTP span│ (pull)  │ Prometheus  │  │    on-call
 │ every log line carries:      │ traces  ├─────────────┤  │    debug
 │  request_id, trace_id,       │ ──────► │ Collector ─►│──┘
 │  span_id                     │ (OTLP)  │ Tempo/X-Ray │
 └──────────────────────────────┘         └─────────────┘

 Debug loop:  alert/symptom ─► dashboard (which route? when?)
   ─► exemplar trace (which span is slow?) ─► logs for that trace_id
   ─► profile (which line?) ─► fix ─► test ─► verify on dashboard
```

Three ideas carry the whole unit:

1. **Metrics tell you *that* something is wrong, traces tell you *where*, logs and profiles tell you *why*.** You need all of them, joined by IDs.
2. **Alert on symptoms users feel** (errors, latency against an SLO), not on causes (CPU 80%). Causes go on dashboards for diagnosis.
3. **Debugging is a measurement loop, not inspiration.** Reproduce, isolate, form one hypothesis, measure, fix, verify with the same measurement, prevent with a test.

## 3. Brief Theory

### 3.1 Monitoring vs observability

**What it is.** *Monitoring* watches known failure modes with predefined checks and dashboards ("is error rate above 1%?"). *Observability* is a property of the system: how well you can answer *new* questions about its behavior from the data it emits, without shipping new code ("why are only EU customers with more than 100 orders slow since Monday?").

**Why it exists.** Distributed systems fail in ways nobody predicted. A dashboard only covers the questions you thought of in advance.

**Why it matters.** As an FDE you debug systems you did not build. Rich, correlated telemetry is the difference between a 20-minute and a 2-day investigation.

**How it works.** Monitoring is a subset: you build alerts and dashboards on top of observable data. High-cardinality, high-dimensional events (structured logs, span attributes) make a system observable; aggregated metrics make it cheap to monitor.

### 3.2 The signals

| Signal | Answers | Cost profile | Example here |
|---|---|---|---|
| Metrics | Is it broken? How much? Trend? | Cheap, aggregated, low cardinality | `http_request_duration_seconds` |
| Traces | Where in the request path is time spent? | Medium; sample in high volume | `GET /reports/revenue` → `SELECT customers` |
| Logs | What exactly happened in this event? | Expensive at volume; rich detail | `{"message":"request completed", "request_id":…}` |
| Profiles | Which code line burns CPU or blocks? | Low overhead when sampling | `py-spy dump` shows `time.sleep` |

OpenTelemetry treats traces, metrics and logs as stable signals and profiles as a newer signal **[Current]**. Correlation is what makes them powerful: a metric exemplar links to a trace, the trace ID is in every log line, and a profile can be filtered by span.

### 3.3 Structured logging

**What it is.** Logs as machine-parseable events (one JSON object per line), not free text.

**Why it exists.** At scale nobody reads logs; they query them: `level="ERROR" and route="/reports/export"`. Regexes over free text break the day someone rewords a message.

**Why it matters.** Support tickets arrive with a time and maybe a request ID. Structured logs turn that into one query.

**How it works.**

- **Fixed fields:** `timestamp` (ISO 8601, UTC), `level`, `logger`, `message`, `request_id`, `trace_id`, `span_id`, plus event fields passed as `extra=` (`route`, `status`, `duration_ms`).
- **Levels:** `DEBUG` off in production; `INFO` for lifecycle and one access line per request; `WARNING` for handled, unusual conditions (a retry); `ERROR` for failed operations that need attention; `CRITICAL` for "the process cannot continue". If an `ERROR` does not need a human, it is a `WARNING`.
- **Correlation:** a request ID (Unit 5) in a `ContextVar`, and the OpenTelemetry trace ID from the current span, both stamped by a logging filter.
- **No PII or secrets.** Never log passwords, tokens, `Authorization` headers, full request bodies, or customer emails. Redact by key in the formatter as a safety net, but the real control is not passing them in the first place. Logs are copied to many systems and kept for months.
- **Volume control:** sample noisy success logs (for example keep 10% of `INFO` access lines), never sample errors. Prefer one rich line per request over ten small ones.
- **Write to stdout.** The platform (Docker, Kubernetes, ECS) ships stdout to the log backend. The app does not manage files.

Reference: Python [logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html) **[Current]**.

### 3.4 Metrics

**What it is.** Numeric time series identified by a name and labels, for example `http_requests_total{method="GET",route="/reports/revenue",status="200"}`.

**Why it exists.** Aggregates are cheap to store and fast to query, so they power dashboards and alerts over months of data.

**Why it matters.** "p95 latency doubled at 14:00 on the export route" is a metrics question. Interviewers expect you to know the types and the classic methods.

**How it works.**

| Type | Behavior | Use for | Query with |
|---|---|---|---|
| Counter | Only goes up (resets on restart) | Requests, errors, bytes | `rate()` / `increase()` |
| Gauge | Goes up and down | In-flight requests, queue depth, pool usage | value, `max_over_time()` |
| Histogram | Counts observations into buckets | Latency, payload sizes | `histogram_quantile()` |
| Summary | Client-side quantiles | Rarely; cannot be aggregated across instances | — |

Three standard checklists:

| Method | For | Signals |
|---|---|---|
| **RED** (Tom Wilkie) | Request-driven services | **R**ate, **E**rrors, **D**uration |
| **USE** (Brendan Gregg) | Resources: CPU, memory, disks, pools | **U**tilization, **S**aturation, **E**rrors |
| **Four golden signals** (Google SRE) | User-facing systems | Latency, traffic, errors, saturation |

**Cardinality.** Every unique combination of label values is a separate time series held in memory. `route="/customers/{customer_id}/summary"` is one series per method and status. `path="/customers/4711/summary"` is one series *per customer*, and a bot scanning `/wp-admin/…` creates thousands more. This is the most common way teams take down their own Prometheus. Rules: label by route *template*; never use user IDs, emails, request IDs or raw URLs as label values; bucket unmatched paths into one value; put high-cardinality detail in logs and span attributes instead.

**Prometheus pull model.** The app exposes `/metrics` as text; Prometheus *scrapes* it every 15–60 s. Pull makes "is the target up?" a free signal (`up == 0`) and keeps the app simple. Short-lived batch jobs use the Pushgateway or push via OTLP instead. With several Python worker processes, each has its own counters: use `prometheus_client` multiprocess mode or one process per container.

**PromQL you should be able to write** ([functions docs](https://prometheus.io/docs/prometheus/latest/querying/functions/)):

```text
# requests per second, per route, over the last 5 minutes
sum by (route) (rate(http_requests_total[5m]))

# error ratio (5xx / all)
sum(rate(http_requests_total{status=~"5.."}[5m]))
  / sum(rate(http_requests_total[5m]))

# p95 latency per route from histogram buckets
histogram_quantile(0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))

# saturation: requests currently in flight
max(http_requests_in_flight)
```

Always `rate()` a counter before summing, and keep `le` in the `by` clause for `histogram_quantile`. Quantiles are estimates within bucket boundaries, so put buckets near your SLO threshold (this project has a `0.3` s bucket for a 300 ms target). Naming rules: base units (seconds, bytes), `_total` suffix for counters ([naming guide](https://prometheus.io/docs/practices/naming/)).

### 3.5 Distributed tracing and OpenTelemetry

**What it is.** A *trace* is the tree of work done for one request across services. Each node is a *span*: a name, start and end time, a parent, a kind (SERVER, CLIENT, INTERNAL, PRODUCER, CONSUMER), attributes and a status.

**Why it exists.** When a request crosses an API, a database and two external services, only a trace shows which hop took the 4 seconds.

**Why it matters.** It is the fastest way from "the route is slow" to "this query runs 26 times".

**How it works.**

```text
 trace 0af7651916cd43dd8448eb211c80319c
 GET /reports/revenue-fx          SERVER  ████████████████████ 2.1 s
 ├─ reports.revenue_by_customer   INTERNAL ██                  0.1 s
 │  └─ SELECT customers           CLIENT   █                   0.01 s
 └─ fx.get_rate                   CLIENT     ████████████████   2.0 s
      └─ (FX service) GET /rates  SERVER     ████████████████
```

*Context propagation* links spans across processes. The W3C Trace Context header ([spec](https://www.w3.org/TR/trace-context/)) carries it:

```text
traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
             │  │                                │                └ flags
             │  └ trace-id (16 bytes, hex)       └ parent span-id   (01 =
             └ version                             (8 bytes, hex)  sampled)
```

The server extracts it and continues the trace; outbound calls inject it. `tracestate` carries vendor data and `baggage` carries user-defined key/values (never secrets: it travels to every downstream service).

**OpenTelemetry (OTel)** **[Current]** is the vendor-neutral CNCF standard ([docs](https://opentelemetry.io/docs/languages/python/)):

| Piece | Role |
|---|---|
| API | What libraries call: `tracer.start_as_current_span(...)`. No-op without an SDK |
| SDK | `TracerProvider`, samplers, span processors (`BatchSpanProcessor`), exporters |
| Auto-instrumentation | Packages that create spans for FastAPI, httpx, SQLAlchemy, etc.; or zero-code `opentelemetry-instrument` |
| OTLP | The wire protocol (gRPC 4317, HTTP 4318) for traces, metrics, logs |
| Collector | A separate process: receive OTLP, batch, filter, redact, tail-sample, export to any backend |
| Semantic conventions | Standard attribute names: `http.response.status_code`, `db.system.name`, `server.address` ([semconv](https://opentelemetry.io/docs/specs/semconv/)) |

Send apps' telemetry to a local Collector (sidecar or DaemonSet), not straight to a vendor. Switching backends then becomes a Collector config change.

**Sampling.** *Head sampling* decides at the start of the trace (`ParentBased(TraceIdRatioBased(0.1))` keeps 10% and respects the caller's decision). It is cheap but blind: it drops the rare slow or failed trace as often as the boring ones. *Tail sampling* decides after the trace completes, in the Collector ("keep all errors, all traces > 1 s, 5% of the rest"). It is smarter, but the Collector must buffer whole traces.

### 3.6 SLIs, SLOs, error budgets and alerting

**What it is.** An **SLI** is a measured ratio of good events ("requests answered successfully in < 300 ms" / all requests). An **SLO** is the target for it over a window ("99.5% over 28 days"). The **error budget** is what is left: 0.5% of requests may be bad, about 3.6 hours of full outage per 30 days. An **SLA** is a contract with penalties, set looser than the SLO.

**Why it exists.** 100% is impossible and wasteful. The budget turns reliability into a number both product and engineering accept: budget left means ship faster; budget burnt means freeze features and fix reliability.

**Why it matters.** Customers escalate when *their* experience degrades. An SLO lets you say "we are at 99.7% this month" instead of arguing about anecdotes.

**How it works: burn-rate alerts** ([SRE workbook](https://sre.google/workbook/alerting-on-slos/)). Burn rate = observed error ratio / allowed error ratio. A burn rate of 1 uses exactly the budget over the window; 14.4 uses 2% of a 30-day budget in one hour.

| Severity | Condition (both windows must fire) | Action |
|---|---|---|
| Page | burn rate > 14.4 over 1 h **and** over 5 m | Wake someone up |
| Page | burn rate > 6 over 6 h **and** over 30 m | Wake someone up |
| Ticket | burn rate > 1 over 3 d **and** over 6 h | Fix this week |

The long window gives significance; the short window makes the alert stop soon after recovery. Alert on symptoms (SLO burn, error ratio, latency); keep cause metrics (CPU, pool usage, GC) on dashboards. Every page needs a runbook link and must be actionable.

**Dashboards.** One per service, top to bottom: SLO status and budget left; RED per route; saturation (in-flight, pools, CPU, memory); dependencies (latency and errors per downstream); deploy markers. Use the same time range across panels so you can line events up.

### 3.7 Tool equivalents [Provider-specific]

| Need | AWS | Grafana stack | Datadog |
|---|---|---|---|
| Metrics | CloudWatch Metrics, Amazon Managed Prometheus | Prometheus / Mimir | Datadog Metrics |
| Logs | CloudWatch Logs + Logs Insights | Loki (LogQL) | Log Management |
| Traces | X-Ray / CloudWatch Application Signals | Tempo (TraceQL) | APM |
| Dashboards | CloudWatch dashboards, Managed Grafana | Grafana | Dashboards |
| Alerts | CloudWatch Alarms (incl. SLO alarms) | Grafana Alerting / Alertmanager | Monitors, SLOs |
| Profiles | CodeGuru Profiler | Pyroscope | Continuous Profiler |
| Ingest | ADOT (AWS Distro for OpenTelemetry) Collector | Grafana Alloy (OTel Collector distribution) | Datadog Agent (accepts OTLP) |

Because all of them accept OTLP, instrument once with OpenTelemetry and choose the backend per customer. AWS recommends OpenTelemetry (ADOT) for new X-Ray instrumentation; check the [X-Ray docs](https://docs.aws.amazon.com/xray/latest/devguide/xray-instrumenting-your-app.html) for the current status of the older X-Ray SDKs. References: [CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html), [Grafana Tempo](https://grafana.com/docs/tempo/latest/), [Grafana Loki](https://grafana.com/docs/loki/latest/), [Datadog OTel](https://docs.datadoghq.com/opentelemetry/).

### 3.8 A debugging method

**What it is.** A fixed loop you follow even when the VP is on the call:

```text
 1 REPRODUCE   get the symptom on demand (load test, same input)
 2 ISOLATE     which route / tenant / time / version / host?
 3 HYPOTHESIZE one testable explanation, written down
 4 MEASURE     a signal that would confirm or kill it
 5 FIX         the smallest change that addresses the cause
 6 VERIFY      same measurement as step 4, before vs after
 7 PREVENT     regression test, alert, runbook entry
```

**Why it exists.** Under pressure, people change three things at once and cannot tell which one helped, or "fix" a coincidence.

**Why it matters.** Interviewers ask "how would you debug X?" to hear this structure, not a lucky guess.

**How it works.** Start with what changed (deploys, config, traffic, data volume, dependencies). Split the problem in half repeatedly: client vs server time, app vs DB, one route vs all. Mitigate first if users are suffering (rollback, scale out, feature flag off), then find the root cause on a calm system.

### 3.9 Profiling

| Tool | What it does | When |
|---|---|---|
| `py-spy dump --pid N` **[External]** | Prints every thread's current stack; no restart, no code change | "It's hung / slow right now" in production |
| `py-spy top --pid N` | Live `top`-like view of hot functions | Where CPU goes under load |
| `py-spy record -o prof.svg --pid N` | Sampling flame graph | Share evidence; compare before/after |
| `cProfile` / `python -m cProfile -s cumtime x.py` | Deterministic profiler (every call) | Local, reproducible CPU hot spots |
| `tracemalloc` | Allocation snapshots and diffs | Memory growth |
| `PYTHONASYNCIODEBUG=1` | asyncio debug mode: logs callbacks slower than 100 ms | Finding blocking calls in `async def` |

`py-spy` needs `SYS_PTRACE` in containers (`--cap-add SYS_PTRACE`, or a Kubernetes debug container). Sampling profilers add little overhead, which is why continuous profiling (Pyroscope, Datadog, CodeGuru) is safe in production. Docs: [cProfile](https://docs.python.org/3/library/profile.html), [py-spy](https://github.com/benfred/py-spy), [asyncio dev mode](https://docs.python.org/3/library/asyncio-dev.html).

### 3.10 Common Python and async performance bugs

| Bug | Symptom | How to see it | Fix |
|---|---|---|---|
| Blocking call in `async def` (`time.sleep`, `requests`, sync DB driver, CPU work) | *All* routes slow under load; latency ≈ queue of blocked work; CPU often low | Trace: server span long with a gap and no child span; `py-spy dump` shows MainThread in `sleep`/`recv`; asyncio debug logs | `await asyncio.to_thread(...)`, plain `def` endpoint (FastAPI runs it in a threadpool), or an async library ([FastAPI async](https://fastapi.tiangolo.com/async/)) |
| N+1 queries | One route slow, grows with data size | Many identical short DB spans per trace; SQL statement count | One JOIN/aggregate query, `selectinload()` ([SQLAlchemy loading](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html)) |
| Missing timeouts | Requests hang, then many fail together; in-flight climbs | In-flight gauge; long CLIENT spans with no end; pool waits | Timeout on every outbound call; map to 504; retries with backoff and a total deadline ([httpx timeouts](https://www.python-httpx.org/advanced/timeouts/)) |
| Pool exhaustion (DB, HTTP, threadpool) | Latency jumps in steps at load; errors like `QueuePool limit … timed out` | Pool metrics; spans waiting before the query starts | Size pools to the DB's limits, shorter transactions, timeouts, don't hold a connection across an outbound call |
| Memory leak | RSS grows until OOM kill, restart "fixes" it | Container memory graph saw-tooth; `tracemalloc` diff | Bound caches (`lru_cache(maxsize=…)`), avoid module-level lists, close clients |
| GC pauses / large heaps | Periodic latency spikes | `gc.callbacks` timing, p99 spikes without load change | Fewer temporary objects, streaming instead of loading all rows |

Note the defaults: `requests` has **no** default timeout; `httpx` defaults to 5 s, but code often sets `timeout=None` "because the upstream is slow". Ruff's `ASYNC` rules catch a direct `time.sleep` inside `async def` (ASYNC251), but not one hidden in a sync helper, which is exactly how it appears in real code.

### 3.11 Incident response

**What it is.** A practiced process for restoring service when something breaks in production.

**Why it exists.** Chaos costs time: five people debugging the same thing, nobody updating the customer, someone restarting the database mid-investigation.

**Why it matters.** FDEs are often the first engineer the customer calls. How you run the first hour shapes the relationship.

**How it works.**

| Severity | Example | Response |
|---|---|---|
| SEV1 | Outage or data loss for many users | Page now; incident commander; updates every 30 min |
| SEV2 | Major feature degraded, SLO burning fast | Page; updates every 1–2 h |
| SEV3 | Minor or single-customer degradation | Ticket; fix in business hours |

- **Roles:** *incident commander* (coordinates, decides, does not debug), *operations* (hands on keyboard), *communications* (status page, customer, executives), *scribe* (timeline).
- **Mitigate before root cause:** roll back the last deploy, disable the feature flag, scale out, shed load, fail over. Root cause can wait until users are fine.
- **Rollback is a feature:** every deploy must be reversible in minutes (Unit 7).
- **Communicate on a schedule**, even with "no news": impact, what we know, what we are doing, next update time. Separate facts from hypotheses.
- **Blameless postmortem** within a few days: summary, impact (users, duration, budget burned), timeline with timestamps, root cause and contributing factors (5 whys), what went well, what was lucky, action items with owners and dates. "Human error" is never a root cause; ask why the system allowed it ([Google SRE postmortem culture](https://sre.google/sre-book/postmortem-culture/)).

Example 5 whys for this unit's scenario: exports were slow → the event loop was blocked → the renderer is synchronous → it was called directly from `async def` → nothing (lint, test, review) checked for blocking calls in async code → *action:* concurrency test in CI and asyncio debug mode in staging.

### 3.12 Observability for LLM features

LLM calls (Units 9–10) are slow, expensive and non-deterministic, so they need extra signals:

| Signal | Why |
|---|---|
| Model ID and provider | Behavior and price change per model |
| Input/output/cached tokens per call | Cost and context-window pressure |
| Cost per request / tenant / feature | Budgets, abuse detection |
| Latency: total and time-to-first-token | Streaming UX; provider slowdowns |
| Prompt template version | Tie quality regressions to prompt changes |
| Tool calls, retries, stop reason, refusals | Agent loops, truncation (`max_tokens`) |
| Eval scores (offline and sampled online) | Quality drift that no error rate shows |

The OpenTelemetry GenAI semantic conventions define attributes such as `gen_ai.request.model`, `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` **[Experimental]** ([GenAI semconv](https://opentelemetry.io/docs/specs/semconv/gen-ai/)). Do not record full prompts and completions by default: they often contain PII. Log them only with consent, redaction and short retention.

## 4. Application in a Real System

A customer's reporting API "gets slow every afternoon". An FDE works through it like this:

- **Hour 1:** acknowledge, agree on an update cadence, ask what changed on Monday (answer: a new CSV export feature, and the EU team started using it after lunch). Check the RED dashboard: p95 rises on *every* route between 13:00 and 17:00, while CPU stays at 30%.
- **Hour 2:** reproduce with the load script against staging: export at concurrency 10 gives p50 1 s for a 0.2 s job. `py-spy dump` shows the event loop thread inside `time.sleep` in `render_report`. Hypothesis confirmed: a blocking call in `async def` serializes the worker.
- **Mitigation:** scale out workers (more event loops) the same afternoon while the fix goes through CI.
- **Day 2:** fix (`asyncio.to_thread`), plus a concurrency test. While in the traces, the FDE notices `/reports/revenue` makes 26 SQL queries (N+1), the FX client has `timeout=None`, and Prometheus memory has grown because the metrics label uses raw paths. Each gets a fix and a test.
- **Day 3:** before/after numbers to the customer (p95 1.1 s → 0.24 s), an SLO with a burn-rate alert, a runbook, and a short blameless postmortem.

## 5. Implementation

### 5.1 JSON logs with request and trace IDs

```python
class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = None
            record.span_id = None
        return True
```

The filter sits on the *handler* in `dictConfig`, so records from every logger (ours, uvicorn's, SQLAlchemy's) get the IDs. The formatter turns each record into one JSON object and redacts sensitive keys:

```python
for key, value in vars(record).items():
    if key in _STANDARD or key in payload:
        continue                  # skip built-in LogRecord attributes
    if key.lower() in SENSITIVE_KEYS:
        value = "[REDACTED]"      # safety net, not the main control
    payload[key] = value          # fields passed with extra={...}
```

One access line per request looks like this (wrapped for print):

```text
{"timestamp": "2026-10-14T15:28:12.879+00:00", "level": "INFO",
 "logger": "app.access", "message": "request completed",
 "request_id": "3c8159ed47ac4be1961a180635a53bcd",
 "trace_id": "56a5dcbb6e67bafd81a7085b5e3d7f49",
 "span_id": "98190d6ad1e26c2b", "method": "GET",
 "path": "/reports/export", "route": "/reports/export",
 "status": 200, "duration_ms": 213.36}
```

### 5.2 Metrics labeled by route template

```python
def route_template(scope: Scope) -> str:
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else UNMATCHED
```

The middleware is pure ASGI (no `BaseHTTPMiddleware`): it wraps `send` to capture the status and reads the route *after* the app ran, because routing stores the matched route in the scope:

```python
self.metrics.in_flight.inc()
start = time.perf_counter()
try:
    await self.app(scope, receive, send_wrapper)
finally:
    elapsed = time.perf_counter() - start
    self.metrics.in_flight.dec()
    route = route_template(scope)
    if route != "/metrics":
        method = scope["method"]
        self.metrics.requests.labels(method, route, str(status)).inc()
        self.metrics.duration.labels(method, route).observe(elapsed)
```

Each app instance owns a `CollectorRegistry`, so tests that build many apps never collide with "Duplicated timeseries" errors from the global registry.

### 5.3 Tracing: provider, auto spans, manual spans, propagation

```python
provider = TracerProvider(
    resource=Resource.create({"service.name": settings.service_name}),
    sampler=ParentBased(TraceIdRatioBased(settings.trace_sample_ratio)),
)
if exporter is not None:              # tests: InMemorySpanExporter
    provider.add_span_processor(SimpleSpanProcessor(exporter))
elif settings.otel_exporter == "otlp":  # reads OTEL_EXPORTER_OTLP_*
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
FastAPIInstrumentor.instrument_app(
    app, tracer_provider=provider, excluded_urls="metrics,health"
)
```

Manual spans mark the service and DB work, with semantic-convention attributes:

```python
with self._tracer.start_as_current_span(
    "reports.revenue_by_customer"
) as span:
    with self._db_span("SELECT", "customers") as db_span:
        rows = self._session.execute(stmt).all()
        db_span.set_attribute("db.response.returned_rows", len(rows))
    span.set_attribute("app.report.rows", len(rows))
```

The outbound call injects `traceparent`, so the FX service can continue the same trace:

```python
headers: dict[str, str] = {}
inject(headers)  # {"traceparent": "00-<trace>-<this span>-01"}
response = await self.http.get("/rates", params=..., headers=headers)
```

In production you would add `opentelemetry-instrumentation-httpx` and `-sqlalchemy` to get these spans automatically; writing them once by hand shows what auto-instrumentation does.

### 5.4 The four fixes

```python
# Bug 1: blocking call in async def            (routes.py)
body = render_report(rows, delay)                       # before
body = await asyncio.to_thread(render_report, rows, delay)  # after

# Bug 2: N+1 queries                           (services.py)
for c in customers:                 # before: 1 + N queries
    total = sum(o.amount_cents for o in c.orders)   # lazy load
stmt = (select(Customer.id, Customer.name,          # after: 1 query
               func.count(Order.id),
               func.coalesce(func.sum(Order.amount_cents), 0))
        .outerjoin(Order, Order.customer_id == Customer.id)
        .group_by(Customer.id, Customer.name))

# Bug 3: no timeout                            (fx.py)
httpx.AsyncClient(base_url=url, timeout=None)            # before
httpx.AsyncClient(base_url=url,                          # after
                  timeout=httpx.Timeout(settings.fx_timeout_seconds),
                  limits=httpx.Limits(max_connections=20))
# ... and httpx.TimeoutException -> UpstreamTimeoutError -> 504

# Bug 4: high-cardinality label                (metrics.py)
return str(scope["path"])            # before: /customers/42/summary
return scope["route"].path           # after: /customers/{customer_id}/…
```

### 5.5 Tests that prove performance fixes

Counting SQL statements turns "N+1" into an assertion:

```python
def count(*args: Any) -> None:
    statements.append(args[2])          # (conn, cursor, statement, …)

event.listen(engine, "before_cursor_execute", count)
rows = client.get("/reports/revenue").json()
assert len(statements) <= 2, statements
```

A concurrency test proves the event loop stays free. Five requests that each need 0.2 s of blocking work finish in about 0.2 s, not 1 s:

```python
async with (
    app.router.lifespan_context(app),
    httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                      base_url="http://t") as ac,
):
    start = time.perf_counter()
    results = await asyncio.gather(
        *(ac.get("/reports/export") for _ in range(5)))
    elapsed = time.perf_counter() - start
assert elapsed < 0.2 * 5 * 0.6
```

`ASGITransport` does not run the lifespan, hence `lifespan_context`. The load test also found a bug that unit tests missed: a single shared in-memory SQLite connection (`StaticPool`) corrupts results when two threads query at once. The project therefore uses a file database, which gives each thread its own pooled connection.

## 6. How It Connects to the Rest of the System

```text
 Unit 11 observability
   ├─ builds on: request IDs + problem+json (U5), async and
   │   timeouts (U1), SQL and query plans (U3)
   ├─ runs in: containers writing to stdout; probes vs metrics (U6)
   ├─ CI: lint (ruff ASYNC), perf/regression tests, deploy markers,
   │   fast rollback (U7)
   ├─ distributed: traceparent across services and queues;
   │   timeouts, retries, circuit breakers (U8)
   ├─ LLM features: tokens, cost, prompt version, evals (U9-U10)
   └─ FDE delivery: runbooks, SLOs and postmortems are customer
       deliverables (U12)
```

## FDE Scenario 10 — "Since Monday the API is slow every afternoon and the customer escalated to their VP"

**Stakeholder (customer VP of Operations, by email to your manager):** "Our analysts can't work after lunch. Reports take 30 seconds or time out. This started Monday. I need to know what is going on and when it will be fixed."

- *Own the response:* reply within the hour. Acknowledge the impact, name yourself as the point of contact, promise an update at a fixed time (for example 16:00 and daily after), and ask for two concrete examples (time, user, report) and any error reference shown.
- *Investigate with evidence:*
  - what changed on Monday: deploys, feature flags, new users or tenants, data volume, dependency changes;
  - RED dashboard by route and hour: all routes or one? Correlated with traffic?
  - slowest traces in the window: a long gap with no child spans (blocking), many repeated DB spans (N+1), or one long CLIENT span (slow dependency);
  - `py-spy dump` on a slow worker, and the load script in staging to reproduce.
- *Mitigate first:* scale out, or disable the new export feature with a flag, the same day. Tell the customer it is a mitigation, not the fix.
- *Fix and verify:* one change at a time, each with a test; publish before/after p50/p95/p99 from the same load test and the production dashboard.
- *What must be deterministic:* timeouts on every outbound call, error mapping (504 vs 500), and metric labels. Latency is statistical, so report percentiles, not one lucky run.
- *Communicate:* a short written summary for the VP in plain language: impact, cause, fix, evidence, and what prevents it happening again (SLO alert, concurrency test, runbook). Keep the technical postmortem separate for engineers.
- *Prevent:* agree an SLO with the customer ("p95 < 300 ms for reports, 99.5% of requests") and alert on burn rate, so next time you call them first.

## Comprehension Questions

1. What is the difference between monitoring and observability?
2. Why is a counter queried with `rate()`, and why must `le` stay in the `by` clause of `histogram_quantile()`?
3. Why is `/customers/4711/summary` a bad metric label value but fine in a log line?
4. What do the four parts of a `traceparent` header mean?
5. Compare head and tail sampling. Which one keeps every error trace?
6. With a 99.9% SLO over 30 days, roughly how much full downtime is the error budget? What is a burn rate of 14.4?
7. Why does a `time.sleep()` in one `async def` endpoint slow down *all* routes on that worker?
8. Why do incident responders mitigate before finding the root cause?

## Comprehension Answers

1. Monitoring checks known failure modes with predefined dashboards and alerts. Observability is how well you can answer new, unplanned questions from the telemetry the system emits. Monitoring is built on top of observable data.
2. A counter only grows (and resets on restart); `rate()` converts it into per-second change and handles resets. `histogram_quantile` needs the per-bucket series (`le` label) to estimate the quantile; aggregating `le` away destroys the distribution.
3. Each unique label value creates a new time series held in Prometheus memory: one per customer, forever. Logs are individual events stored and indexed differently, so high-cardinality values are expected there.
4. Version (`00`), trace ID (16 bytes hex, shared by the whole trace), parent span ID (8 bytes hex, the caller's span), and trace flags (`01` = sampled).
5. Head sampling decides at the root before anything happens: cheap, but it drops interesting traces at the same rate as boring ones. Tail sampling decides after the trace completes (in the Collector) and can keep all errors and slow traces.
6. 0.1% of 30 days ≈ 43 minutes. A burn rate of 14.4 consumes budget 14.4 times faster than sustainable: 2% of the 30-day budget in one hour, the classic fast-burn page threshold.
7. One event loop thread runs all coroutines on that worker. A blocking call never yields, so every other request waits until it returns. Requests queue and latency grows with concurrency.
8. Users are hurting now. Rollback, flags or scaling usually restore service in minutes, while root-causing can take hours. Investigation is also safer and calmer on a stable system.

## Interview Questions — Theory-Based

**Q1. What are the pillars of observability and how do they work together?**

- *Strong answer:* metrics for detection and trends (cheap, aggregated), traces for locating the slow or failing hop, logs for event detail, and profiles for the exact code. The key is correlation: trace IDs in every log line, exemplars linking metrics to traces, consistent resource attributes (`service.name`, version, environment) across signals. Emitted via OpenTelemetry to a Collector, so the backend is swappable.
- *What it tests:* whether you see observability as a system, not a list of tools.
- *Follow-up:* "If you could only have one?" (Usually structured, wide events or traces for a service; metrics for alerting on a budget. Explain the trade-off.)

**Q2. Explain RED, USE and the four golden signals. Which do you use where?**

- *Strong answer:* RED (rate, errors, duration) for every request-driven service and route; USE (utilization, saturation, errors) for resources like CPU, memory, connection pools and queues; golden signals (latency, traffic, errors, saturation) combine both for a user-facing system. Alert on RED/golden symptoms tied to SLOs; use USE for diagnosis.
- *Follow-up:* "What is saturation for a Python async service?" (In-flight requests, event loop lag, DB/HTTP pool usage, threadpool queue.)

**Q3. What is metric cardinality and how have you seen it go wrong?**

- *Strong answer:* the number of unique label combinations; each is a series in memory. Raw paths, user IDs, request IDs, error messages as labels cause explosions that slow or crash Prometheus and raise vendor bills. Use route templates, bounded enums, an `<unmatched>` bucket; put detail in logs or span attributes; drop labels with relabeling in an emergency.
- *What it tests:* real production experience versus tutorial knowledge.

**Q4. How does distributed tracing work across services?**

- *Strong answer:* each service creates spans; the client injects W3C `traceparent` (trace ID, parent span ID, flags) into outbound headers or message metadata; the server extracts it and creates a child span. OTel SDK batches spans and exports OTLP to a Collector, which can tail-sample and route to Tempo, X-Ray or Datadog. For queues, propagate the context in message attributes and use span links for batch consumers.
- *Follow-up:* "A trace is broken into two pieces. Why?" (A hop does not propagate: a proxy strips headers, an uninstrumented client, a thread pool or queue that loses context.)

**Q5. What makes a good alert?**

- *Strong answer:* based on a user-facing symptom (SLO burn rate, error ratio, latency), actionable, urgent, with a runbook link and owner. Multi-window burn rate reduces noise and detects both fast and slow burns. Cause-based alerts (CPU 80%) mostly become dashboards. Track pages per week and remove alerts nobody acts on.
- *Follow-up:* "How do you avoid alert fatigue?" (Fewer, symptom-based pages; tickets for slow burns; review every page in a weekly ops meeting.)

**Q6. Your FastAPI service gets slower as concurrency rises but CPU stays low. What do you suspect?**

- *Strong answer:* waiting, not computing: blocking calls in `async def`, a too-small DB or HTTP pool, the threadpool limit for sync endpoints (40 by default in AnyIO), or a slow dependency without timeout. Confirm with in-flight and pool metrics, traces (gaps vs long CLIENT spans) and `py-spy dump`. Fix with `to_thread`/async libraries, pool sizing, timeouts.
- *What it tests:* async mental model and method.

**Q7. How do you find and fix an N+1 query problem?**

- *Strong answer:* symptoms: latency grows with data size; traces show many identical short DB spans; SQL logs show `WHERE customer_id = ?` repeated. Fix with a JOIN or aggregate query, or `selectinload()`/`joinedload()` in SQLAlchemy; set `lazy="raise"` on relationships to make accidental lazy loads fail in tests. Guard with a test that counts statements via an event listener.

**Q8. Describe how you run an incident and a postmortem.**

- *Strong answer:* declare severity; assign an incident commander, ops and comms; mitigate first (rollback, flag off, scale); update stakeholders on a schedule; keep a timeline. Afterwards, a blameless postmortem: impact, timeline, root cause and contributing factors (5 whys), what went well, action items with owners. Focus on system fixes, not people.
- *Follow-up:* "What if the customer wants someone to blame?" (Own it on behalf of the team, explain the systemic cause and the prevention.)

## Interview Questions — Application / Experience-Based

**A1. Tell me about a production issue you debugged.**

- *Cover:* the symptom and impact, how you narrowed it down (which signals), the root cause, mitigation vs fix, verification, and prevention.
- *Structure:* symptom → first data you looked at → hypothesis → measurement that confirmed it → fix → before/after numbers → test or alert added.
- *Personalize:* "`<<personalize: system, symptom, impact>>`. I started with `<<dashboard/logs/traces>>`, which showed `<<finding>>`. I suspected `<<hypothesis>>` and confirmed it with `<<measurement>>`. We mitigated by `<<rollback/flag/scale>>` and fixed `<<root cause>>`. Latency went from `<<before>>` to `<<after>>`."
- *Lab-honest version:* "In a practice project I reproduced 'slow under load' with a small asyncio load generator: p50 was five times the work time at concurrency 5. `py-spy` showed the event loop stuck in a synchronous renderer. I moved it to a worker thread and added a concurrency test; p50 returned to about one unit of work. The same traces exposed an N+1 query: 26 SQL statements became one."
- *Follow-ups:* "How did you know it was fixed and not just quieter traffic?" "What would you alert on?"

**A2. How have you instrumented a service you were responsible for?**

- *Cover:* logs (format, IDs, redaction), metrics (RED by route, histograms, cardinality rules), traces (auto + manual spans, propagation, sampling), dashboards, alerts, and who used them.
- *Personalize:* "`<<stack>>` with `<<OTel/vendor agent>>` exporting to `<<backend>>`. We alerted on `<<SLO/symptom>>`."
- *Lab-honest version:* "I built a FastAPI service with JSON logs carrying request and trace IDs, Prometheus RED metrics labeled by route template, and OpenTelemetry spans for service, DB and outbound calls, all verified by tests."

**A3. Tell me about a time you handled an escalation from a frustrated customer.**

- *Cover:* acknowledge fast, one point of contact, update cadence, separate facts from hypotheses, mitigation, written summary, prevention agreed with them.
- *Structure:* situation → first response → investigation in parallel with comms → resolution → relationship outcome.
- *Personalize:* "`<<customer, issue, who escalated>>`. I `<<first action>>` and committed to updates every `<<interval>>`. We `<<mitigation>>` within `<<time>>`."
- *Lab-honest version:* "I haven't led a customer escalation yet. My approach: reply within the hour with impact acknowledged and a next-update time, mitigate the same day, and send a plain-language summary with before/after numbers and prevention steps."

**A4. Describe a performance optimization with measurable results.**

- *Cover:* baseline measurement, profiling evidence, the change, the same measurement after, and the trade-off (memory, complexity).
- *Personalize:* "`<<endpoint/job>>` took `<<p95>>`. Profiling showed `<<hot spot>>`. After `<<change>>`, p95 was `<<after>>` with `<<trade-off>>`."
- *Lab-honest version:* use the N+1 and blocking-call fixes from this project with the load test's p50/p95/p99 numbers.

**A5. Have you defined SLOs or alerts with a team or customer?**

- *Cover:* choosing an SLI users feel, the target and window, burn-rate alerts, how the error budget changed decisions.
- *Lab-honest version:* "I have practiced it: for a reports API I would propose 99.5% of requests successful under 300 ms over 28 days, page on 14.4x burn over 1 h and 5 m, and ticket on slow burns."
- *Follow-ups:* "How do you pick the target?" (Start from current performance and what users need, not from 99.99% by default.)

## Troubleshooting Scenarios

**T1. Every route gets slow in the afternoon, CPU is low.**

```text
SYMPTOM     p95 up on all routes at peak; in-flight climbs; CPU ~30%
CHECK       traces: long server spans with gaps and no child span?
            py-spy dump --pid <worker>: MainThread in sleep/recv?
            PYTHONASYNCIODEBUG=1 in staging: "Executing ... took"
CAUSES      blocking call in async def; threadpool or DB pool limit;
            slow dependency without timeout holding workers
CONFIRM     load test at concurrency 1 vs 10: latency x10 = blocking
FIX         asyncio.to_thread / def endpoint / async library;
            mitigate first by scaling out workers
PREVENTION  concurrency test in CI; ruff ASYNC rules; asyncio debug
```

**T2. One report endpoint is slow and gets slower every week.**

```text
SYMPTOM     /reports/revenue p95 grows with customer count
CHECK       DB spans per trace; SQL statement count; echo=True locally
CAUSES      N+1 lazy loading; missing index; no pagination
CONFIRM     statement counter: 1 + N queries for N customers
FIX         aggregate/JOIN query or selectinload; add index; paginate
PREVENTION  test asserting statement count <= 2; lazy="raise"
```

**T3. Requests hang for minutes, then many fail at once.**

```text
SYMPTOM     in-flight gauge flat at the max; LB 504s; no app errors
CHECK       open CLIENT spans to one dependency; pool wait time;
            outbound client timeout settings (timeout=None?)
CAUSES      missing timeout; hung upstream; pool exhausted behind it
CONFIRM     make the fake upstream slow: requests never return
FIX         httpx.Timeout on every client; map to 504 problem+json;
            retries with backoff + total deadline; circuit breaker
PREVENTION  test that the client has a timeout; dependency dashboard
```

**T4. Prometheus memory keeps growing and queries time out.**

```text
SYMPTOM     scrape duration up; TSDB head series in the millions
CHECK       topk(10, count by (__name__)({__name__=~".+"}))
            count(count by (route) (http_requests_total))
CAUSES      raw path / user ID / request ID used as a label value
CONFIRM     label values like /customers/4711/summary in /metrics
FIX         route templates; "<unmatched>" bucket; metric_relabel_
            configs to drop the label until the fix deploys
PREVENTION  test that /metrics contains no IDs; review new labels
```

**T5. Logs exist but cannot be joined to traces.**

```text
SYMPTOM     log lines have trace_id null or IDs that match no trace
CHECK       is the log emitted inside an active span? middleware
            order? is the provider sampling the trace out?
CAUSES      logging outside the span (after it ended); sampled-out
            traces; thread/executor losing context; different
            ID format (decimal vs 32-hex)
FIX         log inside the span; ParentBased sampler; to_thread
            copies contextvars; format(trace_id, "032x")
PREVENTION  test asserting log trace_id equals incoming traceparent
```

**T6. Memory grows until the container is OOM-killed every day.**

```text
SYMPTOM     saw-tooth memory graph; restarts "fix" it; OOMKilled
CHECK       tracemalloc snapshot diff; unbounded caches; per-request
            clients never closed; huge result sets loaded at once
CAUSES      lru_cache without maxsize on high-cardinality args;
            module-level lists; new httpx.AsyncClient per call
FIX         bound caches; one shared client closed in lifespan;
            stream/paginate rows
PREVENTION  memory panel + alert on growth rate; soak test
```

## Unit Practice Project — Instrumented Orders API

### Project Goal

Take a working but slow reporting API, make it observable, and use the signals to find and fix four real production bugs:

- JSON logs with `request_id`, `trace_id`, `span_id`, extras and redaction;
- Prometheus RED metrics (`http_requests_total`, a latency histogram, an in-flight gauge) labeled by route template, at `/metrics`;
- OpenTelemetry traces with auto server spans and manual service, DB and outbound spans, and W3C propagation in both directions;
- fixes for a blocking call in `async def`, an N+1 query, a missing outbound timeout, and a high-cardinality label, each proven by a test;
- a load generator and a runbook.

### Architecture

```text
 OTel server span (FastAPIInstrumentor, outermost; reads traceparent)
  └ RequestIdMiddleware  X-Request-ID, ContextVar, access log line
     └ MetricsMiddleware  count, time, in-flight; route template
        └ routes.py
           ├ /customers/{customer_id}/summary   def  ─┐
           ├ /reports/revenue                   def  ─┤ ReportService
           ├ /reports/export        async + to_thread ┤  spans + 1 query
           │        └ legacy.render_report (sync)     │   └ SQLite
           └ /reports/revenue-fx    async ── FxClient (timeout, span,
                                             inject traceparent) ─► FX
 /metrics  ← Prometheus scrape (registry per app)
 errors.py → problem+json (404, 422, 502, 504) with request_id
```

### Requirements

1. Every log line is one JSON object with `timestamp`, `level`, `logger`, `message`, `request_id`, `trace_id`, `span_id`, plus `extra=` fields. Keys like `password` or `api_key` are written as `[REDACTED]`.
2. Every response carries `X-Request-ID`; a safe client ID is echoed, an unsafe one replaced.
3. One access log line per request with method, path, route template, status and `duration_ms`.
4. An incoming `traceparent` continues the trace: the access log's `trace_id` equals the incoming one.
5. `/metrics` exposes `http_requests_total{method,route,status}`, `http_request_duration_seconds` (histogram) and `http_requests_in_flight`. Labels use route templates; unmatched paths share `<unmatched>`; `/metrics` itself is not counted. Each app has its own registry.
6. Spans: `reports.revenue_by_customer` (child of the server span) and `SELECT customers` (CLIENT, with `db.*` attributes and row count); `fx.get_rate` (CLIENT) whose context is sent as `traceparent`.
7. `/reports/revenue` uses at most 2 SQL statements.
8. Five concurrent `/reports/export` calls with 0.2 s of blocking work each finish in well under 1 s.
9. The FX client has explicit timeouts. A timeout returns **504** problem+json; an upstream error returns **502**.
10. `scripts/load_test.py` prints request count, error rate, p50/p95/p99 and max.

### Technical Requirements

- Python 3.12+, FastAPI, SQLAlchemy 2.x, httpx, pydantic-settings (`APP_` prefix).
- `prometheus_client` with a dedicated `CollectorRegistry` per app.
- OpenTelemetry API/SDK, `opentelemetry-instrumentation-fastapi`, OTLP HTTP exporter (optional at runtime). Tests use `InMemorySpanExporter`.
- Tests: pytest, pytest-asyncio, respx (mock the FX service), `httpx.ASGITransport` for real concurrency.
- ruff (line length 76, `ASYNC` rules), mypy strict.

### Project Structure

{{tree projects/unit11-observability/solution}}

### Step-by-Step Implementation

1. **Reproduce before you fix.** Start the starter app and the fake FX service, run the load test against `/reports/export`, look at `/metrics`, and run `py-spy dump`.
   - *Why:* you need a baseline to prove the fix, and practice in reading the signals.
2. **TODO 1–2: JSON formatter and context filter.**
   - *Test:* `pytest -q tests/test_logging.py`.
3. **TODO 4: DB and service spans.**
   - *Test:* `pytest -q tests/test_tracing.py`. Set `APP_OTEL_EXPORTER=console` and look at the spans of one request.
4. **TODO 3: route template label.**
   - *Test:* `pytest -q tests/test_metrics.py`.
5. **TODO 5: N+1.** Look at the trace first: count the `SELECT` statements.
   - *Test:* `pytest -q -k n_plus_one`.
6. **TODO 6: blocking call.**
   - *Test:* `pytest -q -k event_loop`; re-run the load test and compare p50/p95.
7. **TODO 7–8: timeout and error mapping.** Start the fake FX with `FAKE_FX_DELAY=5` and call `/reports/revenue-fx` before and after.
   - *Test:* `pytest -q -k fx`.
8. **Finish:** `pytest -q && ruff check . && ruff format --check . && mypy`. Read the solution's `RUNBOOK.md` and add one entry of your own.

### Starter Code

{{file projects/unit11-observability/starter/app/observability/logging.py}}

{{file projects/unit11-observability/starter/app/services.py}}

The starter also has TODOs in `app/observability/metrics.py` (route template), `app/routes.py` (blocking call) and `app/fx.py` (timeout and error mapping). The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** call every endpoint, then find each request in the logs by `X-Request-ID` and in the spans by `trace_id`.
2. **Validation:** `currency=eur` (422), `/customers/abc/summary` (422), an unsafe `X-Request-ID`.
3. **Errors:**
   - FX service stopped → 502;
   - `FAKE_FX_DELAY=5` → 504 after about 2 s, not a hang;
   - unknown customer → 404 problem+json with `request_id`.
4. **Performance:** load test at concurrency 1, 10 and 50, before and after each fix; record p50/p95/p99 in a table.
5. **Extend:**
   - add `opentelemetry-instrumentation-httpx` and `-sqlalchemy` and remove the manual spans; compare;
   - add a `fx_request_duration_seconds` histogram labeled by outcome;
   - write Prometheus alert rules for a 99.5% availability SLO with multi-window burn rates;
   - log only 10% of successful access lines but all errors;
   - run an OpenTelemetry Collector locally and export OTLP to it.

### Hints

1. `record.created` is a Unix timestamp: `datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds")`.
2. A span context's IDs are integers; `format(ctx.trace_id, "032x")` gives the W3C hex form. Check `ctx.is_valid` first.
3. The matched route is in `scope["route"]` only *after* the app has run, so read it in the `finally` block.
4. `self._session.execute(stmt).all()` with the aggregate select returns `(id, name, count, total)` rows; order with `desc("total")`.
5. `asyncio.to_thread()` copies context variables, so the request ID and current span still work inside the thread.
6. `httpx.TimeoutException` is the base class of `ConnectTimeout`, `ReadTimeout`, `WriteTimeout` and `PoolTimeout`; catch it before `httpx.HTTPError`.

### Expected Behavior

```text
GET /customers/3/summary        → 200 {"order_count":4,"total_cents":12600}
GET /customers/999/summary      → 404 problem+json, request_id set
GET /reports/revenue            → 25 rows, 1 SQL statement
5 x GET /reports/export (0.2 s) → all done in ~0.2-0.3 s
GET /reports/revenue-fx, FX slow → 504 "Gateway Timeout" after 2 s
GET /reports/revenue-fx, FX down → 502 "Bad Gateway"
GET /metrics → http_requests_total{method="GET",
               route="/customers/{customer_id}/summary",status="200"}
GET /wp-admin/1.php             → counted as route="<unmatched>"
log: {"logger":"app.access","request_id":"…","trace_id":"…",…}
```

### Testing Requirements

- **Logging (5):** formatter fields, redaction, access log JSON with IDs, `traceparent` continuation, request-ID echo/replace.
- **Metrics (4):** route template, unmatched bucket, histogram and gauge exposed, registry isolation.
- **Tracing (2):** span names, parents and attributes; `traceparent` injected into the FX call.
- **Seeded bugs (5):** statement count, event loop not blocked, timeout configured, 504 and 502 mapping.
- **API (3)** and **load script (3)**.

```bash
pytest -q && ruff check . && ruff format --check . && mypy
```

### Final Runnable Solution

{{files projects/unit11-observability/solution}}

### How to Run

```bash
cd projects/unit11-observability/solution
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
uvicorn app.main:create_app --factory          # terminal 1, :8000
uvicorn scripts.fake_fx:app --port 9000        # terminal 2
python -m scripts.load_test \
    --url http://127.0.0.1:8000/reports/export \
    --requests 100 --concurrency 20            # terminal 3
```

### Verify the Solution

1. Solution: **22 passed**; `ruff check`, `ruff format --check` and `mypy` clean.
2. Starter: imports, ruff and mypy clean; **12 failed, 10 passed** (the logging, metrics-template, span, and all five seeded-bug tests fail until the TODOs are done).
3. Load test on `/reports/export` at concurrency 10 with 0.2 s render time: p50 about 0.2–0.25 s in the solution, about 1 s or more in the starter.
4. `curl -s localhost:8000/metrics | grep customers` shows only the `{customer_id}` template.
5. With `APP_OTEL_EXPORTER=console`, one request prints the server, service, and DB spans with the same `trace_id` as its access log line.

### Project Interview Debrief

1. **How did you find the blocking call?**
   The load test showed latency growing linearly with concurrency while CPU stayed low, which points to waiting on a single thread. `py-spy dump` showed the event loop thread inside `time.sleep` in the renderer. The concurrency test now fails if anyone reintroduces it.
2. **Why use the route template as a label?**
   Each label value is a time series. Raw paths create one series per customer and per bot URL, which exhausts Prometheus memory. The template keeps cardinality bounded; the concrete path is still in the access log.
3. **Why is the FX timeout part of correctness, not just performance?**
   Without it, one hung upstream holds connections and requests until the worker is saturated, turning a dependency problem into a full outage. With it, the failure is bounded, visible as 504, and the rest of the API keeps working.
4. **Why a registry and tracer provider per app instead of globals?**
   Globals can only be set once per process and leak state between tests (duplicate series, spans from earlier tests). Per-app objects make tests isolated and the factory honest. In production there is one app per process, so the effect is the same.
5. **What would you add before production?**
   An OpenTelemetry Collector with tail sampling, httpx and SQLAlchemy auto-instrumentation, SLO-based burn-rate alerts with a runbook link, exemplars linking latency buckets to traces, log sampling for successful requests, continuous profiling, and a dashboard with deploy markers.
