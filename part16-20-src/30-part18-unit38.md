# Part XVIII — Architecture and System Design

**What this part teaches.** Unit 38 moves from "I can build a Spring Boot service" to "I can design a system a business can depend on." It covers the core properties (scalability, availability, reliability, consistency), the building blocks (load balancing, caching, queues, replication, partitioning, sharding, CDNs, rate limiting) and the correctness tools of distributed systems (distributed locks, idempotency, backpressure) — then applies them in seven worked designs, ending with an agentic workflow platform that reuses everything from Parts XVI–XVII.

**Why it matters.** Most production incidents are not caused by syntax. They come from unbounded queues, missing timeouts, retries without idempotency, caches serving stale or cross-tenant data, hot partitions, lock misuse and agents given more authority than intended. Senior interviews — and senior jobs — test whether you anticipate these failures and can defend trade-offs under time pressure.

**Where it appears.** Payment flows, notification fan-out, e-commerce order pipelines, search, chat, and internal AI platforms. Forward Deployed Engineers do this live with customers: elicit requirements, sketch an architecture, identify the authoritative data sources and failure modes, and defend choices.

**Connections.** Builds on earlier curriculum units on Java concurrency and virtual threads, Spring Boot, JPA/PostgreSQL, Redis, Kafka, Spring Security, Docker/AWS and OpenTelemetry; the agentic design reuses Units 33–37. It feeds the interview units (39–42) and the Unit 43 capstone, whose architecture document follows this unit's template.

## Unit 38 — Java System Design

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Define and quantify** scalability, availability, reliability and consistency; convert an availability target into an error budget; express latency targets as percentiles.
2. **Estimate** load (QPS, peak factor, storage, bandwidth) and **size** a Spring Boot deployment (instances, Tomcat/virtual threads, HikariCP pool, database connections) using Little's law.
3. **Compare** L4 vs L7 load balancing and explain health checks, connection draining and Spring Boot graceful shutdown.
4. **Design** caching (cache-aside, read-through, write-through, write-behind), choose TTL/invalidation strategies, prevent stampedes, and explain Spring's `@Cacheable` proxy behavior.
5. **Choose** queueing technology (Kafka, RabbitMQ, SQS) and design for at-least-once delivery, ordering, retries, dead-letter topics and consumer lag.
6. **Explain** replication (synchronous/asynchronous, read replicas, lag, read-your-writes), partitioning (PostgreSQL declarative partitioning) and sharding (key choice, hot keys, resharding).
7. **Implement** rate limiting (token bucket in Redis with Lua) and **explain** where it belongs (edge, gateway, service, per-tenant).
8. **Explain** distributed locks, their failure modes and fencing tokens, and prefer database constraints/conditional updates where possible.
9. **Implement** idempotency (Idempotency-Key handling, unique constraints, idempotent consumers, transactional outbox).
10. **Implement** backpressure (bounded concurrency, bulkheads, timeouts, load shedding, Kafka consumer pause) — including the virtual-thread caveat.
11. **Design** a URL shortener, notification system, payment service, order platform, document search, chat service and agentic workflow platform using the sequence requirements → API → data model → architecture → scaling → failures → security → observability → trade-offs.
12. **Lead** a 30–45-minute system-design interview and **defend** architectural choices against simpler alternatives.

### 2. Prerequisite Knowledge

- **Java concurrency**: thread pools, `ExecutorService`, virtual threads (Java 21), `Semaphore`, `CompletableFuture`; contention vs blocking.
- **Spring Boot**: request handling in Tomcat (or Jetty/Undertow), `RestClient`, `@Transactional`, `@Cacheable`, `@Scheduled`, Actuator health groups.
- **PostgreSQL/JPA**: indexes, transactions and isolation levels, `EXPLAIN ANALYZE`, connection pooling.
- **Redis**: data types, TTLs, single-threaded command execution, Lua scripts.
- **Kafka**: topics, partitions, consumer groups, offsets, keys.
- **Networking**: DNS, TLS, HTTP/1.1 vs HTTP/2, keep-alive.

**Refresher — latency numbers worth remembering (orders of magnitude).** L1 cache ~1 ns; main memory ~100 ns; SSD random read ~100 µs; same-datacenter round trip ~0.5 ms; Redis GET in-region ~0.5–1 ms; PostgreSQL indexed lookup ~1–5 ms; cross-region round trip 50–150 ms; LLM call 0.5–30 s. Designs that are fine with 1 ms dependencies break when a dependency takes 10 s.

**Refresher — Little's law.** `L = λ × W`: average concurrency = arrival rate × time in system. At 500 requests/s and 200 ms average latency, ~100 requests are in flight. If latency jumps to 2 s (slow dependency), in-flight requests jump to 1,000 — that's how slow dependencies exhaust threads, connections and memory. Backpressure exists to bound `L`.

### 3. Mental Model

System design is **budgeting under uncertainty**. You have budgets for latency, availability, consistency, cost and complexity; every component spends some of them. The design process is a structured conversation:

```
1 Requirements      functional + non-functional (scale, latency, availability, consistency, security, compliance)
2 API               resources, operations, idempotency, pagination, errors, auth
3 Data model        entities, access patterns, keys, indexes, ownership, retention
4 Architecture      components and data flow (sync vs async), source of truth
5 Scaling           estimates → bottlenecks → caching, partitioning, replication, queues
6 Failures          what breaks, blast radius, retries, idempotency, degradation
7 Security          authN/authZ, tenancy, data protection, abuse, rate limits
8 Observability     SLIs/SLOs, traces, metrics, logs, audits, alerts
9 Trade-offs        what you chose, what you rejected, when you'd revisit
```

Three principles:

1. **Start simple and scale on evidence.** A single PostgreSQL primary with a read replica, a Redis cache and a Kafka topic handles more than most interview prompts imply. Add sharding, multi-region and exotic stores only when estimates demand them.
2. **Know your source of truth.** For every piece of data, name the authoritative store; caches, indexes, read models and search engines are derived and may be stale.
3. **Design for partial failure.** Every network call can be slow, fail, or succeed without you knowing. Timeouts, retries with idempotency, and bounded resources are the defaults, not extras.

### 4. Comprehensive Theory

#### 4.1 Scalability

**Definition.** The ability to handle increased load by adding resources, with acceptable cost and performance.

**Vertical vs horizontal.** Vertical scaling (bigger machine) is simple and often the right first step for databases; it has a ceiling and a single failure domain. Horizontal scaling (more instances) requires **stateless services** — session state in a token or external store, no local files that matter, idempotent handlers — and a load balancer.

