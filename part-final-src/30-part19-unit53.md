# Part XIX — Final Capstone

**What this part teaches.** The capstone integrates the entire curriculum — Python, FastAPI, data, distributed systems, security, AI and production operations — into one production-style platform: a multi-tenant **Agentic Knowledge & Operations Platform** ("AKOP") that answers questions over enterprise documents with citations and executes bounded, approval-gated operational workflows.

**Why it matters.** A capstone is your strongest interview asset. It turns "I know about outbox patterns, pgvector and approvals" into "here is the repository, the trace, the eval report, the failure-injection results and the runbook." Every interview track in Part XVIII uses it as an anchor.

**Where it appears.** The platform mirrors what enterprises are actually building in 2026: internal knowledge assistants, support copilots, operations agents — with SSO, RBAC, audit, cost controls and evaluation.

**Connections.** Unit 47 (system design), Unit 48 (agent design), Unit 49 (Python), Unit 50 (FastAPI/backend), Unit 51 (algorithms for retrieval fusion, rate limiters, schedulers), Unit 52 (evals, FDE communication).

## Unit 53 — Production Agentic FastAPI Platform

### 1. Learning Objectives

1. **Implement** a FastAPI platform with Pydantic v2, PostgreSQL/SQLAlchemy 2.x/Alembic, Redis, Kafka and background workers following a clean layered architecture.
2. **Implement** authentication (OIDC/JWT) and RBAC with tenant isolation and object-level authorization, enforced deterministically.
3. **Package and deploy** with Docker, CI/CD and AWS (ECS Fargate or EKS, RDS, ElastiCache, MSK/SQS), with OpenTelemetry end-to-end tracing.
4. **Implement** a provider-neutral LLM client with retries, timeouts, fallback, circuit breaking, token/cost accounting and structured output.
5. **Implement** pgvector-based hybrid RAG with permission-aware retrieval, reranking, citations and abstention.
6. **Implement** a bounded agent workflow with durable state, idempotent tools, a policy-enforcing tool gateway, human approval, optional LangGraph orchestration and MCP integration.
7. **Build** an AI evaluation suite (retrieval, generation, trajectory, safety, cost/latency), token/cost metrics, failure injection and graceful degradation.
8. **Produce** the deliverables: production-style repository, architecture document, runbook, automated tests, AI evaluation report, demo script and an interview-ready system-design walkthrough.
9. **Defend** every architectural choice against a simpler alternative.

### 2. Prerequisite Knowledge

All previous units. Practical prerequisites: Docker and docker-compose locally; an AWS account (or LocalStack for partial simulation) if deploying; access to at least one LLM API and one embedding model (or a local embedding model such as a sentence-transformers model); `uv` for Python project management.

### 3. Mental Model

```
                                ┌──────────────── Control plane ────────────────┐
                                │ Agent registry (versions) · Tool policies ·    │
                                │ Eval gates · Tenant config · Prompt versions   │
                                └───────────────────────────────────────────────┘
Users ─OIDC─▶ [ALB/WAF] ─▶ [FastAPI API pods] ──▶ (Postgres: OLTP + pgvector + outbox + runs)
                               │    │    │                 │
                               │    │    └─▶ (Redis: cache, rate limits, idempotency fast path)
                               │    └──⇢ outbox relay ⇢ [Kafka topics] ⇢ [Workers]
                               │                                   ├─ ingestion (parse/chunk/embed)
                               │                                   ├─ agent runs (orchestrator)
                               │                                   └─ notifications/audit sinks
                               └─▶ [Tool gateway] ─▶ internal services / MCP servers (delegated creds)
                                         │
                               [LLM router] ─▶ {Provider A} / {Provider B} / {local fallback}
Observability: OTel SDK in API & workers ─▶ Collector ─▶ traces/metrics/logs backends; eval reports
```

**Deterministic spine, probabilistic edges.** Identity, authorization, data access, state transitions, tool execution, money/permission changes and audit are deterministic. The model ranks, extracts, drafts and chooses next steps *within* that spine.

### 4. Comprehensive Theory — Integration Decisions

This section explains the reasoning behind each integration; the underlying concepts were taught in earlier units.

#### 4.1 Architecture Style: Modular Monolith + Workers

**Decision.** One FastAPI codebase (modular monolith) deployed as two process types: API and workers (ingestion, agent runner, relay). **Simpler alternative considered:** a single process with `BackgroundTasks` — rejected because ingestion and agent runs must be durable and independently scalable. **More complex alternative:** microservices per domain — rejected for team size and operational cost; module boundaries (`rag`, `agents`, `identity`, `ops`) allow later extraction.

#### 4.2 Data Layer

- **PostgreSQL 16+** as system of record: tenants, users, roles, documents, chunks (pgvector), agent runs/steps/approvals, outbox, idempotency keys, audit log.
- **pgvector ≥ 0.8** with HNSW (cosine) + Postgres FTS for hybrid retrieval. **Alternative:** dedicated vector DB — revisit beyond ~50–100M vectors or when filtered ANN performance becomes the bottleneck.
- **Alembic** migrations, expand/contract discipline, `CREATE INDEX CONCURRENTLY` for large indexes.
- **Row-level security (RLS)** as defense in depth for tenant isolation (`SET LOCAL app.tenant_id` per transaction + policies), in addition to repository-level filters.

```sql
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
-- The app role must not be the table owner or have BYPASSRLS, or policies are skipped.
```

#### 4.3 Messaging

- **Kafka** (MSK or Redpanda locally) for domain events: `documents.ingest.requested`, `agent.runs.requested`, `agent.approvals.decided`, `audit.events`. Keys: `document_id`, `run_id` (per-entity ordering).
- **Transactional outbox** → relay → Kafka; consumers idempotent via `processed_messages`.
- **Alternative:** SQS + Celery/arq — simpler if you don't need replay or multiple consumers; document this trade-off in an ADR. The capstone uses Kafka because the curriculum requires it and audit/analytics consumers benefit from replay.

#### 4.4 Identity and Authorization

- OIDC with an IdP (Keycloak in docker-compose; Cognito/Okta/Entra in AWS). API validates JWTs via JWKS (cache keys; handle rotation via `kid`).
- `Principal(user_id, tenant_id, roles, scopes, groups)` built in a dependency.
- RBAC roles: `viewer`, `member`, `operator`, `approver`, `tenant_admin`. Permissions map to tools and endpoints.
- Object-level checks in repositories; tenant from token only.
- Tools execute with delegated credentials (simulate OAuth token exchange: the gateway mints a short-lived, audience-restricted internal token carrying the user and scope).

