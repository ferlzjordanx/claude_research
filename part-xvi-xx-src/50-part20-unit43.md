# Part XX — Final Capstone

**What this part teaches.** One project integrates the entire curriculum into a defensible, production-style system: Java/Spring Boot, distributed systems, security, AI, agentic workflows and observability. The capstone is both your strongest learning exercise and your interview evidence bank. Every claim you make in Units 39–42 should point to something in this repository.

**Why it matters.** Employers and customers don't hire for knowledge of isolated features. They hire for the ability to integrate them under real constraints and to explain the trade-offs. A capstone that demonstrates *authentication → authorization → retrieval/tool → grounded response → validation → trace/eval* end to end, with tests, evals and documentation, is rare and persuasive.

**Where it appears.** Portfolio reviews, architecture-defense interviews, FDE customer simulations, and as a template for real internal AI platforms.

**Connections.** Everything: Spring Boot APIs, PostgreSQL/JPA, Redis, Kafka, Security/OAuth/JWT, Docker, Testcontainers, CI/CD, AWS; Spring AI, embeddings, pgvector, RAG with citations, structured output, tools, MCP, single-agent and multi-step workflows; agent state, guardrails (Unit 33), structured decisions (Unit 34), human approval (Unit 35), evaluation (Unit 36), OpenTelemetry (Unit 37), system design (Unit 38), and interview defense (Units 39–42).

## Unit 43 — Production Agentic Enterprise Application

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Design** and **document** an integrated architecture for an agentic enterprise application, and **defend** why every component exists, what failure it addresses, and which simpler alternative was considered.
2. **Implement** Spring Boot REST APIs with PostgreSQL/JPA, Redis, Kafka, Spring Security (OAuth2/JWT), Docker, Testcontainers, CI/CD and an AWS deployment.
3. **Implement** Spring AI integration: embeddings and pgvector ingestion, RAG with citations, structured LLM output, tools, a single-agent loop and a multi-step workflow.
4. **Implement** agent state and checkpointing, an MCP server (and client usage), guardrails, human approval, OpenTelemetry tracing, an AI evaluation suite, cost/token measurement and graceful degradation.
5. **Demonstrate** the end-to-end flow *authentication → authorization → retrieval/tool → grounded response → validation → trace/eval* live, from a clean start, in a 5-minute demo.
6. **Produce** the deliverables: a production-style repository, architecture documentation (with ADRs), a demo script, an evaluation report, and an interview-ready technical walkthrough.
7. **Operate** the system: runbooks, dashboards, alerts, SLOs, incident drills and safe deployment.

### 2. Prerequisite Knowledge

Every earlier unit. Before starting, verify you can do each of these in isolation (if not, revisit the unit):

- Unit 33: tool policy + "compromised model" tests.
- Unit 34: `AgentDecision` + strict validation + bounded repair.
- Unit 35: approval state machine + exactly-once execution.
- Unit 36: eval harness + regression gate.
- Unit 37: OTel instrumentation + failure attribution.
- Unit 38: idempotency, outbox, rate limiting, backpressure.
- Unit 41: timed CRUD with security, pagination, Kafka, Redis, Testcontainers.
- Unit 42: bounded agent loop, filtered RAG, deployment pipeline.

### 3. Mental Model

The capstone is **SupportOps**, the agentic support platform used throughout Parts XVI–XVII, built as a real product. Think of it as **five concentric rings**, each of which must hold even if the inner ones misbehave:

```
 ┌───────────────────────────────────────────────────────────────────────────┐
 │ 5. OPERATIONS     CI/CD, eval gates, dashboards, alerts, runbooks, AWS     │
 │ ┌───────────────────────────────────────────────────────────────────────┐ │
 │ │ 4. OBSERVABILITY & EVALUATION   traces, metrics, cost, evals, audit   │ │
 │ │ ┌───────────────────────────────────────────────────────────────────┐ │ │
 │ │ │ 3. CONTROL     authN/Z, policy, validation, approval, limits      │ │ │
 │ │ │ ┌───────────────────────────────────────────────────────────────┐ │ │ │
 │ │ │ │ 2. PLATFORM   Spring Boot, PostgreSQL+pgvector, Redis, Kafka   │ │ │ │
 │ │ │ │ ┌───────────────────────────────────────────────────────────┐ │ │ │ │
 │ │ │ │ │ 1. AI CORE  models, embeddings, RAG, agent loop, MCP tools │ │ │ │ │
 │ │ │ │ └───────────────────────────────────────────────────────────┘ │ │ │ │
 │ │ │ └───────────────────────────────────────────────────────────────┘ │ │ │
 │ │ └───────────────────────────────────────────────────────────────────┘ │ │
 │ └───────────────────────────────────────────────────────────────────────┘ │
 └───────────────────────────────────────────────────────────────────────────┘
```

The headline flow you must be able to demonstrate:

```
authentication (OIDC → JWT)
   ↓
authorization (scopes, tenant, role limits → AgentContext)
   ↓
validated scope (per-turn tool allowlist; tenant/ACL filters)
   ↓
retrieval / tool execution (pgvector RAG; policy-checked tools; approval for writes)
   ↓
LLM (bounded loop; typed decisions)
   ↓
grounded response (citations ⊆ retrieved; output guard)
   ↓
validation (schema, semantics, policy at execution)
   ↓
trace / eval (OTel trace with cost; eval suite + online sampling)
```

### 4. Comprehensive Theory — Architecture and Component Rationale

#### 4.1 Functional Scope

**Personas.** Support rep (tier 1/tier 2), team lead (approver), finance approver, privacy officer, admin, and the end customer (indirect, via tickets/emails).

**Capabilities.**

1. **Ask (RAG):** reps ask policy/product questions and get grounded answers with citations from the tenant's knowledge base.
2. **Investigate (agent):** reps ask about a ticket. A bounded agent uses read-only tools (orders, refunds, shipments, KB, PSP status) to explain what happened.
3. **Act (workflow + approval):** the agent proposes actions (send email, update customer, issue refund, delete data). A deterministic approval workflow handles them.
4. **Ingest:** admins upload KB documents. A pipeline parses, chunks, embeds and indexes them with tenant/ACL metadata.
5. **Govern:** audit trail, approval queue, eval reports, cost per tenant, policy configuration.
6. **Integrate:** an MCP server exposes read-only KB search to other AI clients in the company, and the agent consumes an external MCP server (for example a carrier-tracking tool) through the same policy layer.

**Non-functional targets.** 50 tenants, 2,000 reps, 30k agent runs/day (peak 10 runs/s). Interactive p95 < 10 s (excluding approvals). 99.9% availability for the API. Zero cross-tenant leakage. Every executed action audited. Cost < $0.02 per run on average. Graceful degradation when the model provider is unavailable.

#### 4.2 Architecture