**Where Java services bottleneck.** CPU (serialization, crypto, regex), memory/GC (large heaps, allocation rates), blocking I/O threads (platform threads in Tomcat's pool, default max 200), connection pools (HikariCP default 10), downstream rate limits and the database.

**Virtual threads.** With `spring.threads.virtual.enabled=true` (Boot 3.2+), Tomcat runs each request on a virtual thread, so blocking I/O no longer pins scarce platform threads. This removes the *thread* bottleneck — and moves it to whatever is actually scarce: the DB pool, downstream rate limits, memory. Without explicit limits, virtual threads let you create *unbounded* concurrency against bounded resources. Since Java 24 (JEP 491), `synchronized` blocks no longer pin virtual threads to carriers, removing a major Java 21 caveat **[Version-dependent]**.

**Capacity estimation (back-of-the-envelope).**

```
DAU = 10M, each does 20 reads + 2 writes/day
reads/s avg  = 10M × 20 / 86,400 ≈ 2,300/s ; peak ×3 ≈ 7,000/s
writes/s avg = 10M × 2 / 86,400 ≈ 230/s   ; peak ≈ 700/s
storage: 2 writes × 10M × 1 KB = 20 GB/day ≈ 7.3 TB/year (+ indexes ×1.5–2, + replicas)
instances: if one instance handles 1,000 req/s at target p95 → 7 at peak + N+1 / zone redundancy → 9–12
DB connections: 12 instances × pool 10 = 120 connections (PostgreSQL max_connections, consider PgBouncer)
```

**Pool sizing.** A common starting point for PostgreSQL is a *small* pool per instance (≈ 2 × cores of the DB divided across instances), because more connections increase contention rather than throughput. Measure.

#### 4.2 Availability and Reliability

**Definitions.** *Availability* is the fraction of time (or requests) the system serves correctly: 99.9% ≈ 43.8 min/month downtime; 99.95% ≈ 21.9 min; 99.99% ≈ 4.4 min. *Reliability* is the probability the system performs correctly over time, including correctness (not just being up). An endpoint that returns 200 with wrong data is available but unreliable.

**SLI/SLO/error budget.** SLI = measured indicator (e.g., % of requests < 300 ms and non-5xx). SLO = target (99.9% over 30 days). Error budget = 1 − SLO; spend it on releases and experiments; when exhausted, prioritize reliability.

**Composite availability.** Serial dependencies multiply: three 99.9% services in series ≈ 99.7%. Redundancy improves it: two independent 99% replicas in parallel ≈ 99.99% (if failures are independent — they often aren't: shared config, shared region, shared bug).

**Techniques.** Redundancy across availability zones; health checks and automatic replacement; timeouts; retries with exponential backoff and jitter (only for idempotent operations); circuit breakers (Resilience4j); bulkheads; graceful degradation (serve cached/partial results); static stability (keep working when the control plane is down); safe deployments (rolling, blue/green, canary with automatic rollback).

#### 4.3 Consistency

**Spectrum.** *Linearizability* (every read sees the latest write, as if one copy) → *sequential* → *causal* → *read-your-writes*, *monotonic reads* (session guarantees) → *eventual consistency* (replicas converge if writes stop).

**CAP and PACELC.** Under a network partition (P), a system chooses availability (A) or consistency (C). PACELC adds: Else (no partition), trade Latency vs Consistency. PostgreSQL with synchronous replication favors C; async replicas favor latency/availability with possible lag.

**Database isolation** (PostgreSQL): default READ COMMITTED (each statement sees committed data as of its start; lost updates possible with read-modify-write), REPEATABLE READ (snapshot; serialization failures on conflicting updates), SERIALIZABLE (SSI; retries required). Prefer atomic SQL (`UPDATE … SET balance = balance - :x WHERE balance >= :x`), optimistic locking (`@Version`) or `SELECT … FOR UPDATE` for invariants.

**Choosing consistency per data item.** Payments and inventory reservations: strong. Product catalog, view counts, search indexes, recommendation caches: eventual. User's own profile after editing: read-your-writes.

#### 4.4 Load Balancing

**L4 vs L7.** L4 (TCP/UDP: AWS NLB) forwards connections without inspecting HTTP — very fast, preserves client IP, supports any TCP protocol. L7 (HTTP: AWS ALB, Envoy, NGINX, Spring Cloud Gateway) routes by path/host/headers, terminates TLS, retries, rate limits, does gRPC/HTTP2 multiplexing.

**Algorithms.** Round robin, least outstanding requests (good for variable latency like LLM calls), weighted, consistent hashing (session affinity, cache locality).

**Health checks.** Separate *liveness* (process should be restarted) and *readiness* (can receive traffic). Spring Boot Actuator exposes `/actuator/health/liveness` and `/readiness` groups; don't include downstream dependencies in liveness (a DB outage would restart all pods — a restart storm).

**Graceful shutdown.** `server.shutdown=graceful` (default since Boot 3.4) with `spring.lifecycle.timeout-per-shutdown-phase=30s`: on SIGTERM, readiness goes down, the LB stops routing, in-flight requests complete, then the app exits. Kubernetes `preStop` sleep can cover LB propagation delay.

#### 4.5 Caching

**Patterns.**

| Pattern | Read | Write | Pros | Cons |
|---|---|---|---|---|
| Cache-aside | App checks cache, on miss loads DB and populates | App writes DB, then deletes/updates cache | Simple, cache failures non-fatal | Stale windows; races between write and populate |
| Read-through | Cache library loads on miss | — | Centralized loading | Library coupling |
| Write-through | — | Write cache and DB synchronously | Cache always fresh | Write latency; cache must be durable-ish |
| Write-behind | — | Write cache; async flush to DB | Fast writes | Data loss risk; complex |

**Invalidation.** TTL (bounded staleness), explicit delete on write (delete rather than update avoids some races), versioned keys (`product:42:v17`), event-driven invalidation (CDC/Kafka). "Delete after commit" — invalidate in an after-commit hook (`TransactionSynchronization.afterCommit` or `@TransactionalEventListener(phase = AFTER_COMMIT)`), otherwise a concurrent reader can repopulate the old value before your transaction commits.

**Stampede (thundering herd).** A hot key expires; thousands of requests miss simultaneously and hit the DB. Mitigations: request coalescing (single-flight per key — Caffeine's `AsyncLoadingCache` does this locally), probabilistic early refresh, stale-while-revalidate, TTL jitter, locks around recompute for very expensive values.

**Two-level cache.** Local in-process (Caffeine: nanoseconds, per-instance, inconsistency between instances) + distributed (Redis: ~1 ms, shared). Good for hot, read-mostly data with tolerance for short staleness.

**Spring's `@Cacheable`.** Implemented by a proxy (`CacheInterceptor`): calls from outside the bean consult the `CacheManager` before invoking the method. Consequences: self-invocation bypasses caching; key defaults to method parameters (watch for tenant/user not being part of the key → cross-tenant leaks); `sync = true` enables per-key locking in the local JVM only; cached values must be serializable for Redis; exceptions aren't cached.

**What not to cache.** Authorization decisions without short TTLs and invalidation; per-user data under shared keys; anything where staleness causes money or security errors without compensating checks.

#### 4.6 Queues and Asynchronous Processing

**Why.** Decouple producers from consumers (availability), absorb bursts (load leveling), fan-out events, enable retries without user waiting.

**Technologies.**

| | Kafka | RabbitMQ | AWS SQS |
|---|---|---|---|
| Model | Partitioned, replayable log | Broker with exchanges/queues | Managed queue (standard/FIFO) |
| Ordering | Per partition (by key) | Per queue (single consumer) | FIFO queues per message group |
| Retention/replay | Yes (time/size, compaction) | No (consumed = gone) | No (up to 14 days unconsumed) |
| Throughput | Very high | High | High, managed |
| Best for | Event streaming, event sourcing, many consumers, CDC | Task queues, routing, RPC-ish patterns | Simple managed work queues on AWS |

**Delivery semantics.** At-most-once (may lose), at-least-once (may duplicate — the default you should assume), exactly-once (Kafka transactions provide exactly-once *within Kafka* read-process-write; end-to-end effects on external systems still need idempotency).

**Ordering.** Kafka guarantees order within a partition; choose a key that groups events that must be ordered (`orderId`), accepting that different keys are unordered. Retries with separate retry topics can reorder — use blocking retries for strictly ordered streams or design commutative handlers.

**Failure handling.** Retries with backoff; dead-letter topic (DLT) after N attempts; poison-pill detection (deserialization errors → DLT immediately); consumer lag monitoring; idempotent consumers (4.10). Spring Kafka: `DefaultErrorHandler` with `DeadLetterPublishingRecoverer`, `@RetryableTopic` for non-blocking retries.

#### 4.7 Replication

**Leader–follower.** Writes go to the leader; followers replay its log. *Synchronous* replication waits for at least one follower ack (no data loss on leader failure, higher write latency); *asynchronous* doesn't wait (lower latency, possible loss of recent writes on failover, replica lag).

**Read replicas.** Scale reads; introduce lag. Routing reads to replicas breaks read-your-writes: a user saves a profile then reloads from a lagging replica. Fixes: route reads to primary for a short window after a user's write (session stickiness), use LSN-based checks, or read critical data from primary. In Spring: `AbstractRoutingDataSource` keyed by `@Transactional(readOnly = true)` (via `TransactionSynchronizationManager.isCurrentTransactionReadOnly()`) — plus `LazyConnectionDataSourceProxy` so the routing decision happens after the transaction's read-only flag is set.

**Multi-leader / leaderless.** Multi-region writes (conflict resolution needed: last-write-wins, CRDTs, application merge) or quorum systems (Cassandra/Dynamo-style, `R + W > N`). Use only when requirements demand multi-region writes.

**Managed options.** Amazon RDS Multi-AZ (synchronous standby for failover), Aurora (shared storage, fast replicas, global database).

#### 4.8 Partitioning and Sharding

**Partitioning** splits a table into pieces *within* one database (PostgreSQL declarative partitioning by range/list/hash). Benefits: partition pruning, cheap retention (`DROP` old partitions), smaller indexes. It doesn't add write capacity beyond one server.

```sql
CREATE TABLE notification_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY,
    tenant_id   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    status      TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    PRIMARY KEY (id, created_at)                  -- PK must include the partition key
) PARTITION BY RANGE (created_at);

CREATE TABLE notification_log_2026_10 PARTITION OF notification_log
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
```

**Sharding** splits data across *multiple* databases. Choose a shard key that (1) appears in almost every query, (2) distributes load evenly, (3) keeps related data together (tenant id, user id). Approaches: hash-based (even, hard range queries), range-based (range queries, hotspots), directory/lookup-based (flexible, extra hop), consistent hashing (minimal movement on resharding). Costs: cross-shard queries and transactions, resharding, operational complexity. Alternatives first: vertical scaling, read replicas, caching, partitioning, archiving, or a distributed SQL database (CockroachDB, YugabyteDB, Aurora Limitless, Citus).

**Hot keys/partitions.** A celebrity user, a viral short URL, a large tenant. Mitigations: split hot keys (`key#0..N`), cache aggressively, dedicated shards for large tenants, write coalescing.

#### 4.9 CDN and Edge

A CDN caches static assets and cacheable API responses near users, terminates TLS, absorbs DDoS, and can run edge logic. Use `Cache-Control` (`public, max-age, s-maxage, stale-while-revalidate`), `ETag`/`Last-Modified` for revalidation, and versioned asset URLs for instant invalidation. Never cache personalized responses publicly (`private`/`no-store`); vary on the right headers.

#### 4.10 Rate Limiting

**Why.** Protect capacity, enforce fairness across tenants, control cost (LLM tokens), mitigate abuse.

**Algorithms.** *Fixed window* (simple; bursts at window edges), *sliding window log* (accurate; memory per request), *sliding window counter* (approximation), *token bucket* (allows bursts up to capacity, steady refill; most common), *leaky bucket* (smooth output rate), *concurrency limits* (cap in-flight requests — essential for slow operations like LLM calls).

**Where.** Edge/CDN/WAF (IP-based abuse), API gateway (per API key/tenant), service (per user/operation, cost-based), outbound (respect downstream limits). Return `429 Too Many Requests` with `Retry-After`; IETF `RateLimit` headers are standardizing quota communication.

**Distributed implementation.** Redis with an atomic Lua script (Example 1), or libraries like Bucket4j (with Redis/JCache backends); Spring Cloud Gateway's `RequestRateLimiter` uses a Redis token bucket.

#### 4.11 Distributed Locks

**Definition.** Mutual exclusion across processes. Typical uses: run a scheduled job on one instance, serialize operations on a resource.

**Redis lock.** `SET lock:key <unique-token> NX PX 30000`; release with a Lua script that deletes only if the value matches (so you don't release someone else's lock). Problems: a process pause (GC, VM freeze) longer than the TTL lets another process acquire the lock while the first still thinks it holds it; Redis failover can lose locks. Redlock (multiple Redis masters) is debated precisely because it doesn't solve pauses without fencing.

**Fencing tokens.** The lock service issues a monotonically increasing token with each acquisition; the protected resource rejects writes with a token lower than the highest seen. This makes locks *safe* even with pauses — but requires the resource to check tokens.

**Prefer database primitives** when the protected resource is a database: unique constraints, conditional updates (`UPDATE … WHERE status = 'PENDING'`), `SELECT … FOR UPDATE SKIP LOCKED` for job queues, PostgreSQL advisory locks (`pg_try_advisory_lock`) for coordination. For scheduled jobs: ShedLock (DB-backed). Locks are a last resort for correctness; they're fine for *efficiency* (avoiding duplicate work) where occasional double execution is harmless.

#### 4.12 Idempotency

**Definition.** An operation is idempotent if performing it multiple times has the same effect as once. Required wherever retries happen — which is everywhere.

**Techniques.**

1. **Natural idempotency**: `PUT /users/42 {…}` (set state), `DELETE` (already deleted is fine).
2. **Idempotency keys** for `POST` side effects (payments, orders): client sends `Idempotency-Key: <uuid>`; server stores key → request hash → result; replays return the stored result; same key with different body → 422; concurrent duplicate while in progress → 409. (An IETF draft standardizes the `Idempotency-Key` header.)
3. **Unique constraints** on business identifiers (`payment(provider_reference)`, `processed_event(event_id)`).
4. **Idempotent consumers**: record processed message ids in the same transaction as the side effect.
5. **Transactional outbox**: write business state and an outbox row in one DB transaction; a relay publishes to Kafka (at-least-once); consumers are idempotent. Avoids the dual-write problem (DB commit succeeds, Kafka publish fails, or vice versa). Debezium CDC can relay the outbox.

#### 4.13 Backpressure

**Definition.** Mechanisms that slow producers when consumers can't keep up, instead of letting queues and in-flight work grow without bound.

**Techniques.** Bounded queues (`ThreadPoolExecutor` with bounded `ArrayBlockingQueue` and a rejection policy); semaphores/bulkheads limiting concurrent calls to a dependency (Resilience4j `Bulkhead`); timeouts on every remote call (connect, read, overall); load shedding (reject early with 429/503 when saturated, prioritizing important traffic); Kafka consumers naturally pull, and you can `pause()`/`resume()` partitions when downstream is slow; reactive streams (`Flux` with demand signaling); adaptive concurrency limits (Netflix concurrency-limits, AIMD).

**Virtual-thread caveat.** Virtual threads remove the natural backpressure of a bounded Tomcat thread pool. Add explicit limits around scarce resources: a `Semaphore` per downstream, Hikari's `connectionTimeout` (fail fast rather than queue forever), and request-level concurrency limits.

### 5. Internal Mechanics

#### 5.1 A request through a Spring Boot service at scale

```
Client → DNS → CDN/WAF → ALB (L7, TLS, health-checked targets, least-outstanding-requests)
  → Pod (Kubernetes Service/IP target) → Tomcat connector (NIO acceptor; virtual thread per request)
  → Filter chain (security, observation, rate limiting) → DispatcherServlet → controller
  → Service: cache lookup (Caffeine → Redis) → miss → HikariCP.getConnection() (≤ connectionTimeout)
  → PostgreSQL (primary or replica via routing datasource) → result
  → outbox insert in same tx → commit → after-commit cache invalidation
  → response; Outbox relay ⇢ Kafka → consumers (idempotent) → projections/notifications
```

Where it saturates: Hikari pool (threads wait in `getConnection`), PostgreSQL CPU/locks, Redis single thread for heavy Lua/large values, Kafka consumer lag, downstream rate limits. Observability (Unit 37) tells you which: Hikari metrics (`hikaricp.connections.pending`), DB wait events, Redis latency, consumer lag.

#### 5.2 Kafka consumer groups

Each partition is assigned to exactly one consumer in a group; parallelism ≤ partition count. Rebalancing (consumers join/leave) reassigns partitions; with the cooperative/incremental protocols (and Kafka 4's new consumer group protocol, KIP-848) rebalances are less disruptive **[Version-dependent]**. Offsets are committed after processing (at-least-once); a crash between processing and commit means redelivery — hence idempotent consumers.

#### 5.3 Redis Lua atomicity

Redis executes a Lua script atomically: no other command runs during it (single-threaded command execution). That's why rate limiters and safe lock releases use scripts — but long scripts block everything, so keep them O(1).

### 6. Implementation Examples

#### Example 1 — Minimal: Redis token-bucket rate limiter

```lua
-- src/main/resources/scripts/token_bucket.lua
-- KEYS[1] = bucket key; ARGV[1] = capacity; ARGV[2] = refill tokens per second; ARGV[3] = cost
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local cost     = tonumber(ARGV[3])
local t        = redis.call('TIME')                      -- server clock avoids client clock skew
local now_ms   = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)

local state  = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1]) or capacity
local ts     = tonumber(state[2]) or now_ms

tokens = math.min(capacity, tokens + (math.max(0, now_ms - ts) / 1000.0) * rate)
local allowed = 0
local retry_ms = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_ms = math.ceil((cost - tokens) / rate * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now_ms)
redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / rate * 1000) + 1000)
return { allowed, retry_ms }
```

```java
package com.acme.platform.ratelimit;

import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class TokenBucketRateLimiter {

    public record Decision(boolean allowed, long retryAfterMs) { }

    @SuppressWarnings("rawtypes")
    private final RedisScript<List> script =
            RedisScript.of(new ClassPathResource("scripts/token_bucket.lua"), List.class);
    private final StringRedisTemplate redis;

    public TokenBucketRateLimiter(StringRedisTemplate redis) {
        this.redis = redis;
    }

    public Decision tryConsume(String key, int capacity, double refillPerSecond, int cost) {
        List<?> result = redis.execute(script, List.of("rl:" + key),
                String.valueOf(capacity), String.valueOf(refillPerSecond), String.valueOf(cost));
        long allowed = ((Number) result.get(0)).longValue();
        long retry = ((Number) result.get(1)).longValue();
        return new Decision(allowed == 1, retry);
    }
}
```

Use it in a filter or `HandlerInterceptor` keyed by tenant + user + route, returning `429` with `Retry-After` (seconds, rounded up). **Failure policy:** if Redis is unavailable, decide fail-open (availability) or fail-closed (protection) per endpoint — e.g., fail-open for reads with a local in-memory fallback limiter, fail-closed for expensive LLM endpoints.

#### Example 2 — Realistic: Idempotency-Key handling for a payment endpoint

**Schema.**

```sql
CREATE TABLE idempotency_record (
    owner_id        TEXT        NOT NULL,          -- authenticated client/user; keys are scoped per owner
    idem_key        TEXT        NOT NULL,
    request_hash    CHAR(64)    NOT NULL,
    status          TEXT        NOT NULL CHECK (status IN ('IN_PROGRESS','COMPLETED')),
    response_status INT,
    response_body   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, idem_key)
);
CREATE INDEX idx_idem_created ON idempotency_record (created_at);   -- for TTL cleanup (e.g., 24–72 h)
```

**Service.**

```java
package com.acme.payments.idempotency;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;

@Service
public class IdempotencyService {

    public sealed interface Claim {
        record New() implements Claim { }
        record Replay(int status, String body) implements Claim { }
        record InProgress() implements Claim { }
        record Mismatch() implements Claim { }
    }

    private final JdbcClient jdbc;

    public IdempotencyService(JdbcClient jdbc) { this.jdbc = jdbc; }

    /** Runs in its own transaction so the claim is visible to concurrent duplicates immediately. */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public Claim claim(String ownerId, String key, String requestHash) {
        try {
            jdbc.sql("""
                     INSERT INTO idempotency_record(owner_id, idem_key, request_hash, status)
                     VALUES (:o, :k, :h, 'IN_PROGRESS')
                     """)
                .param("o", ownerId).param("k", key).param("h", requestHash).update();
            return new Claim.New();
        } catch (DuplicateKeyException e) {
            Optional<Existing> existing = jdbc.sql("""
                     SELECT request_hash, status, response_status, response_body
                       FROM idempotency_record WHERE owner_id = :o AND idem_key = :k
                     """)
                .param("o", ownerId).param("k", key)
                .query((rs, n) -> new Existing(rs.getString(1), rs.getString(2),
                        (Integer) rs.getObject(3), rs.getString(4)))
                .optional();
            Existing x = existing.orElseThrow();
            if (!x.requestHash().equals(requestHash)) return new Claim.Mismatch();
            if ("IN_PROGRESS".equals(x.status())) return new Claim.InProgress();
            return new Claim.Replay(x.responseStatus(), x.responseBody());
        }
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void complete(String ownerId, String key, int status, String body) {
        jdbc.sql("""
                 UPDATE idempotency_record SET status = 'COMPLETED', response_status = :s, response_body = :b
                  WHERE owner_id = :o AND idem_key = :k
                 """)
            .param("s", status).param("b", body).param("o", ownerId).param("k", key).update();
    }

    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void release(String ownerId, String key) {   // on retryable failure, allow the client to retry
        jdbc.sql("DELETE FROM idempotency_record WHERE owner_id = :o AND idem_key = :k AND status = 'IN_PROGRESS'")
            .param("o", ownerId).param("k", key).update();
    }

    private record Existing(String requestHash, String status, Integer responseStatus, String responseBody) { }
}
```

**Controller usage.**

```java
@PostMapping("/payments")
public ResponseEntity<String> create(@RequestHeader("Idempotency-Key") @Pattern(regexp = "[A-Za-z0-9-]{16,64}") String key,
                                     @Valid @RequestBody CreatePaymentRequest request,
                                     @AuthenticationPrincipal Jwt jwt) {
    String owner = jwt.getSubject();
    String hash = Hashes.sha256(canonicalJson(request));
    return switch (idempotency.claim(owner, key, hash)) {
        case IdempotencyService.Claim.Replay r -> ResponseEntity.status(r.status()).body(r.body());
        case IdempotencyService.Claim.InProgress p -> ResponseEntity.status(409).body(problem("request in progress"));
        case IdempotencyService.Claim.Mismatch m -> ResponseEntity.unprocessableEntity().body(problem("key reused with different body"));
        case IdempotencyService.Claim.New n -> {
            try {
                PaymentResult result = payments.create(request, key);        // provider call also uses the key
                String body = json(result);
                idempotency.complete(owner, key, 201, body);
                yield ResponseEntity.status(201).body(body);
            } catch (TransientPaymentException e) {
                idempotency.release(owner, key);
                throw e;                                                       // 503 with Retry-After
            }
        }
    };
}
```

Two important details: the claim commits in its own transaction (`REQUIRES_NEW`) so a concurrent duplicate sees it; and the *provider* call also uses an idempotency key, so even if our process crashes after charging but before `complete`, a retry doesn't double-charge (the record stays `IN_PROGRESS`; a reconciler resolves it using the provider's key lookup).

#### Example 3 — Production-oriented: transactional outbox, idempotent Kafka consumer and backpressure

**Outbox write in the same transaction as the business change.**

```java
@Transactional
public Order placeOrder(PlaceOrderCommand cmd) {
    Order order = orders.save(Order.from(cmd));
    outbox.save(OutboxEvent.of("orders", order.id().toString(), "OrderPlaced",
            json(new OrderPlaced(order.id(), order.customerId(), order.total()))));
    return order;
}
```

**Relay** (polling; Debezium CDC is the alternative):

```java
@Scheduled(fixedDelayString = "PT0.5S")
public void relay() {
    List<OutboxEvent> batch = tx.execute(s -> outbox.lockNextBatch(100));   // SELECT … FOR UPDATE SKIP LOCKED
    for (OutboxEvent e : batch) {
        kafka.send(e.topic(), e.key(), e.payload()).join();                  // per-key ordering via key
        tx.executeWithoutResult(s -> outbox.markPublished(e.id()));
    }
}
```

`FOR UPDATE SKIP LOCKED` lets multiple relay instances work without double-claiming rows; at-least-once publication is expected (crash after send, before mark) — consumers dedupe.

**Idempotent consumer with bounded concurrency to a slow downstream.**

```java
package com.acme.notifications;

import io.github.resilience4j.bulkhead.Bulkhead;
import io.github.resilience4j.bulkhead.BulkheadConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;

@Component
public class OrderPlacedConsumer {

    private final JdbcClient jdbc;
    private final EmailSender email;
    private final Bulkhead emailBulkhead = Bulkhead.of("email", BulkheadConfig.custom()
            .maxConcurrentCalls(20)                      // provider allows ~20 concurrent sends
            .maxWaitDuration(Duration.ofSeconds(2))      // wait briefly, then fail → retry/backoff
            .build());

    public OrderPlacedConsumer(JdbcClient jdbc, EmailSender email) {
        this.jdbc = jdbc;
        this.email = email;
    }

    @KafkaListener(topics = "orders", groupId = "notifications", concurrency = "3")
    @Transactional
    public void on(ConsumerRecord<String, String> record) {
        String eventId = new String(record.headers().lastHeader("eventId").value());
        try {
            jdbc.sql("INSERT INTO processed_event(consumer, event_id) VALUES ('notifications', :id)")
                .param("id", eventId).update();
        } catch (DuplicateKeyException duplicate) {
            return;                                      // already processed: at-least-once delivery handled
        }
        OrderPlaced event = parse(record.value());
        Bulkhead.decorateRunnable(emailBulkhead,
                () -> email.sendOrderConfirmation(event, /* idempotency key */ eventId)).run();
    }
}
```

The `processed_event` insert and the email are not atomic (email is external): if the email fails, the transaction rolls back, the insert disappears and Kafka redelivers — correct. If the email succeeds but the commit fails, the email may be sent twice — mitigated by passing `eventId` as the provider's idempotency key. Configure `DefaultErrorHandler` with exponential backoff and a dead-letter topic; when `BulkheadFullException` happens repeatedly, backoff naturally slows consumption — the pull model provides backpressure.

#### Worked Designs (the core practice of this unit)

Each design follows: **Requirements → API → Data model → Architecture → Scaling → Failures → Security → Observability → Trade-offs.** Numbers are illustrative assumptions you would state in an interview.

##### Design 1 — URL Shortener

**Requirements.** Create short links for long URLs; redirect quickly; optional custom alias and expiry; click analytics. Scale: 100M new links/month (~40/s avg, 400/s peak), 10B redirects/month (~4K/s avg, 40K/s peak; read:write ≈ 100:1). Redirect p99 < 50 ms; availability 99.99% for redirects; analytics eventually consistent.

**API.**
- `POST /api/links {longUrl, alias?, expiresAt?}` → `201 {code, shortUrl}` (auth required; idempotency key optional).
- `GET /{code}` → `301/302 Location: longUrl` (302 if analytics must see every click; 301 lets browsers cache).
- `GET /api/links/{code}/stats` → aggregates.

**Data model.** `link(code PK, long_url, owner_id, created_at, expires_at, status)`; `click_event` (Kafka) → aggregated `link_stats(code, day, clicks)`. 100M/month × 500 B ≈ 50 GB/month → partition/archive by creation month or move to a key-value store when large.

**Code generation.** Base62 of a unique id: 7 chars = 62⁷ ≈ 3.5 × 10¹² codes. Options: (a) DB sequence/Snowflake-like id → Base62 (predictable/enumerable — add an offset/permutation if guessing matters); (b) random 7–8 chars with a unique constraint and retry on collision; (c) pre-generated key ranges allocated per instance. Hashing the URL (MD5 prefix) gives deduplication but collisions must be handled.

**Architecture.**

```
Client → CDN (cache 301s / hot codes) → ALB → Redirect service (Spring Boot, stateless, virtual threads)
     → Caffeine (hot codes) → Redis (code → url, TTL) → PostgreSQL primary/replicas (source of truth)
     ⇢ Kafka click events → stream aggregator → link_stats
Create service → PostgreSQL primary (unique code) → cache warm
```

**Scaling.** Reads dominate: CDN + two-level cache gets >95% hit rate; 40K/s peak at ~5K/s per instance → ~10 instances + headroom. Writes are small. Click analytics asynchronous via Kafka (never block the redirect on analytics).

**Failures.** Redis down → fall back to replicas (with a bulkhead) and Caffeine; DB down → serve from caches (static stability for popular links); Kafka down → buffer click events locally with bounded queue and drop with a metric (analytics is not critical). Expired links → 404/410.

**Security.** Malicious URLs (phishing/malware): scan on create (Safe Browsing APIs), block lists, abuse reporting; rate-limit creation per user/IP; prevent open-redirect abuse of your domain's reputation; private links not enumerable (random codes).

**Observability.** SLI: redirect success and latency; cache hit rates; DB fallback rate; creation errors; abuse flags.

**Trade-offs.** 301 vs 302 (performance vs analytics fidelity); sequential vs random codes (simplicity vs enumeration); PostgreSQL vs DynamoDB (relational familiarity vs effortless horizontal scale at very large size).

##### Design 2 — Notification System

**Requirements.** Send notifications via email, SMS, push and in-app on behalf of other services; user preferences and quiet hours; templates; priorities (OTP/transactional vs marketing); deduplication; delivery tracking; retries. Scale: 50M notifications/day (~600/s avg, bursts 10K/s for campaigns). Transactional p95 < 5 s end-to-end; at-least-once with dedupe.

**API.** `POST /api/notifications {recipientId, type, channelHints?, templateId, params, priority, idempotencyKey}` → `202 {notificationId}`; `GET /api/notifications/{id}`; preferences CRUD; provider webhooks `POST /webhooks/{provider}` (signed).

**Data model.** `notification(id, idempotency_key UNIQUE, recipient_id, type, priority, status, created_at)`; `delivery_attempt(notification_id, channel, provider, status, provider_msg_id, attempt, error)` partitioned by month; `user_preference(user_id, type, channel, enabled, quiet_hours)`; templates versioned.

**Architecture.**

```
Producers → Notification API (validate, dedupe, persist, outbox) ⇢ Kafka topics by priority
   (notifications.high / .normal / .bulk) → Router workers (preferences, quiet hours, template render)
   ⇢ per-channel topics → Channel workers (email/SMS/push) → providers (SES, Twilio, FCM/APNs)
   ← provider webhooks (delivered/bounced) → status updates
```

**Scaling.** Separate topics and consumer groups per priority so marketing bursts never delay OTPs; channel workers sized to provider rate limits (token buckets per provider/account); campaigns throttled via scheduling; partition by recipient for per-user ordering where it matters.

**Failures.** Provider outage → circuit breaker, failover to secondary provider, retry topics with backoff, DLT; duplicates → idempotency keys at API and provider; poison templates → DLT + alert; webhook loss → reconciliation polling.

**Security.** Service-to-service auth (mTLS/OAuth client credentials), per-producer quotas, PII minimization (render at send time; don't store full bodies longer than needed), verified webhooks (signatures), unsubscribe compliance (CAN-SPAM/GDPR), OTP rate limiting.

**Observability.** End-to-end latency by priority, queue lag per topic, provider error rates, bounce rates, dedupe hits, DLT size.

**Trade-offs.** Kafka vs SQS (replay and throughput vs managed simplicity); storing rendered content (debuggability vs privacy); exactly-once is impossible end-to-end — dedupe + idempotent providers instead.

##### Design 3 — Payment Service

**Requirements.** Accept payments for orders via external PSPs (card processors), refunds, payment status, ledger, reconciliation. Correctness over availability: never double-charge, never lose money records. Scale: 2M payments/day (~25/s avg, 500/s peak events). Strong consistency for money movements; auditability; PCI DSS scope minimization.

**API.** `POST /payments` with `Idempotency-Key` → `201 {paymentId, status: PENDING|AUTHORIZED|…}`; `POST /payments/{id}/capture`; `POST /payments/{id}/refunds` (idempotent); `GET /payments/{id}`; PSP webhooks.

**Data model.** `payment(id, order_id, amount, currency, status, psp, psp_reference UNIQUE, version)`; state machine (CREATED → AUTHORIZED → CAPTURED → REFUNDED/PARTIALLY_REFUNDED; FAILED; CANCELED); **double-entry ledger** `ledger_entry(id, txn_id, account, debit, credit, currency, created_at)` with invariant Σdebits = Σcredits per transaction (append-only); `idempotency_record`; `outbox`.

**Architecture.**

```
Order service → Payment API (idempotency, validation, state machine)
   → PSP adapter (tokenized card data; PSP idempotency keys)
   → PostgreSQL (payments, ledger, outbox in one tx) ⇢ Kafka payment events → Order service, notifications
PSP webhooks → verify signature → idempotent state transition
Reconciliation job: daily PSP settlement files vs ledger → discrepancies → ops queue
```

**Scaling.** Modest throughput; focus on correctness. Vertical PostgreSQL with Multi-AZ synchronous standby; partition ledger by month; read replicas for reporting.

**Failures.** PSP timeout after charge: status unknown → record `PENDING_UNKNOWN`, query PSP by idempotency key, never blindly retry with a new key; webhook duplicates/out-of-order → state machine ignores invalid transitions; outbox for events; saga with Order service (reserve → pay → confirm; compensations: release reservation, refund).

**Security.** PCI: never touch raw card data — use PSP tokenization/hosted fields; mTLS; strict authZ (only Order service can create payments); audit log; encryption; fraud checks; amount/currency validation with `BigDecimal` and ISO 4217.

**Observability.** Payment success rate by PSP, unknown-state count, reconciliation discrepancies, webhook lag, ledger imbalance alarm (should be zero).

**Trade-offs.** Sync vs async payment confirmation (UX vs resilience); single PSP vs multi-PSP routing (simplicity vs availability/cost); ledger in same DB vs separate service.

##### Design 4 — Order Platform

**Requirements.** Cart → checkout → order creation → inventory reservation → payment → fulfillment → shipping updates → cancellations/returns. Scale: 1M orders/day (~12/s avg, 1K/s flash sales). Inventory must not oversell; order history readable by customers; eventual consistency acceptable for search/analytics.

**API.** `POST /orders` (idempotent) → `202 {orderId, status: PENDING}`; `GET /orders/{id}`; `POST /orders/{id}/cancel`; `GET /customers/me/orders?cursor=…` (cursor pagination).

**Data model.** `order(id, customer_id, status, total, version)`, `order_line`, `inventory(sku, warehouse, available, reserved, version)`, `reservation(order_id, sku, qty, expires_at)`, outbox; order status history table.

**Architecture — orchestrated saga.**

```
Order API → Order service (create PENDING + outbox) ⇢ Kafka
  → Saga orchestrator (state per order):
       ReserveInventory → Inventory service (atomic:
                            UPDATE inventory SET available = available - q, reserved = reserved + q
                             WHERE sku = ? AND available >= q)
       ChargePayment   → Payment service (idempotent)
       ConfirmOrder    → Order service
     compensations: ReleaseInventory, RefundPayment
  ⇢ Fulfillment, Notifications, Search/Read models (CQRS projections)
```

**Scaling.** Flash sales: hot SKUs → inventory row contention; mitigate with sharded counters/buckets per SKU, queue-based reservation, pre-allocated stock per region, or virtual waiting room with admission control (rate limit at the edge). Read models for order history (replica/Elasticsearch) and caching product data.

**Failures.** Payment failure → compensate reservation; reservation timeout (abandoned checkout) → expiry job releases; duplicate events → idempotent handlers; orchestrator crash → saga state persisted, resume.

**Security.** Customers see only their orders (object-level authZ); admin actions audited; price/total computed server-side (never trust client totals); fraud screening.

**Observability.** Saga step latency and failure rates, stuck sagas, oversell alarms (should be zero), reservation expiry rates, conversion funnel.

**Trade-offs.** Orchestration vs choreography (central visibility vs coupling via events); synchronous checkout vs async (immediate confirmation vs resilience); reservation at cart vs checkout.

##### Design 5 — Document Search

**Requirements.** Full-text and semantic search over tenant documents (PDFs, HTML, Office), with permissions (document ACLs), facets, highlighting; ingestion within minutes of upload; 5M documents, 50 QPS avg, 500 peak; p95 < 300 ms (lexical), < 800 ms (hybrid with reranking).

**API.** `POST /documents` (upload → 202), `GET /search?q=&filters=&cursor=` → results with snippets, `DELETE /documents/{id}`.

**Data model.** Source of truth: `document(id, tenant_id, acl_groups[], status, version, storage_key)` in PostgreSQL + object storage (S3). Index: chunks with text, metadata, ACL, embedding — in OpenSearch/Elasticsearch (BM25 + kNN) or PostgreSQL (tsvector + pgvector).

**Architecture.**

```
Upload → S3 + document row + outbox ⇢ Kafka → Ingestion workers: extract text (Tika), clean, chunk, embed (batch),
   index (upsert by doc id+version) → status INDEXED
Search API → authZ → build query with tenant + ACL filter → hybrid retrieval (BM25 + vector, RRF fusion)
   → optional reranker (cross-encoder) → highlights → results
```

**Scaling.** Index sharding by tenant or by hash; replicas for query throughput; embedding throughput via batching and rate-limited workers; cache popular queries per tenant+ACL set.

**Failures.** Extraction failures → DLT and status FAILED with reason; embedding provider down → lexical-only degraded mode; index lag → show "processing"; deletes must propagate (tombstones, reconciliation) — stale deleted docs in results are a security bug.

**Security.** ACL filtering *inside* the query (pre-filter), never post-filtering after top-k (leaks counts and can return empty pages); tenant isolation; malware scanning of uploads; encryption at rest.

**Observability.** Ingestion lag, failure rates by type, query latency per stage, zero-result rate, click-through/relevance metrics (offline eval with judged queries: nDCG — Unit 36).

**Trade-offs.** OpenSearch vs PostgreSQL+pgvector (scale/features vs operational simplicity); chunk size (precision vs context); reranking (quality vs latency/cost).

##### Design 6 — Chat Service

**Requirements.** 1:1 and group chat, online presence, typing indicators, message history, push notifications for offline users, read receipts. 20M DAU, 1M concurrent connections, 50K messages/s peak; delivery latency p95 < 200 ms for online recipients; ordered messages per conversation; history durable.

**API.** WebSocket (or SSE + POST) for real-time: `send {conversationId, clientMsgId, body}`, server pushes `message`, `ack`, `typing`, `presence`. REST: `GET /conversations/{id}/messages?before=cursor`, conversation management.

**Data model.** `message(conversation_id, seq, sender_id, client_msg_id, body, created_at)` with primary key `(conversation_id, seq)` — wide-column stores (Cassandra/ScyllaDB/DynamoDB) fit this partition-by-conversation, cluster-by-sequence pattern; PostgreSQL partitioned by conversation hash works at smaller scale. Per-conversation sequence assigned by a single writer per partition. Membership table; per-user inbox/unread counters.

**Architecture.**

```
Clients ⇄ WebSocket gateways (stateful connections; L4/L7 LB with long-lived connections)
   → Connection registry (Redis: userId → gatewayId, TTL heartbeats)
   → Message service: validate membership, dedupe by clientMsgId, assign seq, persist ⇢ Kafka (key = conversationId)
   → Fan-out workers: for each member → online? route to gateway (Redis pub/sub or gateway topic)
                                         : push notification
```

**Scaling.** Gateways scale horizontally (~50–100K connections per instance depending on memory); Kafka partitions by conversation keep per-conversation order; large groups use fan-out-on-read (members fetch from conversation log) instead of fan-out-on-write.

**Failures.** Gateway crash → clients reconnect with last seq; server replays missed messages from history; duplicate sends → clientMsgId dedupe; partition lag → delayed delivery but ordered; presence is best-effort (eventual).

**Security.** Authenticated WebSocket handshake (token), membership checks on every send and history read, rate limits per user, abuse/spam filtering, optional end-to-end encryption (changes server capabilities: no server-side search/moderation).

**Observability.** Connection counts, delivery latency, reconnect rates, fan-out lag, undelivered queue size.

**Trade-offs.** WebSocket vs SSE/long-polling; fan-out on write vs read; wide-column vs relational; E2EE vs server features.

##### Design 7 — Agentic Workflow Platform

**Requirements (clarify first).** A multi-tenant platform where teams define agents (support agent, refund agent, research agent) with tools, knowledge bases and policies; runs can be interactive (chat) or long-running (minutes to days, with approvals); must enforce authorization, approvals, budgets; must be observable and evaluable. Scale: 200 tenants, 50K runs/day, 5 turns avg, peaks 50 runs/s; interactive p95 first token < 2 s; LLM provider rate limits per tenant; data isolation by tenant; audit for all side effects.

**API.**
- `POST /agents/{agentId}/runs {input, conversationId?}` → `202 {runId}` (long) or streaming SSE (interactive).
- `GET /runs/{runId}` (status, outputs, pending approvals), `POST /runs/{runId}/cancel`.
- `GET /approvals?status=PENDING`, `POST /approvals/{id}/approve|reject` (Unit 35).
- Admin: agent definitions (versioned: prompt, model policy, tool set, KB bindings, budgets), tool registry, evaluation runs.

**Data model.** `agent_definition(id, tenant_id, version, model_policy, tool_ids, kb_ids, budgets, prompt_ref)`; `run(id, tenant_id, agent_version, status, state JSONB, turns, tokens, cost, trace_id, created_by)`; `run_event` (append-only: decisions, tool calls, observations); `action_proposal`/`approval_decision`/`audit_event` (Unit 35); `tool_definition(id, schema, risk, required_scopes, executor)`; KB chunks with pgvector and ACLs; eval datasets and reports (Unit 36).

**Architecture.**

```
                          ┌──────────── Control plane ────────────┐
Admin UI → Agent Registry (versioned definitions) · Tool Registry · Policy store · Eval service (gates releases)
                          └────────────────────────────────────────┘
Client → API Gateway (OIDC, tenant, rate limits) → Run API → Run Store (PostgreSQL) + outbox ⇢ Kafka runs.requested
  → Run Workers (bounded concurrency per tenant; virtual threads + semaphores)
       loop (maxTurns, deadline, token/cost budget):
         Model Router (provider/model per policy; retries; circuit breakers; fallback) → LLM providers
         Decision Parser (Unit 34) → Tool Gateway (Unit 33: allow-list, authZ, policy) → Approval Service (Unit 35)
         Retriever (pgvector + BM25, ACL-filtered) · MCP client (external tools behind gateway)
         checkpoint run state after each step (resume after crash or approval)
  ⇢ events (run progress) → SSE to clients; notifications to reviewers
Observability: OTel traces/metrics (Unit 37); Online eval sampler (Unit 36); Audit chain
```

**Scaling.** Workers scale on Kafka lag; per-tenant concurrency limits and token budgets (fairness); provider rate limits enforced with distributed token buckets per provider/model/tenant; streaming for interactive runs; caching of embeddings and retrieval results per tenant; prompt caching where providers support it.

**Failures.** Provider outage/429 → router failover to secondary model (only if evaluated as acceptable for that agent), queue with backoff, degrade to "will follow up"; worker crash → resume from last checkpoint (idempotent tools with keys); tool failure → structured observation; loops → max turns, repeated-call detection; approval timeout → expire and notify; poisoned content → guardrails; cost runaway → budgets and kill switch per tenant/agent.

**Security.** Deterministic boundary: authN → tenant/user authZ → effective tools → gateway checks → approvals; delegated, scoped credentials for tools; MCP servers vetted and proxied; tenant-isolated retrieval (filters + RLS); secrets in a vault, never in prompts; output guards; audit of every side effect; data residency per tenant.

**Observability.** Per-run traces; metrics by tenant/agent/model (cost, tokens, latency, outcomes, stop reasons, approvals); online eval scores; dashboards for queue lag and provider health; alerts on critical eval failures and cost anomalies.

**Trade-offs.** Agents vs workflows (use deterministic workflows where steps are known; agents only where flexible decisions add value — Unit 42); build vs adopt a durable execution engine (Temporal, or framework checkpointers) vs PostgreSQL-backed state machine; single-agent vs multi-agent (complexity and cost vs specialization); one model vs routing (simplicity vs cost/latency optimization, which must be evaluated).

### 7. Comparative Analysis

| Comparison | Key difference | When to use each | Trade-offs | Interview trap |
|---|---|---|---|---|
| Vertical vs horizontal scaling | Bigger box vs more boxes | Vertical first for DBs; horizontal for stateless services | Ceiling/SPOF vs distributed complexity | Sharding on day one |
| Cache-aside vs write-through | Lazy load vs synchronous write | Cache-aside default; write-through for read-heavy, write-light consistency | Staleness vs write latency | "Just add Redis" without invalidation plan |
| Kafka vs RabbitMQ vs SQS | Log vs broker vs managed queue | Kafka for streams/replay; Rabbit for routing/task queues; SQS for simple AWS work queues | Ops burden vs features | "Kafka gives exactly-once end-to-end" |
| Replication vs partitioning vs sharding | Copies vs splits in one DB vs splits across DBs | Replicas for reads/HA; partitions for large tables/retention; shards for write scale | Lag vs pruning vs cross-shard complexity | Confusing partitioning with sharding |
| Distributed lock vs DB constraint | External mutual exclusion vs atomic DB rule | DB constraints/conditional updates for correctness; locks for efficiency | Locks unsafe without fencing | "Redis lock guarantees exactly-once" |
| Token bucket vs fixed window | Burst-tolerant refill vs counter per window | Token bucket for APIs; fixed window for simple quotas | Precision vs simplicity | Ignoring concurrency limits for slow ops |
| Retry vs circuit breaker | Try again vs stop trying | Retry transient errors (idempotent ops) with jitter; break on sustained failure | Retry storms vs availability | Retrying non-idempotent POSTs |
| Orchestration vs choreography | Central coordinator vs event reactions | Orchestration for complex sagas; choreography for simple fan-out | Coupling to orchestrator vs hidden flows | "Microservices must use choreography" |
| Strong vs eventual consistency | Latest value vs converging | Money/inventory vs feeds/search/analytics | Latency/availability vs staleness | Global strong consistency everywhere |
| Workflow vs agent | Predefined steps vs model-chosen steps | Workflow when steps are known; agent for open-ended decisions | Predictability vs flexibility | Using an agent for a fixed process |

### 8. Failure Modes and Debugging

**D1 — Connection-pool exhaustion after enabling virtual threads.**
SYMPTOM: Latency spikes, `SQLTransientConnectionException: Connection is not available, request timed out after 30000ms`.
↓ CAUSE: Virtual threads admitted thousands of concurrent requests; Hikari pool of 10 became the queue; 30 s connection timeout let requests pile up.
↓ INVESTIGATE: `hikaricp.connections.pending`, active, usage time; DB `pg_stat_activity`; thread dumps (`jcmd <pid> Thread.dump_to_file -format=json`).
↓ FIX: Bound concurrency (semaphore/bulkhead per DB-heavy endpoint), fail fast (`connectionTimeout` 1–3 s), shed load (503), optimize slow queries, size pool from DB capacity.
↓ PREVENT: Load tests with realistic concurrency; alerts on pending connections.

**D2 — Cache stampede on a hot key.**
SYMPTOM: Periodic DB CPU spikes every 10 minutes.
↓ CAUSE: Same TTL on hot keys; synchronized expiry.
↓ FIX: TTL jitter, single-flight loading, stale-while-revalidate.

**D3 — Duplicate payment.**
SYMPTOM: Customer charged twice.
↓ CAUSE: Client retried after timeout; server created a new PSP charge (no idempotency key) — or reused key with new PSP key.
↓ FIX: Idempotency keys at API and PSP; unknown-state reconciliation.
↓ PREVENT: Chaos test: inject timeout after PSP success.

**D4 — Consumer lag grows without bound.**
SYMPTOM: Notifications delayed hours.
↓ CAUSE: Slow downstream; retries blocking partitions (blocking retries); too few partitions for desired parallelism; poison message stuck.
↓ INVESTIGATE: Lag per partition (`kafka-consumer-groups.sh --describe --group notifications`), processing time, error logs.
↓ FIX: Non-blocking retry topics for non-ordered work, DLT for poison, increase partitions (plan ahead: partition count changes key→partition mapping), scale consumers, bulkheads.

**D5 — Stale reads after write.**
SYMPTOM: User updates address, page shows old address.
↓ CAUSE: Read routed to lagging replica.
↓ FIX: Read-your-writes routing for that user/session; read from primary after writes.

**D6 — Lock held by a paused process.**
SYMPTOM: Scheduled job ran twice concurrently; data corruption.
↓ CAUSE: Redis lock TTL 30 s; GC pause/long run exceeded TTL.
↓ FIX: Fencing tokens or DB-level conditional updates; ShedLock with `lockAtMostFor` above max runtime; make the job idempotent.

**D7 — Restart storm.**
SYMPTOM: All pods restart during a DB blip.
↓ CAUSE: DB health in liveness probe.
↓ FIX: Dependencies only in readiness (or not at all); liveness checks the process only.

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Estimation drills.* For each of the seven systems, compute avg/peak QPS, storage/year and instance counts from stated assumptions. Hints: 86,400 s/day; peak factor 3–10×.

*1.2 Consistency map.* For the order platform, list each data item and its required consistency level with justification.

*1.3 Pattern matching.* Match 12 symptoms to patterns (stampede → single-flight; duplicates → idempotency; hot partition → key splitting; …).

**Level 2 — Implementation**

*2.1 Rate limiter.* Implement Example 1 with a `HandlerInterceptor`, per-tenant config, `Retry-After`, fail-open/closed policy per route. Tests: Testcontainers Redis; concurrency test with 100 threads proving no over-admission.

*2.2 Idempotency.* Implement Example 2 with tests: replay, mismatch (422), concurrent duplicates (one 201, others 409/replay), crash simulation leaving `IN_PROGRESS`.

*2.3 Outbox + idempotent consumer.* Implement Example 3 with Testcontainers PostgreSQL + Kafka; test duplicate delivery, poison message to DLT, ordering per key.

**Level 3 — Integration**

*3.1 Read/write routing.* Implement `AbstractRoutingDataSource` with `LazyConnectionDataSourceProxy` routing read-only transactions to a replica; add read-your-writes window per user. Test with two PostgreSQL containers (replication optional: simulate lag with a separate DB).

*3.2 Backpressure lab.* Spring Boot app with virtual threads calling a slow stub (WireMock with delay); load test with k6; observe pool exhaustion; add bulkhead + timeouts + 503 shedding; compare p99 and error rates.

**Level 4 — Debugging / Production Scenario**

*4.1 Review this design.* "Checkout calls Inventory, Payment and Shipping synchronously in sequence with 30 s timeouts and 3 retries each; on any failure it returns 500." List failure modes (latency amplification, retry storms, non-idempotent retries, partial completion without compensation) and propose a redesign.

*4.2 Incident reconstruction.* Given metrics (Hikari pending ↑, DB CPU flat, p99 ↑, error 5xx ↑ after a deploy enabling virtual threads), write the root-cause analysis.

### 10. Independent Implementation Project

**Goal.** Produce a **System Design Portfolio**: seven one-to-two-page design documents (URL shortener, notification system, payment service, order platform, document search, chat service, agentic workflow platform) following the nine-step template, plus a working **reliability toolkit** module that implements the cross-cutting mechanisms used by the designs.

**Functional requirements (toolkit).**
1. Redis token-bucket rate limiter with per-tenant policies and `429`/`Retry-After`.
2. Idempotency-Key support for `POST` endpoints.
3. Transactional outbox with relay and idempotent consumer base class.
4. Bulkhead + timeout + circuit breaker configuration for outbound clients (`RestClient` + Resilience4j).
5. Read/write datasource routing.
6. Graceful shutdown and health groups configured.

**Technical requirements.** Java 25, Spring Boot 4, PostgreSQL, Redis, Kafka, Resilience4j, Testcontainers, k6 or Gatling, OpenTelemetry.

**Suggested structure.**

```
system-design-portfolio/
├── designs/
│   ├── 01-url-shortener.md … 07-agentic-workflow-platform.md   (template: 9 sections + diagrams + estimates)
│   └── template.md
└── reliability-toolkit/
    └── src/
        ├── main/java/com/acme/platform/
        │   ├── ratelimit/   TokenBucketRateLimiter, RateLimitInterceptor, RateLimitProperties
        │   ├── idempotency/ IdempotencyService, IdempotencyKeyFilter (or @Idempotent aspect)
        │   ├── outbox/      OutboxEvent, OutboxRepository, OutboxRelay, IdempotentConsumerSupport
        │   ├── resilience/  ResilientHttpClientConfig
        │   └── routing/     ReadWriteRoutingDataSource, ReadYourWritesContext
        ├── main/resources/  scripts/token_bucket.lua, db/migration/*
        └── test/java/...    RateLimiterIT, IdempotencyIT, OutboxIT, RoutingIT, BackpressureLoadTest (k6 script)
```

**Milestones.** (1) template + URL shortener doc; (2) rate limiter; (3) idempotency; (4) outbox/consumer; (5) resilience/backpressure lab; (6) remaining design docs; (7) agentic platform doc referencing Units 33–37; (8) mock interviews using the docs.

**Testing requirements.** Concurrency tests for limiter and idempotency; duplicate/poison tests for consumer; load test showing backpressure working (bounded latency, explicit 503s instead of timeouts).

**Definition of Done.**
- [ ] Seven design docs, each with estimates, API, data model, architecture diagram, scaling, failures, security, observability and trade-offs (with rejected alternatives).
- [ ] Toolkit mechanisms implemented and tested under concurrency.
- [ ] Load-test report demonstrating backpressure.
- [ ] Three recorded 45-minute mock interviews with self-review notes.

**Optional extensions.** Consistent-hashing shard router; Debezium-based outbox; multi-region read design for the URL shortener; Temporal-based saga for the order platform.

### 11. Testing Strategy

- **Unit:** algorithm logic (bucket math with an injected clock in a Java implementation), state machines.
- **Integration with Testcontainers:** Redis scripts, PostgreSQL constraints/locking, Kafka delivery semantics.
- **Concurrency:** latch-synchronized threads for limiter, idempotency, claims; repeated runs (`@RepeatedTest`).
- **Contract tests:** between services (Spring Cloud Contract/Pact) for API compatibility.
- **Load/performance:** k6/Gatling with realistic arrival rates; measure p50/p95/p99, error rates, saturation metrics.
- **Chaos/fault injection:** Toxiproxy for latency/timeouts, kill consumers mid-processing, Redis failover.
- **Resilience assertions:** circuit opens, bulkhead rejects, shedding returns 503 quickly.

### 12. Engineering Scenarios

**Scenario 1 — Black Friday.** Traffic will be 20× normal for 6 hours on the order platform.
*Expected reasoning.* Capacity plan from estimates and load tests; pre-scale; cache catalog aggressively; waiting room/admission control at the edge; protect inventory with atomic reservations and per-SKU strategies; degrade non-critical features (recommendations, analytics); freeze deploys; runbooks; dashboards on saturation signals.

**Scenario 2 — FDE: "Make it real-time."** A logistics customer asks for "real-time order tracking."
*Expected reasoning.* Clarify: how fresh (seconds vs minutes)? for whom (customer app, ops dashboard)? volume? data source (carrier webhooks vs polling)? Many "real-time" needs are satisfied by 30–60 s freshness with polling/SSE; true push needs WebSockets and event pipelines. Identify the authoritative source (carrier events), failure handling (missed webhooks → reconciliation), and how to demonstrate (latency SLI from carrier event to UI).

**Scenario 3 — Multi-tenant noisy neighbor.** One tenant's batch job saturates the DB and slows everyone.
*Expected reasoning.* Per-tenant rate limits and concurrency budgets; separate queues/worker pools for batch vs interactive; query optimization; consider dedicated resources (shards) for large tenants; fair scheduling.

**Scenario 4 — Shard or not?** Orders table is 3 TB and growing 1 TB/year; writes 300/s.
*Expected reasoning.* Writes are fine for one PostgreSQL primary; problem is size/maintenance. Partition by month, archive old partitions, read replicas for reporting, consider Citus/Aurora only if growth or write rate demands. Don't shard prematurely.

**Scenario 5 — LLM provider limits.** The agentic platform hits provider rate limits at peak.
*Expected reasoning.* Per-tenant token buckets, priority queues (interactive over batch), caching, smaller models for simple steps (evaluated), multi-provider routing, request batching for embeddings, negotiate higher limits; graceful degradation messages.

### 13. Interview Preparation

#### How to run a 30–45-minute system-design interview

| Minutes | Activity | Output |
|---|---|---|
| 0–5 | Clarify functional and non-functional requirements; state assumptions | Scope list, scale numbers, SLOs |
| 5–8 | Estimates | QPS, storage, bandwidth |
| 8–12 | API | 3–6 endpoints, idempotency, pagination |
| 12–17 | Data model | Entities, keys, indexes, source of truth |
| 17–27 | High-level architecture | Diagram with data flow (sync/async) |
| 27–37 | Deep dives (interviewer-led): scaling, consistency, failures | Bottlenecks and mitigations |
| 37–42 | Security, observability | Controls, SLIs, alerts |
| 42–45 | Trade-offs and evolution | Rejected alternatives, when to revisit |

Narrate decisions ("I'll start with a single PostgreSQL primary because writes are 300/s; if we exceed X, I'd partition by…"). Invite the interviewer to steer deep dives.

#### Quick Questions

**Q: What does 99.9% availability allow per month?** About 43 minutes of downtime (30 days × 24 × 60 × 0.001 ≈ 43.2).

**Q: Cache-aside: delete or update the cache on write?** Usually delete after commit — updating races with concurrent writers; deletion forces a fresh load.

**Q: Why idempotency keys?** Clients and infrastructure retry; without keys, retries duplicate side effects (charges, orders). Keys let the server recognize and replay.

**Q: Why are Redis locks risky?** TTL expiry during process pauses or failover lets two holders act; without fencing tokens the resource can't reject the stale holder.

#### Intermediate Questions

**Q: Design rate limiting for a public API with per-tenant quotas.**
*Strong answer:* Token bucket in Redis via atomic Lua (or gateway rate limiter), keyed by tenant + route class, capacity/refill from tenant plan; concurrency limits for expensive endpoints; 429 with Retry-After and quota headers; local fallback limiter if Redis fails; metrics on throttles; edge protection for abuse.

**Q: How do you avoid the dual-write problem?**
*Strong answer:* Transactional outbox: business state and event row in one DB transaction; relay to Kafka at-least-once; idempotent consumers. Or CDC. Avoid writing to DB and Kafka independently.

**Q: How do virtual threads change scaling?**
*Strong answer:* Blocking I/O no longer consumes platform threads, so request concurrency rises cheaply; bottlenecks shift to DB pools, downstream limits and memory, so explicit backpressure (bulkheads, timeouts, shedding) becomes essential. CPU-bound work doesn't benefit.

#### Advanced Questions

**Q: Walk through exactly-once processing from Kafka to an external email provider.**
*Strong answer:* True end-to-end exactly-once isn't possible across systems without cooperation; achieve effectively-once with at-least-once delivery + idempotent consumer (processed-event table in the same transaction as local effects) + idempotency key passed to the provider; handle the crash window via provider dedupe; DLT for poison messages.

**Q: How would you shard a multi-tenant SaaS database?**
*Strong answer:* Tenant id as shard key (queries are tenant-scoped); directory service mapping tenant → shard to allow moving big tenants; small tenants packed together, large tenants isolated; cross-tenant analytics via a separate warehouse; resharding by tenant migration (dual writes or logical replication + cutover); consider Citus/managed distributed SQL before building custom.

#### Coding Questions

1. Implement a token bucket in Java with an injected `Clock` and thread safety; then explain why a distributed version needs Redis/Lua.
2. Implement `IdempotencyService.claim` with a unique constraint.
3. Implement an LRU cache (`LinkedHashMap` with `removeEldestEntry`) and discuss why production uses Caffeine (W-TinyLFU, async loading, stats).

#### Scenario Questions

**Q: Design the agentic workflow platform (45 minutes).** Use Design 7 (agentic workflow platform): clarify run types and risk; API with async runs and approvals; data model for runs, events, proposals; architecture with run workers, model router, tool gateway, approval service, retriever, MCP; scaling with per-tenant budgets and provider rate limits; failures (provider outage, crash resume, loops); security boundary; observability and evals; trade-offs (workflow vs agent, durable execution engine choice).

### 14. Explain-It-at-Three-Levels

**Idempotency**
- *30 seconds:* Retries are inevitable, so side-effecting operations must produce the same effect when repeated — via idempotency keys, unique constraints and idempotent consumers.
- *2 minutes:* Key → request hash → stored response; claim in its own transaction; replay on duplicate; 409 while in progress; 422 on mismatch; propagate keys to providers; outbox + processed-event tables for messaging.
- *Deep:* Crash windows (after provider success, before recording), reconciliation, key scoping and TTLs, interaction with sagas and exactly-once semantics, testing with fault injection.

**Backpressure**
- *30 seconds:* Bound the work in flight so slow dependencies cause fast, explicit rejection or slowing producers — not unbounded queues, timeouts and cascading failure.
- *2 minutes:* Little's law; bulkheads, semaphores, bounded queues, timeouts, shedding with 429/503, Kafka pull/pause; virtual threads remove implicit limits so add explicit ones.
- *Deep:* Adaptive concurrency limits, priority shedding, retry budgets, coordinated omission in load tests, observability signals of saturation.

**Caching**
- *30 seconds:* Store derived copies of hot data closer to readers, with explicit staleness bounds and invalidation; the database stays the source of truth.
- *2 minutes:* Patterns, invalidation after commit, stampede protection, two-level caches, `@Cacheable` proxy caveats, tenant-aware keys.
- *Deep:* Consistency races, hit-rate economics, memory sizing, eviction policies (W-TinyLFU), cache warming and failure modes.

### 15. Knowledge Check

**Conceptual**
1. What is Little's law and why does it explain thread/connection exhaustion?
2. Difference between partitioning and sharding?
3. Why is liveness different from readiness?
4. When is eventual consistency acceptable in an order platform?
5. Why prefer DB conditional updates over distributed locks for correctness?

**Code reading**
6. What's wrong with `@Cacheable("orders") public Order getOrder(String id)` in a multi-tenant app?
7. In the idempotency example, why does `claim` use `REQUIRES_NEW`?
8. What does `FOR UPDATE SKIP LOCKED` do in the outbox relay?

**Debugging**
9. After enabling virtual threads, p99 latency got worse and connection timeouts appeared. Why?
10. Consumer lag grows only on partition 7. Likely causes?

**Design**
11. URL shortener: 301 or 302? Defend.
12. Payment PSP call times out. What do you do?

### Knowledge Check Answers

1. L = λW: in-flight work equals arrival rate times latency; when latency rises, in-flight requests rise proportionally until pools/threads/memory are exhausted.
2. Partitioning splits a table within one database instance (pruning, retention); sharding distributes data across multiple instances (write scale) with cross-shard costs.
3. Liveness decides restarts (process stuck); readiness decides traffic routing (temporarily unable to serve). Mixing them causes restart storms during dependency outages.
4. For derived views: search indexes, order history read models, analytics, recommendation caches, notification status — not for inventory reservation or payment state.
5. Conditional updates are atomic and enforced by the store holding the data; locks can be lost (TTL, pauses, failover) without the resource knowing, unless fencing tokens are checked.
6. Cache key is only `id`; if ids aren't globally unique or authorization differs by tenant, another tenant could receive the cached object. Include tenant in the key and still authorize; also self-invocation bypasses the cache.
7. So the claim row commits immediately and concurrent duplicates see it; if it were in the outer transaction, duplicates wouldn't see it until commit, and a rollback of business logic would erase the claim.
8. Locks the selected rows and skips rows locked by other transactions, enabling multiple relays to process disjoint batches without blocking.
9. Virtual threads admitted much more concurrency; requests queued on the small Hikari pool, waiting up to `connectionTimeout`; add bulkheads/timeouts/shedding and right-size.
10. Hot key (skewed key distribution), a poison message being retried (blocking retries), or a slow consumer instance assigned that partition.
11. 302 (or 307) if accurate click analytics and the ability to change/expire destinations matter; 301 if maximal performance and destinations are permanent. Most commercial shorteners favor 302 for analytics.
12. Treat status as unknown: don't retry with a new key; query the PSP by idempotency key/reference; retry the same request with the same key if the PSP supports it; mark `PENDING_UNKNOWN`; reconcile; inform order flow asynchronously.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "Microservices scale better." | Scaling comes from stateless services, data design and bottleneck removal; microservices add network failure modes. |
| "Kafka is exactly-once, so no duplicates." | End-to-end effects still need idempotency. |
| "Add a cache to fix latency." | Caches need invalidation, stampede protection and tenant-aware keys. |
| "Redis lock = mutual exclusion." | Not under pauses/failover without fencing. |
| "Virtual threads mean infinite scalability." | They move the bottleneck; add backpressure. |
| "Shard early to be safe." | Shard when estimates require it; partitioning/replicas/vertical first. |
| "Retries improve reliability." | Without idempotency, jitter and budgets they cause duplicates and storms. |
| "The LLM decides the workflow." | Use deterministic workflows for known steps; agents only where needed. |

### 17. Cheat Sheet

- **Template:** Requirements → API → Data → Architecture → Scaling → Failures → Security → Observability → Trade-offs.
- **Numbers:** 99.9% ≈ 43 min/month; 99.99% ≈ 4.3 min; 86,400 s/day; peak 3–10× avg; Redis ~1 ms, PG ~1–5 ms, cross-region 50–150 ms.
- **Little's law:** L = λW.
- **Caching:** cache-aside + delete after commit + TTL jitter + single-flight; tenant in keys; `@Cacheable` proxy caveats.
- **Queues:** at-least-once + idempotent consumers; order per partition key; DLT; lag alerts; outbox for dual writes.
- **Replication:** sync (no loss, latency) vs async (lag); read-your-writes routing.
- **Partition vs shard:** within DB vs across DBs; shard key = tenant/user; hot keys.
- **Rate limit:** token bucket (Redis Lua, `TIME`), concurrency limits, 429 + Retry-After.
- **Locks:** prefer constraints/conditional updates/SKIP LOCKED/advisory locks; fencing tokens; ShedLock for jobs.
- **Idempotency:** key + hash + stored response; REQUIRES_NEW claim; 409/422; provider keys.
- **Backpressure:** bulkheads, semaphores, bounded queues, timeouts, 503 shedding, Kafka pause; virtual-thread caveat.
- **Spring:** `server.shutdown=graceful`, health groups, `spring.threads.virtual.enabled`, Resilience4j, `AbstractRoutingDataSource` + `LazyConnectionDataSourceProxy`, `@TransactionalEventListener(AFTER_COMMIT)`.

### 18. Completion Checklist

- [ ] I can estimate load and size a Spring Boot deployment with Little's law.
- [ ] I can explain availability math, SLOs and error budgets.
- [ ] I can choose consistency levels per data item and isolation levels per operation.
- [ ] I can design caching with invalidation and stampede protection.
- [ ] I can implement rate limiting, idempotency, outbox and idempotent consumers.
- [ ] I can implement and demonstrate backpressure under load.
- [ ] I can explain why locks need fencing and when to avoid them.
- [ ] I have written all seven design docs and can present each in 30–45 minutes.
- [ ] I can defend choices against simpler alternatives and say when I'd revisit them.

### 19. Further Research

**Essential**
- *Designing Data-Intensive Applications* (Kleppmann), 2nd edition — replication, partitioning, transactions, consistency, stream processing.
- Spring Boot reference: graceful shutdown, health groups, virtual threads, Kafka, data access. <https://docs.spring.io/spring-boot/reference/>
- PostgreSQL docs: partitioning, MVCC/isolation, explicit locking, `SKIP LOCKED`. <https://www.postgresql.org/docs/current/>
- Apache Kafka documentation: delivery semantics, consumer groups, transactions. <https://kafka.apache.org/documentation/>
- Resilience4j documentation (circuit breaker, bulkhead, rate limiter, retry, time limiter). <https://resilience4j.readme.io/>
- Google SRE book: SLOs, handling overload, addressing cascading failures. <https://sre.google/books/>

**Deeper Study**
- Martin Kleppmann, "How to do distributed locking" (fencing tokens; Redlock critique).
- AWS Builders' Library: timeouts, retries and backoff with jitter; avoiding insurmountable queue backlogs; static stability. <https://aws.amazon.com/builders-library/>
- microservices.io: saga, outbox, CQRS, API gateway patterns.
- JEP 444 (virtual threads) and JEP 491 (synchronize virtual threads without pinning).

**Practice**
- *System Design Interview* (Alex Xu) volumes 1–2 for additional prompts; compare with your own designs.
- k6 and Toxiproxy labs from Sections 9–10.
- Record and review mock interviews using the timing table.

### Unit Completion Standard

Before moving on, you must be able to: **explain** scalability, availability, reliability and consistency with numbers, and the purpose and failure modes of load balancing, caching, queues, replication, partitioning, sharding, CDNs, rate limiting, distributed locks, idempotency and backpressure; **implement** in Spring Boot a Redis token-bucket rate limiter, Idempotency-Key handling, a transactional outbox with idempotent Kafka consumers, read/write routing and explicit backpressure; **test** them under concurrency, duplicate delivery, faults and load; **debug** pool exhaustion, stampedes, duplicates, consumer lag, stale reads and lock failures from metrics and traces; and **defend**, in a 30–45-minute interview, complete designs for a URL shortener, notification system, payment service, order platform, document search, chat service and agentic workflow platform — including requirements, API, data model, architecture, scaling, failures, security, observability and the simpler alternatives you rejected.