#### 4.5 AI Layer

- **Provider-neutral LLM client**: `Protocol` with `complete()`, `structured()`, `stream()`; adapters per provider; router with fallback chain and circuit breakers; token and cost accounting from provider usage fields and a versioned pricing table.
- **Embeddings client**: batched, versioned (`embedding_model` column on chunks), retry with backoff.
- **RAG service**: hybrid retrieval with ACL filters, RRF fusion, reranker (API or local cross-encoder), context builder with token budget, structured answers with citations, citation validation, abstention.
- **Agent service**: bounded orchestrator (Unit 48), tool gateway with policy and approvals, durable runs/steps, idempotent tools, loop detection, budgets.
- **Optional LangGraph**: implement the approval flow once by hand and once in LangGraph (with the Postgres checkpointer), then write an ADR comparing them.
- **MCP integration**: (a) expose two read-only platform tools (`search_knowledge`, `get_run_status`) as an MCP server over Streamable HTTP behind OAuth; (b) consume one external MCP server through the tool gateway, with its tools wrapped by your policies. **[Version-dependent]** Target the MCP 2026-07-28 revision if your SDK supports it (stateless core); otherwise document the negotiated version.

#### 4.6 Operations

- **OpenTelemetry**: FastAPI, SQLAlchemy, httpx, Redis, Kafka instrumentation; custom spans for agent runs, model calls (GenAI conventions — Development status; pin semconv version), tool executions and retrievals; trace context propagated through Kafka headers; metrics for tokens, cost, latency, policy denials, degraded mode.
- **Docker**: multi-stage, non-root, health checks; docker-compose for local full stack (Postgres+pgvector, Redis, Redpanda/Kafka, Keycloak, OTel collector, Jaeger, Prometheus, Grafana).
- **CI/CD**: GitHub Actions — lint (ruff), type-check (mypy/pyright), unit tests, integration tests (services/Testcontainers), security tests, eval gate (on changes to prompts/agents/RAG), Docker build + scan (Trivy/Grype), push to ECR, migrate, deploy (ECS rolling or blue/green), smoke tests.
- **AWS**: VPC (private subnets), ALB+WAF, ECS Fargate services (api, worker-ingest, worker-agent, relay), RDS PostgreSQL Multi-AZ (pgvector supported on RDS), ElastiCache Redis/Valkey, MSK Serverless (or SQS alternative), Secrets Manager, IAM task roles, ADOT collector sidecar, CloudWatch alarms. IaC with Terraform or CDK.

#### 4.7 Failure Handling and Graceful Degradation

| Failure | Injection method | Expected behavior |
|---|---|---|
| Primary LLM provider 5xx/timeout | Fault-injecting provider adapter (`FAULT_LLM_PRIMARY=error_rate:0.5`) | Breaker opens → fallback provider; responses labeled `degraded: fallback_model` |
| All LLM providers down | Disable both | Degrade to search-results mode for `/ask`; agent runs queued with `WAITING_DEPENDENCY` |
| Embedding service down | Fault injection | Ingestion retries with backoff, DLQ after N; queries use lexical-only retrieval |
| Bad retrieval | Corrupt/remove gold docs in test tenant | Abstention, not hallucination |
| Unauthorized tool attempt | Injection document instructing deletion | Gateway deny, security event, run continues/terminates per policy |
| Worker crash mid-run | Kill container between tool execution and checkpoint | Resume without duplicate side effects |
| Kafka unavailable | Stop broker | Outbox accumulates; API unaffected; relay catches up |
| Redis unavailable | Stop Redis | Cache bypass, rate limiter fail-open (except login: fail-closed) |
| Postgres failover | RDS reboot with failover / container restart | Brief errors; retries for idempotent ops; readiness gating |

### 5. Internal Mechanics — End-to-End Flows

**Flow A — Ask (RAG).**
```
POST /v1/ask → OTel span → auth dependency (JWT→Principal) → rate limit (Redis token bucket)
→ RagService.ask: cache lookup key=(tenant, acl_hash, normalized_q, corpus_version)
→ query rewrite (small model, cached) → embed query → hybrid SQL (tenant+ACL filters, RLS on)
→ rerank top-50 → context builder (budget) → LLM structured answer (router: primary→fallback)
→ citation validation → response (SSE stream optional) → metrics: tokens, cost, latency, degraded flag
```

**Flow B — Agent run with approval.**
```
POST /v1/runs {agent: "support-ops", input} → validate → create run (CREATED) + outbox(AgentRunRequested) in one TX → 202 {run_id}
relay → Kafka agent.runs.requested (key=run_id) → agent worker consumes (idempotent)
→ load agent version config → orchestrator loop (bounded) → model → tool gateway
   READ tools → execute → observation → checkpoint
   WRITE_HIGH tool → approval record (PENDING) + run WAITING_APPROVAL + outbox(ApprovalRequested) → stop
POST /v1/approvals/{id}/decision (approver role, not requester; args hash must match)
→ TX: approval APPROVED + outbox(ApprovalDecided) → worker resumes run → gateway executes with idempotency key
→ final answer validated → run SUCCEEDED → outbox(AgentRunCompleted) → notifications/audit consumers
```

**Flow C — Ingestion.**
```
POST /v1/documents (presigned upload or connector sync) → document row (PENDING) + outbox
→ ingest worker: fetch → parse (sandboxed process, size/time limits) → chunk (structure-aware)
→ dedupe by content_hash → embed (batched) → upsert chunks (embedding_model, acl_principals) → document READY
→ on ACL change: update acl_principals on chunks (no re-embed); on delete: hard-delete chunks
```

### 6. Implementation Examples (Key Building Blocks)

The capstone is yours to build; these are the load-bearing pieces whose design is easiest to get wrong.

#### Example 1 — Minimal: Settings, app factory and lifespan

```python
# app/core/config.py
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKOP_", env_file=".env", extra="ignore")

    env: str = "local"
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    kafka_bootstrap: str = "localhost:9092"
    oidc_issuer: str
    oidc_audience: str = "akop-api"
    llm_primary: str = "provider_a:model-large"
    llm_fallback: str = "provider_b:model-medium"
    llm_api_keys: dict[str, SecretStr] = Field(default_factory=dict)
    embedding_model: str = "provider_a:embed-v1"
    run_max_turns: int = 8
    run_max_seconds: int = 120
    run_max_tokens: int = 60_000
    otel_enabled: bool = True


settings = Settings()  # type: ignore[call-arg]
```