```
                        ┌────────────── AWS (eu-west-1) ──────────────────────────────────────┐
 Browser (SPA)          │                                                                      │
   │ OIDC (Cognito/     │  ALB (TLS, WAF) ──→ ECS Fargate: supportops-api (×2–10, virtual threads)│
   │ Keycloak) → JWT    │                      │   ├─ REST: /api/agent, /api/kb, /api/approvals,│
   └────────────────────┼──────────────────────┘   │        /api/admin, SSE /api/runs/{id}/events│
                        │                          │   ├─ Security: resource server (JWT)        │
                        │                          │   ├─ Guardrails, DecisionValidator, ToolPolicy│
                        │                          │   ├─ AgentService (bounded loop) + Workflow  │
                        │                          │   ├─ LLM Gateway (Spring AI; fallback; cost) │
                        │                          │   ├─ Retrieval (pgvector, tenant/ACL filter) │
                        │                          │   ├─ MCP client (carrier tool) via policy    │
                        │                          │   └─ Outbox writer                          │
                        │                          │                                             │
                        │  ECS: supportops-worker (×1–N) ⇠ MSK/Kafka ⇠ outbox relay              │
                        │     ├─ ingestion (parse → chunk → embed → upsert)                     │
                        │     ├─ approved-action executor (claim → re-validate → idempotent)    │
                        │     ├─ agent resume listener                                          │
                        │     └─ online eval sampler                                            │
                        │  ECS: supportops-mcp (MCP server: search_kb, read-only, OAuth2)        │
                        │                                                                        │
                        │  Aurora PostgreSQL 17 + pgvector (app schema, vectors, audit, outbox)  │
                        │  ElastiCache Redis/Valkey (rate limits, budgets, cache)                │
                        │  S3 (raw documents, eval artifacts)   Secrets Manager (provider keys)  │
                        │  ADOT/OTel Collector → Grafana Cloud or CloudWatch/X-Ray               │
                        └────────────────────────────────────────────────────────────────────────┘
                                          │ egress (NAT + allowlist)
                                          ▼
                         {Model providers: primary + fallback}   {Carrier MCP server}   {PSP API}
```

#### 4.3 Component Rationale (the defense table)

| Component | Why it exists / failure addressed | Simpler alternative considered | Why rejected / when to switch |
|---|---|---|---|
| Spring Boot 4 modular monolith (api) + worker + mcp | Clear deployables for different scaling and risk profiles | One service | Ingestion and execution have different scaling/failure needs; the MCP server has a separate exposure surface |
| Spring Modulith modules inside api | Enforced internal boundaries | Microservices per module | Premature distribution; keep in-process transactions for outbox |
| PostgreSQL (Aurora) + pgvector | One transactional store for domain, vectors, audit, outbox; SQL filters for ACL | Dedicated vector DB | Extra infra and consistency issues; switch at ~10⁸ vectors or high vector QPS |
| Flyway | Versioned, reviewable schema | `ddl-auto=update` | Unsafe and unreviewable |
| Redis | Distributed rate limits, token budgets, short-lived caches | In-memory per instance | Inconsistent across replicas |
| Kafka (MSK) + outbox | Reliable async (ingestion, execution, resume, notifications) without dual-write bugs | `@TransactionalEventListener` / SQS | Event loss on crash; Kafka chosen for replay and multiple consumers (SQS acceptable alternative) |
| OAuth2/OIDC + JWT resource server | Standard identity; scopes; tenant claims | Custom auth | Never roll your own |
| ToolPolicy + GuardedToolExecutor | Unauthorized/injected actions (Unit 33) | Prompt rules | Not enforceable |
| DecisionValidator (typed output) | Malformed/ambiguous decisions (Unit 34) | Prose parsing | Fragile and unsafe |
| Approval service | Irreversible high-impact actions; compliance (Unit 35) | Auto-execute / approve-all | Unsafe / fatigue |
| Bounded agent + workflow hybrid | Variable investigations + deterministic actions | Pure agent / pure workflow | Eval comparison (Unit 42) |
| LLM Gateway | Provider abstraction, timeouts, retries, fallback, cost metering, caching | Direct `ChatClient` everywhere | Duplicated resilience/cost logic |
| MCP server (search_kb) | Reuse KB search across company AI clients via a standard protocol | Bespoke REST | MCP clients can discover and use tools natively; REST still available |
| MCP client (carrier tool) | Integrate external tool without custom SDK | Custom HTTP client | Standard interface, still wrapped by policy |
| OpenTelemetry | One trace per workflow; attribution; cost (Unit 37) | Logs only | No causality |
| Eval suite + CI gate | Regressions on prompt/model/tool change (Unit 36) | Manual testing | Not repeatable |
| Testcontainers | Real PostgreSQL/Kafka/Redis behavior in tests | H2/mocks | Dialect drift, false confidence |
| ECS Fargate | Simple container ops | EKS | No platform team; switch for K8s ecosystem needs |
| Secrets Manager + IAM task roles | No static credentials | Env-var keys | Leakage risk |

#### 4.4 Data Model (core tables)

```
tenant(id, name, plan, monthly_token_budget)
app_user(id, tenant_id, idp_subject, role, refund_limit)
ticket(id, tenant_id, customer_id, subject, status, created_at)
ticket_message(id, ticket_id, direction, body, source, untrusted bool)
customer(id, tenant_id, email citext, name, phone, ...)            -- SupportOps domain fixtures
orders(id, tenant_id, customer_id, total, refunded, status, ...)

kb_document(id, tenant_id, title, source_uri, version, acl_groups text[], status, ingested_at)
kb_chunk(id uuid, document_id, tenant_id, acl_groups text[], ordinal, content text,
         embedding vector(1024), content_hash, created_at)
   INDEX hnsw (embedding vector_cosine_ops); INDEX (tenant_id); GIN (acl_groups)

agent_run(id, tenant_id, user_id, agent_id, agent_version, status, stop_reason,
          checkpoint jsonb, steps, input_tokens, output_tokens, cost_usd, origin_trace, created_at)
action_proposal / approval_decision / action_execution / audit_event      (Unit 35)
outbox(id, aggregate_type, aggregate_id, event_type, payload jsonb, traceparent, created_at, published_at)
processed_message(consumer, message_id)                                   (Unit 38)
idempotency_record                                                         (Unit 38)
eval_run(id, dataset_version, config_hash, scorecard jsonb, created_at); online_eval_score(trace_id, metric, value)
```

The embedding dimension must match the embedding model (for example 1024 or 1536). Record the embedding model and version on `kb_document` so you can re-embed on model change.

#### 4.5 Key Flows

**Flow A — Grounded answer (RAG).**

```
POST /api/agent/ask {question}  (JWT)
→ AgentContext(tenant, groups, scopes) → InputGuard
→ Retrieval: embed query → pgvector search WHERE tenant_id = ? AND acl_groups && ? → top 20 → rerank → top 5
→ ContextBuilder (doc IDs, spotlighting, budget)
→ LLM Gateway: structured AgentDecision{ANSWER, answer, citations}
→ DecisionValidator: schema + citations ⊆ retrieved → OutputGuard
→ response {answer, citations[{id, title, url}], traceId}
→ trace: invoke_agent → embeddings → retrieval(DB) → chat → validate → guardrail.output
```

**Flow B — Investigation (bounded agent, read-only).** `POST /api/agent/runs {ticketId, message}` → `202 {runId}` + SSE events. The worker runs `BoundedAgent` with read-only tools (`get_order`, `get_refunds`, `get_shipment` via MCP carrier server, `search_kb`). Each step is checkpointed. Stop reasons are recorded.

**Flow C — Action with approval.** The agent proposes `issue_refund` → policy → `RequireApproval` → proposal persisted → run paused → lead approves (four-eyes, hash) → outbox → executor claims → re-validates → PSP call with idempotency key → `EXECUTED` → resume → agent tells the rep the refund reference.

**Flow D — Ingestion.** Upload → S3 → `kb_document(PENDING)` + outbox → worker: parse (Apache Tika), normalize, chunk (by headings, ~500–800 tokens, overlap ~50–100), dedupe by content hash, embed in batches (with rate limiting), upsert chunks with tenant/ACL metadata in one transaction → `READY`. Re-ingesting a document version replaces its chunks atomically.

**Flow E — Degradation.** Primary provider 5xx/timeouts → bounded retries → circuit opens → fallback model (pre-evaluated) → if the fallback also fails: Ask returns top KB snippets with links ("I can't generate an answer right now; here are the most relevant articles"), and Investigate returns "queued, we'll notify you" (runs are retried later from the checkpoint).

