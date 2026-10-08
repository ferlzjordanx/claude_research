# Part XVIII — Architecture and System Design

**What this part teaches.** Unit 38 moves from "I can build a Spring Boot service" to "I can design a system a business can depend on". It covers the vocabulary (scalability, availability, reliability, consistency), the building blocks (load balancers, caches, queues, replicas, partitions, shards, CDNs, rate limiters), the correctness tools for distributed systems (idempotency, distributed locks with fencing, backpressure), and seven end-to-end designs, including an agentic workflow platform that reuses everything from Parts XVI–XVII.

**Why it matters.** Most production incidents aren't syntax errors. They come from unbounded queues, missing timeouts, retries without idempotency, caches serving stale authorization data, hot partitions, and locks that aren't actually exclusive. Senior interviews, and senior jobs, test whether you anticipate these failures and can defend trade-offs under time pressure.

**Where it appears.** Payment and order flows, notification fan-out, search, chat, URL services, and internal AI platforms. Forward Deployed Engineers do this live with customers: elicit requirements, sketch the architecture, estimate load, and defend choices.

**Connections.** Uses earlier units on Java concurrency (virtual threads, executors, `CompletableFuture`), Spring Boot/Web/Data, PostgreSQL (indexes, isolation, replication), Redis, Kafka, Docker/AWS, Spring Security, and OpenTelemetry. Feeds Unit 41 (timed Spring builds), Unit 42 (AI/FDE design defense) and the capstone.

## Unit 38 — Java System Design

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Define and quantify** scalability, availability, reliability and consistency; convert an availability target into an error budget; and compute composite availability of serial and redundant components.
2. **Estimate** load (QPS, peak factor, read/write ratio, storage growth, bandwidth) from requirements, and **size** a Spring Boot deployment (instances, thread/virtual-thread concurrency, DB connections) using Little's Law.
3. **Compare** L4 vs L7 load balancing, health checks (liveness vs readiness), connection draining and graceful shutdown in Spring Boot on Kubernetes/AWS.
4. **Design** caching (cache-aside, read-through, write-through, write-behind) with TTLs, invalidation, stampede protection and correctness boundaries, and implement it with Spring Cache, Caffeine and Redis.
5. **Explain** queues and streams (SQS/RabbitMQ vs Kafka), delivery semantics, consumer groups, ordering by key, retries, DLQs and the transactional outbox.
6. **Explain** replication (leader-follower, sync/async, replica lag, read-your-writes) and partitioning/sharding (range, hash, directory; consistent hashing; hot keys; resharding), and choose a partition key.
7. **Implement** rate limiting (token bucket, sliding window) with Redis Lua scripts, and decide where rate limiting belongs.
8. **Evaluate** distributed locks: why a lease-based lock without fencing tokens is unsafe, and when to prefer DB constraints, advisory locks, conditional updates or idempotency.
9. **Implement** idempotent APIs and consumers (idempotency keys, dedupe tables, natural keys, upserts).
10. **Implement** backpressure (bounded queues/semaphores, load shedding with 429/503 + `Retry-After`, timeouts, circuit breakers, bulkheads) in Spring Boot with virtual threads.
11. **Design** seven systems (URL shortener, notification system, payment service, order platform, document search, chat service, agentic workflow platform) following *requirements → API → data model → architecture → scaling → failures → security → observability → trade-offs*.
12. **Conduct** a 30–45-minute system-design interview: time-box phases, drive the conversation, and defend choices.

### 2. Prerequisite Knowledge

- **Java concurrency:** platform vs virtual threads (Java 21+), `ExecutorService`, `Semaphore`, `CompletableFuture`. Virtual threads make blocking I/O cheap, but **they don't make downstream resources infinite**. A DB pool of 20 connections still admits only 20 concurrent queries. **[Version-dependent]** Java 24 (JEP 491) removed most pinning on `synchronized`, which improved virtual-thread behavior with older libraries.
- **Spring Boot:** `spring.threads.virtual.enabled=true` runs Tomcat request handling, `@Async` and scheduling on virtual threads. HikariCP pool sizing, `server.shutdown=graceful`, Actuator health groups (`/actuator/health/liveness`, `/readiness`).
- **PostgreSQL:** MVCC, isolation levels (Read Committed default), unique constraints, `INSERT … ON CONFLICT`, `SELECT … FOR UPDATE SKIP LOCKED`, advisory locks, `EXPLAIN (ANALYZE, BUFFERS)`, streaming replication.
- **Redis:** single-threaded command execution per shard, atomic ops, TTL, Lua scripts (`EVAL`/`EVALSHA`) or Redis Functions, Redis Cluster hash slots.
- **Kafka (4.x, KRaft only):** topics, partitions, consumer groups, offsets, key-based ordering, idempotent producer, transactions, `acks=all`, `min.insync.replicas`.

**Refresher: Little's Law.** `L = λ × W`. At 2,000 req/s with 50 ms per request, about 100 requests are in flight. If a dependency slows to 1 s, in-flight requests jump to 2,000. With virtual threads you won't run out of threads, but you'll exhaust the DB pool, heap or the downstream service. Every capacity and backpressure argument starts here.

**Refresher: numbers to know (orders of magnitude).** L1 cache ~1 ns; main memory ~100 ns; SSD random read ~100 µs; same-AZ network round trip ~0.5 ms; cross-region ~50–150 ms; Redis GET ~0.2–1 ms over network; PostgreSQL indexed point lookup ~1–5 ms; LLM call ~0.5–30 s. Typical single-instance ballparks (very workload-dependent): a Spring Boot instance serves ~1–5k simple req/s; a PostgreSQL primary handles ~5–20k simple writes/s; a Redis shard ~100k ops/s; a Kafka partition ~10 MB/s.

### 3. Mental Model

A distributed system is **a network of queues connected by pipes of limited width, where any box can disappear and every message can be duplicated, delayed or reordered**.

```
            Clients ──→ [CDN/edge] ──→ [L7 LB / API gateway: TLS, auth, rate limit]
                                              │
                         ┌────────────────────┼────────────────────┐
                         ▼                    ▼                    ▼
                  [Service A ×N]       [Service B ×N]       [Workers ×M]
                   │      │                │                    ▲
                (Redis) (PostgreSQL)   (PostgreSQL)              │
                   cache  primary→replicas                     ⇢ [Kafka] ⇢
```

Design is deciding:

1. **Where work waits,** and how much is allowed to wait (bounded queues).
2. **What happens when a queue is full** (reject, shed, degrade, buffer durably).
3. **What is the source of truth** for each piece of data, and how stale copies may be.
4. **What happens when any single box disappears or responds slowly** (timeouts, retries, idempotency, redundancy).
5. **Who is allowed to do what** (authN/Z at the edge and at each service).
6. **How you'll know** (SLIs, traces, alerts).

### 4. Comprehensive Theory

#### 4.1 Scalability, Availability, Reliability, Consistency

**Scalability.** The ability to handle more load by adding resources. *Vertical* scaling is a bigger box: simple, but it has a ceiling and is a single point of failure. *Horizontal* scaling is more boxes, which requires statelessness or partitioned state. Measure scalability as *throughput vs resources* at a latency target, not just maximum QPS.