```python
# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api import ask, documents, runs, approvals, health
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.telemetry import setup_telemetry
from app.db.session import engine
from app.llm.factory import build_llm_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(settings.redis_url)
    app.state.llm = build_llm_router(settings)
    app.state.ready = True
    yield
    app.state.ready = False
    await app.state.llm.aclose()
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="AKOP", version="1.0.0", lifespan=lifespan)
    install_error_handlers(app)
    for r in (health.router, ask.router, documents.router, runs.router, approvals.router):
        app.include_router(r)
    if settings.otel_enabled:
        setup_telemetry(app, engine, service_name="akop-api", version="1.0.0")
    return app


app = create_app()
```

#### Example 2 — Realistic: Provider-neutral LLM client with router, breaker and cost accounting

```python
# app/llm/types.py
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


@dataclass
class Completion:
    text: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    usage: Usage = Usage(0, 0)
    model: str = ""
    provider: str = ""
    stop_reason: str = ""


class ProviderError(Exception):
    def __init__(self, msg: str, retryable: bool) -> None:
        super().__init__(msg)
        self.retryable = retryable


class ChatProvider(Protocol):
    name: str
    async def complete(self, *, model: str, system: str, messages: list[dict],
                       tools: list[dict] | None, max_tokens: int, timeout_s: float) -> Completion: ...
    async def aclose(self) -> None: ...
```

```python
# app/llm/router.py
import time
from dataclasses import dataclass

from opentelemetry import metrics, trace
from pydantic import BaseModel, ValidationError

from app.llm.pricing import cost_usd
from app.llm.types import ChatProvider, Completion, ProviderError

tracer = trace.get_tracer("akop.llm")
meter = metrics.get_meter("akop.llm")
token_counter = meter.create_counter("gen_ai.client.token.usage.total", unit="{token}")
cost_counter = meter.create_counter("akop.llm.cost", unit="USD")


@dataclass
class Breaker:
    failure_threshold: int = 5
    cooldown_s: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown_s:
            return True                      # half-open: allow a probe
        return False

    def record(self, ok: bool) -> None:
        if ok:
            self.failures, self.opened_at = 0, None
        else:
            self.failures += 1
            if self.failures >= self.failure_threshold:
                self.opened_at = time.monotonic()


@dataclass
class Route:
    provider: ChatProvider
    model: str
    breaker: Breaker


class AllProvidersFailed(Exception):
    pass


class LLMRouter:
    def __init__(self, routes: list[Route]) -> None:
        self._routes = routes

    async def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None = None,
                       max_tokens: int = 1024, timeout_s: float = 30.0,
                       tenant_id: str = "-") -> tuple[Completion, bool]:
        """Returns (completion, degraded) where degraded=True if a fallback served the request."""
        last_error: Exception | None = None
        for idx, route in enumerate(self._routes):
            if not route.breaker.allow():
                continue
            with tracer.start_as_current_span(f"chat {route.model}") as span:
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.provider.name", route.provider.name)
                span.set_attribute("gen_ai.request.model", route.model)
                try:
                    out = await route.provider.complete(model=route.model, system=system,
                                                        messages=messages, tools=tools,
                                                        max_tokens=max_tokens, timeout_s=timeout_s)
                except ProviderError as exc:
                    route.breaker.record(ok=False)
                    span.record_exception(exc)
                    last_error = exc
                    if not exc.retryable:
                        raise
                    continue
                route.breaker.record(ok=True)
                span.set_attribute("gen_ai.usage.input_tokens", out.usage.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", out.usage.output_tokens)
                attrs = {"provider": route.provider.name, "model": route.model, "tenant": tenant_id}
                token_counter.add(out.usage.input_tokens + out.usage.output_tokens, attrs)
                cost_counter.add(cost_usd(route.model, out.usage), attrs)
                return out, idx > 0
        raise AllProvidersFailed(str(last_error))

    async def structured(self, schema: type[BaseModel], *, repair_attempts: int = 1, **kw) -> tuple[BaseModel, bool]:
        """Ask for JSON matching schema; validate; bounded repair."""
        messages = kw.pop("messages")
        for attempt in range(repair_attempts + 1):
            out, degraded = await self.complete(messages=messages, **kw)
            try:
                return schema.model_validate_json(out.text or ""), degraded
            except ValidationError as exc:
                if attempt == repair_attempts:
                    raise
                messages = messages + [
                    {"role": "assistant", "content": out.text or ""},
                    {"role": "user", "content": f"Invalid JSON for schema: {exc.errors(include_url=False)}. Return only valid JSON."},
                ]
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        for r in self._routes:
            await r.provider.aclose()
```

Notes: prefer the provider's native structured-output/strict tool mode when available and keep Pydantic validation as the final check; breakers are per process (acceptable — each process learns quickly; share state via Redis only if needed); the `degraded` flag flows to API responses and metrics.

#### Example 3 — Production-oriented: Schema + migration for chunks with pgvector, ACLs and FTS

```python
# migrations/versions/20261001_0003_chunks.py
"""chunks with pgvector, FTS and ACL arrays"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision = "20261001_0003"
down_revision = "20261001_0002"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chunks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", pg.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("section_path", sa.Text, nullable=False, server_default=""),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("acl_principals", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("tsv", pg.TSVECTOR,
                  sa.Computed("to_tsvector('english', section_path || ' ' || text)", persisted=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "ordinal"),
    )
    op.create_index("ix_chunks_tenant_doc", "chunks", ["tenant_id", "document_id"])
    op.create_index("ix_chunks_acl", "chunks", ["acl_principals"], postgresql_using="gin")
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
    )
    op.execute("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON chunks "
               "USING (tenant_id = current_setting('app.tenant_id')::uuid)")


def downgrade() -> None:
    op.drop_table("chunks")
```

For large existing tables, build the HNSW index `CONCURRENTLY` in an autocommit block and raise `maintenance_work_mem` during the build. Store `embedding_model` so a model upgrade can be done by adding a new column/index, backfilling, evaluating, and switching reads atomically.

**Retriever (sketch).**