### 5. Internal Mechanics — What Happens in One Investigation Run

```
t=0     ALB → api (virtual thread) → JwtAuthenticationFilter → AgentController.startRun
        → idempotency check (Idempotency-Key) → agent_run(PENDING) + outbox(run.requested) → 202
t=5ms   relay → Kafka runs.requested (key=runId)
t=20ms  worker consumer (dedupe) → AgentContextFactory.forRun (user's CURRENT scopes/limits from DB)
        → Redis: tenant token budget check (Lua) → BoundedAgent.run
          step 1: LLM Gateway.chat (span chat; tokens; cost) → DecisionValidator → CALL_TOOL get_order
                  → ToolPolicy ALLOW → execute (span execute_tool) → observation (spotlighted)
                  → checkpoint (agent_run.checkpoint jsonb, steps=1)
          step 2: … search_kb (retrieval span → DB span)
          step 3: … carrier.get_shipment via MCP client (HTTP span with traceparent)
          step 4: ANSWER with citations → validator → output guard → stop(ANSWERED)
        → agent_run(COMPLETED, tokens, cost, stop_reason) + outbox(run.completed)
        → SSE pushes events to the browser (subscribed via api; Redis pub/sub or Kafka → api fan-out)
        → online eval sampler (2%) → groundedness judge → online_eval_score(trace_id)
```

### 6. Implementation Examples

The examples below show the integration-critical pieces not already covered in Units 33–42. Reuse those units' classes (`InputGuard`, `ToolPolicy`, `GuardedToolExecutor`, `DecisionValidator`, `DecisionLoop`, `ApprovalService`, `ApprovedActionExecutor`, `BoundedAgent`, `KnowledgeRetriever`, observability classes).

#### Example 1 — Minimal: Repository skeleton, build and local stack

```
supportops/
├── README.md                        quick start, architecture summary, demo link
├── docs/
│   ├── architecture.md              (template §10)
│   ├── adr/0001-modular-monolith.md … 0010-*.md
│   ├── threat-model.md              (Unit 33 table)
│   ├── observability.md             (span catalogue, dashboards, failure demo)
│   ├── evaluation-report.md         (template §10)
│   ├── demo-script.md               (template §10)
│   ├── runbook.md                   (template §10)
│   └── walkthrough.md               (interview walkthrough, template §10)
├── compose.yaml                     postgres(pgvector), redis, kafka, otel-lgtm, keycloak
├── pom.xml                          (multi-module)
├── supportops-core/                 domain, policy, decision, approval, audit, outbox (no web)
├── supportops-ai/                   LLM gateway, retrieval, ingestion, agent, eval harness
├── supportops-api/                  REST, security, SSE (Spring Boot app)
├── supportops-worker/               Kafka consumers, executor, ingestion, sweeper (Spring Boot app)
├── supportops-mcp/                  MCP server (Spring Boot app)
├── eval/                            datasets, baselines, human labels
├── ops/                             otel-collector.yaml, grafana dashboards, alerts
├── infra/                           terraform/ (vpc, ecs, aurora, elasticache, msk, s3, secrets)
└── .github/workflows/               ci.yml, eval.yml, deploy.yml
```

```yaml
# compose.yaml (local development)
services:
  postgres:
    image: pgvector/pgvector:pg17          # PostgreSQL 17 with pgvector preinstalled
    environment: { POSTGRES_DB: supportops, POSTGRES_USER: app, POSTGRES_PASSWORD: app }
    ports: ["5432:5432"]
  redis:
    image: redis:8-alpine
    ports: ["6379:6379"]
  kafka:
    image: apache/kafka:4.1.0              # KRaft single-node
    ports: ["9092:9092"]
  keycloak:
    image: quay.io/keycloak/keycloak:26.4
    command: start-dev --import-realm
    volumes: ["./ops/keycloak:/opt/keycloak/data/import"]
    environment: { KC_BOOTSTRAP_ADMIN_USERNAME: admin, KC_BOOTSTRAP_ADMIN_PASSWORD: admin }
    ports: ["8081:8080"]
  lgtm:
    image: grafana/otel-lgtm:latest        # pin a digest for real use
    ports: ["3000:3000", "4317:4317", "4318:4318"]
```

(Pin all image tags and digests you've actually tested. Spring Boot's Docker Compose support can start this file automatically during `spring-boot:run`.)

```xml
<!-- supportops-api/pom.xml (key dependencies; versions managed by the Spring Boot 4.1 and Spring AI 2.0 BOMs) -->
<dependencies>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-webmvc</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-validation</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-security</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-oauth2-resource-server</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-redis</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-kafka</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-actuator</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-opentelemetry</artifactId></dependency>
  <dependency><groupId>org.flywaydb</groupId><artifactId>flyway-database-postgresql</artifactId></dependency>
  <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId><scope>runtime</scope></dependency>
  <dependency><groupId>org.springframework.ai</groupId><artifactId>spring-ai-starter-model-anthropic</artifactId></dependency>
  <dependency><groupId>org.springframework.ai</groupId><artifactId>spring-ai-starter-vector-store-pgvector</artifactId></dependency>
  <dependency><groupId>org.springframework.ai</groupId><artifactId>spring-ai-starter-mcp-client</artifactId></dependency>
  <!-- tests -->
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-webmvc-test</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-testcontainers</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.springframework.security</groupId><artifactId>spring-security-test</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.testcontainers</groupId><artifactId>testcontainers-postgresql</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.testcontainers</groupId><artifactId>testcontainers-kafka</artifactId><scope>test</scope></dependency>
  <dependency><groupId>com.tngtech.archunit</groupId><artifactId>archunit-junit5</artifactId><scope>test</scope></dependency>
</dependencies>
```

[Version-dependent] Starter artifact names changed across Spring AI 1.0 → 2.0 and Boot 3 → 4 (for example `spring-boot-starter-web` → `spring-boot-starter-webmvc`; Kafka starter naming; Testcontainers 2.x module coordinates). Generate the skeleton at start.spring.io for your exact versions, then copy the coordinates.

#### Example 2 — Realistic: LLM gateway with timeouts, fallback, cost metering and degradation