**Availability.** The fraction of time (or requests) the system serves correctly. 99.9% = 43.8 min/month downtime; 99.95% = 21.9 min; 99.99% = 4.4 min. **Composite availability:** components in series multiply (0.999 × 0.999 = 0.998), while redundant components improve it (1 − (1 − 0.99)² = 0.9999 if failures are independent, which they often aren't: shared AZ, shared config, shared deploy). The **error budget** is 1 − SLO. Spend it on releases and experiments; when it's exhausted, slow down.

**Reliability.** Correct behavior over time, including under faults: no lost orders, no double charges. A system can be available and unreliable (fast wrong answers), or reliable and unavailable (correctly refuses during an outage).

**Consistency.** Several meanings. Don't conflate them in interviews:

- **ACID "C":** invariants hold after a transaction (application-defined, enforced by constraints).
- **Isolation levels:** read committed, repeatable read, serializable: what concurrent transactions can observe.
- **Replication consistency:** linearizable (behaves like one copy), sequential, causal, read-your-writes, monotonic reads, eventual.
- **CAP:** during a network *partition*, choose consistency (refuse some requests) or availability (serve possibly stale/conflicting data). **PACELC** adds: *else* (no partition), trade latency vs consistency.

**Interview perspective.** Interviewers check whether you attach numbers (SLOs, budgets) and pick a *specific* consistency model per data type: balances need strong consistency, view counts can be eventual.

#### 4.2 Load Balancing

**L4 vs L7.** L4 (TCP/UDP, AWS NLB) forwards connections and is fast and protocol-agnostic. L7 (HTTP, AWS ALB, Envoy, NGINX, Spring Cloud Gateway) routes by path/header, terminates TLS, retries, and handles auth and rate limits.

**Algorithms.** Round robin, least outstanding requests (good for variable latency), weighted, and consistent hashing (stickiness for caches/sessions).

**Health checks.** *Liveness* = "restart me if this fails" (process wedged). *Readiness* = "don't send traffic" (warming up, dependency down, draining). Don't make liveness depend on the database, or a DB blip restarts your entire fleet. Spring Boot exposes `/actuator/health/liveness` and `/readiness` with configurable groups.

**Graceful shutdown.** `server.shutdown=graceful` + `spring.lifecycle.timeout-per-shutdown-phase=30s`: stop accepting, finish in-flight, then exit. On Kubernetes, add a `preStop` sleep so the endpoint is removed from the load balancer before the app stops accepting. Kafka consumers should commit offsets and leave the group cleanly.

**Common mistakes.** LB retries on non-idempotent POSTs (duplicates). Sticky sessions hiding statefulness. Health checks that call every dependency.

#### 4.3 Caching

**Patterns.**

| Pattern | Read | Write | Use |
|---|---|---|---|
| Cache-aside (lazy) | App checks cache → miss → DB → populate | App writes DB → **invalidates** cache | Default; simple; tolerates cache loss |
| Read-through | Cache library loads on miss | — | Same as above, encapsulated (Caffeine `LoadingCache`) |
| Write-through | — | Write cache and DB synchronously | Read-heavy, need fresh cache |
| Write-behind | — | Write cache, flush to DB async | Very write-heavy, can tolerate loss (risky) |

**Levels.** Browser/CDN → gateway → local in-process (Caffeine, nanoseconds, per instance, inconsistent across instances) → distributed (Redis, ~1 ms, shared) → DB buffer cache.

**Invalidation and staleness.** Prefer **delete on write** over update-on-write (avoids racing writers leaving stale values). Use TTLs as a safety net. Cross-instance local caches need pub/sub invalidation or short TTLs. A known race: reader misses, reads old value from DB, writer updates DB and deletes cache, then reader writes the stale value to cache. Mitigate with short TTLs, versioned values, or delayed double-delete.

**Stampede (thundering herd).** A hot key expires and 1,000 requests hit the DB at once. Mitigations: request coalescing (one loader per key; Caffeine does this per instance, Spring's `@Cacheable(sync = true)` too), probabilistic early refresh, stale-while-revalidate, and jittered TTLs.

**Correctness boundaries.** Never cache authorization decisions longer than you can tolerate stale permissions. Cache keys must include the tenant (or anything else that changes the answer). Never cache personalized responses at a shared CDN.

**Spring.** `@EnableCaching` + `@Cacheable("products")` is implemented with an AOP proxy (`CacheInterceptor`). Self-invocation bypasses it, and `@Cacheable` on a private method does nothing. `@CacheEvict` on writes. Configure a `CacheManager` (Caffeine for local, `RedisCacheManager` for distributed) with per-cache TTLs.

#### 4.4 Queues and Streams

**Why.** Decouple producers from consumers, absorb bursts, retry asynchronously, and fan out.

| | Queue (SQS, RabbitMQ) | Log/stream (Kafka) |
|---|---|---|
| Model | Messages deleted when acked | Append-only log, consumers track offsets |
| Replay | No (DLQ aside) | Yes (retention) |
| Ordering | Limited (SQS FIFO per group) | Per partition (by key) |
| Fan-out | Exchanges/SNS | Multiple consumer groups |
| Scaling consumers | Add consumers | ≤ partitions per group |
| Typical use | Task distribution, work queues | Event streaming, CDC, event sourcing, many consumers |

**Delivery semantics.** At-most-once (may lose), at-least-once (may duplicate, the default you design for), and "exactly-once" (Kafka transactions give exactly-once *within Kafka* for read-process-write; for external side effects you still need idempotency).

**Retries and DLQ.** Retry transient failures with exponential backoff + jitter. Send poison messages to a DLQ/dead-letter topic after N attempts, with alerting and a replay tool. Spring Kafka offers `DefaultErrorHandler` with `DeadLetterPublishingRecoverer`, or non-blocking retry topics (`@RetryableTopic`).

**Ordering.** Kafka guarantees order within a partition. Choose the key so that events needing order share it (`orderId`). Retries can reorder events: blocking retries preserve order but stall the partition, while retry topics don't preserve order.

**Transactional outbox.** Write the business change and an `outbox` row in one DB transaction. A relay (polling, or CDC with Debezium) publishes to Kafka. This avoids the dual-write problem (DB committed, publish failed, or vice versa).

#### 4.5 Replication

**Leader–follower (primary–replica).** Writes go to the leader. Followers replicate the WAL. Async replication means low write latency and possible data loss on failover plus replica lag. Sync replication means no loss for acknowledged writes, at the cost of higher latency and availability depending on the sync replica.

**Read replicas and consistency.** Reads from replicas may be stale, which breaks **read-your-writes** ("I updated my address and it still shows the old one"). Fixes: route a user's reads to the primary for N seconds after their write, read from the primary for critical reads, or track LSN/position and wait for the replica to catch up.

**Failover.** Automatic failover (Patroni, RDS Multi-AZ, Aurora) has an RTO of tens of seconds. Clients must reconnect: set HikariCP `maxLifetime` below server-side limits and handle transient errors with retries on idempotent operations. **Split brain** (two leaders) is prevented with consensus/fencing in the HA tooling.

**Multi-leader / leaderless** (Cassandra/Dynamo-style, quorum `R + W > N`): higher write availability across regions, but conflicts need resolution (last-writer-wins loses data; CRDTs or application merges).

#### 4.6 Partitioning and Sharding

**Partitioning** splits data so that each part is handled by different resources. Inside one PostgreSQL instance, *declarative partitioning* (by range/list/hash) helps maintenance and pruning (for example time-partitioned events with cheap `DROP PARTITION`). **Sharding** spreads partitions across *independent* database instances to scale writes and storage.

**Strategies.**

- **Range** (by date, by ID range): efficient range scans; hot spots on the latest range.
- **Hash** (`hash(key) mod N`): even spread; range scans need scatter-gather; changing N moves almost everything.
- **Consistent hashing / virtual nodes:** adding a node moves ~1/N of keys. Used by Redis Cluster (16,384 hash slots) and Cassandra.
- **Directory/lookup:** a mapping service (tenant → shard). Flexible, supports moving big tenants, but adds a dependency.

**Choosing a key.** High cardinality, even access, and aligned with your most frequent queries (so they hit one shard). For multi-tenant SaaS, `tenant_id` is common, with a directory for whale tenants.

**Pain points.** Cross-shard transactions (avoid them; use sagas), cross-shard queries (scatter-gather or a separate read model/search index), resharding (double-write + backfill + cutover), and hot keys (a celebrity user; split the key, add a cache, or isolate).

#### 4.7 CDN

Edge caches for static assets and cacheable GET responses, close to users. Controlled with `Cache-Control` (`public, max-age, s-maxage, stale-while-revalidate`), `ETag`/`Last-Modified` for revalidation, and versioned asset URLs (`app.3f9a.js`) for instant invalidation. Also absorbs DDoS and terminates TLS. Don't cache personalized or authorized responses at shared edges unless the cache key includes the auth context (usually: don't).

#### 4.8 Rate Limiting

**Why.** Protect capacity, ensure fairness between tenants, enforce commercial quotas, and slow abuse (credential stuffing, scraping, LLM cost attacks).

**Algorithms.**

- **Fixed window:** a counter per minute. Simple, but allows 2× bursts at window boundaries.
- **Sliding window log:** stores timestamps. Exact, but memory-heavy.
- **Sliding window counter:** weighted current + previous window. A good approximation.
- **Token bucket:** a bucket of capacity *B* refilled at rate *r*. Allows bursts up to *B* while enforcing average *r*. The most common choice.
- **Leaky bucket:** smooths output to a constant rate.

**Where.** At the edge/gateway (cheap rejection, per IP/API key), and in the service for per-tenant/per-user business quotas (needs the identity). Distributed limits need shared state (Redis) or approximate local limits (N instances × local limit).

**Response.** `429 Too Many Requests` with `Retry-After`, and optionally `RateLimit`/`RateLimit-Policy` headers (IETF draft). Clients must back off with jitter.

#### 4.9 Distributed Locks

**The problem.** "Only one worker should process invoice X" or "only one instance should run this job".

**Why naive locks fail.** A lease-based lock (Redis `SET key value NX PX 30000`) expires after 30 s. If the holder pauses (GC, VM stall, network partition) for 40 s, the lease expires, another worker acquires it, and now **two workers believe they hold the lock**. When the first resumes, it writes stale data.

**Fencing tokens.** The lock service issues a monotonically increasing token with each acquisition. The *storage* rejects writes with a token lower than the last seen (`UPDATE … SET … , fence = :token WHERE id = :id AND fence < :token`). Without the storage checking the token, the lock is only a performance optimization (reducing duplicate work), not a correctness guarantee. (Martin Kleppmann's analysis of Redlock is the standard reference.)

**Prefer, in order:**

1. **No lock:** make the operation idempotent or use a conditional update (`UPDATE … WHERE status='PENDING'`, as in Unit 35's claim).
2. **DB constraints:** a unique index makes the second insert fail.
3. **Row locks in the same DB:** `SELECT … FOR UPDATE` (short transactions), or `FOR UPDATE SKIP LOCKED` for work queues.
4. **PostgreSQL advisory locks** (`pg_try_advisory_xact_lock(key)`) for coordinating jobs that use the same DB. Released at transaction end.
5. **ZooKeeper/etcd** locks with fencing (sequence numbers / revisions) when you need a dedicated coordination service.
6. **Redis locks** (Redisson, ShedLock with Redis) for efficiency-only mutual exclusion, such as scheduled jobs where a rare double run is harmless.

#### 4.10 Idempotency

**Definition.** Performing an operation multiple times has the same effect as performing it once.

**Why it's central.** With timeouts and retries, the client can't distinguish "request lost" from "response lost". Without idempotency, safe retries are impossible.

**Techniques.**

- **Idempotency keys (client-supplied):** the client sends `Idempotency-Key: <uuid>`. The server stores `(key, request hash, response)` and returns the stored response for repeats. If the same key arrives with a different body, return 422. If the first request is still in progress, return 409. Store with TTL (for example 24 h).
- **Natural keys + upsert:** `INSERT … ON CONFLICT (order_id) DO NOTHING`.
- **Dedupe table for consumers:** `processed_messages(message_id PK)` inserted in the same transaction as the side effect.
- **Conditional updates / state machines:** transitions only from expected states.
- **Downstream idempotency:** pass keys to payment providers.

#### 4.11 Backpressure

**Definition.** Mechanisms by which an overloaded component signals upstream to slow down, rather than accepting unbounded work and collapsing.

**Tools.**

- **Bounded concurrency:** `Semaphore` per downstream (bulkhead). With virtual threads this is *the* way to cap concurrency, because thread pools no longer do it implicitly.
- **Bounded queues:** `ArrayBlockingQueue`, executor queue limits; reject when full.
- **Load shedding:** fail fast with 503/429 + `Retry-After` when saturated (in-flight > limit, queue wait > threshold). Shed low-priority traffic first.
- **Timeouts everywhere:** connect/read timeouts on HTTP clients, JDBC query timeouts, and an overall request deadline propagated to downstream calls.
- **Retries with exponential backoff + jitter, and retry budgets** (for example retries ≤ 10% of requests). Without budgets, retries amplify an outage (retry storms).
- **Circuit breakers:** stop calling a failing dependency for a cool-down, and serve a fallback (Resilience4j; Spring Framework 7 adds `@ConcurrencyLimit` and `@Retryable` in core [Version-dependent]).
- **Kafka consumer lag** as natural backpressure: consumers pull at their own pace, and you scale on lag.
- **Reactive streams** (Project Reactor) propagate demand (`request(n)`) end-to-end. Useful for streaming, but not required for backpressure in a virtual-thread service.

### 5. Internal Mechanics

#### 5.1 Request path through a Spring Boot service under load (virtual threads)

```
LB → Tomcat acceptor → connection → request dispatched to a NEW virtual thread (spring.threads.virtual.enabled)
  → Spring Security filter chain → DispatcherServlet → @RestController
  → service: semaphore.tryAcquire(timeout) for downstream X ── fail → 503 + Retry-After (shed)
  → HikariCP getConnection (connectionTimeout 250–1000 ms) ── pool exhausted → SQLTransientConnectionException → 503
  → JDBC query (statement timeout) → PostgreSQL backend process
  → virtual thread parks during I/O; carrier thread runs other virtual threads
  → response; semaphore released; connection returned
```

With platform threads, Tomcat's `maxThreads` (default 200) was an implicit bulkhead. With virtual threads, that limit disappears, so add explicit limits (semaphores, pool sizes, `server.tomcat.max-connections`, gateway concurrency limits). Otherwise a slow dependency lets in-flight requests grow without bound (Little's Law), and memory and downstreams collapse.

#### 5.2 Redis token bucket internals

A Lua script runs atomically on the Redis shard (single-threaded execution), so read-refill-decide-write can't interleave across instances. The script reads `tokens` and `ts`, refills `min(capacity, tokens + (now − ts) × rate)`, decides, writes and sets a TTL. Use the Redis server's `TIME` (or pass the client time consistently) to avoid clock skew between app instances. Keys must hash to one slot in Redis Cluster (`{tenant:42}:bucket`).

#### 5.3 Kafka consumer group mechanics relevant to design

Partitions are assigned to consumers in a group. At most one consumer per partition, so max parallelism = partition count. Rebalances (consumer joins/leaves, or `max.poll.interval.ms` exceeded by slow processing) pause consumption. Use cooperative-sticky assignment and keep processing per poll bounded. Kafka 4.x also offers the new consumer group protocol (KIP-848) with server-side assignment and fewer stop-the-world rebalances [Version-dependent]. Offsets are committed after processing (at-least-once), so duplicates appear after crashes and rebalances, and consumers must be idempotent.

### 6. Implementation Examples

#### Example 1 — Minimal: Bounded concurrency with load shedding

```java
package com.example.design.backpressure;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

import java.time.Duration;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/** A bulkhead: caps concurrent calls to one dependency; sheds instead of queuing unboundedly. */
public final class Bulkhead {

    @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)
    public static class SaturatedException extends RuntimeException {
        public SaturatedException(String name) { super(name + " saturated"); }
    }

    private final String name;
    private final Semaphore permits;
    private final Duration maxWait;

    public Bulkhead(String name, int maxConcurrent, Duration maxWait) {
        this.name = name;
        this.permits = new Semaphore(maxConcurrent, true);
        this.maxWait = maxWait;
    }

    public <T> T call(Supplier<T> work) {
        boolean acquired;
        try {
            acquired = permits.tryAcquire(maxWait.toMillis(), TimeUnit.MILLISECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new SaturatedException(name);
        }
        if (!acquired) throw new SaturatedException(name);
        try {
            return work.get();
        } finally {
            permits.release();
        }
    }

    public int inFlight(int max) { return max - permits.availablePermits(); }
}
```

A `@RestControllerAdvice` maps `SaturatedException` to `503` with `Retry-After: 1` and a `ProblemDetail`. Size `maxConcurrent` from Little's Law and the dependency's capacity (for example DB pool size, or the downstream's documented concurrency limit).

#### Example 2 — Realistic: Idempotency keys for a POST endpoint

```sql
-- V1__idempotency.sql
CREATE TABLE idempotency_record (
    tenant_id     text        NOT NULL,
    idem_key      text        NOT NULL,
    request_hash  char(64)    NOT NULL,
    status        text        NOT NULL CHECK (status IN ('IN_PROGRESS','COMPLETED')),
    response_code int,
    response_body jsonb,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, idem_key)
);
CREATE INDEX idempotency_expiry ON idempotency_record (expires_at);
```

```java
package com.example.design.idempotency;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.function.Supplier;

@Service
public class IdempotencyService {

    public record StoredResponse(int status, String body) {}

    private final JdbcClient jdbc;
    private final TransactionTemplate tx;
    private final JsonMapper json;

    public IdempotencyService(JdbcClient jdbc, TransactionTemplate tx, JsonMapper json) {
        this.jdbc = jdbc;
        this.tx = tx;
        this.json = json;
    }

    /**
     * Runs `operation` at most once per (tenant, key). The operation must perform its own DB writes
     * inside the provided transaction so that "business effect" and "COMPLETED marker" commit atomically.
     */
    public ResponseEntity<String> execute(String tenant, String key, String requestHash,
                                          Supplier<ResponseEntity<Object>> operation) {
        try {
            jdbc.sql("""
                INSERT INTO idempotency_record (tenant_id, idem_key, request_hash, status, expires_at)
                VALUES (:t, :k, :h, 'IN_PROGRESS', :exp)
                """).param("t", tenant).param("k", key).param("h", requestHash)
                .param("exp", java.sql.Timestamp.from(Instant.now().plus(Duration.ofHours(24))))
                .update();
        } catch (DuplicateKeyException e) {
            return replay(tenant, key, requestHash);
        }

        return tx.execute(status -> {
            ResponseEntity<Object> result = operation.get();      // business writes in this tx
            String body = json.writeValueAsString(result.getBody());
            jdbc.sql("""
                UPDATE idempotency_record SET status='COMPLETED', response_code=:c, response_body=:b::jsonb
                 WHERE tenant_id=:t AND idem_key=:k
                """).param("c", result.getStatusCode().value()).param("b", body)
                .param("t", tenant).param("k", key).update();
            return ResponseEntity.status(result.getStatusCode()).body(body);
        });
        // If the operation throws, the business tx rolls back. A cleanup step (or a catch block) should
        // delete the IN_PROGRESS row so the client can retry; omitted here for brevity.
    }

    private ResponseEntity<String> replay(String tenant, String key, String requestHash) {
        Optional<Object[]> row = jdbc.sql("""
            SELECT request_hash, status, response_code, response_body::text
              FROM idempotency_record WHERE tenant_id=:t AND idem_key=:k
            """).param("t", tenant).param("k", key)
            .query((rs, n) -> new Object[]{rs.getString(1), rs.getString(2), rs.getInt(3), rs.getString(4)})
            .optional();
        if (row.isEmpty()) return ResponseEntity.status(HttpStatus.CONFLICT).body("retry");
        Object[] r = row.get();
        if (!requestHash.equals(r[0])) {
            return ResponseEntity.unprocessableEntity().body("Idempotency-Key reused with different request");
        }
        if ("IN_PROGRESS".equals(r[1])) {
            return ResponseEntity.status(HttpStatus.CONFLICT).header("Retry-After", "1").body("in progress");
        }
        return ResponseEntity.status((int) r[2]).body((String) r[3]);
    }
}
```

**Explanation.** The `INSERT` of the `IN_PROGRESS` row is the claim: the primary key guarantees one winner. The operation and the `COMPLETED` update share a transaction, so a crash can't leave a completed business effect without a stored response. If the operation calls an *external* system, you also need that system's idempotency key (as in Unit 35), because the DB transaction doesn't cover it. A scheduled job deletes expired rows.

#### Example 3 — Production-oriented: Redis token bucket, Kafka idempotent consumer, fenced lock

**Token bucket rate limiter (Spring Data Redis + Lua).**

```lua
-- src/main/resources/redis/token_bucket.lua
-- KEYS[1] = bucket key; ARGV = capacity, refill_per_sec, cost
local capacity = tonumber(ARGV[1])
local rate     = tonumber(ARGV[2])
local cost     = tonumber(ARGV[3])
local t        = redis.call('TIME')
local now      = tonumber(t[1]) + tonumber(t[2]) / 1000000

local state  = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1]) or capacity
local ts     = tonumber(state[2]) or now

tokens = math.min(capacity, tokens + (now - ts) * rate)
local allowed = tokens >= cost
if allowed then tokens = tokens - cost end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], math.ceil(capacity / rate) + 1)

local retry_after = 0
if not allowed then retry_after = math.ceil((cost - tokens) / rate) end
return { allowed and 1 or 0, math.floor(tokens), retry_after }
```

```java
package com.example.design.ratelimit;

import org.springframework.core.io.ClassPathResource;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class RedisTokenBucket {

    public record Decision(boolean allowed, long remaining, long retryAfterSeconds) {}

    @SuppressWarnings("rawtypes")
    private static final RedisScript<List> SCRIPT =
        RedisScript.of(new ClassPathResource("redis/token_bucket.lua"), List.class);

    private final StringRedisTemplate redis;

    public RedisTokenBucket(StringRedisTemplate redis) { this.redis = redis; }

    public Decision tryConsume(String tenantId, String bucket, int capacity, double refillPerSec, int cost) {
        String key = "rl:{" + tenantId + "}:" + bucket;     // hash tag keeps the key on one cluster slot
        try {
            List<?> r = redis.execute(SCRIPT, List.of(key),
                String.valueOf(capacity), String.valueOf(refillPerSec), String.valueOf(cost));
            return new Decision(((Long) r.get(0)) == 1L, (Long) r.get(1), (Long) r.get(2));
        } catch (RuntimeException redisDown) {
            // Fail-open vs fail-closed is a product decision: fail-open for a general API,
            // fail-closed (or local fallback limit) for expensive endpoints like LLM calls.
            return new Decision(true, -1, 0);
        }
    }
}
```

A `OncePerRequestFilter` (or a `HandlerInterceptor`) resolves the tenant from the authenticated JWT, calls `tryConsume`, and on denial returns `429` with `Retry-After`. `RedisScript` caches the SHA, and Spring uses `EVALSHA` with an `EVAL` fallback.

**Idempotent Kafka consumer (dedupe table in the same transaction).**

```java
package com.example.design.orders;

import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
class PaymentCapturedListener {

    private final JdbcClient jdbc;
    private final OrderRepository orders;

    PaymentCapturedListener(JdbcClient jdbc, OrderRepository orders) {
        this.jdbc = jdbc;
        this.orders = orders;
    }

    @KafkaListener(topics = "payments.captured", groupId = "order-service")
    @Transactional
    public void on(ConsumerRecord<String, PaymentCaptured> record) {
        String messageId = record.value().eventId();
        int inserted = jdbc.sql("""
            INSERT INTO processed_message (consumer, message_id) VALUES ('order-service', :id)
            ON CONFLICT DO NOTHING
            """).param("id", messageId).update();
        if (inserted == 0) return;                         // duplicate delivery: already applied

        orders.markPaid(record.value().orderId(), record.value().amount());  // conditional state transition
    }
}
```

The dedupe insert and the state change commit together. If the transaction fails, both roll back and Kafka redelivers. The offset is committed after the listener returns (at-least-once). `markPaid` itself uses `UPDATE … WHERE status='PENDING_PAYMENT'` so that out-of-order or replayed events can't regress state.

**Fenced write (lock is advisory; storage enforces).**

```java
// Lock service (e.g. etcd revision, ZooKeeper sequence, or a DB sequence) returns a monotonic token.
long fence = lockService.acquire("invoice:" + invoiceId).token();
int updated = jdbc.sql("""
    UPDATE invoice SET status = :s, last_fence = :f
     WHERE id = :id AND last_fence < :f
    """).param("s", "SENT").param("f", fence).param("id", invoiceId).update();
if (updated == 0) {
    throw new StaleLockException(invoiceId, fence);   // a newer holder already wrote: abort
}
```

### 7. Comparative Analysis

| Comparison | Key difference | Use when | Interview trap |
|---|---|---|---|
| Vertical vs horizontal scaling | Bigger box vs more boxes | Vertical first for DBs; horizontal for stateless services | "Just add instances" with shared DB bottleneck |
| L4 vs L7 LB | Connections vs HTTP-aware | L7 for HTTP routing/auth; L4 for raw TCP/gRPC passthrough | LB retries on POST |
| Cache-aside vs write-through | Lazy + invalidate vs synchronous write | Cache-aside default | Updating cache on write (race) |
| Local vs distributed cache | Per-instance ns vs shared ms | Local for hot immutable; Redis for shared | Inconsistent local caches across instances |
| Queue vs Kafka | Delete-on-ack tasks vs replayable log | Work distribution vs event streaming | "Kafka is exactly-once" for external effects |
| Sync vs async replication | Durability vs latency | Sync for financial primaries (or quorum) | Ignoring replica lag in read-after-write |
| Partitioning vs sharding | Within instance vs across instances | Partition for maintenance; shard for write scale | Sharding prematurely |
| Hash vs range sharding | Even spread vs range scans | Hash for point lookups; range for time series | Hot latest range |
| Redis lock vs DB constraint | Lease (unsafe w/o fencing) vs atomic invariant | Constraint/conditional update for correctness | Redlock as correctness guarantee |
| Token bucket vs fixed window | Smooth burst control vs boundary bursts | Token bucket | Per-instance limits counted as global |
| Retry vs circuit breaker | Try again vs stop trying | Retries for transient; breaker for sustained failure | Retries without budgets → storms |
| REST vs messaging | Sync request/response vs async events | REST for queries/commands needing an answer; messaging for decoupled workflows | "Microservices = REST calls everywhere" |
| Platform vs virtual threads | Expensive pooled vs cheap per-task | Virtual for blocking I/O; still bound downstream concurrency | "Virtual threads remove the need for backpressure" |

### 8. Failure Modes and Debugging

**Failure 1 — Retry storm.**

- SYMPTOM: Downstream recovers from a 30 s blip, then immediately falls over again; QPS 5× normal.
- CAUSE: Every layer retries 3× with no jitter (3 × 3 × 3 = 27× amplification); no retry budget.
- INVESTIGATE: Traces show nested retries; metrics show request rate vs unique request IDs.
- FIX: Retry at one layer only, with exponential backoff + full jitter, a retry budget and a circuit breaker.
- PREVENT: Chaos test (inject latency) in staging; dashboards for retry ratio.

**Failure 2 — Connection pool exhaustion after enabling virtual threads.**

- SYMPTOM: `SQLTransientConnectionException: Connection is not available, request timed out after 30000ms`; p99 30 s.
- CAUSE: Unbounded concurrency (no Tomcat thread cap anymore); 5,000 virtual threads waiting for 20 connections; slow query holds connections.
- INVESTIGATE: Hikari metrics (`hikaricp.connections.pending`, `.usage`), thread dump (`jcmd <pid> Thread.dump_to_file -format=json`), `pg_stat_activity`.
- FIX: Bulkhead before DB access, short `connectionTimeout` (fail fast → 503), fix slow query (index), statement timeout.
- PREVENT: Load test with dependency latency injection; alert on pending connections.

**Failure 3 — Hot partition.**

- SYMPTOM: One Kafka partition lagging hours; others idle.
- CAUSE: Key = `tenantId` and one tenant produces 60% of events.
- FIX: Key by `tenantId:orderId` when per-order ordering suffices; isolate the whale tenant's topic.
- PREVENT: Monitor per-partition lag and bytes-in.

**Failure 4 — Stale read after write.**

- SYMPTOM: User updates profile, refreshes, sees the old data; support tickets.
- CAUSE: Reads routed to an async replica with 2 s lag.
- FIX: Read-your-writes routing (primary for that user for N seconds, or LSN wait).

**Failure 5 — Double processing despite lock.**

- SYMPTOM: Invoice emailed twice.
- CAUSE: Redis lock TTL 10 s, job took 14 s (GC + slow SMTP); second worker acquired.
- FIX: Idempotent send (dedupe by invoice ID + state transition), fencing if lock retained.

**Failure 6 — Cache stampede.**

- SYMPTOM: DB CPU 100% every hour on the hour.
- CAUSE: All product keys share a 1-hour TTL set at startup.
- FIX: Jittered TTL, `@Cacheable(sync = true)`/request coalescing, stale-while-revalidate.

**Debugging toolkit.** Distributed traces (critical path, retries), RED metrics per endpoint/dependency, Hikari/Kafka/Redis metrics, `EXPLAIN (ANALYZE, BUFFERS)`, `pg_stat_statements`, JFR (`jcmd <pid> JFR.start duration=60s filename=rec.jfr`) for latency and allocation, thread dumps for blocked/pinned threads, `kafka-consumer-groups.sh --describe` for lag, `redis-cli --latency`, `INFO`, `SLOWLOG`.

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**1.1 Numbers.** A service has 99.95% availability and calls two dependencies with 99.9% each, serially. What's the composite? What if one dependency is called with a fallback that is itself 99.9% available?
*Hints:* Multiply for series; the fallback improves the effective availability of that leg.

**1.2 Little's Law.** 3,000 req/s, p50 latency 40 ms, DB used for 10 ms of each request. How many concurrent DB connections are needed on average? At p99, DB time is 200 ms. What happens with a 30-connection pool?

**1.3 Consistency picks.** For each data item, choose a consistency model and justify: account balance, product view count, shopping cart, user profile, chat message order, search index.

#### Level 2 — Implementation

**2.1 Sliding-window counter limiter.** Implement in Redis Lua with two keys (current, previous window). Test with a fixed clock argument.
*Hints:* weight = (window − elapsed) / window; count = prev × weight + curr.

**2.2 Cache-aside with stampede protection.** Implement `ProductService.get(id)` with Caffeine (local, 10 s) in front of Redis (5 min, jittered) in front of PostgreSQL. Concurrent misses for the same key must result in one DB call per instance.
*Hints:* Caffeine `AsyncLoadingCache`, or `@Cacheable(sync = true)`; test with 100 virtual threads and a counting repository.

**2.3 Outbox relay.** Implement a polling relay using `SELECT … FOR UPDATE SKIP LOCKED LIMIT 100` that publishes to Kafka and marks rows sent. Make multiple relay instances safe.

#### Level 3 — Integration

**3.1 Order placement end-to-end.** `POST /orders` with an idempotency key → order row + outbox in one tx → relay → `orders.created` → payment consumer (idempotent) → `payments.captured` → order consumer marks paid (dedupe + conditional update). Testcontainers PostgreSQL + Kafka. Kill the consumer mid-processing and verify no double effects.

**3.2 Graceful degradation.** Add a circuit breaker around the recommendations service with a cached fallback. Inject failures with WireMock and verify `/products/{id}` still returns 200 with an empty recommendations list.

#### Level 4 — Debugging / Production Scenario

**4.1 Diagnose this code.**

```java
@Scheduled(fixedRate = 60000)
public void sendReminders() {
    if (redis.opsForValue().setIfAbsent("reminder-lock", "1")) {
        for (User u : userRepo.findAll()) {
            emailClient.send(u.getEmail(), "Reminder");   // 30s timeout, no retry
        }
        redis.delete("reminder-lock");
    }
}
```

*Hints:* Lock without TTL? Crash leaves lock forever? `findAll` on millions? Duplicate emails if the job overlaps? Idempotency per user/day? Timeouts and throughput?

**4.2 Postmortem.** Write a blameless postmortem for "payment service double-charged 312 customers during a 4-minute DB failover". Include the timeline, root causes (retries + no idempotency key to the PSP), contributing factors, and action items.

### 10. Independent Implementation Project — System Design Portfolio + Three Labs

**Goal.** Produce seven one-to-two-page design docs (the systems in Section 12A) and implement three labs that prove the core mechanisms.

**Requirements.**

1. Seven design docs following the template: requirements (functional, non-functional with numbers) → API → data model → architecture diagram → scaling (estimates) → failures → security → observability → trade-offs (with at least one rejected alternative each).
2. Lab A: idempotent order API + outbox + idempotent consumers (Testcontainers PostgreSQL + Kafka).
3. Lab B: Redis token bucket + bulkhead + load shedding, with a k6 or Gatling test showing 429/503 behavior and stable p99 under overload.
4. Lab C: cache-aside with stampede protection and invalidation via Kafka events across two app instances.

**Technical requirements.** Java 25, Spring Boot 4.1 (virtual threads on), PostgreSQL 17, Redis 7/8, Kafka 4.x, Testcontainers, k6/Gatling, OpenTelemetry.

**Suggested structure.**

```
system-design/
├── docs/  01-url-shortener.md … 07-agentic-workflow-platform.md, template.md, numbers.md
└── labs/
    ├── lab-a-orders/      src/main/java/com/example/orders/{api,domain,outbox,consumers}/...
    ├── lab-b-ratelimit/   src/main/java/com/example/ratelimit/{filter,bucket,bulkhead}/... + load/k6.js
    └── lab-c-cache/       src/main/java/com/example/catalog/{cache,events}/... + compose.yaml
```

**Milestones.** (1) Template + URL shortener doc. (2) Lab A. (3) Notification + payment + order docs. (4) Lab B. (5) Search + chat docs. (6) Lab C. (7) Agentic workflow doc (reuse Parts XVI–XVII). (8) Mock interviews (Section 13).

**Testing requirements.** Lab A: duplicate POST, duplicate Kafka delivery, consumer crash mid-tx, and an out-of-order event test. Lab B: unit tests for the Lua script via Testcontainers Redis; load test report. Lab C: stampede test; cross-instance invalidation test.

**Definition of done.** Each doc fits the template and includes back-of-envelope numbers. Each lab has green tests and a README with a diagram and the failure scenarios demonstrated. You can present any design in 35 minutes.

**Optional extensions.** Resharding plan for the URL shortener (directory-based). Multi-region active-passive for payments with RPO/RTO analysis. CDC with Debezium replacing the polling relay.

### 11. Testing Strategy

- **Unit:** algorithms (rate limit math, consistent hashing ring, retry backoff calculation), state machines.
- **Integration with Testcontainers:** Lua scripts on real Redis; unique constraints, `SKIP LOCKED` and advisory locks on real PostgreSQL; Kafka redelivery and ordering.
- **Concurrency:** many virtual threads hitting the same idempotency key / same cache key / same lock; assert single effect.
- **Fault injection:** WireMock delays/faults; Toxiproxy (Testcontainers module) for network latency and partitions between app and Redis/PostgreSQL.
- **Load/performance:** k6/Gatling with SLO assertions (p95, error rate); overload tests verifying shedding instead of collapse.
- **Chaos (staging):** kill pods, fail over DB, restart Kafka brokers; verify SLOs and no duplicate effects.
- **Contract tests** for APIs and event schemas.

```java
package com.example.design.idempotency;

import org.junit.jupiter.api.Test;
import java.util.concurrent.Executors;
import java.util.stream.IntStream;
import static org.assertj.core.api.Assertions.assertThat;

class IdempotencyConcurrencyIT extends PostgresIT {   // base class with Testcontainers @ServiceConnection

    @Test
    void fiftyConcurrentRetriesCreateOneOrder() throws Exception {
        try (var pool = Executors.newVirtualThreadPerTaskExecutor()) {
            var futures = IntStream.range(0, 50).mapToObj(i -> pool.submit(() ->
                client.post("/orders", "{\"sku\":\"A1\",\"qty\":1}", "Idempotency-Key", "k-123"))).toList();
            var statuses = futures.stream().map(f -> {
                try { return f.get().status(); } catch (Exception e) { throw new RuntimeException(e); }
            }).toList();
            assertThat(statuses).allMatch(s -> s == 201 || s == 409);
        }
        assertThat(orderCount()).isEqualTo(1);
    }
}
```

### 12. Engineering Scenarios

#### 12A. Seven Worked Designs

Each design follows **requirements → API → data model → architecture → scaling → failures → security → observability → trade-offs**. Numbers are deliberately round: show the method, not false precision.

**Design 1 — URL Shortener**

- *Requirements.* Create short links (custom alias optional, expiry), redirect fast, basic click analytics. 100M new links/month (~40 writes/s avg, 400 peak), 10B redirects/month (~4k/s avg, 40k/s peak). Redirect p99 < 50 ms. 99.99% for redirects.
- *API.* `POST /api/links {url, alias?, expiresAt?}` → `201 {code, shortUrl}` (idempotency key). `GET /{code}` → `301/302 Location`. `GET /api/links/{code}/stats`.
- *Data model.* `link(code PK, long_url, owner_id, created_at, expires_at)`. Clicks go to an event stream → aggregated `link_daily_clicks(code, day, count)`.
- *Architecture.* Code generation via a **counter + base62** (pre-allocated ID ranges per instance from a DB sequence: no coordination per request, ~7 chars for 3.5T codes) or a random 7-char base62 with uniqueness check on insert. Redirect path: CDN/edge cache → service → Redis cache → PostgreSQL. Click events → Kafka → aggregator.
- *Scaling.* Read-heavy (100:1): cache hot codes (Zipfian distribution), CDN caching with short TTL for 302 (or 301 if analytics at edge aren't needed). Storage: 1.2B links/year × ~500 B ≈ 600 GB/year, so PostgreSQL with hash partitioning by code, later sharding by code prefix if needed.
- *Failures.* Redis down → fall back to DB (with bulkhead). Analytics pipeline down → redirects unaffected (async). Sequence range lost on crash → gaps, which are harmless.
- *Security.* Malicious URL scanning (Safe Browsing) on create, abuse rate limits per user/IP, no open redirect to `javascript:` schemes, enumeration resistance (random codes if links are private).
- *Observability.* Redirect latency SLO, cache hit ratio, 404 rate, create error rate.
- *Trade-offs.* 301 (cached by browsers → fewer hits, lost analytics) vs 302. Sequential codes (short, guessable) vs random (unguessable, needs collision check).

**Design 2 — Notification System**

- *Requirements.* Send email/SMS/push from many internal services; user preferences and quiet hours; templates; at-least-once delivery without user-visible duplicates; 50M notifications/day (~600/s avg, 10k/s peak for campaigns); transactional (OTP) p95 < 5 s, marketing best-effort.
- *API.* `POST /notifications {userId, type, templateId, data, idempotencyKey, priority}` → `202`. `GET /users/{id}/preferences`.
- *Data model.* `notification(id, user_id, type, channel, status, idem_key UNIQUE, created_at)`, `delivery_attempt(...)`, `user_preference(user_id, channel, type, enabled, quiet_hours)`.
- *Architecture.* API → validation + preference check → Kafka topics per priority (`notify.transactional`, `notify.bulk`) → channel workers (email via SES/SendGrid, SMS via Twilio, push via FCM/APNs) → provider webhooks for delivery status.
- *Scaling.* Separate topics/consumer groups so campaigns don't starve OTPs (bulkhead by priority). Respect provider rate limits with token buckets per provider. Partition by `userId` for per-user ordering and rate limits.
- *Failures.* Provider outage → retry with backoff, failover to a secondary provider for transactional. Duplicates → idempotency key end to end, provider-side idempotency where supported. Poison templates → DLQ.
- *Security.* PII minimization in payloads, signed provider webhooks, unsubscribe compliance (CAN-SPAM/GDPR), per-service auth to call the API.
- *Observability.* End-to-end latency per priority, delivery rate per provider, bounce/complaint rates, consumer lag.
- *Trade-offs.* Push vs pull for in-app; a single topic vs per-priority topics; storing full rendered content (audit) vs template + data (privacy).

**Design 3 — Payment Service**

- *Requirements.* Authorize/capture/refund via payment service providers (PSPs); exactly-once *effect* per payment intent; ledger correctness; 2k payments/s peak; 99.99% availability for auth; PCI DSS scope minimized.
- *API.* `POST /payment-intents {amount, currency, customerId, idempotencyKey}`; `POST /payment-intents/{id}/confirm`; `POST /payment-intents/{id}/refunds`. Webhooks from the PSP.
- *Data model.* `payment_intent(id, status, amount, currency, psp_ref, version)` state machine; **double-entry ledger** `ledger_entry(id, txn_id, account, debit, credit, created_at)` with the invariant Σdebits = Σcredits per txn (enforced in the same transaction); `idempotency_record`; `outbox`.
- *Architecture.* API → payment orchestrator (state machine) → PSP adapter (timeouts, idempotency keys to PSP) → ledger → outbox → events (`payment.captured`). Reconciliation job compares PSP settlement reports against the ledger daily.
- *Scaling.* Strongly consistent primary (sync replica or Aurora), partition by `payment_intent_id`. The ledger is append-only with periodic balance snapshots.
- *Failures.* PSP timeout = **unknown outcome**: never retry blindly with a new key; query the PSP by idempotency key or wait for the webhook, with the state `PENDING_UNKNOWN` until resolved. DB failover → idempotent retries. Webhook duplicates/out-of-order → dedupe + state machine.
- *Security.* Tokenization (card data never touches your servers; PSP-hosted fields), PCI scope reduction, mTLS to the PSP, HMAC-verified webhooks, least privilege, audit logs, fraud checks.
- *Observability.* Auth success rate per PSP/BIN/country, latency, unknown-outcome count, reconciliation mismatches (alert on any).
- *Trade-offs.* Sync capture vs async; single PSP vs routing across PSPs (resilience vs complexity); event sourcing the ledger vs state + entries.

**Design 4 — Order Platform (E-commerce)**

- *Requirements.* Cart → checkout → order → payment → inventory reservation → fulfilment; 5k orders/min peak (Black Friday 10×); no overselling of limited stock; order history.
- *API.* `POST /carts/{id}/checkout` (idempotent) → `201 {orderId, status: PENDING_PAYMENT}`; `GET /orders/{id}`; events `order.created`, `inventory.reserved`, `payment.captured`, `order.confirmed`, `order.cancelled`.
- *Data model.* `order(id, customer_id, status, total, version)`, `order_line`, `inventory(sku, available, reserved)` with `CHECK (available >= 0)`, `reservation(order_id, sku, qty, expires_at)`.
- *Architecture.* **Saga** (orchestrated by an order service state machine, or choreographed via events): create order → reserve inventory (conditional update `UPDATE inventory SET available = available - :q WHERE sku = :s AND available >= :q`) → payment → confirm; compensations: release reservation, refund. Outbox everywhere.
- *Scaling.* Hot SKUs (flash sales): a reservation token pool in Redis with DB reconciliation, or queue-based admission (virtual waiting room). Read side: CQRS projections for order history/search.
- *Failures.* Payment timeout → reservation TTL releases stock; duplicate events → idempotent consumers; compensation failures → retry + manual queue.
- *Security.* AuthZ that customers only see their orders (IDOR protection), price recomputed server-side (never trust client totals), anti-bot on checkout.
- *Observability.* Saga step durations, stuck sagas (orders in `PENDING_PAYMENT` > N min), oversell incidents (should be 0), conversion funnel.
- *Trade-offs.* Orchestration (visible, central logic) vs choreography (decoupled, harder to see); reserve-at-cart vs reserve-at-checkout.

**Design 5 — Document Search**

- *Requirements.* Full-text + semantic search over 50M documents for 5k tenants; per-document ACLs; p95 < 300 ms; index freshness < 1 min.
- *API.* `GET /search?q=…&filters=…&page=…`; `POST /documents` (ingest); `DELETE /documents/{id}`.
- *Data model.* Source of truth in PostgreSQL/S3. A search index (OpenSearch/Elasticsearch) with fields: tenant_id, acl_groups, title, body, updated_at; optional vector field (or pgvector for smaller corpora).
- *Architecture.* Ingest → outbox/CDC → indexer workers (parse, chunk, embed) → index. Query → auth (tenant, groups) → **filtered** query (BM25 + vector kNN, fused with reciprocal rank fusion) → rerank (optional cross-encoder) → highlight → results.
- *Scaling.* Index sharding by tenant (routing key) or by doc ID with tenant filter; replicas for read QPS; separate hot/warm tiers.
- *Failures.* Index lag → serve with "results may be up to N seconds stale"; rebuild from source of truth (index is derived); embedding service outage → degrade to keyword search.
- *Security.* **ACL filters inside the query**, never post-filtered; tenant isolation tests; delete propagation for GDPR (tombstones, reindex).
- *Observability.* Query latency, zero-result rate, click-through/MRR from logs, indexing lag.
- *Trade-offs.* OpenSearch vs PostgreSQL FTS + pgvector (operational simplicity vs scale/features); per-tenant index vs shared index.

**Design 6 — Chat Service**

- *Requirements.* 1:1 and group chat (≤ 500 members), online presence, delivery/read receipts, history, 10M DAU, 1M concurrent connections, message delivery p95 < 300 ms.
- *API.* WebSocket `/ws` (send, ack, typing); REST `GET /conversations/{id}/messages?before=…`.
- *Data model.* `message(conversation_id, seq, sender_id, body, created_at)` with PK `(conversation_id, seq)`, partitioned by conversation (Cassandra/ScyllaDB or sharded PostgreSQL); `conversation_member`; per-user inbox pointers (last read seq).
- *Architecture.* Gateway nodes hold WebSocket connections (connection registry in Redis: user → node). Send → chat service assigns a per-conversation sequence (single writer per conversation or DB sequence) → persist → fan-out via pub/sub (Redis or Kafka) to the gateway nodes holding members' connections → push. Offline members get push notifications (Design 2).
- *Scaling.* ~1M connections / ~50k per node ≈ 20+ gateway nodes; sticky routing by user; fan-out cost for big groups (fan-out on read for large groups, on write for small).
- *Failures.* Gateway crash → clients reconnect and resync from last seq (gap detection); duplicates → client-generated message IDs dedupe; ordering via per-conversation seq.
- *Security.* AuthN on WebSocket handshake (token), authZ per conversation on every send/read, rate limits, E2E encryption trade-offs (server can't search/moderate).
- *Observability.* Connection count, send→deliver latency, reconnect rate, fan-out lag.
- *Trade-offs.* Per-conversation ordering vs global; server-side search vs E2E encryption.

**Design 7 — Agentic Workflow Platform**

- *Requirements.* Host multiple agents (support, IT, finance) for 200 enterprise tenants; tools via internal APIs and MCP servers; RAG over tenant data; human approval for high-risk actions; full audit; per-tenant cost budgets; 500 concurrent runs/tenant peak; run p95 < 15 s (excluding human waits); zero cross-tenant leakage.
- *API.* `POST /agents/{agentId}/runs {input, idempotencyKey}` → `202 {runId}` + SSE stream `/runs/{runId}/events`; `GET /runs/{runId}`; `POST /approvals/{id}/decision`; admin APIs for tool registration, policies and budgets.
- *Data model.* `agent_definition(id, version, prompt_ref, tools, limits)`, `agent_run(id, tenant, user, status, checkpoint jsonb, tokens, cost, trace_ref)`, `tool_definition(name, schema, risk, scope)`, `action_proposal` / `approval_decision` / `audit_event` (Unit 35), `eval_result`, vector store (pgvector, partitioned by tenant).
- *Architecture.*

```
Client → Gateway (OIDC/JWT, tenant, rate limit, per-tenant token budget)
       → Run API → (agent_run row + outbox) ⇢ Kafka runs.requested (key = runId)
       ⇢ Agent Workers (virtual threads; bounded concurrency per tenant and per model provider)
            loop ≤ maxSteps / deadline / token budget:
              LLM Gateway (provider routing, retries, fallback, caching, cost metering)
              Retrieval service (tenant + ACL filtered, pgvector/OpenSearch)
              Tool Gateway (Unit 33 policy, Unit 34 validation, MCP clients, delegated credentials)
              Approval service (Unit 35) → checkpoint → pause
       ⇢ events → SSE to client; audit; OTel traces; online eval sampler
```

- *Scaling.* Workers scale on Kafka lag. The real bottleneck is **model provider rate limits (tokens/min)**: per-provider token-bucket limiters shared across workers, priority queues (interactive > batch), and fair queuing per tenant. Cache embeddings and deterministic retrievals. Use smaller models for routing/classification.
- *Failures.* Provider 429/5xx → retry with jitter within budget, then fallback model (evaluated in advance) or graceful degradation ("I can't complete this now; created ticket"). Tool timeouts → bounded retries only for idempotent tools. Worker crash → resume from checkpoint (steps are idempotent; tool executions keyed). Runaway loops → step/token/deadline limits. Approval timeouts → expiry and notification.
- *Security.* Units 33–35: delegated identity, per-tool scopes, tenant-filtered retrieval, injection containment, approvals, audit, secrets in a vault, MCP server allowlisting and sandboxing, egress controls.
- *Observability.* Unit 37: one trace per run, cost per tenant, stop reasons, policy denials, approval latency; Unit 36: eval gates per agent version, online sampled evals.
- *Trade-offs.* Agent vs deterministic workflow per use case (prefer workflows where steps are known); single platform vs per-team agents (governance vs autonomy); a framework (Spring AI) vs a direct SDK (portability vs control); synchronous chat vs async runs (UX vs resilience).

#### 12B. Decision Scenarios

**Scenario 1 — "We need 99.999%."** A stakeholder asks for five nines on an internal reporting service. *Reasoning:* Translate it: 26 seconds of downtime per month. That requires multi-region active-active, zero-downtime deploys and on-call staffing. Ask what the business impact of 1 hour of downtime is. Usually 99.9% with clear degradation is the right answer.

**Scenario 2 — Redis lock for payments (FDE).** A customer's team uses a Redis lock to prevent double charges. *Reasoning:* Explain lease expiry and pause scenarios. Replace with an idempotency key at the API and the PSP plus a state-machine conditional update. Demonstrate with a test that injects a pause.

**Scenario 3 — Microservices split.** A team wants to split a monolith into 12 services. *Reasoning:* What problem are they solving (deploy independence, scaling a hot path, team boundaries)? Consider a modular monolith (Spring Modulith) first. Splitting introduces partial failure, distributed transactions and network latency, so split along data-ownership boundaries where it pays.

### 13. Interview Preparation

**How to run a 30–45-minute system-design interview (your side).**

| Minutes | Phase | What you do |
|---|---|---|
| 0–5 | Requirements | Functional (top 3 features), non-functional with numbers (QPS, latency, availability, data size, consistency), explicit out-of-scope |
| 5–8 | Estimates | QPS, storage, bandwidth; read/write ratio; identify the hard part |
| 8–12 | API + data model | Endpoints/events, key entities, access patterns, keys/indexes |
| 12–22 | High-level architecture | Diagram; walk one request end-to-end; source of truth for each datum |
| 22–35 | Deep dives | The hard part(s): scaling, consistency, failure handling; propose, evaluate, choose |
| 35–42 | Failures, security, observability | What breaks, how you know, how you recover; authN/Z; SLOs |
| 42–45 | Trade-offs and evolution | What you'd change at 10× load; rejected alternatives |

**Defending choices:** state the requirement it serves, the alternative you rejected, and the cost you accept. "I chose Kafka over SQS because we need replay for the search indexer and three independent consumers; the cost is operational complexity, mitigated by using a managed service."

#### Quick Questions

**Q: What's the difference between availability and reliability?**
*Strong answer:* Availability = serving requests when asked; reliability = doing so correctly over time. Fast wrong answers are available but unreliable.

**Q: When does cache-aside break consistency?**
*Strong answer:* A race where a reader repopulates the cache with a stale DB value after a writer's invalidation; replicas lagging; TTL windows. Mitigate with delete-on-write, short or jittered TTLs, versioned values and not caching critical data.

**Q: Why are idempotency keys necessary even with exactly-once Kafka?**
*Strong answer:* Kafka's exactly-once covers Kafka read-process-write. External effects (DB writes outside the transaction, PSP calls, emails) still see retries.

#### Intermediate Questions

**Q: How do you choose a partition key?**
*Strong answer:* High cardinality, even load, aligned with the dominant access pattern and ordering requirement. Check for hot keys and plan for resharding. Example: `orderId` for order events (per-order ordering), not `tenantId` if tenant sizes vary wildly.

**Q: Explain backpressure in a Spring Boot service with virtual threads.**
*Strong answer:* Virtual threads remove the thread-pool bound, so you add explicit bounds: semaphores/bulkheads per dependency, pool sizes, short acquisition timeouts, load shedding with 503/429 + `Retry-After`, timeouts on all I/O, retry budgets, circuit breakers, and Kafka lag-based scaling for async work.

**Q: How would you implement a distributed rate limiter?**
*Strong answer:* Token bucket in Redis via an atomic Lua script keyed by tenant/API key (hash-tagged for Cluster), server time, TTL, a fail-open/closed decision per endpoint, 429 + `Retry-After`, edge limits for abuse, and metrics on rejections.

#### Advanced Questions

**Q: Is Redlock safe for mutual exclusion?**
*Strong answer:* Not as a correctness guarantee. Lease expiry plus process pauses or clock issues let two holders act. Use fencing tokens checked by the storage, or avoid locks with idempotent conditional updates and constraints. Redis locks are fine for efficiency.

**Q: Design a payment flow that survives a PSP timeout.**
*Strong answer:* Idempotency key per intent sent to the PSP, state `PENDING_UNKNOWN` on timeout, resolve by querying the PSP with the key or via webhook, never create a new charge with a new key, outbox events, reconciliation jobs, ledger invariants, and alerts on unresolved unknowns.

**Q: How does read-your-writes break with replicas, and how do you fix it?**
*Strong answer:* Async replica lag returns old data after a write. Fixes: route the user's reads to the primary for a window, LSN-based waits, session stickiness to the primary for critical flows, or a cache populated on write for that user.

#### Coding Questions

1. Implement a token bucket in Java (thread-safe, `System.nanoTime()`), then explain how to distribute it.
2. Implement consistent hashing with virtual nodes (`TreeMap<Long, Node>`, `ceilingEntry`) and measure key movement when adding a node.
3. Implement `retryWithBackoff(Supplier<T>, maxAttempts, base, cap)` with full jitter and only for retryable exceptions.

#### Scenario Questions

**Q: Black Friday is in 3 weeks; last year checkout fell over. What do you do?**
*Strong answer:* Get last year's data (QPS, failure point). Load test to find the bottleneck (often DB connections, hot SKU rows, payment provider limits). Add a virtual waiting room/admission control, idempotent checkout, inventory reservation with conditional updates, a cached catalog, and pre-scaled infra. Define SLOs and dashboards, prepare a runbook and game day, freeze risky changes.

### 14. Explain-It-at-Three-Levels

**Concept: Idempotency**

- *30 seconds:* Retries are unavoidable because you can't tell a lost request from a lost response, so every state-changing operation must be safe to repeat. I use idempotency keys at APIs, dedupe tables at consumers, conditional state transitions, and downstream idempotency keys.
- *2 minutes:* Show the idempotency-key table flow (claim, in-progress, completed with stored response, mismatched body → 422), consumer dedupe in the same transaction, and why Kafka exactly-once doesn't cover external effects.
- *Deep:* Cover crash windows (between the external call and recording), unknown outcomes and reconciliation, TTLs and storage, key scoping per tenant, and interaction with retries, circuit breakers and sagas.

**Concept: Backpressure**

- *30 seconds:* When a component is overloaded, it should push back (reject, shed or slow producers) instead of queuing forever. I bound concurrency per dependency, set timeouts everywhere, shed with 429/503, budget retries and use circuit breakers.
- *2 minutes:* Little's Law, virtual threads removing implicit limits, bulkheads, queue bounds, Kafka pull-based consumption and lag-based scaling.
- *Deep:* Concurrency-limit algorithms (adaptive limits based on latency), priority shedding, retry storm math, deadline propagation, and reactive demand signaling vs blocking with semaphores.

**Concept: Distributed locks**

- *30 seconds:* I avoid them when I can. Constraints, conditional updates and idempotency usually solve the problem. If I need one, I use fencing tokens checked by the storage, because leases can expire while a process is paused.
- *2 minutes:* Lease mechanics, the GC-pause scenario, fencing, advisory locks and `SKIP LOCKED`.
- *Deep:* Consensus-based lock services, Redlock's assumptions, clock issues, and why correctness must be enforced at the resource.

### 15. Knowledge Check

1. Compute the monthly downtime allowed by 99.95%.
2. Why can't liveness probes depend on the database?
3. What's the difference between partitioning and sharding?
4. Why does a fixed-window limiter allow bursts?
5. Why is "exactly-once delivery" misleading for side effects?
6. *Code reading:* In `RedisTokenBucket`, why is the key wrapped in `{…}`?
7. *Code reading:* In `IdempotencyService`, what happens if the same key arrives with a different body?
8. *Code reading:* In `PaymentCapturedListener`, why must the dedupe insert and `markPaid` be in one transaction?
9. *Debugging:* After enabling virtual threads, p99 latency jumps to 30 s with Hikari timeouts. Why?
10. *Debugging:* An hourly DB CPU spike aligns with cache TTLs. Fix?
11. *Design:* For a chat app, fan-out on write or on read for a 500-member group? Why?
12. *Design:* Orchestrated or choreographed saga for an order platform with 6 steps and frequent changes?

#### Knowledge Check Answers

1. 0.0005 × 30 × 24 × 60 ≈ 21.6 min/month (21.9 with 30.44 days).
2. A DB outage would fail liveness on every pod, triggering mass restarts that don't fix the DB and make recovery worse. Use readiness for dependency status.
3. Partitioning splits data within one system (for example PostgreSQL partitions on one instance). Sharding distributes partitions across independent instances.
4. Counters reset at boundaries, so a client can send the full quota at the end of one window and again at the start of the next.
5. Delivery guarantees apply within the messaging system. Any external effect can be repeated on redelivery or retry unless the effect is idempotent.
6. Redis Cluster hash tags: only the part inside braces is hashed, so related keys share a slot (required for multi-key scripts, and consistent placement per tenant).
7. Replay detects the hash mismatch and returns 422. The key was reused for a different operation.
8. So either both happen or neither. Otherwise a crash could record the message as processed without applying it (lost update), or apply it without recording it (duplicate on redelivery).
9. Tomcat's thread cap no longer limits concurrency, so thousands of virtual threads contend for 20 connections and wait up to `connectionTimeout`. Add a bulkhead, shorter timeouts and query fixes.
10. Jittered TTLs, request coalescing (`sync = true`), stale-while-revalidate or background refresh.
11. Usually fan-out on write for small groups (cheap reads, fast delivery). For 500 members it depends on write rate and online ratio: a hybrid (write to online members' gateways via pub/sub, read for offline from history) is common.
12. Orchestration: central visibility and easier changes and compensations for many steps. Choreography suits few, stable steps.

### 16. Common Interview Traps

- **"Virtual threads mean we don't need backpressure."** Downstream capacity is still finite.
- **"Kafka gives exactly-once, so no duplicates."** Not for external effects.
- **"A Redis lock prevents double processing."** Not without fencing or idempotency.
- **"Caching always helps."** Stale authZ, stampedes and invalidation bugs. Measure hit ratio and correctness.
- **"Microservices scale better."** Only the parts that need it; they add partial failure and distributed transactions.
- **"CAP means pick two."** The choice is only during partitions; otherwise it's latency vs consistency (PACELC).
- **"Just retry on failure."** Without idempotency, backoff, jitter and budgets, retries cause duplicates and storms.
- **"Shard from day one."** Most systems need indexes, caching and read replicas first.

### 17. Cheat Sheet

- **Availability:** 99.9% = 43.8 min/mo; 99.95% = 21.9; 99.99% = 4.4. Serial multiplies; redundancy `1 − Π(1 − a)` if independent.
- **Little's Law:** `L = λW`. Use it for pools, semaphores and queue sizes.
- **LB:** L4 vs L7; liveness ≠ readiness; graceful shutdown + preStop; no LB retries on non-idempotent requests.
- **Cache:** cache-aside + delete-on-write + jittered TTL + coalescing; tenant in keys; don't cache authZ long.
- **Queues:** at-least-once + idempotent consumers; DLQ; key = ordering unit; outbox for dual writes.
- **Replication:** async lag → read-your-writes fixes; failover → reconnect + idempotent retries.
- **Sharding:** key = high cardinality + access-aligned; consistent hashing; directory for whales; avoid cross-shard tx (sagas).
- **Rate limit:** token bucket in Redis Lua; hash tags; 429 + `Retry-After`; edge + service.
- **Locks:** prefer constraints/conditional updates; fencing tokens; advisory locks; `SKIP LOCKED`.
- **Idempotency:** key table (claim, in-progress, completed, 422 mismatch), dedupe tables, downstream keys, reconciliation for unknown outcomes.
- **Backpressure:** bulkheads, bounded queues, shedding, timeouts, retries with jitter + budgets, circuit breakers, lag-based autoscaling.
- **Interview flow:** requirements → estimates → API/data → architecture → deep dive → failures/security/observability → trade-offs.

### 18. Completion Checklist

- [ ] I can quantify availability and use Little's Law for sizing.
- [ ] I can explain and choose LB, caching, queue, replication, partitioning, sharding, CDN and rate-limiting strategies.
- [ ] I can implement idempotent APIs and consumers.
- [ ] I can implement a Redis token-bucket rate limiter and bulkheads with load shedding.
- [ ] I can explain why lease locks need fencing and choose safer alternatives.
- [ ] I can design the seven systems through all nine steps.
- [ ] I can run a 35–45-minute design interview and defend trade-offs.
- [ ] I can debug retry storms, pool exhaustion, hot partitions, stale reads and stampedes.

### 19. Further Research

**Essential**

- Martin Kleppmann, *Designing Data-Intensive Applications* (2nd ed. in progress; 1st ed. 2017). The foundation for replication, partitioning, transactions and consistency.
- Martin Kleppmann, "How to do distributed locking" — <https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html>. Fencing tokens and Redlock critique.
- Google SRE Book, chapters "Handling Overload" and "Addressing Cascading Failures" — <https://sre.google/sre-book/handling-overload/>. Load shedding and retry budgets.
- AWS Builders' Library, "Timeouts, retries, and backoff with jitter" and "Making retries safe with idempotent APIs" — <https://aws.amazon.com/builders-library/>. Production patterns from AWS.
- Spring Boot reference: virtual threads, graceful shutdown, health groups — <https://docs.spring.io/spring-boot/reference/>.

**Deeper Study**

- Alex Xu, *System Design Interview* vols. 1–2. Interview-shaped walkthroughs (compare with your own docs).
- Kafka documentation, design section — <https://kafka.apache.org/documentation/#design>. Delivery semantics, replication, KRaft.
- PostgreSQL documentation: high availability and replication — <https://www.postgresql.org/docs/current/high-availability.html>; explicit locking and advisory locks — <https://www.postgresql.org/docs/current/explicit-locking.html>.
- Marc Brooker's blog (AWS) — <https://brooker.co.za/blog/>. Retries, backoff, metastable failures.
- JEP 444 (Virtual Threads) — <https://openjdk.org/jeps/444>; JEP 491 (synchronized without pinning) — <https://openjdk.org/jeps/491>.

**Practice**

- System Design Primer — <https://github.com/donnemartin/system-design-primer>. Practice prompts and diagrams.
- k6 docs — <https://grafana.com/docs/k6/latest/>. Write overload tests with thresholds.
- Testcontainers Toxiproxy module — <https://java.testcontainers.org/modules/toxiproxy/>. Inject network faults in tests.

### Unit Completion Standard

Before moving on, you must be able to:

- **Explain** scalability, availability (with error budgets), reliability and consistency models; load balancing, caching, queues, replication, partitioning, sharding, CDN and rate limiting; distributed locks, idempotency and backpressure, all with concrete numbers and failure modes.
- **Implement** idempotent APIs and Kafka consumers, a Redis token-bucket limiter, bulkheads with load shedding, cache-aside with stampede protection, and an outbox relay in Spring Boot with virtual threads.
- **Test** these mechanisms with Testcontainers, concurrency tests, fault injection and load tests with SLO thresholds.
- **Debug** retry storms, pool exhaustion, hot partitions, stale reads, double processing and cache stampedes using metrics, traces, thread dumps and database tools.
- **Defend** in a 30–45-minute interview a complete design for any of the seven systems, from requirements to trade-offs, including what you rejected and why.