```python
# app/rag/retriever.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HYBRID_SQL = text("""
WITH dense AS (
  SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:qvec AS vector)) AS r
  FROM chunks
  WHERE tenant_id = :tenant AND acl_principals && CAST(:principals AS text[])
    AND embedding_model = :emodel
  ORDER BY embedding <=> CAST(:qvec AS vector) LIMIT :k_dense
), lexical AS (
  SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS r
  FROM chunks, websearch_to_tsquery('english', :qtext) q
  WHERE tenant_id = :tenant AND acl_principals && CAST(:principals AS text[]) AND tsv @@ q
  ORDER BY ts_rank_cd(tsv, q) DESC LIMIT :k_lex
)
SELECT c.id, c.document_id, c.text, c.section_path, c.token_count, f.score
FROM (SELECT id, SUM(1.0 / (60 + r)) AS score
      FROM (SELECT * FROM dense UNION ALL SELECT * FROM lexical) u GROUP BY id) f
JOIN chunks c ON c.id = f.id
ORDER BY f.score DESC LIMIT :k_out
""")


async def hybrid_search(session: AsyncSession, *, tenant_id: str, principals: list[str],
                        qvec: list[float], qtext: str, emodel: str, k_out: int = 50):
    await session.execute(text("SET LOCAL app.tenant_id = :t"), {"t": tenant_id})   # RLS
    await session.execute(text("SET LOCAL hnsw.ef_search = 100"))
    await session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))     # pgvector >= 0.8
    rows = await session.execute(HYBRID_SQL, {
        "tenant": tenant_id, "principals": principals, "qvec": str(qvec), "qtext": qtext,
        "emodel": emodel, "k_dense": 50, "k_lex": 50, "k_out": k_out})
    return rows.mappings().all()
```

(`SET LOCAL` with bind parameters may not be accepted by every driver; use `SELECT set_config('app.tenant_id', :t, true)` as the portable form.)

### 7. Comparative Analysis — Defend Every Choice

| Decision | Chosen | Simpler alternative | Why chosen / when to switch |
|---|---|---|---|
| Service shape | Modular monolith + workers | Single process with BackgroundTasks | Durability and independent scaling; switch to services when teams/scale demand |
| Vector store | pgvector in Postgres | Managed vector DB | One transactional store with ACL joins/RLS; switch at very large scale or specialized needs |
| Retrieval | Hybrid + rerank | Dense only | Exact identifiers/acronyms; measured recall gain must justify reranker latency |
| Messaging | Kafka + outbox | SQS/arq | Replay, multiple consumers (audit/analytics); choose SQS if ops burden outweighs |
| Orchestration | Hand-rolled state machine (+ optional LangGraph) | Framework-only | Full control and debuggability; LangGraph if interrupts/durability features save real work |
| Agents | Single agent + tools | Multi-agent | Evidence-driven; add research sub-agent only if evals show gain |
| AuthN | OIDC IdP | Local passwords | Enterprise SSO; less credential risk |
| AuthZ | RBAC + object checks + RLS | RBAC only | Defense in depth for tenant isolation |
| LLM access | Provider-neutral router | Direct SDK calls | Fallbacks, cost accounting, vendor flexibility; costs an abstraction layer |
| Deployment | ECS Fargate | EKS | Lower ops overhead; EKS if org standard or advanced scheduling needed |
| MCP | Expose 2 read-only tools; consume 1 external via gateway | No MCP | Interop demonstration; tools still governed by your policy |

### 8. Failure Modes and Debugging (Capstone Runbook Seeds)

Each entry belongs in `docs/runbook.md` with dashboards, queries and commands.

**R1 — /ask latency SLO burn.** Check trace breakdown (retrieval vs rerank vs LLM); provider status and breaker state; DB `pg_stat_statements` for retrieval SQL; HNSW `ef_search`; Redis hit rate. Mitigate: switch to fallback model, reduce rerank top-k, enable search-only mode via flag.

**R2 — Agent runs stuck in RUNNING.** Query `SELECT id, updated_at FROM agent_runs WHERE status='RUNNING' AND updated_at < now() - interval '10 min'`. Check worker health and Kafka consumer lag (`kafka-consumer-groups --describe --group agent-workers`). Mitigate: reaper job re-enqueues stale runs (idempotent resume).

**R3 — Approval executed with different arguments (should be impossible).** Treat as security incident; verify args-hash check; audit log; add regression test.

**R4 — Cost anomaly.** Dashboard cost by tenant/agent version/model; tokens per run p95; recent prompt/agent deploys; rollback agent version; enforce budgets.

**R5 — Cross-tenant data exposure report.** Contain (disable feature), preserve logs, run security test suite, inspect RLS policies and repository filters, check caches keyed without tenant, notify per policy.

**R6 — Ingestion backlog.** Kafka lag on `documents.ingest.requested`; embedding provider rate limits; parser failures in DLQ; scale ingest workers (bounded by provider limits).

**R7 — Outbox growth.** `SELECT count(*) FROM outbox WHERE published_at IS NULL`; relay logs; Kafka availability; relay will catch up — ensure partition-ordered publish.

### 9. Guided Practice (Capstone Milestone Exercises)

#### Level 1 — Concept Reinforcement
**1.1 ADRs.** Write ADRs for: modular monolith; pgvector; Kafka vs SQS; hand-rolled vs LangGraph; single vs multi-agent; ECS vs EKS. Each: context, options, decision, consequences, revisit triggers. Hints: include a simpler alternative every time.
**1.2 Threat model.** STRIDE + OWASP LLM Top 10 over the data-flow diagram. Hints: mark trust boundaries (user, model, tools, documents, MCP servers).

#### Level 2 — Implementation
**2.1 Core API.** Tenants/users/roles, documents CRUD, OIDC auth, RBAC dependencies, RLS, Alembic, tests.
**2.2 LLM layer.** Router with two providers + fake provider + fault injection + cost metrics; unit tests for breaker and fallback.
**2.3 RAG.** Ingestion worker, chunking, embeddings, hybrid retrieval, reranking, citations, abstention; retrieval tests on a seeded corpus.

#### Level 3 — Integration
**3.1 Agent workflow.** Support-ops agent with tools (`search_knowledge`, `get_ticket`, `get_order`, `draft_reply`, `issue_credit` [approval]); durable runs; approvals API; resume; idempotency.
**3.2 Messaging + observability.** Outbox → Kafka → workers; trace propagation; dashboards; SLOs.
**3.3 MCP.** Expose two tools via MCP server; consume an external MCP server via gateway; tests that policy still applies.