```java
package com.example.supportops.ai.gateway;

import com.example.supportops.observability.AgentAttributes;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.concurrent.*;

@Component
public class LlmGateway {

    public sealed interface Result {
        record Ok(String content, String model, long inputTokens, long outputTokens, BigDecimal costUsd,
                  boolean fallbackUsed) implements Result {}
        record Unavailable(String reason) implements Result {}
    }

    private final ChatClient primary;
    private final ChatClient fallback;
    private final CircuitBreaker breaker;      // small in-house or Resilience4j CircuitBreaker
    private final PriceTable prices;
    private final TenantBudget budgets;        // Redis Lua: reserve/settle tokens per tenant per day
    private final MeterRegistry meters;
    private final Duration timeout = Duration.ofSeconds(20);

    public LlmGateway(@Qualifier("primaryChat") ChatClient primary, @Qualifier("fallbackChat") ChatClient fallback,
                      CircuitBreaker breaker, PriceTable prices, TenantBudget budgets, MeterRegistry meters) {
        this.primary = primary; this.fallback = fallback; this.breaker = breaker;
        this.prices = prices; this.budgets = budgets; this.meters = meters;
    }

    public Result chat(String tenantId, String system, String user, int maxOutputTokens) {
        if (!budgets.tryReserve(tenantId, estimateTokens(system, user) + maxOutputTokens)) {
            meters.counter("llm.budget.rejected", "tenant_tier", budgets.tier(tenantId)).increment();
            return new Result.Unavailable("TENANT_BUDGET_EXHAUSTED");
        }
        if (breaker.allowRequest()) {
            try {
                var r = call(primary, system, user);
                breaker.recordSuccess();
                return settle(tenantId, r, false);
            } catch (TimeoutException | RuntimeException e) {
                breaker.recordFailure();
                meters.counter("llm.primary.failure", "type", e.getClass().getSimpleName()).increment();
            }
        }
        try {
            var r = call(fallback, system, user);
            meters.counter("llm.fallback.used").increment();
            return settle(tenantId, r, true);
        } catch (TimeoutException | RuntimeException e) {
            budgets.release(tenantId);
            return new Result.Unavailable("ALL_PROVIDERS_FAILED");
        }
    }

    private ChatResponse call(ChatClient client, String system, String user) throws TimeoutException {
        // The HTTP client underneath also has connect/read timeouts; this is the overall deadline.
        var f = CompletableFuture.supplyAsync(
            () -> client.prompt().system(system).user(user).call().chatResponse(),
            Executors.newVirtualThreadPerTaskExecutor());
        try {
            return f.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(e);
        } catch (ExecutionException e) {
            throw e.getCause() instanceof RuntimeException re ? re : new IllegalStateException(e.getCause());
        } finally {
            f.cancel(true);
        }
    }

    private Result settle(String tenantId, ChatResponse r, boolean fallbackUsed) {
        var usage = r.getMetadata().getUsage();
        long in = usage.getPromptTokens() == null ? 0 : usage.getPromptTokens();
        long out = usage.getCompletionTokens() == null ? 0 : usage.getCompletionTokens();
        String model = r.getMetadata().getModel();
        BigDecimal cost = prices.cost(model, in, out);
        budgets.settle(tenantId, in + out);
        meters.counter("agent.cost.usd", "model", model).increment(cost.doubleValue());
        return new Result.Ok(r.getResult().getOutput().getText(), model, in, out, cost, fallbackUsed);
    }

    private static long estimateTokens(String... parts) {
        long chars = 0;
        for (String p : parts) chars += p == null ? 0 : p.length();
        return chars / 4 + 1;     // rough estimate for budget reservation; settled with actual usage
    }
}
```

**Notes.** Creating a new virtual-thread executor per call is cheap but should be closed. In real code, inject a shared `ExecutorService` bean (`Executors.newVirtualThreadPerTaskExecutor()` as a singleton) or use the HTTP client's own timeouts plus Spring Framework 7 resilience annotations. Spring AI's `ChatResponse` metadata API names (`getUsage`, `getPromptTokens`, `getCompletionTokens`) follow 1.x/2.0 conventions [Version-dependent]. The fallback model must be in the eval suite, because you shouldn't fail over to an unevaluated model. Spring AI's own observations already record token usage on `chat` spans. The gateway adds tenant budgets, cost and fallback metrics.

**Ingestion chunker (heading-aware, token-bounded).**

```java
package com.example.supportops.ai.ingest;

import java.util.ArrayList;
import java.util.List;

public final class HeadingAwareChunker {

    public record Chunk(int ordinal, String heading, String text) {}

    private final int maxChars;      // ≈ tokens × 4
    private final int overlapChars;

    public HeadingAwareChunker(int maxChars, int overlapChars) {
        if (overlapChars >= maxChars) throw new IllegalArgumentException("overlap must be < max");
        this.maxChars = maxChars;
        this.overlapChars = overlapChars;
    }

    /** Splits markdown-like text on headings first, then on paragraph boundaries within a section. */
    public List<Chunk> chunk(String text) {
        List<Chunk> out = new ArrayList<>();
        String heading = "";
        StringBuilder buf = new StringBuilder();
        for (String block : text.split("\\n\\s*\\n")) {                 // paragraphs
            String b = block.strip();
            if (b.isEmpty()) continue;
            if (b.startsWith("#")) {                                       // new section: flush
                flush(out, heading, buf);
                heading = b.replaceFirst("^#+\\s*", "");
                continue;
            }
            if (buf.length() + b.length() + 2 > maxChars && !buf.isEmpty()) {
                String carry = tail(buf.toString(), overlapChars);
                flush(out, heading, buf);
                buf.append(carry);
            }
            if (b.length() > maxChars) {                                   // very long paragraph (e.g. table)
                for (int i = 0; i < b.length(); i += maxChars - overlapChars) {
                    flush(out, heading, buf);
                    buf.append(b, i, Math.min(b.length(), i + maxChars));
                }
            } else {
                if (!buf.isEmpty()) buf.append("\n\n");
                buf.append(b);
            }
        }
        flush(out, heading, buf);
        return out;
    }

    private void flush(List<Chunk> out, String heading, StringBuilder buf) {
        if (buf.isEmpty()) return;
        String body = heading.isEmpty() ? buf.toString() : heading + "\n\n" + buf;   // keep section context
        out.add(new Chunk(out.size(), heading, body));
        buf.setLength(0);
    }

    private static String tail(String s, int n) {
        return s.length() <= n ? s : s.substring(s.length() - n);
    }
}
```

Test it on real KB samples: tables, lists, very long paragraphs, and documents without headings. Chunking quality shows up directly in retrieval recall@k (Unit 36), so the eval suite compares chunker configurations.

#### Example 3 — Production-oriented: MCP server, end-to-end test, CI with eval gate, AWS deployment

**MCP server exposing read-only KB search** (separate deployable `supportops-mcp`):

```java
package com.example.supportops.mcp;

import com.example.supportops.rag.KnowledgeRetriever;
import org.springframework.ai.mcp.annotation.McpTool;
import org.springframework.ai.mcp.annotation.McpToolParam;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.List;

@Component
class KnowledgeBaseMcpTools {

    record Hit(String docId, String title, String snippet, String url) {}

    private final KnowledgeRetriever retriever;

    KnowledgeBaseMcpTools(KnowledgeRetriever retriever) { this.retriever = retriever; }

    @McpTool(name = "search_kb",
             description = "Search the caller's tenant knowledge base. Returns up to 5 snippets with document IDs. Read-only.")
    List<Hit> searchKb(@McpToolParam(description = "Natural-language query, max 300 chars", required = true)
                       String query) {
        if (query == null || query.isBlank() || query.length() > 300) {
            throw new IllegalArgumentException("query must be 1–300 characters");
        }
        // Identity comes from the OAuth2 access token on the MCP HTTP request, never from tool arguments.
        var auth = (JwtAuthenticationToken) SecurityContextHolder.getContext().getAuthentication();
        String tenant = auth.getToken().getClaimAsString("tenant_id");
        var groups = new HashSet<>(auth.getToken().getClaimAsStringList("groups"));
        return retriever.retrieve(query, tenant, groups).stream()
            .map(e -> new Hit(e.docId(), e.title(), snippet(e.text()), "https://kb.example.com/d/" + e.docId()))
            .toList();
    }

    private static String snippet(String text) {
        return text.length() <= 600 ? text : text.substring(0, 600) + "…";
    }
}
```

[Version-dependent] Spring AI 2.0 includes the MCP annotations (`@McpTool`, `@McpToolParam`) and server starters (`spring-ai-starter-mcp-server-webmvc`), with Streamable HTTP as the default transport. Package names for the annotations and the OAuth2 integration (spring-ai-community `mcp-security`) should be checked against your version. Secure the MCP endpoint as an OAuth2 resource server. The tool takes no identity parameters.

**End-to-end IT (the demo flow as a test).**

