## Unit 45 — AI Observability and Tracing

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Explain** traces, spans, span context, attributes, events, links, metrics and logs in OpenTelemetry, and how context propagates across process and agent boundaries.
2. **Implement** one trace that spans the API request, agent loop, retriever, model calls and tools, using the OpenTelemetry GenAI semantic conventions (and **identify** which parts are experimental).
3. **Attribute** latency, errors, tokens and cost to specific spans, models, tenants and features.
4. **Correlate** work across agents, queues and asynchronous approvals with W3C Trace Context propagation and span links.
5. **Design** safe metadata and content logging: opt-in content capture, redaction, pseudonymization, separate restricted content stores, retention.
6. **Record** provenance — model, prompt, index, embedding model and policy versions — on every relevant span.
7. **Inject** retrieval, model and tool failures and **diagnose** them from traces.
8. **Record** evaluation outcomes alongside operational telemetry and **build** dashboards that support incident reconstruction.

### 2. Prerequisite Knowledge

* Agent loop, tools, retrieval, approvals (Units 41–44).
* Basic observability vocabulary: logs, metrics (counters, histograms), traces; percentiles.
* HTTP headers, async Python (`contextvars` — OpenTelemetry's Python context is built on them, so it follows `await` boundaries automatically within a task).
* Unit 44's distinction: *observability = what happened; evaluation = was it good*.

### 3. Mental Model

A trace is a **flight recorder for one business operation**.

```
trace_id = 4bf9…  ("customer asks about a refund")
│
├─ POST /v1/agent/chat                        SERVER    1.9 s
│  └─ invoke_agent support_agent              INTERNAL  1.8 s   prompt=v14 policy=2026-10-01
│     ├─ retrieval kb-acme                    CLIENT    120 ms  index=2026-10-05 docs=[…] top=0.91
│     ├─ chat model-large-2026-08             CLIENT    640 ms  in=1850 out=42 finish=tool_use
│     ├─ execute_tool get_order               INTERNAL   45 ms  decision=allow
│     │  └─ GET orders-api /orders/{id}       CLIENT     40 ms
│     ├─ chat model-large-2026-08             CLIENT    910 ms  in=2300 out=120 finish=end_turn
│     └─ (proposal created → approval later, linked by span link)
└─ evaluate support_agent  (async, separate trace, LINKED)  task_success=true faithfulness=1.0
```

* Every box is a **span** with a start, end, status and attributes.
* Parent–child relationships come from **context propagation** (in-process via `contextvars`; across services via the `traceparent` header).
* **Metrics** aggregate across many traces (p95 latency, tokens per model, error rate); **traces** explain individual operations; **logs** carry details and are correlated by `trace_id`.
* **Evaluation results** are joined to traces so you can ask "show me slow *and* wrong answers on prompt v14".

### 4. Comprehensive Theory

#### 4.1 OpenTelemetry Building Blocks

| Concept | Definition | Agent example |
|---|---|---|
| **Trace** | Tree (DAG) of spans sharing a `trace_id` | One user request to the agent |
| **Span** | A timed operation with name, kind, attributes, events, status, links | `chat model-x`, `execute_tool get_order` |
| **Span kind** | SERVER, CLIENT, INTERNAL, PRODUCER, CONSUMER | Model call = CLIENT; in-process agent = INTERNAL |
| **Attributes** | Key–value metadata | `gen_ai.request.model`, `gen_ai.usage.input_tokens` |
| **Events** | Timestamped annotations within a span | exception, "policy_denied" |
| **Links** | References to spans in other traces | Async evaluation → judged trace; approval resume → original request |
| **Context propagation** | Carrying trace context across boundaries | `traceparent` header; message metadata on queues |
| **Resource** | Attributes of the emitting entity | `service.name`, `service.version`, `deployment.environment.name` |
| **Metrics** | Counters, histograms, gauges with attributes | token usage histogram by model |
| **Logs** | Structured records, correlated by trace/span IDs | redacted decision logs |
| **Collector** | Vendor-neutral pipeline: receive → process → export | tail sampling, attribute redaction, routing |

**Why OpenTelemetry.** It is the CNCF standard for vendor-neutral telemetry; you instrument once and export via OTLP to any backend (Jaeger, Tempo, Honeycomb, Datadog, Langfuse, Arize Phoenix, etc.). Many LLM observability tools ingest OTel GenAI spans.

#### 4.2 GenAI Semantic Conventions (Experimental)

The OpenTelemetry **GenAI semantic conventions** define standard span names and attributes for model calls, agents, tools, retrieval and related metrics. Status: **Development** (experimental) — names have changed between releases, and the conventions moved from the main `semantic-conventions` repository to a dedicated `semantic-conventions-genai` repository. Instrumentations emitting older versions may require an opt-in environment variable to emit the latest experimental names; check your instrumentation's docs. **Pin a version and re-verify on upgrade.**

Key conventions (as of the current Development version):

| Operation | Span name | Selected attributes |
|---|---|---|
| Model inference | `{gen_ai.operation.name} {gen_ai.request.model}` e.g. `chat model-x` | `gen_ai.operation.name` (`chat`, `generate_content`, `text_completion`, `embeddings`), `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.request.max_tokens`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `gen_ai.response.id`, `error.type` |
| Retrieval | `retrieval {gen_ai.data_source.id}` | `gen_ai.operation.name=retrieval`, `gen_ai.data_source.id`; opt-in `gen_ai.retrieval.query.text`, `gen_ai.retrieval.documents` |
| Tool execution | `execute_tool {gen_ai.tool.name}` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type`; opt-in `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` |
| Agent | `invoke_agent {gen_ai.agent.name}` | `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.conversation.id`; kind CLIENT for remote agent services, INTERNAL for in-process frameworks |
| Workflow / planning | `invoke_workflow {name}`, `plan {agent}`, `create_agent {agent}` | |
| Content (all opt-in) | — | `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions` |

Metrics include `gen_ai.client.operation.duration` and token-usage histograms (the token metric's name and shape have been revised across versions — e.g. older `gen_ai.client.token.usage` with a `gen_ai.token.type` attribute — so confirm against the version you pin). Agent-level metrics (agent invocation duration, tool-call counts) are also being defined.

**Note on `gen_ai.system`:** older versions used `gen_ai.system` to identify the provider; current versions use `gen_ai.provider.name`. Treat `gen_ai.system` as **legacy**.

**Custom attributes.** Anything not covered (prompt version, index version, policy decision, cost) goes under your own namespace (e.g. `app.*`), consistently named and documented.

#### 4.3 One Trace Across API, Agent, Retriever, Model and Tools

**How it works in Python.**

* Auto-instrumentation creates the SERVER span for FastAPI (`opentelemetry-instrumentation-fastapi`), CLIENT spans for `httpx`/`requests`, DB spans for SQLAlchemy/asyncpg, and (where available) GenAI spans for provider SDKs via instrumentation libraries.
* Your agent code creates INTERNAL/CLIENT spans with `tracer.start_as_current_span(...)`. Because the OTel context lives in `contextvars`, spans started inside `await`ed coroutines become children automatically.
* **Gotcha — concurrency:** `asyncio.create_task` copies the current context, so tasks inherit the parent; thread pools (`run_in_executor`, `anyio.to_thread`) may need explicit context passing (`contextvars.copy_context().run(...)`) depending on the API; background jobs started *after* the request finishes should use a *link*, not a parent.

**Design considerations.** One span per meaningful unit (model call, tool call, retrieval, policy decision, approval) — not per function. Name spans with low-cardinality names (`execute_tool get_order`, not `execute_tool get_order ord_123`); put IDs in attributes.

#### 4.4 Span Attribution for Latency, Errors and Tokens

* **Latency**: span durations show where time goes (model vs retrieval vs tools vs your code — the gap between child spans is your own overhead). Time-to-first-token for streaming can be recorded as an event or attribute.
* **Errors**: set span status `ERROR` with `error.type` (low-cardinality category like `timeout`, `rate_limited`, `provider_overloaded`, `validation_failed`) and `record_exception` for details. Distinguish *handled* degradation (span error, operation succeeded with fallback) from *failed operation* (root span error).
* **Tokens and cost**: tokens on each model span; cost computed from a versioned price table (not a semantic convention — use a custom attribute and metric). Aggregate by model, tenant, feature, agent and prompt version to find who/what spends.
* **Agent-specific**: number of turns, tool calls, stop reason, retries, validation failures — attributes on the `invoke_agent` span.

#### 4.5 Cross-Agent Correlation

**Synchronous calls (HTTP/gRPC between agents/services):** inject W3C `traceparent` (and optionally `tracestate`) into outgoing headers; extract in the callee. Auto-instrumentation does this for supported clients/servers.

**Asynchronous messaging (queues, Kafka, approval workflows):** inject context into message headers/metadata; consumer extracts it. For long gaps (approval after 3 hours) or fan-in (one batch processing many requests), prefer **span links** to avoid absurd multi-hour traces and to represent many-to-one relationships.

**Multi-agent systems:** each agent has its own `invoke_agent` span (`gen_ai.agent.name`), with handoffs as child spans or links; propagate a *business correlation ID* (e.g. `conversation.id`, `case_id`) as an attribute so you can search all traces for a case.

**Baggage caution:** OTel Baggage propagates key–values to *all* downstream services (including third parties). Never put PII or secrets in baggage.

#### 4.6 Safe Metadata and Content Logging

Telemetry is a data store that often has broader access and longer retention than your production database. Treat it accordingly.

| Data | Default | How |
|---|---|---|
| Model/provider/version, token counts, latencies, finish reasons, tool names, decision outcomes, doc IDs | **Capture** | Attributes/metrics |
| User identifiers | **Pseudonymize** | Keyed HMAC (not plain hash) |
| Tenant ID | Capture if not sensitive | Attribute (watch cardinality in metrics) |
| Prompts, completions, retrieved text, tool arguments/results | **Off by default** (semconv marks them opt-in) | Enable per environment/tenant with redaction; or store in a restricted content store keyed by trace ID |
| Secrets, auth headers | **Never** | Scrub in SDK and Collector |

**Patterns:**

* **Redact at the source** (before export) and **again in the Collector** (defense in depth: `attributes`/`transform`/`redaction` processors).
* **Two-tier storage**: metadata in the general observability backend; content (when needed for debugging/evals) in a restricted store with short retention and access logging, referenced by `trace_id`.
* **Sampling**: head sampling (decide at trace start) reduces cost; **tail sampling** in the Collector keeps all error/slow traces and a fraction of the rest.
* **Retention and deletion**: align with privacy policy; support data-subject deletion by pseudonym mapping if required.

#### 4.7 Model, Prompt and Index Provenance

To explain a behaviour change you must know *exactly* what produced it. Record on spans:

* `gen_ai.request.model` and `gen_ai.response.model` (aliases like "latest" resolve to concrete versions — record the response model).
* Prompt template ID and version (`app.prompt.version`), and a hash of the rendered system prompt if templates are dynamic.
* Retrieval index ID and build version, embedding model and version, chunker version, reranker version.
* Tool schema version, policy version, decision schema version.
* Service version (git SHA) and deployment environment (resource attributes).
* Feature flags / experiment arm (Unit 46 canaries).

Provenance turns "quality dropped on Tuesday" into "quality dropped for traces with `app.index.version=2026-10-05`".

#### 4.8 Dashboards and Incident Reconstruction

**Dashboards (per agent, filterable by provenance):**

* Traffic, error rate by `error.type`, p50/p95/p99 latency (overall and by span type).
* Tokens and cost per request, per successful task, per tenant/model.
* Agent behaviour: turns per session, tool-call distribution, stop reasons, validation failure rate, approval rate, refusal rate.
* Retrieval: empty-result rate, top-score distribution, index version mix.
* Quality (from online evals, Unit 44): task success, faithfulness, forbidden-behaviour count — by prompt/model/index version.

**Incident reconstruction procedure:**

1. Start from a symptom (customer report, alert, audit record) → find `trace_id` (from audit table, logs or support ticket).
2. Walk the trace: which spans errored or were slow? Which tool calls happened with which decisions?
3. Check provenance attributes: what changed (model/prompt/index version) vs a good trace?
4. If permitted, fetch content from the restricted store for the trace.
5. Correlate with metrics (is it one trace or a trend?).
6. Convert to an eval case (Unit 44) and write the post-incident review.

### 5. Internal Mechanics

#### 5.1 What happens when you start a span in Python

```
tracer.start_as_current_span("chat model-x")
  → get current Context from contextvars (contains parent span, if any)
  → Sampler decides (ParentBased(TraceIdRatioBased(r)) is common) → RECORD_AND_SAMPLE or DROP
  → new SpanContext(trace_id = parent's or new random 128-bit, span_id = new 64-bit, flags)
  → Span object records start time; attributes set via set_attribute (validated types: str/bool/int/float/sequences)
  → context with this span set as current is attached (token saved)
  ... your code (awaits keep the same contextvars context) ...
  → on exit: end time recorded, status set, context detached (token restored)
  → SpanProcessor.on_end → BatchSpanProcessor queues → exporter sends OTLP (gRPC/HTTP) in background
```

* Spans are **not** sent when they start; they are exported after they end (batch processor), so a crashed process may lose in-flight spans — call `provider.shutdown()` on graceful shutdown (FastAPI lifespan).
* Attribute values must be primitives or homogeneous sequences; complex objects must be serialized (and respect size limits — SDKs truncate/limit attribute counts and lengths, configurable via env vars like `OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT`).

#### 5.2 W3C Trace Context

`traceparent: 00-<32 hex trace-id>-<16 hex parent-span-id>-<2 hex flags>`. The callee creates its span as a child of the parent span ID. `tracestate` carries vendor-specific data. Propagators are configured globally (`OTEL_PROPAGATORS=tracecontext,baggage` by default).

#### 5.3 Where the Collector fits

```
app SDK ──OTLP──> Collector [receivers: otlp] → [processors: memory_limiter, redaction/transform,
                                                 tail_sampling, batch] → [exporters: traces backend,
                                                 metrics backend, restricted content store]
```

The Collector centralizes policy (redaction, sampling, routing) so that every service doesn't reimplement it, and so a misconfigured service can't leak content to the general backend.

### 6. Implementation Examples

#### Example 1 — Minimal: a span with GenAI attributes (Runnable)

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("demo")

with tracer.start_as_current_span("chat model-x", kind=trace.SpanKind.CLIENT) as span:
    span.set_attribute("gen_ai.operation.name", "chat")
    span.set_attribute("gen_ai.provider.name", "example_provider")
    span.set_attribute("gen_ai.request.model", "model-x")
    span.set_attribute("gen_ai.usage.input_tokens", 812)
    span.set_attribute("gen_ai.usage.output_tokens", 64)
```

#### Example 2 — Realistic and production-oriented: one traced agent workflow with injected failures, cost attribution, provenance, privacy and eval linkage (Runnable)

**Architecture.** A simulated HTTP server span propagates W3C context to `invoke_agent`; the agent creates `retrieval`, `chat` and `execute_tool` spans following GenAI conventions; failures are injected per dependency; costs come from a price table; provenance is attached to the agent span; user IDs are pseudonymized; content capture is opt-in; an asynchronous evaluation span **links** to the agent span it judged. An in-memory exporter makes it runnable without a backend.

```python
# traced_agent.py — one OpenTelemetry trace across request → agent → retriever → model → tools.
# pip install opentelemetry-sdk   (exporter: opentelemetry-exporter-otlp for a real backend)
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from decimal import Decimal

from opentelemetry import metrics, propagate, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

# ----------------------------------------------------------------------------- setup
RESOURCE = Resource.create({
    "service.name": "supportops-agent",
    "service.version": "2026.10.1",
    "deployment.environment.name": "staging",
})
EXPORTER = InMemorySpanExporter()                      # swap for OTLPSpanExporter in production
_provider = TracerProvider(resource=RESOURCE)
_provider.add_span_processor(SimpleSpanProcessor(EXPORTER))   # BatchSpanProcessor in production
trace.set_tracer_provider(_provider)
METRIC_READER = InMemoryMetricReader()
metrics.set_meter_provider(MeterProvider(resource=RESOURCE, metric_readers=[METRIC_READER]))

tracer = trace.get_tracer("supportops.agent", "1.0.0")
meter = metrics.get_meter("supportops.agent", "1.0.0")
token_usage = meter.create_histogram("gen_ai.client.token.usage", unit="{token}",
                                     description="Tokens per model call (check current semconv name)")
op_duration = meter.create_histogram("gen_ai.client.operation.duration", unit="s")
cost_counter = meter.create_counter("app.llm.cost", unit="USD")

# Provenance of everything that can change behaviour without a code change.
PROVENANCE = {
    "app.prompt.id": "support_system",
    "app.prompt.version": "v14",
    "app.index.id": "kb-acme",
    "app.index.version": "2026-10-05T02:00Z",
    "app.embedding.model": "text-embed-v3",
    "app.policy.version": "2026-10-01",
}
PRICE_PER_MTOK = {"model-large-2026-08": (Decimal("3.00"), Decimal("15.00"))}  # (input, output)

CAPTURE_CONTENT = os.getenv("APP_CAPTURE_GENAI_CONTENT", "false") == "true"   # opt-in only
_PSEUDONYM_KEY = os.getenv("APP_PSEUDONYM_KEY", "dev-only-key").encode()


def pseudonymize(value: str) -> str:
    """Keyed hash: correlate the same user across spans without storing the identifier."""
    return hmac.new(_PSEUDONYM_KEY, value.encode(), hashlib.sha256).hexdigest()[:16]


# ----------------------------------------------------------------------------- fake dependencies
class InjectedFailure(Exception):
    pass


@dataclass
class Faults:
    retriever_timeout: bool = False
    model_error: bool = False
    tool_error: bool = False


async def fake_retrieve(query: str, faults: Faults) -> list[tuple[str, float]]:
    await asyncio.sleep(0.01)
    if faults.retriever_timeout:
        raise TimeoutError("vector store timed out after 2s")
    return [("kb_refund_timing", 0.91), ("kb_shipping", 0.72)]


async def fake_model(turn: int, faults: Faults) -> dict:
    await asyncio.sleep(0.02)
    if faults.model_error:
        raise InjectedFailure("provider 529 overloaded")
    if turn == 0:
        return {"model": "model-large-2026-08", "finish": "tool_use", "in": 1850, "out": 42,
                "tool": ("get_order", {"order_id": "ord_aaaaaaaaaaaa"})}
    return {"model": "model-large-2026-08", "finish": "end_turn", "in": 2300, "out": 120, "tool": None}


async def fake_tool(name: str, args: dict, faults: Faults) -> dict:
    await asyncio.sleep(0.005)
    if faults.tool_error:
        raise InjectedFailure("orders-api 503")
    return {"order_id": args["order_id"], "status": "delivered"}


# ----------------------------------------------------------------------------- instrumented steps
async def traced_retrieval(query: str, faults: Faults) -> list[str]:
    with tracer.start_as_current_span("retrieval kb-acme", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "retrieval")
        span.set_attribute("gen_ai.data_source.id", "kb-acme")
        span.set_attribute("app.index.version", PROVENANCE["app.index.version"])
        span.set_attribute("app.retrieval.top_k", 5)
        try:
            hits = await fake_retrieve(query, faults)
        except TimeoutError as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, "retrieval timeout"))
            span.set_attribute("error.type", "timeout")
            return []                                     # degrade: answer without KB (Unit 46)
        span.set_attribute("app.retrieval.doc_ids", [d for d, _ in hits])   # IDs, not content
        span.set_attribute("app.retrieval.top_score", hits[0][1] if hits else 0.0)
        return [d for d, _ in hits]


async def traced_chat(turn: int, messages: list[dict], faults: Faults) -> dict:
    model = "model-large-2026-08"
    with tracer.start_as_current_span(f"chat {model}", kind=SpanKind.CLIENT) as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "example_provider")
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.request.max_tokens", 1024)
        span.set_attribute("app.prompt.version", PROVENANCE["app.prompt.version"])
        if CAPTURE_CONTENT:                                 # opt-in, redacted upstream
            span.set_attribute("gen_ai.input.messages", str(messages)[:4000])
        start = time.perf_counter()
        try:
            r = await fake_model(turn, faults)
        except InjectedFailure as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.set_attribute("error.type", "provider_overloaded")
            op_duration.record(time.perf_counter() - start,
                               {"gen_ai.request.model": model, "error.type": "provider_overloaded"})
            raise
        span.set_attribute("gen_ai.response.model", r["model"])
        span.set_attribute("gen_ai.response.finish_reasons", [r["finish"]])
        span.set_attribute("gen_ai.usage.input_tokens", r["in"])
        span.set_attribute("gen_ai.usage.output_tokens", r["out"])
        p_in, p_out = PRICE_PER_MTOK[r["model"]]
        cost = (p_in * r["in"] + p_out * r["out"]) / Decimal(1_000_000)
        span.set_attribute("app.llm.cost_usd", float(cost))
        attrs = {"gen_ai.request.model": model, "gen_ai.response.model": r["model"]}
        token_usage.record(r["in"], {**attrs, "gen_ai.token.type": "input"})
        token_usage.record(r["out"], {**attrs, "gen_ai.token.type": "output"})
        op_duration.record(time.perf_counter() - start, attrs)
        cost_counter.add(float(cost), {"gen_ai.request.model": model, "tenant.tier": "enterprise"})
        return r


async def traced_tool(name: str, call_id: str, args: dict, faults: Faults) -> dict:
    with tracer.start_as_current_span(f"execute_tool {name}", kind=SpanKind.INTERNAL) as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", name)
        span.set_attribute("gen_ai.tool.call.id", call_id)
        span.set_attribute("gen_ai.tool.type", "function")
        span.set_attribute("app.policy.decision", "allow")
        try:
            return await fake_tool(name, args, faults)
        except InjectedFailure as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.set_attribute("error.type", "dependency_unavailable")
            return {"error": "tool_failed"}


async def invoke_agent(user_id: str, tenant_id: str, question: str, faults: Faults,
                       carrier: dict[str, str] | None = None) -> dict:
    # Continue a trace started upstream (HTTP gateway or another agent) if headers are present.
    parent_ctx = propagate.extract(carrier or {})
    with tracer.start_as_current_span("invoke_agent support_agent", context=parent_ctx,
                                      kind=SpanKind.INTERNAL) as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.agent.name", "support_agent")
        span.set_attribute("gen_ai.conversation.id", "sess_123")
        span.set_attribute("app.user.pseudonym", pseudonymize(user_id))
        span.set_attribute("app.tenant.id", tenant_id)
        for k, v in PROVENANCE.items():
            span.set_attribute(k, v)
        docs = await traced_retrieval(question, faults)
        messages: list[dict] = [{"role": "user", "content": question}]
        try:
            for turn in range(4):                                   # bounded loop
                r = await traced_chat(turn, messages, faults)
                if r["tool"] is None:
                    span.set_attribute("app.agent.stop_reason", "final_answer")
                    span.set_attribute("app.agent.turns", turn + 1)
                    ctx = span.get_span_context()
                    return {"answer": "Your order was delivered.", "docs": docs,
                            "trace_id": format(ctx.trace_id, "032x"),
                            "span_id": format(ctx.span_id, "016x")}
                name, args = r["tool"]
                result = await traced_tool(name, f"call_{turn}", args, faults)
                messages.append({"role": "tool", "content": str(result)})
            span.set_attribute("app.agent.stop_reason", "max_turns")
            return {"answer": "Escalated.", "docs": docs}
        except InjectedFailure:
            span.set_status(Status(StatusCode.ERROR, "model unavailable"))
            span.set_attribute("error.type", "model_unavailable")
            span.set_attribute("app.agent.stop_reason", "model_error")
            return {"answer": "Sorry, I'm having trouble right now.", "degraded": True,
                    "trace_id": format(span.get_span_context().trace_id, "032x")}


def record_eval_outcome(trace_id_hex: str, span_id_hex: str, case_id: str,
                        task_success: bool, faithfulness: float) -> None:
    """Attach an (asynchronous) evaluation result to the agent span it judged, via a span link."""
    linked = trace.SpanContext(trace_id=int(trace_id_hex, 16), span_id=int(span_id_hex, 16),
                               is_remote=True, trace_flags=trace.TraceFlags(0x01))
    with tracer.start_as_current_span("evaluate support_agent", links=[trace.Link(linked)]) as span:
        span.set_attribute("app.eval.case_id", case_id)
        span.set_attribute("app.eval.task_success", task_success)
        span.set_attribute("app.eval.faithfulness", faithfulness)
        span.set_attribute("app.eval.judge.version", "judge-v3")
        span.set_attribute("app.eval.target_trace_id", trace_id_hex)


# ----------------------------------------------------------------------------- demo
def print_tree() -> None:
    spans = EXPORTER.get_finished_spans()
    by_parent: dict[int | None, list] = {}
    for s in spans:
        by_parent.setdefault(s.parent.span_id if s.parent else None, []).append(s)

    def walk(parent: int | None, depth: int) -> None:
        for s in sorted(by_parent.get(parent, []), key=lambda x: x.start_time):
            ms = (s.end_time - s.start_time) / 1e6
            err = f" ERROR({s.attributes.get('error.type')})" if s.status.status_code is StatusCode.ERROR else ""
            tok = s.attributes.get("gen_ai.usage.input_tokens")
            extra = f" tokens={tok}+{s.attributes.get('gen_ai.usage.output_tokens')}" if tok else ""
            print(f"{'  ' * depth}{s.name:<34} {ms:6.1f} ms{extra}{err}")
            walk(s.context.span_id, depth + 1)
    walk(None, 0)


async def main() -> None:
    # Simulate an upstream HTTP server span and propagate W3C trace context to the agent.
    with tracer.start_as_current_span("POST /v1/agent/chat", kind=SpanKind.SERVER) as http:
        http.set_attribute("http.request.method", "POST")
        http.set_attribute("http.route", "/v1/agent/chat")
        carrier: dict[str, str] = {}
        propagate.inject(carrier)                      # {'traceparent': '00-<trace>-<span>-01'}
        ok = await invoke_agent("jane@example.com", "acme", "Where is my order?", Faults(), carrier)
    print("== healthy run", carrier["traceparent"])
    print_tree()
    EXPORTER.clear()

    for label, faults in [("retriever timeout", Faults(retriever_timeout=True)),
                          ("tool failure", Faults(tool_error=True)),
                          ("model outage", Faults(model_error=True))]:
        await invoke_agent("jane@example.com", "acme", "Where is my order?", faults)
        print(f"== {label}")
        print_tree()
        EXPORTER.clear()

    record_eval_outcome(ok["trace_id"], ok["span_id"], "kb-001", task_success=True, faithfulness=1.0)
    ev = EXPORTER.get_finished_spans()[0]
    print("== eval span", ev.name, dict(ev.attributes), "links:", len(ev.links))


if __name__ == "__main__":
    asyncio.run(main())
```

Output (durations will vary):

```
== healthy run 00-06bb36bef6da7ea765ed56509d2121b1-366a11bbe60305f5-03
POST /v1/agent/chat                  57.6 ms
  invoke_agent support_agent           57.5 ms
    retrieval kb-acme                    10.3 ms
    chat model-large-2026-08             21.1 ms tokens=1850+42
    execute_tool get_order                5.3 ms
    chat model-large-2026-08             20.5 ms tokens=2300+120
== retriever timeout
invoke_agent support_agent           57.6 ms
  retrieval kb-acme                    11.1 ms ERROR(timeout)
  chat model-large-2026-08             20.4 ms tokens=1850+42
  execute_tool get_order                5.3 ms
  chat model-large-2026-08             20.4 ms tokens=2300+120
== tool failure
invoke_agent support_agent           59.1 ms
  retrieval kb-acme                    10.2 ms
  chat model-large-2026-08             22.4 ms tokens=1850+42
  execute_tool get_order                5.7 ms ERROR(dependency_unavailable)
  chat model-large-2026-08             20.4 ms tokens=2300+120
== model outage
invoke_agent support_agent           32.5 ms ERROR(model_unavailable)
  retrieval kb-acme                    10.2 ms
  chat model-large-2026-08             21.9 ms ERROR(provider_overloaded)
== eval span evaluate support_agent {'app.eval.case_id': 'kb-001', 'app.eval.task_success': True, 'app.eval.faithfulness': 1.0, 'app.eval.judge.version': 'judge-v3', 'app.eval.target_trace_id': '06bb36bef6da7ea765ed56509d2121b1'} links: 1
```

**Reading the traces.**

* *Retriever timeout*: `retrieval` span is ERROR with `error.type=timeout`, but the agent span is OK — the agent degraded (answered without KB). Dashboards should show "degraded success", and online evals should check whether answers without retrieval were grounded.
* *Tool failure*: `execute_tool` ERROR; the model continued with an error result. Check that the final answer didn't claim success (an eval check).
* *Model outage*: `chat` ERROR `provider_overloaded` and the root agent span ERROR `model_unavailable`; the user received a fallback message (Unit 46 adds circuit breaking).
* *Eval span*: a separate trace that **links** to the agent span with task success and faithfulness — queryable together with provenance.

**Wiring into FastAPI (production).**

```python
# app/telemetry.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

def setup_telemetry(app: FastAPI, *, service_version: str, environment: str) -> TracerProvider:
    resource = Resource.create({"service.name": "supportops-agent",
                                "service.version": service_version,
                                "deployment.environment.name": environment})
    tp = TracerProvider(resource=resource, sampler=ParentBased(TraceIdRatioBased(0.2)))
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))   # endpoint via OTEL_EXPORTER_OTLP_ENDPOINT
    trace.set_tracer_provider(tp)
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[
        PeriodicExportingMetricReader(OTLPMetricExporter())]))
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz")
    HTTPXClientInstrumentor().instrument()
    return tp

@asynccontextmanager
async def lifespan(app: FastAPI):
    tp = setup_telemetry(app, service_version="2026.10.1", environment="prod")
    yield
    tp.shutdown()            # flush pending spans on graceful shutdown
```

Head sampling at 20% here; keep *all* errors and slow traces with **tail sampling** in the Collector:

```yaml
# otel-collector.yaml (excerpt)
processors:
  memory_limiter: {check_interval: 1s, limit_percentage: 80, spike_limit_percentage: 20}
  attributes/scrub:
    actions:
      - {key: gen_ai.input.messages,  action: delete}     # content never reaches general backend
      - {key: gen_ai.output.messages, action: delete}
      - {key: http.request.header.authorization, action: delete}
  tail_sampling:
    decision_wait: 10s
    policies:
      - {name: errors, type: status_code, status_code: {status_codes: [ERROR]}}
      - {name: slow,   type: latency,     latency: {threshold_ms: 5000}}
      - {name: sample, type: probabilistic, probabilistic: {sampling_percentage: 10}}
  batch: {}
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, attributes/scrub, tail_sampling, batch]
      exporters: [otlp/backend]
```

(If you head-sample at 20% in the SDK, tail sampling can only choose among that 20%; to keep *all* errors, send 100% from SDKs to the Collector and sample there — a cost trade-off.)

**Correlating logs.** Add `trace_id`/`span_id` to structured logs (e.g., `opentelemetry-instrumentation-logging` or a custom `logging.Filter` reading `trace.get_current_span().get_span_context()`), so audit and decision logs (Units 41–43) join to traces.

### 7. Comparative Analysis

| Comparison | Key difference | Use | Trap |
|---|---|---|---|
| **Trace vs eval** | What happened vs was it good | Join eval results to traces | "Trace looks fine" ≠ answer correct |
| **Traces vs metrics vs logs** | Single operation detail vs aggregates vs discrete records | Metrics alert, traces explain, logs detail | High-cardinality IDs in metric labels |
| **Parent-child vs span link** | Synchronous causality vs related/async/fan-in | Links for approvals, batch jobs, async evals | 6-hour traces |
| **Head vs tail sampling** | Decide at start vs after completion | Tail to keep errors/slow; head for cost | Losing the only failing trace to head sampling |
| **Content capture on vs off** | Debuggability vs privacy risk | Off by default; restricted store when needed | Prompts with PII in a broadly accessible backend |
| **OTel GenAI conventions vs vendor SDK tracing** | Vendor-neutral standard (experimental) vs proprietary | OTel for portability; vendor features on top | Locking traces into one vendor format |
| **Plain hash vs keyed HMAC for user IDs** | Reversible by dictionary vs requires key | HMAC | SHA-256 of an email is guessable |

### 8. Failure Modes and Debugging

**F1 — Broken traces (orphan spans).** SYMPTOM: tool spans appear as separate root traces. CAUSE: work moved to a thread pool/background task without context; missing propagation through a queue. INVESTIGATE: compare `parent_span_id`s; check where the context is lost. FIX: `contextvars.copy_context()` for threads; inject/extract on queues; links for background jobs.

**F2 — Token cost doesn't match the invoice.** CAUSE: retries not instrumented; cached tokens or embeddings not counted; sampling drops spans used for cost. FIX: compute cost from **metrics** (unsampled) not from sampled traces; include retries, embeddings, judges.

**F3 — PII in the observability backend.** CAUSE: content capture enabled by default in an instrumentation library; exception messages containing user text. FIX: disable capture; Collector scrub; review `record_exception` messages; purge per policy.

**F4 — Metric cardinality explosion.** CAUSE: `user_id` or `order_id` as a metric attribute. FIX: IDs only on spans; metrics by low-cardinality dimensions (model, tenant tier, operation, error.type).

**F5 — Can't explain a quality drop.** CAUSE: no provenance attributes; "latest" model alias. FIX: record response model, prompt/index versions; dashboards by version.

**F6 — Trace missing during outages.** CAUSE: exporter blocked/backpressure; process killed before flush. FIX: batch processor with bounded queue (drops rather than blocks), graceful shutdown flush, Collector close to the app (sidecar/agent).

**Fault-injection drill (practice).** Use the `Faults` flags in Example 2 (or a proxy like Toxiproxy in integration environments) to inject: retriever timeout, empty retrieval, model 429/529, malformed model output (validation failure), tool 503, policy-service timeout. For each, predict the trace shape, then confirm.

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Span design.* Draw the expected trace tree for a request that retrieves, calls the model twice, executes two tools (one denied by policy) and creates an approval proposal. Hints: Is the policy decision a span or an attribute? What links the later approval?

*1.2 Attribute triage.* Classify 25 candidate attributes as span attribute, metric attribute, opt-in content, or never-record. Hints: cardinality and sensitivity.

**Level 2 — Implementation**

*2.1 Instrument the agent loop.* Add GenAI spans to your Unit 41 agent (agent, chat, tool, retrieval) with provenance. Tests: in-memory exporter asserts span names, parentage and required attributes. Hints: `InMemorySpanExporter`, check `span.parent.span_id`.

*2.2 Cost attribution.* Add a price table and a cost counter by model and tenant tier; produce a per-request cost attribute. Tests: known tokens → known cost. Hints: `Decimal` for prices; metrics in floats.

*2.3 Safe logging.* Implement opt-in content capture with redaction and a restricted content store keyed by trace ID. Tests: with capture off, no content attributes exist.

**Level 3 — Integration**

*3.1 Cross-agent trace.* Split SupportOps into a router agent service and a refund agent service (two FastAPI apps). Propagate context via HTTP. Tests: one trace ID across both; agent spans named per agent.

*3.2 Approval linkage.* When an approval resumes the agent hours later, start a new trace linked to the original. Tests: link exists; audit row stores both trace IDs.

*3.3 Eval join.* Record online eval outcomes as linked spans or as rows keyed by trace ID; build a query "faithfulness < 0.5 by prompt version". 

**Level 4 — Debugging / Production Scenario**

*4.1 What's wrong with this instrumentation?*

```python
with tracer.start_as_current_span(f"llm call for {user.email} order {order_id}") as s:
    s.set_attribute("prompt", full_prompt)
    s.set_attribute("user", user.email)
    token_hist.record(n, {"user_id": user.id, "order_id": order_id})
    loop.run_in_executor(None, call_tool, args)      # tool span appears as a new trace
```

Hints: span-name cardinality and PII; content capture; metric cardinality; context loss across executor.

*4.2 Trace-based diagnosis.* Given three trace trees (text) for slow requests, identify whether the bottleneck is retrieval, model, tool, or agent overhead (gaps), and propose a fix.

### 10. Independent Implementation Project — "Trace Everything in SupportOps"

**Goal.** Instrument one complete SupportOps workflow end to end, inject failures and diagnose them from traces, and record eval outcomes next to telemetry.

**Functional requirements.**

1. FastAPI auto-instrumentation + manual GenAI spans for agent, retrieval, chat, tools, policy decisions and approvals.
2. Provenance attributes on all relevant spans; resource attributes with version/environment.
3. Token, latency and cost metrics by model/operation/tenant tier; per-request cost attribute.
4. Privacy: content capture off by default; opt-in with redaction; restricted store; pseudonymized user IDs; Collector scrub.
5. Cross-service propagation between two agent services and through the approval queue (links).
6. Fault injection for retrieval, model, tool and policy failures; runbook entries showing the trace signature of each.
7. Online eval results joined to traces; dashboard queries.

**Technical requirements.** OpenTelemetry Python SDK + instrumentations, OTLP exporter, OpenTelemetry Collector (docker-compose), a trace backend (Jaeger or Grafana Tempo) and metrics backend (Prometheus), pytest with in-memory exporters.

**Suggested structure.**

```
app/
├── telemetry/{setup.py, genai.py (span helpers), redaction.py, cost.py, provenance.py}
├── agent/… (instrumented)
├── approvals/… (links on resume)
└── evals/online.py
deploy/
├── docker-compose.yaml        app, collector, jaeger/tempo, prometheus, grafana
├── otel-collector.yaml
└── dashboards/supportops.json
docs/runbooks/{retrieval_timeout.md, model_outage.md, tool_failure.md, policy_timeout.md}
tests/telemetry/{test_span_tree.py, test_no_content_by_default.py, test_cost.py, test_propagation.py}
```

**Milestones.** (1) setup + auto-instrumentation; (2) GenAI span helpers; (3) provenance + cost; (4) privacy controls; (5) propagation + links; (6) fault injection + runbooks; (7) eval join + dashboards.

**Testing requirements.** Span-tree assertions; "no content attributes when capture off"; cost math; propagation across two ASGI apps in-process; Collector config validated (`otelcol validate`).

**Definition of Done.**

* [ ] A single trace shows API → agent → retrieval → model → tools → policy for a request.
* [ ] Each injected failure is diagnosable from the trace alone, documented in a runbook.
* [ ] Cost per request and per successful task are visible by model and prompt version.
* [ ] No prompt/response content or raw user identifiers in the general backend.
* [ ] Eval outcomes can be filtered together with latency and provenance.

**Optional extensions.** Export to an LLM-observability tool that ingests OTel GenAI spans; exemplars linking metrics to traces; SLOs with burn-rate alerts.

### 11. Testing Strategy

* **Span-tree tests** with `InMemorySpanExporter`: names, kinds, parentage, required attributes.
* **Negative privacy tests**: content attributes absent by default; redaction applied when enabled; no emails/tokens in any attribute (scan all attributes with regexes).
* **Propagation tests**: two ASGI apps with `httpx.ASGITransport`; same `trace_id`.
* **Metric tests**: `InMemoryMetricReader` collects expected data points and attribute sets (and no high-cardinality keys).
* **Fault-injection tests**: each fault produces the expected error span and root status.
* **Load tests**: instrumentation overhead and exporter backpressure under load.

```python
# tests/telemetry/test_span_tree.py
import asyncio, re
import traced_agent as ta

def test_healthy_trace_shape():
    ta.EXPORTER.clear()
    asyncio.run(ta.invoke_agent("u@example.com", "acme", "q", ta.Faults()))
    spans = ta.EXPORTER.get_finished_spans()
    names = [s.name for s in spans]
    assert "invoke_agent support_agent" in names and "retrieval kb-acme" in names
    root = next(s for s in spans if s.name.startswith("invoke_agent"))
    children = [s for s in spans if s.parent and s.parent.span_id == root.context.span_id]
    assert {c.attributes["gen_ai.operation.name"] for c in children} == {"retrieval", "chat", "execute_tool"}

def test_no_raw_pii_in_attributes():
    ta.EXPORTER.clear()
    asyncio.run(ta.invoke_agent("u@example.com", "acme", "q", ta.Faults()))
    email = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
    for s in ta.EXPORTER.get_finished_spans():
        for value in s.attributes.values():
            assert not email.search(str(value)), (s.name, value)
```

### 12. Engineering Scenarios

**Scenario 1 — p95 latency doubled.** *Investigate:* span-type latency breakdown by version; gaps between spans; number of turns per trace. *Reasoning:* If turns increased after a prompt change, the cause is behavioural (agent loops more), not infrastructure — fix the prompt/decision schema and add a turns metric to the gate.

**Scenario 2 — Legal asks to log every prompt "for compliance".** *Investigate:* What is the regulatory requirement (audit of decisions vs full content)? Retention? Access? *Reasoning:* Audit tables already capture decisions; full content goes to a restricted, encrypted store with short retention and access logging, not to the general observability backend.

**Scenario 3 — Multi-agent blame game.** Two teams own the router and refund agents; errors are "the other team's". *Reasoning:* One propagated trace with per-agent spans and `error.type` attributes ends the argument; agree on span conventions as an interface contract.

**Scenario 4 (FDE) — Customer wants "visibility into what the AI is doing".** *Clarify:* who is the audience (ops, compliance, business)? What questions must they answer? What data may leave their environment (self-hosted Collector/backends)? *Reasoning:* Deliver role-specific views: ops (latency/errors/cost), compliance (decisions/approvals/audit with trace links), business (task success/deflection). Run telemetry inside the customer's boundary if required, exporting only aggregates.

### 13. Interview Preparation

#### Quick Questions

**Q: Trace vs eval?** A trace records what happened (spans, timings, errors, tokens); an eval judges whether behaviour was good. Join them by trace ID.

**Q: What is a span link and when would you use it?** A reference to a span in another trace; for async work (approval resume, batch jobs, evaluations) and fan-in.

**Q: Which attributes would you put on a model-call span?** Operation, provider, request/response model, max tokens, finish reasons, input/output (and cached) tokens, error type, prompt version; content only if opted in.

**Q: How do you correlate across agents?** W3C Trace Context propagation (headers/message metadata), per-agent `invoke_agent` spans, links for async, a business correlation ID attribute.

#### Intermediate Questions

**Q: How do you attribute token cost?**
Strong answer: Tokens on each model span plus unsampled metrics by model/tenant/feature; cost from a versioned price table; include retries, embeddings, judges; report cost per successful task by joining evals.

**Q: What is provenance and why record it?**
Strong answer: The exact versions of model, prompt, index, embedding, policy and code that produced an output; it lets you attribute behaviour changes to specific changes and compare cohorts.

**Q: How do you make telemetry privacy-safe?**
Strong answer: Metadata by default; content opt-in with redaction and a restricted store; keyed pseudonyms; Collector scrubbing; no PII in baggage or metric labels; retention policies.

#### Advanced Questions

**Q: Design tracing for an agent whose approvals take hours and whose tools publish to Kafka.**
Strong answer: Request trace ends when the proposal is created; audit row stores trace/span IDs; approval decision starts a new trace linked to the proposal span; Kafka producer injects context into headers, consumers extract and start CONSUMER spans (or link for batches); a correlation attribute (`case_id`) ties everything for search.

**Q: The GenAI semantic conventions are experimental. How do you adopt them safely?**
Strong answer: Pin instrumentation/semconv versions, wrap span creation in your own helper module so renames are one-file changes, use the opt-in mechanism for latest names during migration, and write tests asserting the attributes your dashboards depend on.

#### Coding Questions

1. Write a span helper `traced_tool(name)` decorator that records GenAI tool attributes and errors.
2. Propagate trace context through an `asyncio.Queue` producer/consumer.
3. Write a test asserting no attribute contains an email address.

#### Scenario Questions

* "A customer says the agent gave a wrong refund amount last Tuesday. Reconstruct what happened."
* "Costs doubled overnight with flat traffic. How do you find out why?" (Tokens per request by prompt/model version; turns per trace; retries; cache hit rate.)

### 14. Explain-It-at-Three-Levels

**AI tracing**

* *30 s:* We give each request one trace that covers the API, agent, retrieval, model calls and tools, with token, latency, error and version attributes, so we can explain any outcome and attribute cost — without storing sensitive content by default.
* *2 min:* Add GenAI semantic conventions, context propagation and links, provenance, cost metrics, sampling, and privacy tiers.
* *Deep:* contextvars mechanics, batch export and shutdown, Collector pipelines (redaction, tail sampling), cardinality management, experimental-convention migration, joining online evals, incident reconstruction workflow.

### 15. Knowledge Check

**Conceptual**

1. What does the span kind tell you, and which kind should a model API call have?
2. Why should cost be computed from metrics rather than sampled traces?
3. What's the risk of putting user IDs in OTel Baggage?
4. Why record `gen_ai.response.model` in addition to `gen_ai.request.model`?
5. Name three provenance attributes besides model version.

**Code reading**

6. In Example 2, why is the retrieval timeout span ERROR while the agent span is OK?
7. Why does `record_eval_outcome` use a link rather than making the eval span a child?
8. What does `propagate.inject(carrier)` put into the carrier?

**Debugging**

9. Tool spans show up as separate traces. Name two likely causes.
10. Your trace backend shows full prompts with customer addresses. List immediate and preventive actions.

**Design**

11. Head sampling at 5% hides rare failures. What do you change?
12. Which attributes are appropriate as metric dimensions for token usage?

#### Knowledge Check Answers

1. The role in the interaction (server, client, internal, producer, consumer). A model API call is CLIENT.
2. Metrics are aggregated from every operation; sampled traces omit most requests, so cost would be under-counted or require re-weighting.
3. Baggage propagates to every downstream service, including third parties, and may be logged — leaking PII.
4. The request may name an alias; the response names the concrete version actually served — essential for attributing behaviour changes.
5. Prompt version, index version, embedding model, policy version, decision schema version, service version, experiment arm.
6. The agent handled the failure by degrading (answering without retrieval); the operation succeeded with a fallback, while the dependency failed.
7. The evaluation happens later and in a different context; a link records the relationship without distorting the original trace's duration.
8. The W3C `traceparent` (and possibly `tracestate`/`baggage`) headers for the current span context.
9. Context lost across a thread pool/executor or background task; missing propagation through a queue or HTTP client not instrumented.
10. Immediate: disable capture, scrub/delete affected data per incident process, restrict access. Preventive: content opt-in only, Collector delete/redaction processors, tests scanning attributes, restricted content store.
11. Send all spans to the Collector and use tail sampling to keep all errors/slow traces plus a sample; or increase head sampling for error-prone routes; compute rates from metrics.
12. Low-cardinality ones: model (request/response), operation, provider, token type, tenant tier, environment, prompt version (if few). Not user/order/session IDs.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "Logging prompts is observability." | Observability is structured, correlated telemetry; content is a sensitive, opt-in subset. |
| "If it's traced, we know it was right." | Traces show what happened; evals judge quality. |
| "Hashing emails makes them anonymous." | Unkeyed hashes are reversible by dictionary; use keyed HMAC, and treat pseudonyms as personal data under GDPR. |
| "The GenAI conventions are stable." | They are in Development; pin and wrap. |
| "Put the user ID on every metric for debugging." | Cardinality explosion; IDs belong on spans. |
| "Each agent can have its own trace." | Propagate context so one business operation is one trace (plus links). |

### 17. Cheat Sheet

* **Span names:** `chat {model}` · `embeddings {model}` · `retrieval {data_source}` · `execute_tool {tool}` · `invoke_agent {agent}` · `invoke_workflow {name}`.
* **Model span attrs:** `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.usage.cache_read.input_tokens`, `error.type`.
* **Tool:** `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type` (+ opt-in arguments/result).
* **Agent:** `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.conversation.id`.
* **Content (opt-in):** `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`, `gen_ai.tool.definitions`.
* **Legacy:** `gen_ai.system` → use `gen_ai.provider.name`.
* **Provenance (custom):** `app.prompt.version`, `app.index.version`, `app.embedding.model`, `app.policy.version`, `service.version`.
* **Propagation:** `traceparent: 00-<trace>-<span>-<flags>`; inject/extract; links for async; no PII in baggage.
* **Python:** `tracer.start_as_current_span(name, kind=…)`; `span.set_attribute`; `span.record_exception`; `span.set_status(Status(StatusCode.ERROR))`; `FastAPIInstrumentor.instrument_app(app)`; `provider.shutdown()` in lifespan.
* **Collector:** memory_limiter → scrub → tail_sampling → batch.
* **Rules:** metadata by default, content by exception; IDs on spans not metrics; cost from metrics; join evals by trace ID.

### 18. Completion Checklist

* [ ] I can explain spans, context propagation, links, metrics and logs and how they relate.
* [ ] I can instrument an agent workflow with GenAI-convention spans and provenance.
* [ ] I can attribute latency, errors, tokens and cost to spans, models and tenants.
* [ ] I can correlate traces across agents, queues and asynchronous approvals.
* [ ] I can implement privacy-safe telemetry and prove it with tests.
* [ ] I can inject failures and diagnose them from traces.
* [ ] I can join eval outcomes to telemetry and build dashboards by version.

### 19. Further Research

**Essential**

* OpenTelemetry GenAI semantic conventions (repository): <https://github.com/open-telemetry/semantic-conventions-genai> — current span/metric/attribute definitions and their status.
* OpenTelemetry Python documentation: <https://opentelemetry.io/docs/languages/python/> — SDK setup, instrumentation, propagation.
* W3C Trace Context: <https://www.w3.org/TR/trace-context/> — `traceparent`/`tracestate` format.
* OpenTelemetry Collector: <https://opentelemetry.io/docs/collector/> — receivers, processors (tail sampling, transform/redaction), exporters.

**Deeper Study**

* OpenTelemetry Python Contrib — GenAI instrumentations: <https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation-genai> — how provider SDK calls are instrumented and how content capture is gated.
* Google SRE Book, "Monitoring Distributed Systems": <https://sre.google/sre-book/monitoring-distributed-systems/> — golden signals, alerting philosophy.
* Charity Majors et al., *Observability Engineering* (O'Reilly, 2022) — high-cardinality debugging mindset.

**Practice**

* Run Jaeger or Grafana Tempo with the Collector locally (docker-compose) and send Example 2's spans via OTLP.
* Arize Phoenix (<https://github.com/Arize-ai/phoenix>) or Langfuse (<https://langfuse.com/docs>) — explore LLM-specific trace views that ingest OpenTelemetry data.
* Toxiproxy: <https://github.com/Shopify/toxiproxy> — inject latency/failures into dependencies and observe traces.

### Unit Completion Standard

Before moving on, you must be able to: **explain** trace vs eval, span links vs parent-child, and why GenAI conventions must be pinned; **implement** one OpenTelemetry trace across API, agent, retriever, model and tools with provenance, token and cost attribution and privacy-safe defaults; **test** span structure, propagation and the absence of sensitive content; **debug** injected retrieval, model and tool failures from traces alone; and **defend** in an interview your attribute choices, sampling strategy, cross-agent correlation and telemetry privacy design.