#### Level 4 — Debugging / Production
**4.1 Failure-injection campaign.** Execute every row of §4.7; record expected vs observed; fix gaps.
**4.2 Red team.** Injection documents, cross-tenant probes, approval bypass attempts, oversized inputs, cost exhaustion attempts; produce findings and fixes.

### 10. Independent Implementation Project — Full Capstone Specification

**Goal.** Build AKOP: a production-style, multi-tenant agentic FastAPI platform with RAG, bounded agents, approvals, evaluations and operations — plus the complete deliverable set.

**Functional requirements.**
1. Tenant and user management with OIDC login, roles and groups.
2. Document ingestion (upload + one connector, e.g. a Git repository of Markdown or an S3 prefix), with ACLs, updates and deletions propagated.
3. `/v1/ask` with streamed answers, citations, abstention and degraded-mode labeling.
4. Agent runs: create, stream progress (SSE), cancel, view trace summary; approvals with separation of duties.
5. Admin: agent versions, tool policies, budgets per tenant, cost reports.
6. Audit log of authentication events, tool executions, approvals and admin changes.
7. MCP server exposing read-only tools; MCP client integration for one external server.

**Technical requirements.**
- Python 3.12+ (CI also on 3.14), FastAPI, Pydantic v2, SQLAlchemy 2.x async, Alembic, PostgreSQL 16+ with pgvector ≥ 0.8, Redis/Valkey, Kafka (Redpanda locally; MSK in AWS), background workers (Kafka consumers; optional arq for scheduled jobs).
- AuthN OIDC (Keycloak locally), RBAC + object-level + RLS.
- Docker, docker-compose, GitHub Actions CI/CD, AWS deployment via Terraform/CDK (ECS Fargate, RDS, ElastiCache, MSK, ALB, Secrets Manager).
- OpenTelemetry traces/metrics/logs → Collector → Jaeger/Tempo + Prometheus/Grafana (local) and CloudWatch/X-Ray or vendor (AWS).
- Provider-neutral LLM client, embeddings, pgvector RAG, citations, structured output, tools.
- Bounded agent workflow, durable state, optional LangGraph, MCP integration, guardrails, human approval.
- AI eval suite, token/cost metrics, failure injection, graceful degradation.

**Suggested project structure.**

```
akop/
├── pyproject.toml  uv.lock  Dockerfile  docker-compose.yml  Makefile  README.md
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── health.py  ask.py  documents.py  runs.py  approvals.py  admin.py  mcp_http.py
│   │   └── schemas/ (ask.py, documents.py, runs.py, approvals.py, common.py)
│   ├── core/
│   │   ├── config.py  security.py  rbac.py  errors.py  logging.py  telemetry.py  rate_limit.py
│   ├── domain/
│   │   ├── runs.py (state machine)  approvals.py  documents.py  errors.py  policies.py
│   ├── services/
│   │   ├── rag_service.py  ingest_service.py  run_service.py  approval_service.py  audit_service.py
│   ├── repositories/
│   │   ├── documents_repo.py  chunks_repo.py  runs_repo.py  approvals_repo.py  outbox_repo.py  idempotency_repo.py
│   ├── db/ (base.py, models.py, session.py, rls.py)
│   ├── llm/ (types.py, router.py, pricing.py, factory.py, providers/{provider_a.py, provider_b.py, fake.py, faulty.py})
│   ├── embeddings/ (client.py, providers/...)
│   ├── rag/ (chunking.py, retriever.py, rerank.py, context.py, citations.py, query_rewrite.py)
│   ├── agents/ (orchestrator.py, gateway.py, policy.py, registry.py, limits.py, loop_detector.py, graph_langgraph.py)
│   ├── tools/ (knowledge.py, tickets.py, orders.py, replies.py, credits.py)
│   ├── messaging/ (kafka.py, outbox_relay.py, consumers.py, propagation.py)
│   ├── workers/ (ingest_worker.py, agent_worker.py, relay_worker.py, reaper.py)
│   └── mcp/ (server.py, client.py)
├── migrations/ (env.py, versions/)
├── evals/
│   ├── datasets/ (retrieval.jsonl, answers.jsonl, agent_tasks.jsonl, safety.jsonl)
│   ├── metrics.py  judges.py  runner.py  gate.py  baselines/main.json  reports/
├── tests/
│   ├── unit/  integration/  contract/  security/  chaos/  e2e/  load/
├── deploy/
│   ├── terraform/ (vpc, ecs, rds, elasticache, msk, alb, iam, secrets)
│   ├── otel-collector.yaml  prometheus.yml  grafana/dashboards/
├── .github/workflows/ (ci.yml, eval-gate.yml, deploy.yml)
└── docs/
    ├── architecture.md  runbook.md  threat-model.md  eval-report.md  demo-script.md
    ├── system-design-walkthrough.md
    └── adr/ (0001-modular-monolith.md ... 0008-mcp.md)
```

**Implementation milestones.**

| # | Milestone | Exit criteria |
|---|---|---|
| M0 | Design | Architecture doc draft, threat model, ADRs, eval plan |
| M1 | Skeleton | App factory, settings, health, Docker/compose, CI lint/type/test |
| M2 | Identity & data | OIDC, RBAC, RLS, tenants/users/documents, Alembic, authZ matrix tests |
| M3 | Messaging | Outbox, relay, Kafka consumers, idempotency, trace propagation |
| M4 | LLM layer | Router, providers, fake/faulty, cost metrics, breaker tests |
| M5 | RAG | Ingestion, chunking, embeddings, hybrid retrieval, rerank, citations, abstention |
| M6 | Agents | Orchestrator, gateway, policies, approvals, durable runs, resume |
| M7 | MCP & LangGraph | MCP server/client; LangGraph variant + ADR |
| M8 | Evals | Datasets (≥ 150 retrieval, ≥ 100 answer, ≥ 50 agent, ≥ 50 safety cases), runner, gate |
| M9 | Ops | Dashboards, SLOs, alerts, runbook, failure injection campaign |
| M10 | AWS | Terraform/CDK deploy, CI/CD pipeline, smoke tests |
| M11 | Deliverables | Eval report, demo script + recording, walkthrough, polished README |

**Testing requirements.** See §11. Minimum: unit coverage ≥ 85% on domain/services/agents; authZ matrix covering every endpoint × role; cross-tenant tests for API, retrieval, caches and MCP tools; crash-resume test with no duplicate side effects; chaos suite for every §4.7 row; eval gate in CI.