```java
package com.example.supportops.e2e;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;

@SpringBootTest
@AutoConfigureMockMvc
class AuthToTraceEndToEndIT extends AllContainersBase {   // PG+pgvector, Kafka, Redis; scripted model bean

    @Autowired MockMvcTester mvc;
    @Autowired TestSpanExporter spans;        // in-memory OTel exporter
    @Autowired SeedData seed;                 // two tenants, KB docs, orders, users

    @Test
    void groundedAnswerIsAuthorizedFilteredValidatedAndTraced() {
        seed.tenantA().kb("D-12", "Late delivery policy", "Shipping refund up to $25 when > 5 days late.");
        seed.tenantB().kb("D-99", "Late delivery policy", "Tenant B secret policy text.");

        var res = mvc.post().uri("/api/agent/ask")
            .with(jwt().jwt(j -> j.claim("tenant_id", "A").claim("groups", java.util.List.of("support")))
                       .authorities(new org.springframework.security.core.authority.SimpleGrantedAuthority("SCOPE_agent:ask")))
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"question\":\"What is our late delivery policy?\"}");

        assertThat(res).hasStatusOk();
        assertThat(res).bodyJson().extractingPath("$.citations[*].id").asArray().containsExactly("D-12");
        assertThat(res).bodyJson().extractingPath("$.answer").asString().doesNotContain("Tenant B");

        var trace = spans.singleTrace();
        assertThat(trace.names()).contains("invoke_agent", "retrieval", "chat", "decision.validate", "guardrail.output");
        assertThat(trace.attribute("chat", "gen_ai.usage.input_tokens")).isNotNull();
    }

    @Test
    void anonymousIsRejectedBeforeAnyModelCall() {
        assertThat(mvc.post().uri("/api/agent/ask").contentType(MediaType.APPLICATION_JSON).content("{\"question\":\"x\"}"))
            .hasStatus(401);
        assertThat(spans.namesSince()).doesNotContain("chat");
    }
}
```

**CI pipeline (GitHub Actions).**

```yaml
# .github/workflows/ci.yml
name: ci
on: [pull_request, push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '25', cache: maven }
      - run: ./mvnw -B verify                       # unit + slice + Testcontainers ITs (eval tag excluded)
      - run: ./mvnw -B -pl supportops-api,supportops-worker,supportops-mcp spring-boot:build-image -DskipTests
        if: github.ref == 'refs/heads/main'

  eval-smoke:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - id: changed
        run: |
          if git diff --name-only origin/${{ github.base_ref }}...HEAD | grep -qE '^(supportops-ai/|eval/|.*/prompts/|.*/tools/)'; then
            echo "run=true" >> "$GITHUB_OUTPUT"; fi
      - uses: actions/setup-java@v4
        if: steps.changed.outputs.run == 'true'
        with: { distribution: temurin, java-version: '25', cache: maven }
      - if: steps.changed.outputs.run == 'true'
        run: ./mvnw -B -pl supportops-ai verify -Dgroups=eval -Deval.subset=smoke
        env:
          ANTHROPIC_API_KEY: ${{ secrets.EVAL_ANTHROPIC_API_KEY }}    # separate, budget-capped eval key
      - if: always() && steps.changed.outputs.run == 'true'
        uses: actions/upload-artifact@v4
        with: { name: eval-report, path: supportops-ai/target/eval-report }
```

A nightly workflow runs the full eval suite with N = 3, and `deploy.yml` deploys on tagged releases (build image → push to ECR → update the ECS service with a rolling or blue/green deployment via CodeDeploy, with alarms for automatic rollback).

**AWS (Terraform outline).**

```
infra/terraform/
├── network.tf        VPC, 2–3 AZs, private subnets (apps, data), public subnets (ALB, NAT), VPC endpoints (S3, ECR, Secrets)
├── ecs.tf            cluster; services api/worker/mcp; task roles (least privilege); autoscaling (CPU, ALB req count, Kafka lag)
├── alb.tf            ALB + WAF; target groups with /actuator/health/readiness; HTTPS (ACM)
├── aurora.tf         Aurora PostgreSQL 17 (pgvector extension), Multi-AZ, encrypted, IAM auth or Secrets Manager rotation
├── elasticache.tf    Redis/Valkey replication group, TLS, auth
├── msk.tf            MSK Serverless (IAM auth) or SQS alternative
├── s3.tf             documents bucket (SSE-KMS, block public access), eval artifacts
├── secrets.tf        model provider keys, PSP keys; rotation
├── observability.tf  ADOT collector sidecar/service; Grafana/CloudWatch; alarms (SLOs, cost, stuck executions)
└── egress.tf         NAT + egress allowlist (proxy or Network Firewall) for model providers / carrier MCP
```

### 7. Comparative Analysis — Capstone Decisions

| Decision | Chosen | Alternative | Rationale | Revisit when |
|---|---|---|---|---|
| Deployables | api / worker / mcp | single app; many microservices | Different scaling and exposure; outbox needs shared DB tx | Team grows; modules need independent release cadence |
| Vector store | pgvector in Aurora | OpenSearch, dedicated vector DB | One transactional store; SQL ACL filters | > 10⁸ chunks; hybrid search at scale |
| Messaging | Kafka (MSK) | SQS/SNS | Replay, multiple consumer groups, ordering by key | Ops burden too high: SQS FIFO per group |
| Agent style | Workflow + bounded agent step | Pure agent | Eval comparison: cost/latency/predictability | Use cases with highly variable paths |
| Model access | Spring AI `ChatClient` behind gateway | Provider SDKs | Portability, observations, structured output | Need provider-specific features not exposed |
| Output | Raw text + own validator | `entity()` + validation advisor | Control, failure classes, testability | Low-risk extraction endpoints |
| Approvals | Async via outbox | Sync in reviewer request | Resilience, retries, idempotency | Very low-volume internal tools |
| Identity | Keycloak (dev) / Cognito or enterprise IdP (prod) | Custom auth | Standards, SSO | Never custom |
| Observability | Boot OTel starter | OTel Java agent | Spring-native config, native-image friendly | Need broader library coverage |
| Compute | ECS Fargate | EKS, Lambda | Simplicity | K8s platform exists; event-driven workloads |

### 8. Failure Modes and Debugging — Capstone Game Days

Run these drills before your demo. For each, record the detection signal, diagnosis path and recovery in `docs/runbook.md`.

| Drill | Inject | Expected detection | Expected behavior |
|---|---|---|---|
| Provider outage | Block egress to primary provider | `llm.primary.failure` spike; breaker open | Fallback model; then KB-snippet degradation |
| Prompt injection | Ticket email with hidden instructions | `agent.tool.policy{decision=Deny}`; audit | No write executed; proposal (if any) shows untrusted provenance |
| Cross-tenant probe | Query tenant B content as tenant A | Eval critical case; retrieval filter in trace | Zero tenant-B docs retrieved |
| Duplicate execution | Redeliver `approval.decided` 5× | Executor logs; claim conflicts | One PSP call (idempotency key) |
| Worker crash mid-run | Kill worker during step 3 | Run stuck alert | Resume from checkpoint; tool calls not duplicated |
| Kafka unavailable | Stop broker | Outbox backlog metric | API keeps accepting; relay catches up after recovery |
| Redis down | Stop Redis | Rate-limit fallback metric | Fail-open (general) / fail-closed (LLM budgets) per policy |
| Cost runaway | Tool description that causes loops | `agent.run.stop{reason=MAX_STEPS}`; cost alert | Runs stop at limits; alert fires |
| Bad prompt change | Remove citation instruction | Eval gate fails in CI | PR blocked |
| Model drift | Switch to unpinned alias | Schema compliance drop in canary | Automatic rollback |

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**1.1** Write the component defense table (4.3) in your own words, adding one row for any component you add.
**1.2** Draw the five flows (A–E) as sequence diagrams and mark every trust boundary.

#### Level 2 — Implementation

**2.1** Implement Flow A end to end with tests (Unit 41 style), including tenant isolation.
**2.2** Implement ingestion with the chunker, batch embeddings and atomic chunk replacement per document version. Add tests for re-ingestion and deletion (chunks removed).
**2.3** Implement `TenantBudget` in Redis (reserve/settle/release with Lua) and the `llm.budget.rejected` metric.

#### Level 3 — Integration

**3.1** Implement Flows B and C with pause/resume and SSE updates, and the end-to-end IT with a scripted model.
**3.2** Implement the MCP server and connect the agent to an external MCP tool (a local mock "carrier" MCP server) through `ToolPolicy`.
**3.3** Deploy to AWS (or a local Kubernetes/compose equivalent if cost is a constraint), with dashboards and alerts.

#### Level 4 — Debugging / Production Scenario

**4.1** Run all game-day drills (Section 8) and write a postmortem for the most interesting one.
**4.2** A reviewer finds that `/api/agent/ask` responses sometimes include an outdated policy version. Diagnose (ingestion versioning? cache? chunk replacement not atomic?) and fix with a test.

### 10. Independent Implementation Project — The Capstone Specification

**Goal.** Build SupportOps as a production-style repository and deliver the documentation, demo, evaluation report and walkthrough.

**Functional requirements.**

1. Multi-tenant KB ingestion (upload, versioning, deletion) with ACL metadata.
2. `/api/agent/ask`: RAG with citations, abstention when evidence is missing.
3. `/api/agent/runs`: bounded investigation agent with read-only tools (including one MCP-sourced tool), SSE progress, checkpointing and resume.
4. Action proposals for `send_email`, `update_customer`, `issue_refund`, `delete_customer_data` with risk classification, approvals (four-eyes, eligibility, hash binding), async exactly-once execution with re-validation, and agent resume.
5. Reviewer UI or API: queue, detail with exact effect/diff/provenance, decision.
6. Admin: tenant budgets, policy version display, audit search and chain verification, eval reports.
7. MCP server exposing `search_kb` (read-only, OAuth2).
8. Graceful degradation (fallback model; KB-snippet mode; queued runs).

**Technical requirements.**

- Java 25; Spring Boot 4.1; Spring Framework 7; Spring Security 7 (resource server, method security); Spring Data JPA/Hibernate 7; Flyway; PostgreSQL 17 + pgvector; Redis/Valkey; Kafka 4.x (outbox, idempotent consumers, DLT); Spring AI 2.0 (chat, embeddings, pgvector store, MCP client and server); Jackson 3; OpenTelemetry (Boot starter or Java agent); Docker; Testcontainers 2.x; GitHub Actions; AWS (ECS Fargate, Aurora, ElastiCache, MSK or SQS, S3, Secrets Manager) via Terraform.
- Units 33–37 components implemented as specified in their projects.

**Implementation milestones (8 weeks).**

| Week | Milestone | Exit criteria |
|---|---|---|
| 1 | Skeleton, compose, security (Keycloak), tenants/users, Flyway, CI | Authenticated hello-world with tenant context; CI green |
| 2 | Ingestion + pgvector + Flow A (RAG) | Tenant-isolated retrieval tests; recall@5 on 30-question mini set |
| 3 | Structured decisions + guardrails + tool policy + read tools | Compromised-model suite green |
| 4 | Bounded agent + checkpointing + SSE + MCP client tool | Stop-reason tests; resume test |
| 5 | Approvals + outbox + executor + resume | Concurrency/redelivery ITs; four-eyes tests |
| 6 | Observability + cost + budgets + degradation | Trace structure ITs; failure demo; fallback drill |
| 7 | Eval suite (≥ 120 cases) + CI gate + online sampler; MCP server | Gate blocks bad prompt; baseline committed |
| 8 | AWS deployment, dashboards/alerts, game days, docs, demo, walkthrough | All deliverables complete |

**Testing requirements.** See Section 11. Minimum: compromised-model suite, tenant isolation (critical), approval concurrency, idempotent consumers, end-to-end auth-to-trace IT, eval gate, trace structure, cardinality and no-content tests.

**Definition of done.**

- `docker compose up` + `./mvnw spring-boot:run` gives a working local system. The demo script runs from a clean start in ≤ 5 minutes.
- CI: build, all tests, smoke eval gate on relevant PRs; nightly full eval; baseline committed.
- No path from model output to a write tool without a validated decision, a policy check and (for gated tools) an executed approval, verified by ArchUnit and tests.
- Zero cross-tenant results in the eval suite (critical cases).
- Each executed action traceable from audit to trace to evidence in under a minute.
- Docs complete: architecture (with ADRs), threat model, observability, evaluation report, runbook, demo script, walkthrough.

**Optional extensions.** Multi-agent variant (researcher + writer + reviewer) with per-agent evals. Hybrid search (BM25 + vectors with reciprocal rank fusion). Prompt caching. Per-tenant model routing. Signed approvals. Data residency (EU-only endpoints). Native image for the MCP server.

#### Deliverable Templates

**A. Architecture document (`docs/architecture.md`).**

```
1. Context and goals (problem, users, success metrics, non-goals)
2. Requirements (functional; non-functional with numbers: load, latency, availability, cost, security)
3. Architecture overview (diagram; deployables; data stores; external dependencies; trust boundaries)
4. Key flows (A–E sequence diagrams)
5. Data model (ERD; retention; PII classification)
6. Security (identity; authorization model; tenant isolation; guardrails; approvals; secrets; threat model link)
7. AI design (RAG pipeline stages; agent spec: goal, tools, schemas, state, loop, limits, stops; structured output; MCP)
8. Reliability (failure modes; idempotency; outbox; retries; degradation; RTO/RPO)
9. Observability (span catalogue; metrics; dashboards; alerts; SLOs)
10. Evaluation (datasets; metrics; gates; online loop)
11. Deployment (AWS topology; CI/CD; release strategy; rollback)
12. Cost model (per-run estimate; per-tenant budgets)
13. Decisions (ADR index) and rejected alternatives
14. Risks and open questions
```

**B. ADR template (`docs/adr/NNNN-title.md`).** Status · Context · Decision · Alternatives considered (with why rejected) · Consequences (positive/negative) · Revisit triggers.

**C. Demo script (`docs/demo-script.md`), 5 minutes.**

```
0:00  Context: "SupportOps helps reps resolve tickets with grounded answers and safe actions."
0:20  Login as tier-1 rep (Keycloak) → show JWT claims (tenant, groups, scopes) in a debug panel
0:40  Ask: "What's our late delivery policy?" → answer with citation D-12 → click citation
1:10  Show trace in Grafana: retrieval filtered by tenant/ACL, chat tokens/cost, validation, guardrail
1:40  Investigate ticket T-17 → SSE steps: get_order, get_shipment (MCP), search_kb → explanation
2:20  Agent proposes $20 refund → PENDING_APPROVAL; rep cannot approve own proposal (show 403)
2:50  Login as lead → review card (exact effect, provenance, risk reasons) → approve
3:20  Executor runs → refund reference → agent resumes → final message; audit chain verified
3:50  Injection attempt: ticket with hidden instruction → write tools hidden; denial in trace; no action
4:20  Eval report: scorecard vs baseline (task success, groundedness, recall@5, critical = 0, cost)
4:45  Degradation toggle: primary provider blocked → fallback/KB-snippet mode visible in trace
5:00  Close: "Every component exists for a failure we can show; here's the evidence."
```

**D. Evaluation report (`docs/evaluation-report.md`).**