**Definition of done.**
- `make up && make seed && make demo` runs the full local stack and demo scenario.
- CI green including eval gate; Docker images scanned with no critical vulnerabilities.
- Deployed to AWS (or documented reproducible IaC with a recorded deployment) with OTel traces visible end-to-end.
- Zero cross-tenant leaks in security tests; all high-risk tools approval-gated with args binding.
- Eval report shows retrieval and generation metrics separately, agent task success, safety results (zero tolerance failures = 0), cost and latency distributions, and failure analysis.
- Runbook covers at least R1–R7 with tested commands.
- You can deliver the system-design walkthrough in 15 minutes and answer "why not simpler?" for every component.

**Optional extensions.**
- Online evaluation with sampling and human review queue; user feedback loop into datasets.
- Multi-agent research sub-agent with measured comparison.
- Semantic caching with ACL-scoped keys and corpus versioning.
- Canary releases of agent versions with automated rollback on metric regression.
- Cell-based multi-tenancy (dedicated cell for large tenants).
- Self-hosted fallback model (vLLM) for provider-outage resilience.

#### Deliverable Templates

**Architecture document (`docs/architecture.md`).**
1. Context and goals (users, use cases, non-goals). 2. Requirements (functional, non-functional with numbers). 3. System context diagram. 4. Container/component diagrams. 5. Data model and sources of truth. 6. Key flows (ask, run+approval, ingestion). 7. Deterministic/probabilistic boundary map. 8. Security architecture (identity, authZ, tenant isolation, threat model summary). 9. Reliability (failure modes, degradation ladder, SLOs). 10. Observability and evaluation. 11. Scalability and capacity estimates. 12. Deployment and environments. 13. ADR index and trade-offs. 14. Open risks and future work.

**Runbook (`docs/runbook.md`).** Per alert: meaning, impact, dashboards, diagnosis steps with exact commands/queries, mitigations (with feature flags), escalation, post-incident tasks. Plus routine ops: deploy, rollback, migration, key rotation, re-embedding, tenant onboarding/offboarding, data deletion requests.

**AI evaluation report (`docs/eval-report.md`).** 1. Scope and system versions (agent, prompts, models, embedding model, corpus snapshot). 2. Datasets (sources, sizes, labeling process, unanswerable/adversarial share). 3. Metrics definitions. 4. Results: retrieval (recall@k, MRR, nDCG, ACL correctness), generation (faithfulness, correctness, citation precision/recall, abstention), agent (task success, tool-selection accuracy, turns, budget terminations), safety (injection, exfiltration, cross-tenant, unauthorized tool attempts blocked), cost/latency (p50/p95 per request and per task). 5. Comparisons (baseline vs current; dense vs hybrid; with/without rerank; single vs multi-agent if done; primary vs fallback model). 6. Failure analysis with categorized examples and traces. 7. Judge calibration (agreement with human labels). 8. Limitations and next steps.

**Demo script (`docs/demo-script.md`), 10 minutes.**
1. (1 min) Problem and users. 2. (2 min) Ask a policy question → streamed answer with citations → open a citation. 3. (1 min) Ask an unanswerable question → abstention. 4. (2 min) Start an agent run for a support case → tools in trace → proposes credit → approval request → approver (different user) approves → execution → audit entry. 5. (1 min) Injection document → unauthorized tool attempt denied → security event in trace. 6. (1 min) Kill primary LLM provider → fallback serves, "degraded" label; metrics dashboard. 7. (1 min) Eval report highlights and cost per task. 8. (1 min) Architecture recap and what's next. Prepare a recorded fallback for every live step.

**System-design walkthrough (`docs/system-design-walkthrough.md`).** Structured to mirror an interview: requirements and numbers → API → data → architecture → scale → failures → security → observability → evaluation → trade-offs with simpler alternatives → what you'd change at 10× scale.

### 11. Testing Strategy

| Layer | Examples |
|---|---|
| Unit | Run state machine transitions; policy decisions; budget/loop limits; RRF; context budgeting; citation validation; breaker; pricing |
| Scripted-model | Orchestrator control flow with a fake provider returning scripted tool calls |
| Integration (Testcontainers) | Postgres+pgvector retrieval with ACL + RLS; outbox relay with Redpanda; Redis rate limiter; Alembic upgrade/downgrade |
| Contract | OpenAPI snapshot; Kafka event schemas (Pydantic models + versioning); tool JSON Schemas; MCP tool listings |
| Security | AuthZ matrix; cross-tenant probes (API, retrieval, cache, MCP); JWT tampering; approval bypass; injection suite |
| Chaos | Fault-injecting providers; container kills mid-run; broker/Redis outages |
| E2E | docker-compose stack: login → ingest → ask → run → approve → audit |
| Load | k6: `/ask` at target QPS with fake LLM latency distribution; ingestion throughput |
| AI evals | Retrieval, generation, agent trajectory, safety suites with gates |

```python
# tests/chaos/test_resume_no_duplicate_side_effects.py
import pytest


@pytest.mark.anyio
async def test_crash_between_tool_execution_and_checkpoint(agent_env):
    """Simulate a worker crash right after the credit tool executes but before the step is checkpointed."""
    run_id = await agent_env.start_run(agent="support-ops", input="Order A-17 arrived damaged")
    await agent_env.approve_pending(run_id, approver="lead@t1")
    agent_env.inject_crash(after="tool_execute", tool="issue_credit", times=1)

    await agent_env.drive_until_terminal(run_id)                 # resumes on a new worker

    assert await agent_env.run_status(run_id) == "SUCCEEDED"
    assert agent_env.fake_billing.credit_calls_for("A-17") == 1   # idempotency key honored
```

```python
# tests/security/test_cross_tenant_retrieval.py
import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["salary bands", "acquisition plan", "*", "' OR 1=1 --"])
async def test_tenant_b_cannot_retrieve_tenant_a_chunks(api_as, seeded_two_tenants, query):
    client = api_as(user="bob@t2")
    r = await client.post("/v1/ask", json={"question": query})
    body = r.json()
    cited_docs = {c["document_id"] for c in body.get("citations", [])}
    assert cited_docs.isdisjoint(seeded_two_tenants.tenant_a_document_ids)
```

### 12. Engineering Scenarios