```
1. Summary (headline metrics vs thresholds; go/no-go)
2. Dataset (version; size; slices; sources; labelling process; known gaps)
3. System under test (commit; models + versions; prompt hashes; tool schemas; retrieval config; judge version)
4. Results (tables per metric and per slice, with CIs; retrieval vs generation 2×2; cost/latency)
5. Safety (adversarial slice; model-level vs system-level ASR; critical failures = 0 evidence)
6. Comparison vs baseline (paired analysis; newly failing/passing cases with transcript/trace links)
7. Experiments (workflow vs agent; chunking configs; fallback model)
8. Online signals (pilot/shadow results, approval rejection, feedback)
9. Limitations and next steps
```

**E. Runbook (`docs/runbook.md`).** For each alert: meaning, dashboard link, first queries, likely causes, mitigation steps (flags/kill switches), escalation, and post-incident tasks (add eval case).

**F. Interview walkthrough (`docs/walkthrough.md`).** 10-minute talk track: problem → architecture → one deep flow (C: approval) → one hard problem you solved (with evidence) → evaluation results → what you'd do next. Then the component defense table and the five core AI/FDE answers (Unit 42), each linked to code.

### 11. Testing Strategy

| Layer | Tests | Tools |
|---|---|---|
| Domain/pure | Policy, risk classifier, validator, chunker, budget math, state machines | JUnit, AssertJ, parameterized |
| Security | Compromised-model suite; IDOR; scopes; four-eyes; tenant isolation (critical) | Scripted model, `jwt()`, Testcontainers |
| Persistence | Constraints, conditional updates, `SKIP LOCKED`, pgvector filtered search | Testcontainers `pgvector/pgvector:pg17` |
| Messaging | Outbox relay, idempotent consumers, redelivery, DLT | Testcontainers Kafka |
| Caching/limits | Rate limiter Lua, budgets, cache eviction | Testcontainers Redis |
| Agent | Stop reasons, checkpoint/resume, loop detection, degradation | Scripted model, fixed `Clock` |
| End-to-end | Auth → authZ → retrieval/tool → grounded response → validation → trace | `@SpringBootTest` + all containers + in-memory span exporter |
| Architecture | Only executor invokes tools; modules respect boundaries | ArchUnit, Spring Modulith verification |
| Observability | Trace structure, cardinality, no content | In-memory exporter, MeterRegistry scan |
| Evaluation | Offline suite + gate; judge agreement | Eval harness, CI |
| Performance | Load at target QPS with SLO thresholds; overload shedding | k6/Gatling against staging with stub model |
| Chaos | Game-day drills | Toxiproxy, manual drills in staging |

### 12. Engineering Scenarios

**Scenario 1 — FDE kickoff with a real customer.** The customer's VP says: "We want your agent in production in 6 weeks, connected to our Zendesk, Shopify and Stripe." *Clarify:* which ticket types, which actions, who approves refunds today, data residency, SSO provider, success metric and baseline. *Design adaptation:* Zendesk/Shopify/Stripe adapters as narrow tools (read first). Write actions behind approvals mapped to their existing approval roles. Tenant = customer org. *Evaluate:* build the dataset from 200 of their historical tickets in week 2. *Operate:* shadow in weeks 4–5, canary in week 6, a kill switch. *Evidence:* scorecard on their data, pilot metrics, audit trail demo for their compliance team.

**Scenario 2 — Cost pressure.** Finance says the agent costs too much. *Investigate:* cost per run by step and model, retrieval context size, number of steps, and fallback frequency. *Options:* smaller model for routing/classification, context trimming, prompt caching, caching embeddings, fewer steps through better tool design. *Reasoning:* validate each change with the eval suite (quality must hold) and report cost per resolved ticket, not per call.

**Scenario 3 — Security review.** The customer's security team asks for a threat model and pen-test results. *Reasoning:* Provide the threat model (OWASP LLM/Agentic mapping), the compromised-model test suite, red-team results (attack success rate model-level vs system-level), tenant isolation evidence and data-flow diagrams (what goes to the model provider, retention settings).

**Scenario 4 — Scale ×10.** A new enterprise customer brings 10× traffic. *Reasoning:* Provider tokens/min becomes the bottleneck. Add per-provider rate limiting and queuing, priority classes, more workers (Kafka partitions ≥ workers), Aurora read replicas for retrieval, pgvector index tuning (`ef_search`, iterative scans) or moving vectors to a dedicated store if recall/latency degrade, and load tests with a stub model.

### 13. Interview Preparation

#### Quick Questions

- "Give me the one-minute overview of your capstone." (Problem, users, architecture in one sentence, the headline flow, one result metric.)
- "What's the riskiest component and how did you contain it?" (Refund tool: policy + approval + idempotency + audit.)
- "What would you remove if you had to simplify?" (Show judgment: for example the MCP server if only one AI client consumes KB search.)

#### Intermediate Questions

**Q: Walk me through a request from login to trace.**
*Strong answer:* The headline flow (Section 3) with concrete class names, span names and the guarantees at each step.

**Q: How do you know your agent works?**
*Strong answer:* The eval report: dataset composition, metrics vs thresholds, slice results, critical failures = 0, comparison vs baseline, online signals, and a link to traces for failing cases.

**Q: How does the system behave when the model provider is down?**
*Strong answer:* Flow E with metrics and the game-day result.

#### Advanced Questions

**Q: Defend every component.** Use the defense table (4.3): failure addressed, simpler alternative, why rejected, revisit triggers.

**Q: What was the hardest bug?**
*Strong answer:* A real one, told with STAR-T. Example: duplicate refunds under Kafka redelivery found by the concurrency IT, root-caused to a load-then-check claim, fixed with a conditional update and idempotency key, prevented with a test and alert.

**Q: What would you change for 1,000 tenants?**
*Strong answer:* Per-tenant budgets and fair queuing, sharding strategy (directory by tenant), vector store scaling, per-tenant eval slices, cost attribution, onboarding automation and noisy-neighbor isolation.

#### Coding Questions

Be ready to live-code, in your own repo: a new tool with typed args + policy + tests; a new eval scorer; a new span attribute with a cardinality test; a new approval rule with boundary tests.

#### Scenario Questions

Practice Units 42–43 scenarios against your capstone: "Add a new action `cancel_order`", "Support a second language", "Customer requires EU data residency", "Auditor asks for all actions on customer X", "Reduce p95 latency by 30%".

### 14. Explain-It-at-Three-Levels

**Concept: The capstone architecture**

- *30 seconds:* SupportOps is a multi-tenant Spring Boot platform where support reps get grounded answers and run a bounded investigation agent. Any action the agent proposes goes through deterministic policy and human approval and executes exactly once. Everything is traced, budgeted and evaluated in CI.
- *2 minutes:* Deployables, data stores, the five flows, the control ring (authN/Z, policy, validation, approval, limits), and the ops ring (OTel, evals, CI/CD, AWS).
- *Deep (5–10 minutes):* Walk Flow C in detail with code and traces, then the defense table, the eval report highlights, the game-day results, and the next steps.

**Concept: Graceful degradation**

- *30 seconds:* When the model fails, we fall back to a pre-evaluated model, then to deterministic KB snippets or queued runs, and the user always gets a useful, honest response.
- *2 minutes:* Circuit breaker, budgets, fallback evaluation, UX messaging, traces.
- *Deep:* Failure detection thresholds, retry budgets, queue-and-resume via checkpoints, cost implications, and testing via game days.

### 15. Knowledge Check

1. State the headline end-to-end flow in order.
2. Why does the MCP server take identity from the access token rather than tool arguments?
3. Why must the fallback model be in the eval suite?
4. What makes ingestion re-runs safe?
5. Why are approvals executed asynchronously via the outbox?
6. *Code reading:* In `LlmGateway.chat`, why reserve budget before the call and settle after?
7. *Code reading:* In `HeadingAwareChunker`, why prefix each chunk with its heading?
8. *Code reading:* In `AuthToTraceEndToEndIT`, what does `doesNotContain("chat")` prove for the anonymous case?
9. *Debugging:* Answers cite an outdated policy version. List three causes.
10. *Debugging:* Runs stuck in `RUNNING` after a deploy. What happened, and how do you recover?
11. *Design:* When would you split `supportops-api` into multiple services?
12. *Design:* What's your evidence for "zero cross-tenant leakage"?

#### Knowledge Check Answers

1. Authentication → authorization → validated scope → retrieval/tool execution → LLM → grounded response → validation → trace/eval.
2. Tool arguments are model- or client-controlled and can be manipulated. Identity must come from authenticated transport credentials.
3. Failing over to an unevaluated model risks quality and safety regressions exactly when you're already degraded. It must pass the same gates.
4. Content-hash dedupe, versioned documents, atomic chunk replacement per version in one transaction, and idempotent consumers keyed by document version.
5. Resilience (retries, crash recovery), decoupling from the reviewer's request, exactly-once claim plus idempotency, and the ability to re-validate at execution time.
6. To enforce per-tenant budgets before spending (preventing overrun under concurrency), then correct the reservation with actual usage.
7. Chunks lose section context when split. Including the heading improves embedding relevance and the model's understanding of the snippet.
8. Authentication fails before any model call, so unauthenticated requests never reach the model (security and cost).
9. Old document version's chunks not removed (non-atomic replacement), a stale cache of answers or retrieval results, an ingestion event lost or failed (DLT), or the ACL/version filter not applied.
10. Workers were terminated mid-run without graceful shutdown, or the resume consumer failed. Recover via a sweeper that re-enqueues stale runs from checkpoints (steps are idempotent); fix graceful shutdown and alerting.
11. When modules need independent scaling, release cadence, isolation (security or blast radius), or team ownership boundaries, and the outbox/transaction coupling can be handled.
12. Retrieval filters in SQL (code + tests), critical eval cases (0 failures across runs), the cache-key review, traces showing the tenant filter, and a periodic automated probe.

### 16. Common Interview Traps

- **"It works on my laptop."** Show CI, tests, evals, deployment and dashboards.
- **"The agent decides when it needs approval."** Policy decides.
- **"We use RAG so there are no hallucinations."** Show groundedness and citation metrics.
- **"MCP makes it secure."** Show the policy wrapper and OAuth2 on the MCP server.
- **"We have tracing, so we know it's good."** Show the eval report.
- **"Every component is there because it's best practice."** Each must map to a failure it addresses.
- **"We'll handle cost later."** Show per-run cost, budgets and alerts.

### 17. Cheat Sheet

- **Headline flow:** authN → authZ → validated scope → retrieval/tool → LLM → grounded response → validation → trace/eval.
- **Deployables:** api (REST, SSE, agent ask), worker (runs, ingestion, executor, resume, eval sampler), mcp (search_kb).
- **Stores:** Aurora PostgreSQL + pgvector (domain, vectors, audit, outbox), Redis (limits, budgets, cache), Kafka (events), S3 (docs, eval artifacts).
- **Controls:** InputGuard, per-turn tool allowlist, DecisionValidator, ToolPolicy, approvals (four-eyes, hash, re-validate, idempotent), OutputGuard, limits (steps, deadline, tokens, denials).
- **Ops:** OTel spans (invoke_agent, chat, retrieval, execute_tool, validate, guardrail, approval), metrics (cost, stop reasons, denials), evals (smoke on PR, full nightly, baseline), game days, runbook.
- **Deliverables:** repository, architecture doc + ADRs, threat model, observability doc, evaluation report, demo script, runbook, walkthrough.

### 18. Completion Checklist

- [ ] I can run the full system locally from a clean clone and complete the demo in ≤ 5 minutes.
- [ ] I can explain why every component exists, what failure it addresses and what simpler alternative I considered.
- [ ] I implemented REST APIs, PostgreSQL/JPA, Redis, Kafka, OAuth2/JWT, Docker, Testcontainers, CI/CD and an AWS deployment.
- [ ] I implemented Spring AI chat/embeddings, pgvector RAG with citations, structured output, tools, a bounded agent, a multi-step workflow, MCP server and client.
- [ ] I implemented agent state, guardrails, human approval, OpenTelemetry, evals, cost/token measurement and graceful degradation.
- [ ] My tests include the compromised-model suite, tenant isolation, concurrency/redelivery, end-to-end auth-to-trace and the eval gate.
- [ ] I ran the game-day drills and documented them in the runbook.
- [ ] My architecture doc, ADRs, evaluation report, demo script and walkthrough are complete and current.

### 19. Further Research

**Essential**

- Spring AI reference (chat, embeddings, vector stores, tools, advisors, MCP, observability) — <https://docs.spring.io/spring-ai/reference/>. The integration surface you'll use most.
- Spring Boot reference (Docker Compose, Testcontainers, observability, packaging) — <https://docs.spring.io/spring-boot/reference/>.
- pgvector — <https://github.com/pgvector/pgvector>. HNSW parameters, filtering, iterative index scans.
- MCP specification and Java SDK — <https://modelcontextprotocol.io/specification/latest>, <https://github.com/modelcontextprotocol/java-sdk>.
- AWS Well-Architected Framework (Reliability, Security, Cost pillars) — <https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html>.

**Deeper Study**

- Spring Modulith reference — <https://docs.spring.io/spring-modulith/reference/>. Module boundaries, event publication registry.
- Michael Nygard, *Release It!* (2nd ed.). Stability patterns for production systems.
- Google SRE Workbook — <https://sre.google/workbook/table-of-contents/>. SLOs, alerting, incident response.
- OWASP GenAI Security Project resources — <https://genai.owasp.org/>. Threat modeling for LLM and agentic applications.

**Practice**

- Spring AI examples — <https://github.com/spring-projects/spring-ai-examples>. Compare your integration patterns.
- Grafana `otel-lgtm` — <https://github.com/grafana/docker-otel-lgtm>. Local observability stack for the demo.
- Run a mock "customer kickoff" with a peer playing the stakeholder, and deliver the demo and evaluation report to them.

### Unit Completion Standard

Before you consider the curriculum complete, you must be able to:

- **Explain** the full SupportOps architecture and the end-to-end flow from authentication through authorization, retrieval/tool execution, grounded response and validation to trace and evaluation, and why each component exists.
- **Implement** the complete production-style repository: Spring Boot APIs, PostgreSQL/JPA with pgvector, Redis, Kafka with outbox, OAuth2/JWT security, Docker, Testcontainers, CI/CD, AWS; Spring AI RAG with citations, structured output, tools, a bounded agent and a multi-step workflow, agent state, MCP server/client, guardrails, human approval, OpenTelemetry, evals, cost/token measurement and graceful degradation.
- **Test** it with deterministic control tests, compromised-model tests, tenant-isolation critical cases, concurrency/redelivery tests, end-to-end auth-to-trace tests, observability tests, and a CI evaluation gate against a reviewed baseline.
- **Debug** it through game-day drills (provider outage, injection, cross-tenant probe, duplicate execution, worker crash, broker/cache outage, cost runaway, bad prompt, model drift), with runbook entries for each.
- **Defend** in an interview every component (failure addressed, simpler alternative considered, revisit triggers), with the deliverables in hand: architecture documentation with ADRs, demo script, evaluation report, and an interview-ready technical walkthrough.