**Scenario 1 (FDE) — Pilot customer kickoff.** The customer's VP says: "We want the agent to resolve 50% of tickets autonomously by next quarter." Clarify ticket categories and volumes, current resolution paths, systems and permissions, risk tolerance, measurement method, and who approves. Propose: discovery week → shadow mode on historical tickets with eval report → draft-assist pilot → autonomous resolution for two low-risk categories gated by measured precision ≥ 98% and daily audit sampling. Demonstrate with the capstone's eval report and traces.

**Scenario 2 — Provider price increase of 40%.** Use cost dashboards per step; evaluate routing more steps to smaller models; caching; prompt compaction; run the eval gate on each change; present quality/cost frontier to stakeholders.

**Scenario 3 — Security review finds the agent worker's IAM role can read all S3 buckets.** Fix least privilege (bucket/prefix-scoped policy), per-tenant prefixes, IAM Access Analyzer, add a test/policy check in IaC CI (e.g. checkov), document in threat model.

**Scenario 4 — Retrieval quality drops after onboarding a tenant with scanned PDFs.** OCR pipeline, layout-aware parsing, per-document-type evals, tenant-specific monitoring; communicate timeline and interim workaround.

**Scenario 5 — Leadership asks whether to adopt LangGraph platform-wide.** Present your ADR comparing hand-rolled and LangGraph implementations with complexity, debuggability, durability features, team familiarity, lock-in and test results; recommend scoped adoption if justified.

### 13. Interview Preparation

#### Quick Questions
- **Q: Summarize your capstone in 30 seconds.** "A multi-tenant FastAPI platform that answers questions over enterprise documents with citations and runs bounded, approval-gated agent workflows. Postgres with pgvector is the system of record, Kafka with an outbox carries events to workers, OIDC/RBAC/RLS enforce access deterministically, a provider-neutral LLM router handles fallback and cost accounting, and an eval suite gates every agent change. It degrades to search-only mode when models are down."
- **Q: Where are the deterministic boundaries?** Identity, authorization, retrieval filters, tool policy and execution, approvals, state transitions, money/permission changes, audit.
- **Q: What's the simplest alternative to your architecture?** A single FastAPI app with Postgres FTS and direct LLM calls, no agents — and for some customers that's the right answer; my ADRs explain when each component becomes necessary.

#### Intermediate Questions
- **Q: Walk through what happens when a user asks a question.** Flow A in §5, with numbers (latency budget per stage) and failure handling.
- **Q: How do you guarantee an approved action executes exactly once?** Approval bound to args hash; execution with idempotency key `run:step:hash`; stored tool results checked before execution; downstream API idempotency; crash-resume test proves it.
- **Q: How do you know your RAG is good?** Eval report: retrieval and generation metrics separately, unanswerable handling, judge calibration, online feedback.

#### Advanced Questions
- **Q: Your primary model provider has a 2-hour outage during a customer demo. What happens?** Breakers open within seconds; fallback model serves with degraded label (pre-evaluated quality); if all down, search-only mode and queued runs; dashboards show it; demo script includes the recorded fallback. Afterward: postmortem and drill.
- **Q: How would this scale to 100× tenants?** Hot paths: LLM rate limits (multiple provider accounts, routing), Postgres (read replicas for retrieval, partition chunks by tenant hash, eventually dedicated cells or a vector DB for large tenants), Kafka partitions, worker autoscaling on lag; cost governance per tenant.
- **Q: Defend Kafka over SQS for this system.** Replay for audit/analytics and re-processing, multiple consumers, per-run ordering; concede SQS + arq would be simpler with fewer moving parts; MSK Serverless reduces ops; ADR documents revisit criteria.
- **Q: Defend single-agent over multi-agent.** Evals: single agent achieved X% at Y cost; multi-agent variant improved long research tasks by Z points at 1.7× cost; adopted only for that task type behind a flag, or rejected.

#### Coding Questions
- Implement the breaker and write tests with a fake clock.
- Implement RRF and the context builder with token budgets.
- Implement the run state machine with allowed transitions and optimistic concurrency.
- Write the outbox relay loop with `SKIP LOCKED`.
- Write a Kafka consumer that extracts trace context from headers and processes idempotently.

#### Scenario Questions
- "A customer's CISO asks for your data flow and retention." Use the architecture doc and threat model.
- "The eval gate blocks a prompt improvement that the product manager wants shipped today." Explain the gate's reason with data; offer a scoped rollout (flag for one tenant) if risk is acceptable and documented.

### 14. Explain-It-at-Three-Levels

**The capstone architecture.**
*30 s:* See the quick answer above.
*2 min:* Walk the three flows (ask, run+approval, ingest), naming the deterministic spine, the data stores, the messaging pattern, the AI layer, and how evals and observability wrap it.
*Deep:* Discuss each ADR's trade-offs, failure injection results, cost model, scaling limits, security design (RLS, delegated credentials, approval binding), eval methodology and judge calibration, and what you would change with more time or scale.

**Graceful degradation.**
*30 s:* Every dependency has a planned fallback: fallback model, search-only mode, queued runs, cache bypass — labeled to users and visible in metrics.
*Deep:* Breakers, timeouts, retry budgets, quality baselines for fallback models, chaos tests, and how degradation interacts with SLOs and customer contracts.

### 15. Knowledge Check

**Conceptual**
1. Why use both repository-level tenant filters and Postgres RLS?
2. Why store `embedding_model` on each chunk?
3. Why does the agent worker consume runs from Kafka rather than the API executing them inline?
4. What makes the approval flow safe against a model changing arguments after approval?
5. What's the role of the eval gate relative to unit tests?

**Code reading**
6. What's wrong with this outbox relay?
```python
rows = await s.execute(text("SELECT * FROM outbox WHERE published_at IS NULL LIMIT 100"))
for r in rows: await producer.send("events", r.payload)
await s.execute(text("UPDATE outbox SET published_at = now() WHERE published_at IS NULL"))
```
7. What's the risk here?
```python
cache_key = f"ask:{normalize(question)}"
```
8. What's missing?
```python
async def complete(**kw):
    return await provider.complete(**kw)   # no timeout, no breaker, no usage accounting
```

**Debugging**
9. Runs stay `WAITING_APPROVAL` after approval. Where do you look?
10. Traces from API and worker are disconnected. Why?

**Design**
11. A tenant requires EU data residency. What changes?
12. How would you add a new high-risk tool safely?

#### Knowledge Check Answers
1. Defense in depth: a missed filter in one query (bug) is still blocked by RLS; RLS alone can be bypassed by misconfigured roles, and app filters make intent explicit and testable.
2. To prevent mixing vectors from different models (incomparable spaces) and to support safe migration and evaluation of new embedding models.
3. Durability, retries, independent scaling, long runs and waiting for approvals without holding HTTP requests or API resources; also resilience to API deploys.
4. Approval binds to a hash of the exact tool name and arguments; execution recomputes and compares; any difference requires new approval.
5. Unit tests check deterministic code correctness; the eval gate checks probabilistic behavior quality, safety, cost and latency against baselines before release.
6. No `FOR UPDATE SKIP LOCKED` (concurrent relays double-publish); no key (ordering lost); not awaiting broker acks before marking; the UPDATE marks rows that weren't published (including new ones inserted meanwhile) as published → lost events. Mark by IDs after acks.
7. Cache key lacks tenant, ACL scope and corpus version → cross-tenant leakage and stale answers.
8. Timeout, retries policy, breaker/fallback, usage/cost accounting, tracing span, error classification.
9. Approval decision transaction and outbox event; relay publishing; Kafka topic/consumer lag for approvals; worker's resume handler logs; idempotency table skipping the message erroneously.
10. Trace context isn't propagated through Kafka headers (inject on produce/extract on consume), or the relay publishes without the original context (store `traceparent` in the outbox row).
11. EU deployment (cell) with EU-region data stores and model endpoints (provider regional processing), tenant routing, no cross-region replication of content, logging/trace payloads kept in-region, subprocessors documented.
12. Define schema and risk tier; policy rules and roles; approval required; idempotent implementation with downstream idempotency; tests (authZ matrix, approval bypass, crash-resume); eval cases including forbidden-use scenarios; canary rollout behind a flag; audit and monitoring.

### 16. Common Interview Traps

| Trap | Correct model |
|---|---|
| "My capstone uses every technology, so it's production-grade." | Production-grade means failure handling, security, observability, evaluation and runbooks — with evidence. |
| "The framework handles durability." | You must still design idempotent tools and test crash-resume. |
| "pgvector won't scale." | It scales far for many workloads; state your measured limits and revisit criteria. |
| "We have tracing, so we know it works." | Traces show what happened; evals show whether it was good. |
| "Fallback model = same quality." | Measure fallback quality; label degraded responses; choose per use case. |
| "Approval makes it safe." | Only with argument binding, authorized approvers, expiry, and anti-rubber-stamping monitoring. |

### 17. Cheat Sheet

- **Spine:** OIDC → Principal → RBAC/object checks/RLS → tool gateway → approvals → idempotent execution → audit.
- **Flows:** Ask (cache → rewrite → hybrid ACL retrieval → rerank → context → structured answer → citation check); Run (202 + outbox → Kafka → worker → bounded loop → approval → resume); Ingest (outbox → parse → chunk → embed → upsert).
- **Reliability:** outbox + idempotent consumers; breakers + fallback; degradation ladder; reaper for stale runs.
- **pgvector:** HNSW cosine; `ef_search`; `iterative_scan` (≥ 0.8); `embedding_model` column; GIN on ACL array and tsvector.
- **Evals:** retrieval ≠ generation ≠ trajectory ≠ safety ≠ cost/latency; gate in CI; calibrated judges.
- **Ops:** OTel everywhere incl. Kafka headers; SLOs; runbook R1–R7; chaos campaign.
- **Deliverables:** repo, architecture doc, runbook, tests, eval report, demo script, walkthrough.

### 18. Completion Checklist

- [ ] I built and can run the full stack locally with one command and a seeded demo.
- [ ] I can explain and defend every ADR against a simpler alternative.
- [ ] I implemented OIDC, RBAC, object-level authZ and RLS, with cross-tenant tests.
- [ ] I implemented the outbox/Kafka/worker pipeline with idempotency and trace propagation.
- [ ] I implemented the LLM router with fallback, breakers, structured output and cost metrics.
- [ ] I implemented hybrid pgvector RAG with citations and abstention, and measured it.
- [ ] I implemented bounded agents with durable state, approvals and crash-safe tools.
- [ ] I integrated MCP (server and client) under my own policies.
- [ ] I ran the failure-injection campaign and documented degraded behaviors.
- [ ] I produced the architecture doc, runbook, eval report, demo script and walkthrough.
- [ ] I deployed (or reproducibly scripted deployment) to AWS with CI/CD.

### 19. Further Research

**Essential**
- FastAPI "Bigger Applications", "Settings", "Testing", "Deployment" docs. <https://fastapi.tiangolo.com/>
- SQLAlchemy asyncio and Alembic cookbook (autogenerate, batch operations). <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html>
- pgvector README (HNSW tuning, filtering, iterative scans). <https://github.com/pgvector/pgvector>
- PostgreSQL Row Security Policies. <https://www.postgresql.org/docs/current/ddl-rowsecurity.html>
- OpenTelemetry Python and Collector docs; GenAI semantic conventions. <https://opentelemetry.io/docs/>
- MCP specification and official Python SDK. <https://modelcontextprotocol.io/>
- AWS ECS best practices guide and RDS for PostgreSQL pgvector docs.

**Deeper Study**
- *Designing Data-Intensive Applications* (outbox, logs, consistency).
- Anthropic engineering posts on agents, tool design and evals.
- LangGraph persistence and human-in-the-loop docs (for the optional variant).
- Google SRE Workbook (SLOs, alerting on burn rate).

**Practice**
- full-stack-fastapi-template for comparison of project structure.
- Testcontainers modules for Postgres, Redis, Kafka/Redpanda.
- k6 for load testing; Toxiproxy for network fault injection.

### Unit Completion Standard

You have completed the curriculum when you can: **explain** the end-to-end architecture of your platform — every flow, boundary and trade-off — at 30-second, 2-minute and deep levels; **implement** and run it locally and in AWS with FastAPI, Pydantic, PostgreSQL/pgvector, SQLAlchemy/Alembic, Redis, Kafka, workers, OIDC/RBAC/RLS, Docker, CI/CD and OpenTelemetry, plus the provider-neutral LLM layer, cited RAG, bounded agents with durable state, approvals and MCP; **test** it with unit, integration, contract, security, chaos, load and AI evaluation suites gated in CI; **debug** it from traces, metrics and runbooks under injected failures; and **defend** every architectural choice against a simpler alternative — including deterministic boundaries, failure handling, security and evaluation — in a 15-minute system-design walkthrough and a 45-minute scenario interview, backed by the repository, architecture document, runbook, test results, AI evaluation report and demo.
