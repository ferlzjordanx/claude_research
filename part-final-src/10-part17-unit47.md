# Part XVII — Architecture and System Design

**What this part teaches.** Part XVII moves from "I can build an endpoint" to "I can design a system that a business can depend on." Unit 47 covers classical distributed-system design through the lens of Python and FastAPI: how to scale a Python service whose runtime has a GIL and a single-threaded event loop, where to put caches, queues and databases, how to stay correct under partial failure, and how to make the system observable. Unit 48 applies the same discipline to agentic AI systems, where a probabilistic component (the model) sits inside an otherwise deterministic architecture.

**Why it matters.** Most production incidents are not caused by bad syntax. They are caused by unbounded queues, missing timeouts, retries without idempotency, caches that serve stale authorization decisions, hot partitions, and agents that were given more authority than the business intended. Senior interviews — and senior jobs — are about anticipating those failures.

**Where it appears.** Every non-trivial backend: payment flows, notification fan-out, search, chat, e-commerce, and internal AI assistants. Forward Deployed Engineers (FDEs) do this live in front of customers: they elicit requirements, sketch an architecture on a whiteboard, and defend trade-offs.

**Connections.** This part depends on earlier curriculum units on Python concurrency (threads, processes, asyncio), FastAPI internals, PostgreSQL/SQLAlchemy, Redis, Celery/Kafka, Docker/AWS, OpenTelemetry, LLM APIs, RAG and agents. It feeds directly into Part XVIII (interviews) and Part XIX (the capstone, where you build what you design here).

## Unit 47 — Python/FastAPI System Design

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Define and quantify** scalability, reliability, availability and consistency, and convert an availability target (e.g. 99.9%) into an error budget in minutes per month.
2. **Estimate** load (QPS, peak factor, storage growth, bandwidth) from business requirements using back-of-the-envelope arithmetic, and size a FastAPI deployment (workers, pods, DB connections) from those numbers.
3. **Compare** L4 vs L7 load balancing, and explain how health checks, connection draining and graceful shutdown interact with Uvicorn/Gunicorn workers.
4. **Design** a caching layer (cache-aside, read-through, write-through, write-behind), choose TTL and invalidation strategies, and prevent cache stampedes.
5. **Implement** backpressure in a FastAPI service using bounded concurrency (semaphores, bounded queues, connection-pool limits) and load shedding (HTTP 429/503 with `Retry-After`).
6. **Explain** database replication (synchronous/asynchronous, read replicas, replication lag) and partitioning (PostgreSQL declarative partitioning vs application-level sharding), and choose a partition key.
7. **Implement** a token-bucket or sliding-window rate limiter on Redis with atomic Lua scripts, and justify where rate limiting belongs (gateway vs application).
8. **Evaluate** distributed locks: explain why a lock without a fencing token is unsafe, and prefer database constraints, advisory locks or idempotency keys where possible.
9. **Design** async architectures: request/response vs queue-based processing, the transactional outbox, at-least-once delivery with idempotent consumers, and worker autoscaling on queue lag.
10. **Identify** failure domains (process, pod, node, AZ, region, dependency) and design bulkheads, timeouts, retries with jitter and circuit breakers.
11. **Instrument** a FastAPI service with OpenTelemetry traces, RED/USE metrics and structured logs, and define SLIs/SLOs.
12. **Design** six systems end-to-end — URL shortener, notification system, document search, chat service, order platform and AI knowledge service — following *requirements → API → data → architecture → scale → failures → security → observability → trade-offs*.

### 2. Prerequisite Knowledge

You should already be comfortable with the following. Short refreshers are included where the unit depends heavily on the detail.

- **Python concurrency.** Threads share memory and (in the default CPython build) contend for the GIL; processes do not share memory; `asyncio` runs many coroutines cooperatively on one thread. CPU-bound work blocks the event loop. **[Version-dependent]** Python 3.13 shipped an experimental free-threaded build; PEP 779 made it *officially supported but optional* in 3.14. Most production FastAPI deployments still use the default GIL build plus multiple worker processes.
- **FastAPI basics.** `async def` endpoints run on the event loop; plain `def` endpoints and sync dependencies run in AnyIO's worker thread pool (default capacity limiter of 40 tokens). Dependencies with `yield` provide setup/teardown. `lifespan` creates shared resources (DB engines, HTTP clients, Redis pools).
- **HTTP semantics.** Idempotent methods (GET, PUT, DELETE) vs non-idempotent (POST); status codes 429, 502, 503, 504; headers `Retry-After`, `Cache-Control`, `ETag`, `Idempotency-Key` (an IETF draft convention widely used by payment APIs).
- **PostgreSQL.** Transactions, isolation levels (READ COMMITTED default; REPEATABLE READ; SERIALIZABLE), B-tree indexes, `EXPLAIN (ANALYZE, BUFFERS)`, MVCC, connection cost (one backend process per connection).
- **Redis.** Single-threaded command execution (per shard), atomic commands, TTLs, Lua scripts/functions, pub/sub vs streams.
- **Messaging.** Kafka topics/partitions/consumer groups/offsets; Celery/RQ/arq task queues on Redis or RabbitMQ.

**Refresher: Little's Law.** For any stable system, `L = λ × W` — the average number of in-flight requests (L) equals arrival rate (λ) times average time in system (W). If an endpoint receives 500 req/s and each takes 200 ms, there are on average 100 requests in flight. If the DB slows to 2 s, in-flight requests jump to 1,000 — and if your pool only has 20 connections, 980 are queued somewhere. Little's Law is the single most useful tool for reasoning about capacity and backpressure.

**Refresher: percentiles.** Report latency as p50/p95/p99, never just the mean. With fan-out, tail latency compounds: if a request calls 10 backends each with a 1% chance of being slow, ~10% of requests are slow (1 − 0.99¹⁰ ≈ 0.096).

### 3. Mental Model

Think of a system as **a network of queues connected by pipes of limited width**. Every component — load balancer, Uvicorn worker, event loop, thread pool, DB pool, Postgres, Kafka partition — has a capacity and a queue in front of it. Design is deciding:

1. **Where work waits** (and how much is allowed to wait),
2. **What happens when a queue is full** (reject, shed, degrade, buffer durably),
3. **What the source of truth is** for every piece of data,
4. **What happens when any single box disappears**.

```
                 Clients
                    │
             [CDN / Edge cache]          ← static + cacheable GETs
                    │
         [API Gateway / L7 LB]           ← TLS, authN, rate limit, routing
                    │
     ┌──────────────┼──────────────┐
 [FastAPI pod] [FastAPI pod] [FastAPI pod]   ← stateless, horizontally scaled
     │   │            │
     │   └──→ (Redis) cache / rate-limit / locks
     │
     ├──→ (PostgreSQL primary) ──async replication──→ (read replicas)
     │
     └──⇢ [Outbox → Kafka / queue] ⇢ [Workers (autoscaled on lag)]
                                         │
                                         └──→ {3rd-party APIs, LLMs, email}
   Observability plane: traces + metrics + logs from every box → collector → backends
```

Three rules make this model work:

- **Stateless compute, stateful storage.** API pods hold no user state, so any pod can serve any request and pods can be killed freely. State lives in Postgres, Redis, object storage or Kafka — each with explicit durability guarantees.
- **Synchronous path does the minimum.** The request path validates, authorizes, writes the source of truth, and returns. Anything slow, flaky or fan-out goes asynchronous behind a durable queue.
- **Every queue is bounded, every call has a timeout.** Unbounded anything eventually means out-of-memory or cascading failure.

### 4. Comprehensive Theory

#### 4.1 Scalability, Reliability, Availability and Consistency

**Definitions.**

| Property | Definition | Typical measure |
|---|---|---|
| Scalability | Ability to handle increased load by adding resources, with cost growing roughly linearly | Throughput per pod; cost per 1k requests; max sustainable QPS |
| Reliability | System performs correctly (right answer) over time, including under faults | Error rate; data-loss incidents; correctness SLIs |
| Availability | Fraction of time (or requests) the system serves successfully | `successful requests / valid requests` over a window |
| Consistency | Guarantees about what reads observe relative to writes | Linearizable, sequential, causal, read-your-writes, eventual |
| Durability | Acknowledged writes are not lost | RPO (recovery point objective) |

**Why they exist as separate concepts.** They trade against each other. A system can be highly available but serve stale data (cache during DB outage); highly consistent but unavailable during a partition (refuses writes without quorum); scalable but unreliable (sharded with no rebalancing plan).

**Availability arithmetic.**

| SLO | Downtime / 30 days | Downtime / year |
|---|---|---|
| 99% | 7.2 h | 3.65 days |
| 99.9% | 43.2 min | 8.76 h |
| 99.95% | 21.6 min | 4.38 h |
| 99.99% | 4.32 min | 52.6 min |

Serial dependencies multiply: an API at 99.95% that synchronously depends on a DB at 99.95% and an auth service at 99.9% has an upper bound of ≈ 0.9995 × 0.9995 × 0.999 ≈ 99.8%. Redundancy (parallel replicas) improves it: two independent replicas at 99% give 1 − 0.01² = 99.99% *if failures are independent* — which they often are not (same AZ, same bad deploy, same config). This is why **failure domains** matter (§4.6).

**Error budgets** (from Google's SRE practice). A 99.9% SLO means 0.1% of requests may fail; that budget is spent on deploys, experiments and incidents. When the budget is exhausted, you slow feature releases and invest in reliability.

**Scaling dimensions.**

- **Vertical:** bigger machine. Simple, finite, single failure domain.
- **Horizontal:** more stateless replicas behind a load balancer. Requires externalized state.
- **Functional decomposition:** separate services or worker pools per workload (e.g. search indexing workers vs API).
- **Data partitioning:** split data by key so each partition handles a slice of load.

**Scaling a Python/FastAPI service specifically.**

```
1 machine
 └── N Uvicorn worker processes   (≈ 1 per vCPU for CPU-light I/O-bound APIs)
      └── 1 event loop per process
           ├── thousands of concurrent coroutines (I/O-bound async work)
           └── AnyIO thread pool (default 40 tokens) for sync endpoints/deps
```

- In Kubernetes, the common pattern is **one Uvicorn process per container**, scaled by replicas, letting the orchestrator handle restarts and placement. On VMs, `uvicorn --workers N` or Gunicorn with `uvicorn.workers.UvicornWorker` **[Legacy but still encountered]** — Uvicorn's own `--workers` supervisor is now adequate for most cases, and the `uvicorn-worker` package hosts the Gunicorn worker class.
- **CPU-bound** work (PDF parsing, embeddings on CPU, image processing) does not belong on the event loop. Offload to a process pool, a separate worker service, or a GPU inference service.
- **Connection math:** `pods × workers_per_pod × pool_size (+ max_overflow)` must stay below Postgres `max_connections` minus headroom. Twenty pods × 4 workers × 10 connections = 800 connections — too many for most Postgres instances. Use **PgBouncer** (transaction pooling) or RDS Proxy, and smaller per-process pools.

**Consistency models (from strongest to weakest).**

| Model | Guarantee | Example |
|---|---|---|
| Linearizable | Every read sees the latest committed write; operations appear instantaneous in real-time order | Single Postgres primary; etcd; ZooKeeper |
| Sequential | All nodes see operations in the same order, not necessarily real-time | — |
| Causal | Causally related operations seen in order by all | Comments after the post they reply to |
| Read-your-writes | A client always sees its own writes | Route a user's reads to primary for N seconds after a write |
| Monotonic reads | A client never sees time go backwards | Pin a session to one replica |
| Eventual | Replicas converge if writes stop | DNS, async read replicas, caches, search indexes |

**CAP and PACELC.** CAP: during a network **P**artition, a system must choose between **C**onsistency (refuse some operations) and **A**vailability (serve possibly stale/conflicting data). PACELC extends it: **E**lse (no partition), choose between **L**atency and **C**onsistency. A single-primary Postgres with synchronous replication is PC/EC; DynamoDB with eventually consistent reads is PA/EL by default. In interviews, use CAP to reason about *specific operations*, not whole systems: "Placing an order must be consistent (no overselling); showing the product catalog can be eventually consistent."

**Common mistakes.** Treating availability as "the server is up" instead of "requests succeed"; promising 99.99% on top of a single-AZ database; assuming "eventual consistency" means "consistent within a second"; quoting CAP as "pick two of three" (partitions are not optional).

**Interview perspective.** Interviewers test whether you can turn adjectives into numbers ("highly available" → "99.95% monthly on the write path, 99.9% on search") and whether you assign consistency per operation rather than per system.

#### 4.2 Load Balancing

**Definition.** Distributing requests across a pool of backends to increase capacity and tolerate backend failure.

**How it works.**

- **L4 (transport)** load balancers (AWS NLB) route TCP/UDP connections by IP/port. Very fast, protocol-agnostic, but cannot see HTTP paths or headers. One long-lived connection (WebSocket, HTTP/2, gRPC) always goes to the same backend — which can cause imbalance.
- **L7 (application)** load balancers (AWS ALB, Envoy, NGINX, Traefik) terminate HTTP, route by host/path/header, retry, rewrite, and do per-request balancing even over HTTP/2.

**Algorithms.** Round robin; weighted round robin; least connections / least outstanding requests (better for variable latency); consistent hashing (sticky by key — useful for cache affinity or WebSocket routing); "power of two choices" (pick two random backends, send to the less loaded — near-optimal and cheap; used by Envoy).

**Health checks.** *Liveness* answers "should this process be restarted?" — it must not depend on downstream services, or a DB blip restarts your entire fleet. *Readiness* answers "should this instance receive traffic now?" — it may check that the DB pool can acquire a connection and that warm-up is done.

**Graceful shutdown.** On SIGTERM, Kubernetes removes the pod from Service endpoints *asynchronously* while sending the signal. Uvicorn stops accepting connections and waits for in-flight requests (bounded by `--timeout-graceful-shutdown`), then runs lifespan shutdown. A short `preStop` sleep (5–10 s) avoids routing requests to a pod that has already stopped listening.

```python
# app/main.py — readiness vs liveness, lifespan-managed resources
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine: AsyncEngine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,      # per process
        max_overflow=settings.db_max_overflow,
        pool_timeout=2.0,                     # fail fast instead of queueing forever
        pool_pre_ping=True,
    )
    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=1.0))
    app.state.engine = engine
    app.state.http = http
    app.state.ready = True
    try:
        yield
    finally:
        app.state.ready = False               # readiness flips before resources close
        await http.aclose()
        await engine.dispose()


app = FastAPI(lifespan=lifespan)


@app.get("/livez", include_in_schema=False)
async def livez() -> dict[str, str]:
    return {"status": "ok"}                   # no downstream checks


@app.get("/readyz", include_in_schema=False)
async def readyz(response: Response) -> dict[str, str]:
    if not getattr(app.state, "ready", False):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "starting_or_stopping"}
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "db_unavailable"}
    return {"status": "ready"}
```

**Trade-offs.** L7 gives routing and observability but adds latency and a component to operate. Sticky sessions simplify stateful protocols but defeat even distribution and complicate deploys. Readiness checks that probe downstreams can *amplify* outages: if Postgres hiccups, every pod goes unready and the LB has nothing to route to — consider failing readiness only after sustained failure, or serving degraded responses instead.

**Interview perspective.** Know the difference between liveness and readiness, why WebSockets need special handling (connection-level balancing, draining), and how graceful shutdown prevents 502s during deploys.

#### 4.3 Caching

**Definition.** Storing the result of an expensive operation closer to the consumer so repeated requests are cheaper.

**Where caches live.** Browser (`Cache-Control`) → CDN → API gateway → in-process (LRU dict per worker) → distributed (Redis/Valkey/Memcached) → database buffer cache → OS page cache.

**Patterns.**

| Pattern | Read path | Write path | Use when |
|---|---|---|---|
| Cache-aside (lazy) | App reads cache; on miss reads DB and populates | App writes DB then **deletes** cache key | Default choice; read-heavy |
| Read-through | Cache library loads from DB on miss | — | Same as above with a loader abstraction |
| Write-through | Reads from cache | Write cache and DB synchronously | Read-after-write hot data |
| Write-behind | Reads from cache | Write cache; flush to DB async | Counters, analytics; risk of loss |
| Refresh-ahead | Refresh before TTL expiry | — | Predictable hot keys |

**Invalidation.** "Delete on write" is safer than "update on write" because two concurrent writers updating the cache can leave it with the older value. Even delete-on-write has a race (reader misses, reads old value from a lagging replica, writes it to cache after the writer deleted). Mitigations: short TTLs as a safety net, versioned keys (`product:42:v17`), reading from primary for cache fills, or change-data-capture (CDC) driven invalidation.

**Stampede (thundering herd).** A hot key expires; 5,000 requests miss simultaneously and hammer the DB. Mitigations:

1. **Request coalescing / single-flight** — only one in-process task loads; others await the same future.
2. **Distributed mutex on miss** — `SET lock:key token NX PX 3000`; losers briefly wait or serve stale.
3. **Stale-while-revalidate** — store `soft_expiry` inside the value; serve stale while one worker refreshes.
4. **TTL jitter** — `ttl = base * random.uniform(0.9, 1.1)` to avoid synchronized expiry.
5. **Probabilistic early expiration** (XFetch).

```python
# app/infra/cache.py — cache-aside with single-flight and jittered TTL
import asyncio
import json
import random
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis


class Cache:
    def __init__(self, redis: Redis, default_ttl_s: int = 300) -> None:
        self._redis = redis
        self._ttl = default_ttl_s
        self._inflight: dict[str, asyncio.Future[Any]] = {}

    async def get_or_load(
        self, key: str, loader: Callable[[], Awaitable[Any]], ttl_s: int | None = None
    ) -> Any:
        try:
            raw = await self._redis.get(key)
        except Exception:
            raw = None                       # cache is an optimization: degrade to DB
        if raw is not None:
            return json.loads(raw)

        if key in self._inflight:            # single-flight within this process
            return await self._inflight[key]

        fut: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._inflight[key] = fut
        try:
            value = await loader()
            ttl = int((ttl_s or self._ttl) * random.uniform(0.9, 1.1))
            try:
                await self._redis.set(key, json.dumps(value), ex=ttl)
            except Exception:
                pass
            fut.set_result(value)
            return value
        except BaseException as exc:
            fut.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)

    async def invalidate(self, key: str) -> None:
        await self._redis.delete(key)
```

**Design considerations.** Cache **what is expensive and read often** — measure hit rate. Never cache authorization decisions longer than you can tolerate a revoked user retaining access. Include the tenant/user in keys for personalized data (`tenant:{t}:doc:{id}`) or you will leak data across tenants. Size Redis memory and set an eviction policy (`allkeys-lru` for pure caches; `noeviction` for queues/locks — and never mix those uses on one instance without thought).

**Trade-offs.** Caches add a consistency problem and a new dependency. They hide slow queries until the cache is cold (after a deploy, a flush or a failover), when the DB is suddenly hit with full load. Always load-test with a cold cache.

**Interview perspective.** Interviewers want: which pattern, what TTL, how you invalidate, what happens on cache failure (degrade, not crash), and stampede protection.

#### 4.4 Queues and Backpressure

**Definition.** A **queue** decouples producers from consumers in time. **Backpressure** is the mechanism by which an overloaded consumer signals producers to slow down, instead of silently accumulating unbounded work.

**Why it exists.** Producers and consumers have different and variable rates. Without backpressure, a temporary slowdown becomes memory growth, then latency growth (requests waiting in invisible queues), then timeouts, then retries — which add *more* load (a **retry storm**). This is how a 30-second DB hiccup becomes a 30-minute outage (a **metastable failure**).

**Where hidden queues live in a FastAPI service.**

```
Client retries ─→ LB queue ─→ kernel accept backlog (--backlog, default 2048)
  ─→ Uvicorn concurrency (--limit-concurrency, default unlimited)
  ─→ event loop ready queue (all coroutines)
  ─→ AnyIO thread pool queue (sync endpoints; 40 tokens)
  ─→ SQLAlchemy pool wait (pool_timeout, default 30 s!)
  ─→ Postgres connection / lock waits
```

**Backpressure strategies.**

1. **Bounded concurrency** — `asyncio.Semaphore`, `--limit-concurrency` (Uvicorn returns 503 when exceeded), pool size limits.
2. **Fail fast** — short `pool_timeout`, request deadlines; better a quick 503 than a slow 504.
3. **Load shedding** — reject low-priority work first (e.g. analytics before checkout) with 429/503 and `Retry-After`.
4. **Bounded buffers** — `asyncio.Queue(maxsize=N)`; producers `await put()` (block) or `put_nowait()` and handle `QueueFull` (shed).
5. **Durable queues** — Kafka/SQS/RabbitMQ absorb bursts on disk; consumers pull at their own rate (pull-based consumption is natural backpressure).
6. **Client-side** — exponential backoff with full jitter, retry budgets (e.g. retries ≤ 10% of requests), circuit breakers.
7. **Adaptive concurrency** — TCP-like AIMD limits based on observed latency (Netflix concurrency-limits idea).

```python
# app/core/backpressure.py — bounded concurrency + load shedding for an expensive route
import asyncio
from collections.abc import AsyncIterator

from fastapi import Depends, HTTPException, status


class ConcurrencyLimiter:
    """Admit at most `limit` concurrent operations; wait at most `max_wait_s` for a slot."""

    def __init__(self, limit: int, max_wait_s: float) -> None:
        self._sem = asyncio.Semaphore(limit)
        self._max_wait = max_wait_s

    async def __call__(self) -> AsyncIterator[None]:
        try:
            await asyncio.wait_for(self._sem.acquire(), timeout=self._max_wait)
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server busy, retry later",
                headers={"Retry-After": "2"},
            )
        try:
            yield
        finally:
            self._sem.release()


search_limiter = ConcurrencyLimiter(limit=32, max_wait_s=0.25)

# usage: @router.get("/search", dependencies=[Depends(search_limiter)])
```

Note: the semaphore is **per process**. With 4 workers × 10 pods the effective global limit is 32 × 40 = 1,280. For a global limit, use a Redis-based limiter or size per-process limits from the downstream capacity divided by process count.

**Queue semantics you must state explicitly.**

| Semantic | Meaning | Reality |
|---|---|---|
| At-most-once | Ack before processing; may lose messages | Fire-and-forget metrics |
| At-least-once | Ack after processing; may duplicate | Default for Kafka/SQS/Celery with late ack |
| Exactly-once | Effect happens once | Achieved as *at-least-once delivery + idempotent processing*, or within a closed system (Kafka transactions read-process-write within Kafka) |

**Ordering.** Kafka guarantees order *within a partition*; choose the message key (e.g. `order_id`) so related events share a partition. SQS standard queues are unordered; FIFO queues order per message group. Celery offers no ordering guarantee across workers. Retries and DLQs (dead-letter queues) break ordering — design consumers to tolerate it (version numbers, idempotent upserts with `WHERE version < :new_version`).

**Interview perspective.** "What happens when the consumer is slower than the producer?" is the backpressure question. A strong answer names where the backlog accumulates, how it is bounded, how lag is measured and alerted on, and how consumers autoscale.

#### 4.5 Database Replication and Partitioning

**Replication — definition.** Keeping copies of data on multiple nodes for availability (failover), read scaling and geographic locality.

**How PostgreSQL replication works.** The primary writes changes to the **write-ahead log (WAL)**. Standbys stream WAL and replay it (**physical streaming replication**). With `synchronous_commit = on` plus `synchronous_standby_names`, the primary waits for a standby to confirm before acknowledging commit (no data loss on failover, higher latency). With asynchronous replication, commits return immediately; standbys lag by milliseconds to seconds (possible loss of the last transactions on failover; replicas serve stale reads). **Logical replication** publishes row changes per table — useful for CDC (Debezium), migrations and selective replication.

**Replication lag consequences.** User updates profile → redirect → read from replica → sees old profile. Fixes: read-your-writes routing (primary for that user for a few seconds after a write, or until the replica's replay LSN passes the write's commit LSN), or simply read from primary for user-critical paths.

```python
# Read/write routing with SQLAlchemy 2.x: explicit, boring, testable
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

primary = create_async_engine(settings.primary_url, pool_size=5)
replica = create_async_engine(settings.replica_url, pool_size=10)

WriteSession = async_sessionmaker(primary, expire_on_commit=False)
ReadSession = async_sessionmaker(replica, expire_on_commit=False)


async def get_write_session() -> AsyncIterator[AsyncSession]:
    async with WriteSession() as session:
        yield session


async def get_read_session() -> AsyncIterator[AsyncSession]:
    async with ReadSession() as session:
        yield session
```

Endpoints choose explicitly: dashboards use `get_read_session`; checkout and "just after a write" reads use `get_write_session`. Implicit magic routing ("all SELECTs go to replicas") eventually breaks read-your-writes.

**Failover.** Managed services (RDS Multi-AZ, Aurora, Cloud SQL HA) promote a standby and move a DNS name. Applications see dropped connections for 30–120 s (Aurora often faster). Your app must: retry connection establishment with backoff, use `pool_pre_ping`, keep DNS TTL short, and treat in-flight transactions as failed (retry only if idempotent).

**Partitioning — definition.** Splitting one logical dataset into parts by key.

- **PostgreSQL declarative partitioning** (single server): `PARTITION BY RANGE (created_at)`, `LIST (region)`, or `HASH (tenant_id)`. Benefits: partition pruning, cheap retention (`DROP`/`DETACH PARTITION` instead of huge `DELETE`), smaller indexes. It does **not** add write capacity beyond one machine.
- **Sharding** (multiple servers): application or middleware (Citus, Vitess for MySQL) routes by shard key. Adds capacity but loses cross-shard joins/transactions and complicates rebalancing.

```sql
-- Time-partitioned events table with retention by partition
CREATE TABLE events (
    id          bigint GENERATED ALWAYS AS IDENTITY,
    tenant_id   uuid        NOT NULL,
    created_at  timestamptz NOT NULL,
    kind        text        NOT NULL,
    payload     jsonb       NOT NULL,
    PRIMARY KEY (id, created_at)         -- partition key must be part of PK/unique constraints
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_10 PARTITION OF events
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE INDEX ON events_2026_10 (tenant_id, created_at DESC);

-- Retention: instant, no bloat, no long-running DELETE
ALTER TABLE events DETACH PARTITION events_2025_10 CONCURRENTLY;
DROP TABLE events_2025_10;
```

**Choosing a partition key.** High cardinality, evenly distributed, present in most queries, and aligned with transaction boundaries. `tenant_id` is good for B2B SaaS (keeps a tenant's data together) but beware "whale" tenants causing **hot partitions**. `created_at` is great for retention but makes the newest partition hot for writes. Hash partitioning spreads load but kills range scans.

**Consistent hashing.** Maps keys and nodes onto a ring so adding a node moves only ~1/N of keys (vs nearly all keys with `hash(key) % N`). Virtual nodes smooth the distribution. Used by caches, Cassandra/Dynamo-style stores, and sticky routing.

**Interview perspective.** Interviewers check that you scale reads before sharding writes, that you know replication lag breaks read-your-writes, and that you can pick a shard key and name its hot-spot risk. "We'll shard Postgres" in the first five minutes is a red flag; "a single primary with replicas handles our 2k writes/s; we'll partition the events table by month for retention" is a green flag.

#### 4.6 API Gateways, Rate Limiting and Distributed Locks

**API gateway — definition.** A reverse proxy at the edge that centralizes cross-cutting concerns: TLS termination, routing, authentication (JWT validation, API keys), coarse rate limiting, request size limits, CORS, request IDs, WAF integration and API versioning. Examples: AWS API Gateway, Kong, Envoy Gateway, Apigee, NGINX.

**Design rule.** The gateway enforces **coarse, identity-agnostic or identity-light** policies (per API key quotas, IP throttling, payload size). The application enforces **business authorization** (can user U modify order O?) — the gateway does not know your domain. Do not put business logic in gateway plugins.

**Rate limiting — algorithms.**

| Algorithm | How it works | Pros | Cons |
|---|---|---|---|
| Fixed window | Count per key per minute bucket | Simple, cheap | Bursts of 2× at window boundary |
| Sliding window log | Store timestamp of each request (sorted set) | Exact | Memory O(requests) |
| Sliding window counter | Weighted current + previous window | Good approximation, cheap | Approximate |
| Token bucket | Tokens refill at rate r up to capacity b; request takes a token | Allows controlled bursts; standard | Needs atomic read-modify-write |
| Leaky bucket | Queue drained at constant rate | Smooth output | Adds latency |
| Concurrency limit | Max in-flight per key | Protects slow endpoints | Different from rate |

**Atomic token bucket in Redis.** Read-modify-write must be atomic across pods — use a Lua script (Redis executes it without interleaving).

```python
# app/infra/rate_limit.py
import time

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

TOKEN_BUCKET_LUA = """
local key       = KEYS[1]
local capacity  = tonumber(ARGV[1])
local refill    = tonumber(ARGV[2])   -- tokens per second
local now_ms    = tonumber(ARGV[3])
local cost      = tonumber(ARGV[4])

local state = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(state[1]) or capacity
local ts     = tonumber(state[2]) or now_ms

local elapsed = math.max(0, now_ms - ts) / 1000.0
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
local retry_after_ms = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
else
  retry_after_ms = math.ceil((cost - tokens) / refill * 1000)
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now_ms)
redis.call('PEXPIRE', key, math.ceil(capacity / refill * 1000) + 1000)
return {allowed, retry_after_ms}
"""


class TokenBucketLimiter:
    def __init__(self, redis: Redis, capacity: int, refill_per_s: float) -> None:
        self._redis = redis
        self._capacity = capacity
        self._refill = refill_per_s
        self._script = redis.register_script(TOKEN_BUCKET_LUA)

    async def check(self, key: str, cost: int = 1) -> tuple[bool, int]:
        now_ms = int(time.time() * 1000)
        allowed, retry_ms = await self._script(
            keys=[f"rl:{key}"], args=[self._capacity, self._refill, now_ms, cost]
        )
        return bool(allowed), int(retry_ms)


async def enforce_rate_limit(request: Request) -> None:
    limiter: TokenBucketLimiter = request.app.state.limiter
    principal = getattr(request.state, "principal_id", None) or request.client.host
    try:
        allowed, retry_ms = await limiter.check(principal)
    except Exception:
        return                                     # fail-open: Redis outage must not take down the API
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(1, retry_ms // 1000))},
        )
```

*Design notes:* using app-server time across pods introduces clock skew; for strictness use Redis `TIME` inside the script. Decide **fail-open vs fail-closed** per use case: fail-open for general API protection; fail-closed for abuse-sensitive actions (login attempts, SMS sending — which costs money). Rate-limit keys should be the authenticated principal or API key, not just IP (NAT puts thousands of users behind one IP; attackers rotate IPs).

**Distributed locks — definition.** Mutual exclusion across processes/machines, e.g. "only one worker refreshes this token" or "only one scheduler instance runs the nightly job."

**Why they are dangerous.** A process can acquire a lock, then pause (GC, VM migration, a long `await`, network delay) past the lock's TTL; another process acquires the lock; both now believe they hold it. Martin Kleppmann's analysis of Redlock shows TTL-based locks cannot guarantee safety without **fencing tokens**: a monotonically increasing number issued with each lock acquisition that the *protected resource* checks, rejecting writes with an older token.

**Preference order for correctness:**

1. **Avoid the lock**: make the operation idempotent, or use a DB unique constraint (`INSERT ... ON CONFLICT DO NOTHING`).
2. **Use the database you already trust**: `SELECT ... FOR UPDATE`, `SELECT ... FOR UPDATE SKIP LOCKED` (job queues), optimistic concurrency (`UPDATE ... WHERE version = :v`), or PostgreSQL advisory locks (`pg_try_advisory_xact_lock(key)`).
3. **Lease + fencing token** via a consensus store (etcd, ZooKeeper) when correctness matters across systems.
4. **Redis `SET key token NX PX ttl`** with a compare-and-delete release script — acceptable for **efficiency** locks (avoid duplicate work), not for **correctness** locks.

```python
# Efficiency lock with safe release (only the owner may delete)
import secrets

RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""

async def run_exclusively(redis: Redis, name: str, ttl_ms: int, fn) -> bool:
    token = secrets.token_hex(16)
    if not await redis.set(f"lock:{name}", token, nx=True, px=ttl_ms):
        return False                               # someone else is doing it
    try:
        await fn()
        return True
    finally:
        await redis.eval(RELEASE_LUA, 1, f"lock:{name}", token)
```

```sql
-- Correctness via optimistic concurrency (fencing by version)
UPDATE inventory
SET    quantity = quantity - :qty, version = version + 1
WHERE  sku = :sku AND version = :expected_version AND quantity >= :qty;
-- rowcount = 0 → conflict or insufficient stock → reload and retry or reject
```

**Interview perspective.** The trap question is "how would you implement a distributed lock?" The senior answer starts with "can we avoid needing one?" and mentions fencing tokens and lock-vs-lease semantics.

#### 4.7 Async Architecture and Worker Scaling

**Definition.** Moving work off the synchronous request path into background workers coordinated by durable queues or logs.

**Choices of mechanism.**

| Mechanism | Durability | Use for | Avoid for |
|---|---|---|---|
| FastAPI `BackgroundTasks` | None (in-process, after response) | Tiny, losable work (non-critical log, cache warm) | Anything that must happen; long tasks |
| `asyncio.create_task` | None; can be garbage-collected if not referenced | Rarely in request handlers | Business work |
| Celery / RQ / arq / Dramatiq on Redis/RabbitMQ | Broker-dependent | Job queues: emails, reports, ETL steps | Event streaming, replay |
| Kafka / Redpanda | Durable, replayable log, partition ordering | Events consumed by many services, CDC, high throughput | Per-job priorities, delays (awkward) |
| SQS / SNS | Managed, durable | AWS-native job queues and fan-out | Strict ordering at scale (FIFO limits) |
| Postgres `SKIP LOCKED` queue | Transactional with your data | Low/medium volume, strong consistency with business writes | Very high throughput |
| Durable workflow engine (Temporal, AWS Step Functions) | Durable state machine | Multi-step, long-running, compensations | Simple fire-and-forget |

**The dual-write problem and the transactional outbox.** Writing to the DB *and* publishing to Kafka in one request is two independent operations; a crash between them causes lost or phantom events. The **outbox pattern** writes the event into an `outbox` table in the *same DB transaction* as the business change; a relay (poller or CDC via Debezium) publishes outbox rows to the broker and marks them sent. Delivery becomes at-least-once; consumers must be idempotent.

```python
# app/services/orders.py — business write + outbox in one transaction
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Order, OutboxEvent


async def place_order(session: AsyncSession, cmd: "PlaceOrder") -> Order:
    async with session.begin():
        order = Order(id=uuid.uuid4(), customer_id=cmd.customer_id, status="PENDING",
                      total_cents=cmd.total_cents)
        session.add(order)
        session.add(OutboxEvent(
            id=uuid.uuid4(),
            aggregate_type="order",
            aggregate_id=str(order.id),          # used as Kafka key → per-order ordering
            event_type="OrderPlaced",
            payload={"order_id": str(order.id), "total_cents": cmd.total_cents},
            created_at=datetime.now(UTC),
        ))
    return order
```

```python
# relay: poll unsent outbox rows safely from many relay instances
RELAY_SQL = """
SELECT id, aggregate_id, event_type, payload
FROM outbox
WHERE published_at IS NULL
ORDER BY created_at
LIMIT 100
FOR UPDATE SKIP LOCKED
"""
# publish each row to Kafka with key=aggregate_id, wait for broker ack,
# then UPDATE outbox SET published_at = now() WHERE id = ANY(:ids); COMMIT.
```

**Idempotent consumer.** Record processed message IDs in the same transaction as the side effect:

```sql
CREATE TABLE processed_messages (
    consumer    text NOT NULL,
    message_id  uuid NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, message_id)
);
-- In the consumer transaction:
INSERT INTO processed_messages (consumer, message_id) VALUES ('billing', :id)
ON CONFLICT DO NOTHING;   -- rowcount 0 → duplicate → skip side effect
```

**Worker scaling.**

- Scale on **lag/backlog** (Kafka consumer lag, SQS `ApproximateNumberOfMessagesVisible`, queue age), not CPU. KEDA on Kubernetes is the standard tool.
- Kafka consumers in a group: **max useful consumers = number of partitions**. Choose partition count for future peak parallelism (repartitioning later reshuffles key→partition mapping and breaks ordering assumptions).
- **Prefetch** controls fairness: Celery `worker_prefetch_multiplier=1` with `task_acks_late=True` for long tasks so one worker doesn't hoard jobs and lost workers' tasks are redelivered.
- **Visibility timeout / max poll interval** must exceed worst-case processing time, or messages are redelivered while still processing (duplicates).
- **Poison messages**: after N attempts, route to a DLQ with the error and alert; never infinite-retry.
- **Separate pools per workload class** (bulkheads): a flood of bulk emails must not starve password-reset emails.

**Interview perspective.** Expect "how do you guarantee the event is published if the DB commit succeeds?" (outbox), "what if the consumer processes twice?" (idempotency), "how do you scale consumers?" (partitions, lag-based autoscaling).

#### 4.8 Failure Domains, Resilience Patterns and Observability

**Failure domain — definition.** The set of components that fail together because they share a dependency: a process, a pod, a node, a rack, an availability zone, a region, a cloud provider, a deploy, a config flag, a credential, a third-party API.

**Design implications.**

- Spread replicas across AZs (Kubernetes `topologySpreadConstraints`, Multi-AZ RDS).
- **Cell-based architecture**: partition customers into independent cells (full stacks) so a bad deploy or poison tenant affects only one cell.
- **Bulkheads**: separate thread pools, connection pools, worker pools and even clusters per criticality.
- **Blast-radius control for changes**: canary deploys, feature flags, progressive rollout; most outages are self-inflicted changes.

**Resilience patterns.**

| Pattern | Purpose | Python/FastAPI tooling |
|---|---|---|
| Timeout | Bound waiting | `httpx.Timeout`, `asyncio.timeout()` (3.11+), DB `statement_timeout` |
| Deadline propagation | Downstream calls use remaining budget | Pass a deadline header/context |
| Retry with exponential backoff + full jitter | Survive transient faults | `tenacity`, `stamina` |
| Retry budget | Prevent retry storms | Count retries vs requests |
| Circuit breaker | Stop calling a failing dependency; fail fast; probe to recover | `pybreaker`, `aiobreaker`, or simple custom state machine |
| Bulkhead | Isolate resources | Separate pools/semaphores |
| Fallback / degradation | Serve something useful | Stale cache, default response, feature off |
| Idempotency keys | Make retries safe | Unique constraint on `(client_id, idempotency_key)` |
| Hedged requests | Cut tail latency on idempotent reads | Send a second request after p95 |

**Only retry when safe:** retries on non-idempotent operations duplicate side effects. Retry on connection errors, 502/503/504, 429 (respecting `Retry-After`); do not retry 400/401/403/404/409/422.

```python
# app/infra/http.py — timeouts + bounded retries + jitter for idempotent calls
import httpx
from tenacity import (AsyncRetrying, retry_if_exception, stop_after_attempt,
                      wait_random_exponential)

RETRYABLE_STATUS = {429, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError)):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in RETRYABLE_STATUS


async def get_json(client: httpx.AsyncClient, url: str) -> dict:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=0.2, max=2.0),   # full jitter
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    raise AssertionError("unreachable")
```

**Observability — definition.** The ability to answer new questions about system behavior from its outputs, without shipping new code. Three primary signals, correlated by trace ID:

- **Traces** (OpenTelemetry): a tree of spans across services — "this checkout spent 1.8 s waiting on the payment provider."
- **Metrics**: aggregated numbers. **RED** for services (Rate, Errors, Duration); **USE** for resources (Utilization, Saturation, Errors). Saturation metrics (pool wait time, queue depth, event-loop lag) are the earliest warning of backpressure problems.
- **Logs**: structured JSON events with `trace_id`, `span_id`, `request_id`, tenant, user (never secrets or raw PII).

Plus **profiles** (continuous profiling, e.g. py-spy, Pyroscope) and **events** (deploys, flag changes) annotated on dashboards.

**SLI/SLO/SLA.** SLI = measured indicator ("proportion of `POST /orders` returning non-5xx within 500 ms"). SLO = target (99.9% over 28 days). SLA = contractual promise with penalties (looser than SLO). Alert on **error-budget burn rate** (e.g. multi-window: 2% of monthly budget burned in 1 h), not on raw CPU.

```python
# app/core/telemetry.py — OpenTelemetry setup for FastAPI, SQLAlchemy, httpx, Redis
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_telemetry(app, engine, service_name: str, version: str) -> None:
    resource = Resource.create({"service.name": service_name, "service.version": version})
    tp = TracerProvider(resource=resource)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))   # endpoint from OTEL_EXPORTER_OTLP_ENDPOINT
    trace.set_tracer_provider(tp)
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter())],
    ))
    FastAPIInstrumentor.instrument_app(app, excluded_urls="livez,readyz")
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
```

Alternatively use zero-code auto-instrumentation: `opentelemetry-instrument uvicorn app.main:app` with `OTEL_*` environment variables. **[Version-dependent]** Python instrumentation packages are mostly beta (`0.5xb0` versions) even though the API/SDK are stable; pin versions together.

**Event-loop lag** is a FastAPI-specific saturation metric: schedule a coroutine every 100 ms and record how late it wakes. Lag > 50 ms indicates blocking code on the loop.

**Interview perspective.** Interviewers check that you design observability up front, define SLOs per critical user journey, and alert on symptoms (user-facing errors/latency) rather than causes.

#### 4.9 A Repeatable System-Design Method

Use this template for every design (it maps to the Practice requirement):

1. **Requirements.** Functional (what users do). Non-functional (scale, latency, availability, consistency, durability, compliance). Explicit *out of scope*. Ask clarifying questions; write assumptions down.
2. **Estimates.** DAU → QPS (avg and peak, typically 2–10× avg), read:write ratio, storage per record × records/day × retention, bandwidth.
3. **API.** Resource-oriented endpoints, request/response schemas, pagination (cursor-based), idempotency keys for unsafe operations, error model (RFC 9457 Problem Details), versioning.
4. **Data model.** Entities, keys, indexes, access patterns → store choice. Source of truth per entity.
5. **High-level architecture.** Boxes and arrows; synchronous vs asynchronous paths.
6. **Scale.** Bottleneck analysis: which component saturates first and what is the plan (cache, replica, partition, queue).
7. **Failures.** For each dependency: what if it is slow, down, or returns garbage? Duplicate messages? Region loss?
8. **Security.** AuthN, AuthZ (object-level!), tenant isolation, input validation, secrets, encryption, abuse/rate limits, audit.
9. **Observability.** SLIs/SLOs, key metrics, traces, logs, alerts, dashboards.
10. **Trade-offs.** What you chose, the simpler alternative, and when you would revisit.

**Estimation cheat values.** 1 day ≈ 86,400 s ≈ 10⁵ s. 1M requests/day ≈ 12 req/s avg. A modest FastAPI pod doing light I/O-bound JSON work with a DB call typically sustains hundreds to a couple thousand req/s per core-equivalent — **measure your own**, never assume. Single Postgres primary on good hardware: thousands to tens of thousands of simple writes/s. Redis: ~100k+ simple ops/s per shard.

#### 4.10 The Six Practice Designs (Worked)

Each design below is a compact model answer. In practice you should produce your own one-page version first, then compare.

##### Design A — URL Shortener

**Requirements.** Create short link for long URL (optionally custom alias, expiry); redirect `GET /{code}` → 301/302; per-link click analytics. Non-functional: 100M new links/month (~40 writes/s avg, 400 peak), 100:1 read:write (~4k redirects/s avg, 40k peak), redirect p99 < 50 ms at edge, 99.99% redirect availability, links durable for years.

**API.**

```
POST /v1/links            {long_url, custom_alias?, expires_at?}  Idempotency-Key header
  → 201 {code, short_url, long_url, expires_at}
GET  /{code}              → 302 Location: long_url   (301 is cached forever by browsers → loses analytics/edits)
GET  /v1/links/{code}/stats?from&to  → aggregated clicks
DELETE /v1/links/{code}   → 204 (owner only)
```

**Data.** `links(code PK, long_url, owner_id, created_at, expires_at, is_active)`. 100M/month × 5 years × ~500 B ≈ 3 TB — fits a single Postgres with partitioning, or DynamoDB keyed by `code`. Clicks are an append-only stream → Kafka → aggregated counters in ClickHouse/TimescaleDB or a rollup table.

**Code generation.** Options: (a) random 7-char base62 (62⁷ ≈ 3.5 × 10¹² space) with insert-retry on collision via unique constraint; (b) counter (DB sequence or range allocation per pod) encoded in base62 — no collisions but predictable/enumerable (obfuscate with a bijective shuffle such as a Feistel permutation); (c) hash of URL — dedupes identical URLs but collisions need handling and privacy suffers. Recommend (a) or ranged counters.

**Architecture.** `CDN/edge → redirect service (FastAPI or edge function) → Redis cache → Postgres`. Redirect path is read-only and cache-heavy (hot links follow a power law). Click events are emitted asynchronously (log line or Kafka produce with `acks=1`, non-blocking) — analytics loss under failure is acceptable; redirect failure is not.

**Scale.** 40k peak redirects/s: CDN caching of 302s for a short TTL (seconds–minutes) absorbs viral links; Redis handles the rest; Postgres read replicas for misses. Writes are trivial.

**Failures.** Redis down → read from replicas (pre-ping, timeouts). DB down → serve from cache; creation returns 503. Kafka down → buffer clicks locally (bounded) then drop with a metric.

**Security.** Open-redirect abuse/phishing: scan URLs against Safe Browsing lists asynchronously, allow reporting, block malicious domains; rate-limit creation per user/IP; validate URL scheme (`http/https` only — reject `javascript:`); private links may need auth; enumeration of codes if sequential.

**Observability.** SLIs: redirect success rate and latency at edge; cache hit ratio; creation error rate; click pipeline lag.

**Trade-offs.** 302 vs 301 (analytics vs caching); random vs sequential codes (collision handling vs predictability); Postgres vs DynamoDB (familiarity and SQL analytics vs effortless horizontal scale).

##### Design B — Notification System

**Requirements.** Services request notifications to users across channels (email, SMS, push, in-app); user preferences and quiet hours; templates and localization; priority (transactional OTP vs marketing); deduplication; delivery status tracking; 10M notifications/day avg, 50M peak days, campaign bursts of 5M in an hour; OTP p99 delivery < 10 s.

**API.**

```
POST /v1/notifications  {idempotency_key, user_id | segment_id, template_id, channel_hints[], priority, data{}}
  → 202 {notification_id}
GET  /v1/notifications/{id}  → status per channel
PUT  /v1/users/{id}/preferences
```

**Data.** `notifications(id, idempotency_key UNIQUE(producer, key), user_id, template_id, priority, status, created_at)`, `deliveries(notification_id, channel, provider, status, attempts, provider_message_id, updated_at)`, `preferences(user_id, channel, category, enabled, quiet_hours)`, `templates(id, version, locale, body)`.

**Architecture.**

```
Producers → [Notification API] → (Postgres: notification + outbox)
   ⇢ Kafka topic notifications.requested (key=user_id)
   ⇢ [Router workers]: load prefs, render template, apply quiet hours, fan-out per channel
   ⇢ per-channel queues by priority: email.high, email.bulk, sms.high, push.high ...
   ⇢ [Channel senders] → {SES/SendGrid, Twilio, APNs/FCM}  (rate-limited per provider)
   ⇢ provider webhooks → [Status ingester] → deliveries table, metrics
```

**Scale.** Separate topics/queues per priority (bulkhead) so a 5M marketing campaign cannot delay OTPs. Provider rate limits are the true bottleneck — enforce token buckets per provider account; autoscale senders on lag but cap at provider limits. Segment fan-out (5M users) is done by a batch job producing per-user messages incrementally (stream cursor over segment), not one giant transaction.

**Failures.** Provider outage → circuit breaker, failover to secondary provider for transactional channels; retries with backoff; DLQ after N attempts. Duplicates: idempotency key at API; consumer dedupe on `(notification_id, channel)`; some providers accept idempotency keys. Webhook duplicates and out-of-order status events → monotonic status state machine (`QUEUED < SENT < DELIVERED`, `FAILED` terminal).

**Security.** Only authenticated internal services may send (mTLS/service tokens); templates are not arbitrary code (sandboxed rendering — Jinja2 `SandboxedEnvironment`, autoescape for HTML email); PII minimization in logs; unsubscribe links (legal: CAN-SPAM, GDPR); SMS pumping fraud → rate limits and country allow-lists.

**Observability.** Per-channel/provider send rate, error rate, latency from request to provider acceptance, queue lag per priority, delivery rate from webhooks, cost per channel.

**Trade-offs.** Kafka vs SQS (replay and ordering vs operational simplicity); exactly-once impossible with external providers → at-least-once + dedupe + accept rare duplicates for non-critical messages.

##### Design C — Document Search

**Requirements.** Users in a tenant search their documents (PDF, DOCX, HTML) with keyword search, filters (type, date, owner), highlights, and permission-aware results; new documents searchable within 1 minute; 50M documents, 200 search QPS peak, p95 < 300 ms.

**API.** `POST /v1/documents` (upload → presigned S3 URL), `GET /v1/search?q=&filters=&cursor=`, `GET /v1/documents/{id}`.

**Data.** Source of truth: Postgres `documents(id, tenant_id, owner_id, title, s3_key, status, acl_version, updated_at)` + S3 for blobs. Derived: search index (OpenSearch/Elasticsearch, or Postgres full-text search `tsvector` + GIN for smaller scale).

**Architecture.**

```
Upload → S3 (presigned) → S3 event ⇢ queue ⇢ [Extraction workers: text, OCR] ⇢ [Indexer] → OpenSearch
Postgres changes (ACL, metadata) ⇢ outbox/CDC ⇢ [Indexer] (partial update)
Search: API → authZ (resolve user's groups) → OpenSearch query with tenant_id + ACL filter → hydrate from Postgres/cache
```

**Key decisions.** Permission-aware search: index `allowed_principals` (user IDs, group IDs) on each document and filter at query time (**early binding**) — fast but requires reindex on ACL changes; or post-filter top results by checking ACLs (**late binding**) — always fresh but breaks pagination/recall. Common: early binding + ACL version check on hydration. Always include `tenant_id` filter (or index-per-tenant for large tenants).

**Scale.** OpenSearch shards sized ~10–50 GB; replicas for read throughput; extraction workers autoscaled on queue depth; OCR is CPU-heavy → separate pool.

**Failures.** Index lag (eventual consistency) → show "processing" status; indexer failures → DLQ and reindex job from source of truth (index is rebuildable — never the source of truth). Malformed PDFs crash parsers → sandbox extraction in separate processes with memory/time limits.

**Security.** Tenant isolation in every query (enforced in a repository layer, not by callers remembering); malicious files (zip bombs, XXE in DOCX) → hardened parsers, size limits; presigned URLs short-lived.

**Observability.** Indexing lag (upload → searchable), extraction failure rate by file type, search latency and zero-result rate, click-through on results.

**Trade-offs.** Postgres FTS (one system, transactional, good to a few million docs) vs OpenSearch (relevance tuning, scale, aggregations, extra infra).

##### Design D — Chat Service

**Requirements.** 1:1 and group chats (≤ 500 members); real-time delivery; message history; read receipts; typing indicators; presence; offline push; 10M DAU, 1M concurrent connections, 50k messages/s peak; per-conversation ordering; at-least-once delivery with client dedupe.

**API.** WebSocket `wss://chat/ws` for real-time (send, ack, receive, typing), REST for history `GET /v1/conversations/{id}/messages?before=cursor`, `POST /v1/conversations`.

**Data.** Messages are write-heavy, append-only, read by conversation and time → Cassandra/ScyllaDB/DynamoDB with partition key `conversation_id` (+ time bucket for very active conversations) and clustering key `message_id` (time-ordered, e.g. ULID/Snowflake). Postgres for users, conversations, memberships. Redis for presence (TTL keys) and connection registry.

**Architecture.**

```
Client ⇄ L4/L7 LB (WebSocket aware) ⇄ [Gateway pods: FastAPI/Starlette WebSockets, ~50–100k conns each]
  send → [Chat service]: validate membership, assign seq per conversation, persist message, ack client
       ⇢ Kafka messages topic (key=conversation_id)
       ⇢ [Fan-out workers]: look up members' connection gateways (Redis registry) → push via gateway
                          → offline members ⇢ notification system (Design B)
```

**Ordering.** Assign a per-conversation sequence number at the single writer for that conversation (partition owner) or use the Kafka partition offset; clients order by sequence and detect gaps to fetch missing history.

**Scale.** WebSocket connections are long-lived and stateful → gateways must drain on deploy (send reconnect hint; clients reconnect with backoff and jitter to avoid reconnection storms); balance by connection count. Python async handles many idle connections well per process, but message fan-out for large groups should be done by workers, not in the gateway's event loop.

**Failures.** Gateway crash → clients reconnect and resync from last seen sequence; message persisted before ack → durable; Kafka redelivery → client dedupes by `client_msg_id`. Presence is best-effort.

**Security.** Authenticate WebSocket on connect (token in first message or `Sec-WebSocket-Protocol`; avoid query strings that end up in logs), re-check membership on send and on fan-out, rate-limit messages per user, size limits, E2E encryption as a product decision (changes search/moderation).

**Observability.** Concurrent connections per gateway, message end-to-end latency (send → recipient receive), fan-out lag, reconnect rate, dropped frames.

**Trade-offs.** WebSocket vs SSE + POST (SSE simpler through proxies, one-directional); wide-column store vs Postgres (Postgres works far longer than people expect with partitioning by conversation hash — start there unless scale demands).

##### Design E — Order Platform (E-commerce)

**Requirements.** Browse catalog; cart; checkout with inventory reservation and payment; order lifecycle (placed → paid → fulfilled → shipped → delivered / cancelled / refunded); no overselling; no double charging; 5k orders/min peak during sales; checkout p99 < 1.5 s.

**API.**

```
POST /v1/carts/{id}/checkout   Idempotency-Key: <uuid>   → 201 {order_id, status: PENDING_PAYMENT}
POST /v1/payments/webhook      (provider → us, signature verified)
GET  /v1/orders/{id}
POST /v1/orders/{id}/cancel
```

**Data.** Postgres (strong consistency, transactions): `orders`, `order_items`, `inventory(sku, available, reserved, version)`, `payments(order_id, provider_intent_id UNIQUE, status)`, `idempotency_keys(client_id, key, request_hash, response, status)`, `outbox`.

**Checkout flow (saga with orchestration).**

```
1. Idempotency check (unique key; if completed, return stored response; if in-progress, 409)
2. TX: create order PENDING; reserve inventory
       UPDATE inventory SET available = available - :q, reserved = reserved + :q
       WHERE sku = :sku AND available >= :q        -- rowcount 0 → out of stock → rollback
   + outbox OrderCreated
3. Create payment intent with provider (idempotency key = order_id)
4. Provider webhook PAYMENT_SUCCEEDED → TX: order PAID; commit reservation; outbox OrderPaid
5. Compensation: payment failed or timeout (reservation TTL job) → release reservation; order CANCELLED
```

**Scale.** Hot SKUs during flash sales → row-lock contention on one inventory row. Options: split inventory into N sub-rows ("inventory buckets") and reserve from a random bucket; pre-allocate tokens in Redis with atomic `DECR` as an admission gate, then confirm in Postgres; or a queue-based checkout (virtual waiting room).

**Failures.** Payment provider timeout → do not assume failure; query provider by idempotency key / reconcile via webhook. Duplicate webhooks → unique `provider_event_id`. Partial saga failure → compensating actions and a reconciliation job comparing provider records with orders daily.

**Security.** Object-level authorization (users only see their orders — BOLA is OWASP API Security #1); verify webhook signatures and timestamps; never trust client-sent prices (recompute server-side); PCI scope minimization by using provider-hosted payment fields.

**Observability.** Checkout funnel success rate, payment success by provider, reservation timeouts, oversell incidents (should be zero), saga stuck-state counts.

**Trade-offs.** Orchestrated saga (one coordinator, easy to reason) vs choreography (services react to events, looser coupling, harder to trace); synchronous payment capture vs async webhook confirmation.

##### Design F — AI Knowledge Service (RAG over enterprise documents)

**Requirements.** Employees ask questions over internal documents (Confluence, Google Drive, PDFs) and get answers with citations; only documents the user may access; freshness < 1 h; 2k QPS peak? Clarify — typical enterprise: 50k employees, ~20 queries/s peak; p95 first token < 2 s; cost cap per month; answers must say "I don't know" when evidence is missing.

**API.** `POST /v1/ask {question, conversation_id?, filters?}` → streamed SSE with tokens then final `{answer, citations[{doc_id, chunk_id, title, url, snippet}], confidence}`; `POST /v1/feedback`.

**Data.** Postgres + pgvector: `documents(id, tenant_id, source, source_id, acl_principals text[], updated_at, content_hash)`, `chunks(id, document_id, ordinal, text, embedding vector(1024), tsv tsvector, metadata jsonb)` with HNSW index on embedding and GIN on `tsv` and `acl_principals`.

**Architecture.**

```
Connectors (scheduled + webhooks) ⇢ queue ⇢ [Ingestion workers]: fetch, parse, chunk, embed (batch), upsert by content_hash
Ask: API → authN → resolve principals (user + groups) → query rewrite (optional LLM, cached)
     → hybrid retrieval: vector kNN + BM25/FTS, both filtered by tenant + ACL → fuse (RRF) → rerank (cross-encoder)
     → context build (token budget, dedupe, order) → LLM generate (structured output with citations) → validate citations ⊆ retrieved chunks → stream
```

**Scale.** LLM latency and provider rate limits dominate; embedding throughput dominates ingestion. Use semantic/exact caching for repeated questions *within the same ACL scope*; batch embeddings; separate ingestion workers from query path.

**Failures.** LLM provider outage → fallback model/provider, or degrade to "search results only" mode. Bad retrieval → low reranker scores trigger "insufficient evidence" response. Embedding model change → re-embed into a new column/index and switch atomically.

**Security.** ACL filter **in the retrieval query**, never by asking the model; prompt-injection content in documents treated as data (delimited, never granted tool authority); PII redaction in logs; per-user rate limits and token budgets.

**Observability & evaluation.** Traces across retrieval/rerank/generation with token counts and cost; retrieval metrics (recall@k, MRR on a labeled set); answer metrics (groundedness/faithfulness, citation correctness, answer relevance); user feedback rates. Unit 48 expands this.

**Trade-offs.** pgvector (one database, transactional ACL joins, good to tens of millions of vectors) vs a dedicated vector DB (scale, specialized features, another system to secure and sync).

### 5. Internal Mechanics

#### 5.1 What happens to one request in a scaled FastAPI deployment

```
Client TCP/TLS → DNS → CDN/edge (cache hit? return) → L7 LB (picks pod via least-outstanding)
→ kube-proxy/iptables or eBPF → container port
→ kernel accept queue (backlog) → Uvicorn worker process accepts (one of N processes; SO_REUSEPORT or shared socket)
→ h11/httptools parses HTTP → builds ASGI scope → calls app(scope, receive, send) on the event loop
→ Starlette middleware stack (outermost first: OTel, CORS, GZip, custom)
→ Router matches path → FastAPI solves dependency graph:
     async deps awaited on loop; sync deps run in AnyIO thread pool (capacity limiter 40)
     yield-deps entered (DB session opened; pool checkout may wait up to pool_timeout)
→ Request body read and validated by Pydantic v2 (pydantic-core, Rust)
→ Endpoint runs (async on loop / sync in thread pool)
→ Return value validated/serialized via response_model (Pydantic) → JSON bytes
→ Response sent; yield-deps exit (session closed, connection returned to pool)
   [FastAPI ≥ 0.106: yield-dependency exit code runs before the response is sent;
    later versions refined this—check release notes for your pinned version]
→ BackgroundTasks run after response in the same process
→ Middleware unwinds; OTel span ends; access log line emitted
```

Every arrow is a place where time can be spent and a queue can form. Saturation shows up as: rising event-loop lag (blocking code), thread-pool exhaustion (many sync endpoints waiting), pool checkout waits (DB connections), or kernel backlog drops (accept queue full).

#### 5.2 Why the AnyIO thread pool matters for scaling

Sync (`def`) endpoints and dependencies are run via `anyio.to_thread.run_sync`, gated by a default `CapacityLimiter(40)`. If 40 sync requests are each waiting 2 s on a slow HTTP call with `requests`, request 41 waits even though CPU is idle. Options: convert to `async def` with async clients (httpx, asyncpg/psycopg 3 async); increase the limiter in lifespan (`anyio.to_thread.current_default_thread_limiter().total_tokens = 100`); or isolate slow sync work to a worker service.

#### 5.3 Inside PostgreSQL contention

A hot inventory row under `UPDATE ... WHERE sku = ?` serializes writers: each takes a row lock until commit. Throughput ≈ 1 / (transaction duration while holding lock). Keep that transaction short (no network calls inside it!). Inspect with `pg_stat_activity` (`wait_event_type = 'Lock'`) and `pg_locks`.

#### 5.4 Inside Kafka consumer groups

A topic has P partitions; a consumer group assigns each partition to exactly one consumer. Offsets are committed per partition. On rebalance (consumer joins/leaves/times out after `max.poll.interval.ms`), partitions move; uncommitted work is redelivered — the reason duplicates exist. Cooperative-sticky assignment and the newer consumer rebalance protocol (KIP-848, generally available in Kafka 4.0) reduce stop-the-world rebalances. **[Version-dependent]**

#### 5.5 Inside Redis atomicity

Redis executes commands (and Lua scripts/functions) one at a time per shard, so a script is atomic relative to other commands. In Redis Cluster, all keys in a script must hash to the same slot (use hash tags `{user:42}:tokens`). Replication to replicas is asynchronous: a lock written to a primary that fails before replicating can be lost — another reason Redis locks are for efficiency, not correctness.

### 6. Implementation Examples

#### Example 1 — Minimal: Bounded worker pool with backpressure (pure asyncio)

```python
# backpressure_demo.py — run: python backpressure_demo.py
import asyncio
import random
import time


async def producer(queue: asyncio.Queue[int], n: int) -> None:
    for i in range(n):
        await queue.put(i)               # blocks when queue is full → backpressure
    for _ in range(WORKERS):
        await queue.put(-1)              # poison pills to stop workers


async def worker(name: str, queue: asyncio.Queue[int]) -> None:
    while True:
        item = await queue.get()
        try:
            if item == -1:
                return
            await asyncio.sleep(random.uniform(0.01, 0.05))   # simulated I/O
        finally:
            queue.task_done()


WORKERS = 8


async def main() -> None:
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=50)     # bounded!
    start = time.perf_counter()
    async with asyncio.TaskGroup() as tg:                     # Python 3.11+
        tg.create_task(producer(queue, 1_000))
        for w in range(WORKERS):
            tg.create_task(worker(f"w{w}", queue))
    print(f"processed 1000 items in {time.perf_counter() - start:.2f}s; "
          f"max memory bounded by queue size 50")


if __name__ == "__main__":
    asyncio.run(main())
```

Key lines: `maxsize=50` bounds memory; `await queue.put` suspends the producer when consumers fall behind; `TaskGroup` cancels siblings if one fails (structured concurrency).

#### Example 2 — Realistic: Cached, rate-limited product API

Architecture: `GET /products/{id}` uses cache-aside on Redis; writes invalidate; all routes are rate-limited per principal; DB sessions come from a dependency.

```python
# app/api/products.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product
from app.db.session import get_session
from app.infra.cache import Cache
from app.infra.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/products", tags=["products"],
                   dependencies=[Depends(enforce_rate_limit)])


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    price_cents: int


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(ge=0)


def get_cache(request: Request) -> Cache:
    return request.app.state.cache


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: uuid.UUID,
                      session: AsyncSession = Depends(get_session),
                      cache: Cache = Depends(get_cache)) -> dict:
    async def load() -> dict:
        product = await session.get(Product, product_id)
        if product is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
        return ProductOut.model_validate(product).model_dump(mode="json")

    return await cache.get_or_load(f"product:{product_id}", load, ttl_s=300)


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: uuid.UUID, body: ProductUpdate,
                         session: AsyncSession = Depends(get_session),
                         cache: Cache = Depends(get_cache)) -> Product:
    product = await session.get(Product, product_id, with_for_update=True)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    product.name, product.price_cents = body.name, body.price_cents
    await session.commit()
    await cache.invalidate(f"product:{product_id}")     # delete AFTER commit
    return product
```

Design notes: 404s are not cached here (a "negative cache" with a short TTL would protect against enumeration floods); invalidation happens after commit to avoid caching uncommitted state; `strict=True` rejects `"100"` for an int field at this boundary.

#### Example 3 — Production-oriented: Idempotent POST with outbox, timeouts, and tracing

Architecture: clients send `Idempotency-Key`. The first request records the key with status `IN_PROGRESS` inside the business transaction; completion stores the response. Retries return the stored response. A request with the same key but a different body returns 422. Events go through the outbox.

```python
# app/api/payments.py
import hashlib
import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from opentelemetry import trace
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_scope
from app.db.models import IdempotencyKey, OutboxEvent, Transfer
from app.db.session import get_session

router = APIRouter(prefix="/transfers")
tracer = trace.get_tracer(__name__)


class TransferIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_account: uuid.UUID
    to_account: uuid.UUID
    amount_cents: int = Field(gt=0, le=10_000_000)


class TransferOut(BaseModel):
    id: uuid.UUID
    status: str


def _hash(body: TransferIn) -> str:
    return hashlib.sha256(body.model_dump_json().encode()).hexdigest()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TransferOut)
async def create_transfer(
    body: TransferIn,
    idem_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
    principal: Annotated[Principal, Depends(require_scope("transfers:write"))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransferOut:
    req_hash = _hash(body)
    with tracer.start_as_current_span("transfer.create") as span:
        span.set_attribute("app.idempotency_key_present", True)
        async with session.begin():
            # Claim the key atomically; unique (client_id, key)
            claimed = await session.execute(
                insert(IdempotencyKey)
                .values(client_id=principal.client_id, key=idem_key,
                        request_hash=req_hash, status="IN_PROGRESS")
                .on_conflict_do_nothing()
                .returning(IdempotencyKey.key)
            )
            if claimed.scalar_one_or_none() is None:
                existing = (await session.execute(
                    select(IdempotencyKey).where(
                        IdempotencyKey.client_id == principal.client_id,
                        IdempotencyKey.key == idem_key))).scalar_one()
                if existing.request_hash != req_hash:
                    raise HTTPException(422, "Idempotency-Key reused with different payload")
                if existing.status == "COMPLETED":
                    span.set_attribute("app.idempotent_replay", True)
                    return TransferOut.model_validate_json(existing.response_json)
                raise HTTPException(409, "Request with this key is in progress")

            if not await principal.owns_account(session, body.from_account):
                raise HTTPException(403, "Not allowed to debit this account")   # object-level authZ

            transfer = Transfer(id=uuid.uuid4(), from_account=body.from_account,
                                to_account=body.to_account, amount_cents=body.amount_cents,
                                status="PENDING")
            session.add(transfer)
            session.add(OutboxEvent.for_aggregate("transfer", transfer.id, "TransferRequested",
                                                  body.model_dump(mode="json")))
            out = TransferOut(id=transfer.id, status=transfer.status)
            await session.execute(
                IdempotencyKey.__table__.update()
                .where(IdempotencyKey.client_id == principal.client_id,
                       IdempotencyKey.key == idem_key)
                .values(status="COMPLETED", response_json=out.model_dump_json())
            )
        return out
```

Important decisions: the key claim, business write, outbox event and stored response all commit atomically, so a crash leaves either nothing or everything (an `IN_PROGRESS` row can only exist inside an uncommitted transaction here, so concurrent duplicates block on the unique index until the first commits or rolls back). Authorization is object-level and deterministic. Tests should cover replay, payload mismatch, concurrency (two simultaneous requests with one key) and authorization denial.

### 7. Comparative Analysis

| Comparison | Key difference | Use A when | Use B when | Interview trap |
|---|---|---|---|---|
| Vertical vs horizontal scaling | Bigger box vs more boxes | Early stage, stateful DB primary | Stateless API tiers | "Just add pods" — the DB is usually the bottleneck |
| L4 vs L7 LB | Connection vs request aware | Raw TCP, extreme throughput | Path routing, HTTP/2, retries | Forgetting long-lived connections imbalance L4 |
| Cache-aside vs write-through | Lazy load vs synchronous update | Read-heavy, tolerate brief staleness | Need read-after-write from cache | Updating cache on write (race) instead of deleting |
| Redis vs in-process cache | Shared vs per-worker | Multi-pod consistency, larger data | Tiny hot config; nanosecond reads | In-process cache × N workers = N inconsistent copies |
| Queue (Celery/SQS) vs log (Kafka) | Delete-on-consume jobs vs retained replayable log | Task processing, retries, delays | Event streaming, multiple consumers, replay | "Kafka is a queue" — no per-message ack/delay semantics |
| BackgroundTasks vs Celery | In-process, no durability vs durable broker | Losable trivial work | Must-happen work | Using BackgroundTasks for emails that must be sent |
| Replication vs partitioning | Copies vs splits | Read scaling, HA | Write scaling, data size, retention | Thinking replicas scale writes |
| Sync vs async replication | Durability vs latency | Financial data, RPO = 0 | Read replicas, cross-region | Read-your-writes on async replicas |
| Pessimistic vs optimistic locking | Lock first vs detect conflicts | High contention, short TX | Low contention, web forms | Holding row locks across network calls |
| Redis lock vs DB constraint | Lease (can expire) vs enforced invariant | Avoid duplicate work | Correctness invariant | Redlock without fencing tokens |
| Gateway vs app rate limiting | Coarse edge vs business-aware | Per-key quotas, DDoS shield | Per-tenant plan limits, cost-based limits | Only limiting by IP |
| Orchestrated vs choreographed saga | Central coordinator vs event reactions | Complex flows, visibility | Few steps, autonomous teams | Choreography spaghetti nobody can trace |
| REST vs messaging | Request/response vs async events | Need immediate answer | Decoupling, fan-out, buffering | Calling microservices synchronously in a chain (latency + availability multiply) |

### 8. Failure Modes and Debugging

**F1 — Latency spikes then 504s under moderate load.**
SYMPTOM: p99 climbs from 80 ms to 30 s; CPU low; DB healthy.
↓ LIKELY CAUSE: SQLAlchemy pool exhausted; requests wait up to `pool_timeout=30` s; or sync endpoints exhausted the 40-thread AnyIO pool.
↓ INVESTIGATE: Pool metrics (`engine.pool.status()`, OTel `db.client.connection.*` metrics); traces show long gaps before the first DB span; `py-spy dump --pid <pid>` shows threads blocked in `requests`; check for sessions held across slow external calls.
↓ FIX: Release sessions before external calls; set `pool_timeout` to 1–3 s to fail fast; convert blocking calls to async; size pools from Little's Law.
↓ PREVENT: Saturation metrics and alerts (pool wait time, thread-pool queue); load tests including slow-dependency injection.

**F2 — Event loop blocked.**
SYMPTOM: All endpoints in a worker slow simultaneously, including `/livez`; liveness probes fail; pods restart.
↓ CAUSE: CPU-bound work or blocking I/O (`time.sleep`, `requests`, sync DB driver, big `json.dumps`) inside `async def`.
↓ INVESTIGATE: `PYTHONASYNCIODEBUG=1` / `loop.slow_callback_duration` logs callbacks > 100 ms; event-loop-lag metric; `py-spy top`.
↓ FIX: Use async libraries, `await asyncio.to_thread(...)`, or a process pool / worker service.
↓ PREVENT: Lint rules (ruff `ASYNC` rules flag blocking calls in async functions), code review, loop-lag alert.

**F3 — Cache stampede after deploy.**
SYMPTOM: DB CPU 100% right after a Redis flush or failover; recovers after minutes.
↓ CAUSE: Simultaneous misses for hot keys; no coalescing; synchronized TTLs.
↓ INVESTIGATE: Cache hit ratio drop correlated with DB QPS spike; top queries in `pg_stat_statements`.
↓ FIX: Single-flight + stale-while-revalidate + TTL jitter; warm critical keys.
↓ PREVENT: Cold-cache load tests; never `FLUSHALL` in production.

**F4 — Retry storm / metastable failure.**
SYMPTOM: A 20-second dependency blip causes a 40-minute outage; traffic is 3–5× normal although users didn't increase.
↓ CAUSE: Clients and every service layer retrying (multiplicative retries: 3 × 3 × 3 = 27×), no jitter, no budgets.
↓ INVESTIGATE: Compare inbound request rate at LB vs unique client requests; retry-attempt metrics per layer.
↓ FIX: Retry at one layer only, with jitter and budgets; circuit breakers; load shedding to drain backlog.
↓ PREVENT: Retry policy standard across services; chaos experiments.

**F5 — Duplicate charges / duplicate emails.**
SYMPTOM: Customers charged twice; two welcome emails.
↓ CAUSE: At-least-once delivery + non-idempotent consumer; Celery visibility timeout shorter than task duration; client retried POST without idempotency key.
↓ INVESTIGATE: Search logs by business ID; look for two task executions with the same message ID; compare task duration to visibility timeout.
↓ FIX: Idempotency keys, processed-message table, provider idempotency keys, correct visibility timeouts.
↓ PREVENT: Contract tests that deliver every message twice.

**F6 — Read-your-writes violation.**
SYMPTOM: "I saved my settings but they reverted" — then they appear after refresh.
↓ CAUSE: Reads from async replica lagging.
↓ INVESTIGATE: `SELECT now() - pg_last_xact_replay_timestamp();` on replica; correlate with complaint times.
↓ FIX: Route post-write reads to primary; session stickiness for N seconds.
↓ PREVENT: Explicit read/write session dependencies; replica-lag alerts.

**F7 — Hot partition.**
SYMPTOM: One Kafka consumer lags while others idle; one DB shard at 100%.
↓ CAUSE: Skewed key (a whale tenant; `null` key; low-cardinality key like `country`).
↓ INVESTIGATE: Per-partition lag and message rates; key distribution histogram.
↓ FIX: Better key (compound key with salt for whale tenants, accepting loss of total order), dedicated partition/cell for whales.
↓ PREVENT: Analyze key distribution before choosing; monitor per-partition metrics.

**F8 — Two cron instances ran the same job.**
SYMPTOM: Nightly invoice job ran twice after scaling scheduler pods to 2.
↓ CAUSE: Schedulers run in every replica; Redis lock TTL shorter than job duration.
↓ FIX: Single scheduler (Kubernetes CronJob with `concurrencyPolicy: Forbid`), Postgres advisory lock, and idempotent job design (unique `(customer, period)` invoice constraint).
↓ PREVENT: Assume any job can run twice.

**Diagnostic toolkit.** `py-spy top/dump/record` (sampling profiler, attach to running process), `austin`, Scalene, `asyncio` debug mode, OTel traces in Jaeger/Tempo/Honeycomb, `pg_stat_statements`, `pg_stat_activity`, `EXPLAIN (ANALYZE, BUFFERS)`, `redis-cli --latency`, `redis-cli --bigkeys`, `SLOWLOG GET`, `kafka-consumer-groups.sh --describe`, k6/Locust for load tests, `kubectl top`, `kubectl describe pod` (OOMKilled, probe failures).

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**Exercise 1.1 — Availability arithmetic.**
Objective: compute composite availability. Requirements: a checkout API (99.95%) synchronously calls auth (99.9%), inventory (99.95%), payments provider (99.9%), and Postgres (99.95%). Compute the upper bound, then redesign to reach ≥ 99.9% for "order accepted." Constraints: payments provider SLA cannot change. Expected behavior: a numeric answer and a design change (e.g. async payment confirmation, cached auth keys). Suggested tests: recompute with your redesign. Hints: (1) multiply serial availabilities; (2) which dependencies can be taken off the synchronous path? (3) JWT verification with cached JWKS removes a synchronous auth call.

**Exercise 1.2 — Little's Law sizing.**
Objective: size a DB pool. Requirements: 1,200 req/s peak; 60% of requests hit DB; mean DB time 15 ms, p99 80 ms; 6 pods × 2 workers. Compute connections needed at mean and with headroom; compare to `max_connections=400`. Hints: (1) L = λW per resource; (2) divide by processes; (3) consider PgBouncer.

**Exercise 1.3 — Consistency per operation.**
Objective: assign consistency requirements. For the order platform list 10 operations (view catalog, add to cart, place order, view order, etc.) and assign strong/read-your-writes/eventual with justification. Hints: (1) money and inventory invariants; (2) what does the user just did expect to see?

#### Level 2 — Implementation

**Exercise 2.1 — Sliding-window-counter rate limiter.**
Objective: implement and test a sliding window counter in Redis with Lua. Requirements: `allow(key, limit, window_s) -> (bool, retry_after_s)`; atomic; works across processes. Constraints: O(1) memory per key; Redis Cluster-compatible keys. Expected: within any 60-s window no more than ~`limit` requests (allowing approximation). Suggested tests: fakeredis or Testcontainers Redis; burst at window boundary; concurrent calls with `asyncio.gather`. Hints: (1) keys `rl:{key}:{window_index}`; (2) weight previous window by overlap fraction; (3) `EXPIRE` both keys to 2× window; (4) compare with the token bucket's behavior on bursts.

**Exercise 2.2 — Single-flight cache with stale-while-revalidate.**
Objective: extend the §4.3 cache. Requirements: store `{value, soft_exp}`; after soft expiry, return stale value immediately and trigger one background refresh; hard TTL deletes. Tests: concurrent 100 requests on expired key call the loader once; loader failure keeps serving stale until hard expiry. Hints: (1) keep strong references to refresh tasks; (2) use a Redis `SET NX` lock to coordinate across processes; (3) record metrics for stale serves.

**Exercise 2.3 — Outbox relay.**
Objective: implement an outbox table, relay loop and idempotent consumer. Requirements: relay uses `FOR UPDATE SKIP LOCKED`; publishes to Kafka (or Redis Streams if Kafka unavailable) with key = aggregate ID; marks published; consumer dedupes. Tests: kill relay mid-batch (simulate by raising after publish, before mark) → message delivered twice → consumer effect once. Hints: (1) two relays must not publish the same row concurrently; (2) a crash between publish and mark is expected; (3) order by `created_at, id`.

#### Level 3 — Integration

**Exercise 3.1 — Notification service vertical slice.**
Objective: build Design B's transactional path. Requirements: `POST /notifications` (idempotent) → Postgres + outbox → Kafka → router worker → fake email provider (an HTTP stub that randomly returns 500/timeout) → status updates via webhook endpoint. Priority bulkhead: separate topics for `high` and `bulk`. Constraints: docker-compose with Postgres, Kafka (KRaft), Redis; OpenTelemetry traces visible in Jaeger end-to-end (propagate trace context in Kafka headers). Expected: under a 10k-message bulk flood, high-priority p95 end-to-end latency stays < 2 s. Tests: integration with Testcontainers; duplicate delivery test; provider outage with circuit breaker. Hints: (1) inject `traceparent` into Kafka headers with the OTel propagator; (2) separate consumer groups per priority; (3) token bucket per provider; (4) state machine for statuses.

**Exercise 3.2 — URL shortener with load test.**
Objective: implement Design A with Redis cache and async click events; run k6 or Locust at 2k req/s locally; report p50/p95/p99, cache hit ratio and DB QPS. Hints: (1) seed 100k links with Zipf-distributed access; (2) compare cold vs warm cache; (3) measure with and without single-flight.

#### Level 4 — Debugging / Production Scenario

**Exercise 4.1 — Diagnose this service.**

```python
@app.post("/reports")
async def create_report(req: ReportRequest, db: Session = Depends(get_sync_session)):
    rows = db.execute(text("SELECT * FROM events WHERE tenant_id = :t"), {"t": req.tenant_id}).all()
    pdf = render_pdf(rows)                       # ~3 s CPU
    requests.post(STORAGE_URL, data=pdf)         # no timeout
    background_tasks.add_task(send_email, req.email)
    return {"ok": True}
```

Objective: list every scaling, reliability and correctness problem, then propose a redesign. Expected findings include: sync session and `requests` inside `async def` blocking the loop; CPU work on loop; unbounded `SELECT *`; no timeout; email via losable BackgroundTasks; `background_tasks` not declared as a parameter; no idempotency; no authorization of `tenant_id`; synchronous long-running work should be a 202 + job resource. Hints: (1) classify each line as loop-blocking, unbounded, or non-durable; (2) what happens with 50 concurrent requests? (3) design `POST /reports → 202 {job_id}` + `GET /reports/{job_id}`.

**Exercise 4.2 — Incident: lock expired.**
A Redis-locked "recompute balances" job sometimes produces wrong balances when the job runs long. Explain the failure timeline, and redesign so correctness does not depend on the lock. Hints: (1) draw two timelines with a GC pause; (2) fencing token or version column; (3) make the computation idempotent per account and period.

**Exercise 4.3 — Incident: Kafka lag growing forever.**
Consumer lag grows only on partition 7; restarting consumers helps briefly. Diagnose. Hints: (1) per-partition key distribution; (2) a poison message causing repeated failure and rebalance (`max.poll.interval.ms` exceeded); (3) DLQ policy.

### 10. Independent Implementation Project — "Six Designs, Two Builds"

**Goal.** Produce a system-design portfolio of the six required systems and implement two of them (the order platform core and the notification system) as running, observable, load-tested services.

**Functional requirements.**

1. Six design documents (≤ 4 pages each) following requirements → API → data → architecture → scale → failures → security → observability → trade-offs, each with a diagram and back-of-the-envelope estimates.
2. Order platform core: catalog read API with caching; idempotent checkout with inventory reservation; payment provider stub with webhooks; saga with compensation and reservation expiry; order status API.
3. Notification system: idempotent intake; priority bulkheads; provider stubs with failure injection; status webhooks.

**Technical requirements.** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x async + Alembic, PostgreSQL, Redis, Kafka (KRaft) or Redpanda, OpenTelemetry → Jaeger/Tempo + Prometheus, docker-compose, pytest + Testcontainers, k6 or Locust.

**Suggested structure.**

```
system-design-portfolio/
├── designs/
│   ├── 01-url-shortener.md   02-notifications.md   03-document-search.md
│   ├── 04-chat.md            05-order-platform.md  06-ai-knowledge.md
│   └── diagrams/
├── services/
│   ├── orders/
│   │   ├── app/
│   │   │   ├── api/ (catalog.py, checkout.py, orders.py, webhooks.py)
│   │   │   ├── domain/ (order.py state machine, inventory.py, errors.py)
│   │   │   ├── services/ (checkout_service.py, saga.py)
│   │   │   ├── repositories/ (orders_repo.py, inventory_repo.py, idempotency_repo.py)
│   │   │   ├── infra/ (db.py, cache.py, kafka.py, outbox_relay.py, telemetry.py, payment_client.py)
│   │   │   └── main.py
│   │   ├── migrations/ (Alembic)
│   │   └── tests/ (unit/ integration/ contract/ load/)
│   ├── notifications/ (same layering; workers/ router.py, sender.py)
│   └── provider-stubs/ (fake_payments.py, fake_email.py with failure knobs)
├── deploy/ (docker-compose.yml, otel-collector.yaml, prometheus.yml, grafana/)
└── reports/ (load-test-results.md, chaos-results.md)
```

**Milestones.**

1. Design docs for all six systems (peer review or self-review checklist).
2. Orders: schema + migrations + catalog API + cache + tests.
3. Orders: idempotent checkout + inventory reservation + outbox + relay.
4. Orders: payment stub + webhooks + saga compensation + reservation expiry job.
5. Notifications: intake + router + senders + priority bulkheads.
6. Observability: traces across HTTP and Kafka, RED dashboards, SLOs defined.
7. Load and chaos: k6 flash-sale test (hot SKU); kill relay; provider outage; Redis outage.
8. Write-up: results, bottlenecks found, fixes, trade-offs.

**Testing requirements.** Unit tests for state machines and pricing; integration tests with real Postgres/Redis/Kafka containers; concurrency test (200 concurrent checkouts on a SKU with stock 50 → exactly 50 orders); duplicate-delivery tests; idempotency replay tests; authorization tests (user A cannot read user B's order); load test with defined pass criteria.

**Definition of done.** All six designs complete; `docker compose up` brings both services up; test suite green in CI; zero oversells under concurrency test; end-to-end trace from checkout through notification visible; load test meets SLO (checkout p99 < 1.5 s at 80 orders/s locally) or documents the bottleneck; chaos report shows graceful degradation.

**Optional extensions.** Virtual waiting room for flash sales; multi-region read path; CDC with Debezium instead of polling relay; cell-based tenant isolation; adaptive concurrency limiter.

### 11. Testing Strategy

| Layer | What to test | Tools |
|---|---|---|
| Unit | Domain state machines, pricing, rate-limit math, key generation | pytest, Hypothesis |
| Parameterized | Retryable vs non-retryable status codes; state transitions | `pytest.mark.parametrize` |
| Integration | Repositories against real Postgres; Lua scripts on real Redis; Kafka produce/consume | Testcontainers (`testcontainers[postgres,redis,kafka]`) |
| Contract | Event schemas between producer/consumer; provider webhooks | JSON Schema / Pydantic models shared or versioned; Pact |
| Concurrency | No oversell; idempotency under simultaneous requests; locks | `asyncio.gather`, multiple processes |
| Negative | 429/503 paths; invalid idempotency reuse; authZ denial | HTTPX AsyncClient |
| Failure injection | Dependency slow/down; message duplication; relay crash | Toxiproxy, provider stubs with knobs |
| Performance | Throughput/latency SLOs; cold cache | k6, Locust |
| Security | BOLA, rate-limit bypass, webhook signature | pytest; OWASP ZAP for API scanning |

```python
# tests/integration/test_inventory_concurrency.py
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_no_oversell_under_concurrency(seed_sku_with_stock):
    sku = await seed_sku_with_stock(stock=50)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        async def checkout(i: int) -> int:
            r = await client.post("/v1/checkout", json={"sku": sku, "qty": 1},
                                  headers={"Idempotency-Key": f"k-{i:04d}",
                                           "Authorization": "Bearer test-user"})
            return r.status_code

        codes = await asyncio.gather(*(checkout(i) for i in range(200)))

    assert codes.count(201) == 50
    assert codes.count(409) == 150          # out of stock
```

```python
# tests/unit/test_retry_policy.py — Hypothesis property: backoff never exceeds cap
from hypothesis import given, strategies as st

from app.infra.backoff import full_jitter_delay


@given(attempt=st.integers(min_value=0, max_value=50))
def test_full_jitter_bounds(attempt: int) -> None:
    d = full_jitter_delay(attempt, base=0.1, cap=5.0)
    assert 0.0 <= d <= 5.0
```

Note on ASGI test transports: `httpx.AsyncClient(transport=ASGITransport(app=app))` does not run lifespan events by itself; use `asgi-lifespan`'s `LifespanManager` or FastAPI's `TestClient` as a context manager when lifespan resources are needed.

### 12. Engineering Scenarios

**Scenario 1 — "Make it faster" (FDE).** A customer says the document search you deployed "is too slow." *Investigate:* Which queries? p50 or p99? Since when? Traces split time between authZ group resolution, OpenSearch, hydration. *Options:* cache group memberships (with TTL ≤ acceptable revocation delay), reduce hydration via `_source` fields, add replicas. *Reasoning:* Never optimize before measuring; clarify "slow" into an SLI ("p95 < 500 ms for queries over tenants of ≤ 1M docs") and show before/after evidence.

**Scenario 2 — Flash sale in two weeks.** Marketing expects 50× normal checkout traffic for one SKU. *Investigate:* current hot-row throughput, provider rate limits, cache readiness. *Options:* inventory buckets, Redis admission tokens, waiting room, pre-scaled pods and DB, disable non-critical features (recommendations) via flags. *Trade-offs:* complexity vs one-time event; fairness of waiting room; cost of pre-scaling.

**Scenario 3 — Kafka or Celery?** A team wants Kafka for sending password-reset emails. *Expected reasoning:* job semantics (retries, delays, per-task ack) fit a task queue or SQS; Kafka adds operational load unless the organization already runs it and multiple consumers need the event. Prefer the simplest durable option the org can operate.

**Scenario 4 — Cross-region availability.** Leadership asks for "zero downtime even if a region fails." *Investigate:* RPO/RTO actually required and budget; which journeys. *Options:* active-passive with async replication (RPO seconds, RTO minutes), active-active for read paths only, multi-region databases (Aurora Global, Spanner, CockroachDB) with latency cost. *Reasoning:* translate "zero downtime" into numbers and cost; most businesses accept minutes of RTO for the write path.

**Scenario 5 — Rate limiting a paid API.** Customers on different plans; one customer's integration bug sends 10k req/s. *Options:* gateway per-API-key quotas, app-level cost-based limits (expensive endpoints cost more tokens), concurrency limits per tenant. *Reasoning:* protect shared resources first (fairness), give clear 429s with `Retry-After` and headers (`RateLimit-*` fields are an IETF draft), alert the customer success team.

### 13. Interview Preparation

#### Quick Questions (30–60 s)

**Q: How do you scale a FastAPI service?**
Strong answer: Keep the API stateless and scale horizontally — multiple Uvicorn processes per node or one per container with many replicas — behind an L7 load balancer. Use async I/O so each process handles many concurrent requests, move CPU-bound and slow work to workers, and protect shared bottlenecks (database connections via PgBouncer, caches for hot reads). Scale based on measured saturation, not guesses.
Why asked: tests whether you know the process/event-loop/thread-pool model and where the real bottleneck is.
Weak answer/trap: "Use async, it's faster" or "add more pods" without considering the DB connection limit.

**Q: Liveness vs readiness?**
Strong: Liveness = should the orchestrator restart me; it must not check dependencies. Readiness = should I receive traffic; it may check warm-up and critical dependencies, carefully to avoid fleet-wide unreadiness.
Trap: Putting a DB check in liveness, causing restart storms during DB maintenance.

**Q: What is backpressure?**
Strong: A mechanism by which a slow consumer limits the rate of producers — bounded queues, concurrency limits, rejecting with 429/503 — so overload causes fast, explicit rejection instead of unbounded queues and timeouts.
Trap: "Add a queue" — an unbounded queue just moves the problem.

**Q: Cache invalidation on update — update or delete the key?**
Strong: Delete after commit (and keep TTL as a safety net); updating risks concurrent writers leaving an older value.

**Q: Why not exactly-once?**
Strong: Across networks with independent failure, delivery can be at-most or at-least once; "exactly-once effect" is achieved with at-least-once delivery plus idempotent processing (or within a closed transactional system like Kafka transactions).

#### Intermediate Questions

**Q: Design the caching for a product page with 100:1 read:write.**
Strong: Cache-aside in Redis keyed by product (and locale/currency if relevant), TTL 5–15 min with jitter, delete on write after commit, single-flight for hot keys, negative caching for 404s with short TTL, CDN caching for anonymous pages with `stale-while-revalidate`. On Redis failure, fall back to DB with a concurrency limit to protect it. Measure hit ratio and DB load.
Why asked: practical caching judgment and failure thinking.
Trap: No answer for Redis failure or stampede.

**Q: How do you make POST /payments safe to retry?**
Strong: Require an `Idempotency-Key`; store `(client, key, request_hash, status, response)` with a unique constraint, claimed in the same transaction as the business write; replay stored responses; reject reuse with different payload; pass downstream idempotency keys to the payment provider; expire keys after a retention window.
Trap: "Check if a payment with same amount exists" (not a real key; race conditions).

**Q: Replication lag broke something. Explain and fix.**
Strong: Async replicas apply WAL later than the primary commits; reads routed to replicas immediately after a write may miss it. Fix with read-your-writes routing, LSN-based waits, or primary reads for that flow; monitor lag.

**Q: When would you choose Kafka over SQS/Celery?**
Strong: When events have multiple independent consumers, need replay/retention, high throughput, and per-key ordering. Choose a task queue for job semantics (retries, delays, priorities, per-message ack). Consider operational cost — managed services (MSK, Confluent) reduce but don't eliminate it.

**Q: How does async design affect a FastAPI service's capacity?**
Strong: `async def` lets one process multiplex thousands of I/O waits; capacity becomes bounded by downstream limits (pools, provider rate limits) rather than threads. But a single blocking call stalls every request in that process, and CPU-bound work gains nothing. Sync endpoints run in a 40-token thread pool by default.

#### Advanced Questions

**Q: Walk through what happens when the database becomes 10× slower for 60 seconds, and how your design limits the blast radius.**
Strong: By Little's Law in-flight DB work grows 10×; pool saturates; with a long pool timeout requests queue in memory, latency climbs, LB timeouts fire, clients retry → amplification. Design: short pool timeouts and statement timeouts, per-route concurrency limits, load shedding of low-priority endpoints, cached reads with stale-serving, retries only at one layer with jitter and budgets, circuit breaker around the DB for non-critical paths, and SLO burn alerts. After recovery, backlog drains because nothing was queued unboundedly.
Why asked: tests systems thinking about queues, metastability and graceful degradation.
Trap: "Autoscale the pods" — more pods means more connections against an already slow DB.

**Q: Implement a distributed lock. What can go wrong?**
Strong: First ask if it can be avoided via constraints/idempotency. If needed for efficiency, `SET NX PX` with a random token and compare-and-delete release. For correctness, use a lease with fencing token checked by the resource (e.g. version column) or a consensus system; explain process-pause and clock issues; Redis async replication can lose locks on failover.
Trap: Presenting Redlock as safe without fencing.

**Q: How would you partition a multi-tenant events table at 2 TB/month?**
Strong: Range partitioning by month for retention and pruning, with `(tenant_id, created_at)` indexes per partition; consider hash sub-partitioning or Citus distribution by `tenant_id` when write throughput exceeds one node; handle whale tenants with dedicated shards; partition management automation (pg_partman); queries must include partition keys for pruning.

**Q: Design trace propagation through Kafka.**
Strong: Inject W3C `traceparent`/`tracestate` into message headers at produce time (OTel propagators), extract on consume and start a consumer span linked (span link) or child of the producer span; batch consumers use span links to many producers; record messaging semantic attributes; correlate logs via trace IDs.

#### Coding Questions

1. Implement a token bucket in pure Python for a single process, with `try_acquire(cost)` using `time.monotonic()`; then explain what changes for multiple pods.
2. Write an `asyncio` function `gather_limited(coros, limit)` that runs coroutines with bounded concurrency and preserves result order.
3. Write a base62 encoder/decoder and a collision-retry loop for code generation using `INSERT ... ON CONFLICT DO NOTHING RETURNING`.
4. Implement a circuit breaker class (closed/open/half-open) with a failure-rate threshold and cool-down; write tests with a fake clock.
5. Write the SQL for an idempotent consumer and a `SKIP LOCKED` job queue.

Model solution for (2), because it appears constantly:

```python
import asyncio
from collections.abc import Awaitable, Iterable
from typing import TypeVar

T = TypeVar("T")


async def gather_limited(aws: Iterable[Awaitable[T]], limit: int) -> list[T]:
    sem = asyncio.Semaphore(limit)

    async def run(aw: Awaitable[T]) -> T:
        async with sem:
            return await aw

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(run(aw)) for aw in aws]
    return [t.result() for t in tasks]
```

Discuss: tasks are all created up front (memory O(n)); for millions of items use a bounded queue with N workers instead; `TaskGroup` cancels remaining work on first failure — sometimes you want `return_exceptions`-style behavior instead.

#### Scenario Questions

- "Your notification system sent 400k duplicate push notifications last night. Walk me through the investigation."
- "Checkout p99 doubled after a deploy with no code changes to checkout. What do you look at?" (Shared dependencies, connection pool sizes, new N+1 elsewhere saturating DB, noisy neighbor, config.)
- "A customer wants on-prem deployment of your AI knowledge service with no internet access. What changes?" (Self-hosted models/embeddings, offline updates, observability export, security review.)

### 14. Explain-It-at-Three-Levels

**Backpressure.**
*30 s:* Backpressure means the system pushes back when it's overloaded — bounded queues and concurrency limits that reject or slow producers — so overload produces quick, explicit errors instead of runaway latency and memory.
*2 min:* Every component has a capacity and a queue. If arrival rate exceeds service rate, the queue grows; by Little's Law latency grows with it. Without limits, requests pile up in kernel backlogs, the event loop, thread pools and connection pools until timeouts trigger retries, which add more load. Backpressure bounds each queue: semaphores around expensive operations, short pool timeouts, Uvicorn concurrency limits, bounded `asyncio.Queue`s, pull-based consumers on Kafka. When limits are reached we shed load — lower priority first — with 429/503 and `Retry-After`, and clients back off with jitter.
*Deep:* Discuss metastable failures (a trigger pushes the system into a state where retries sustain overload after the trigger ends), the multiplicative effect of layered retries, adaptive concurrency limits based on latency gradients, how pull-based consumers make lag a visible metric for autoscaling, and why autoscaling can worsen DB overload. Show the semaphore dependency and per-process vs global limits; tie to SLOs and error budgets.

**Idempotency.**
*30 s:* An operation is idempotent if doing it twice has the same effect as once. Because networks force retries and queues deliver at least once, every side-effecting operation needs a way to recognize duplicates — usually an idempotency key with a unique constraint.
*2 min:* GET/PUT/DELETE are idempotent by HTTP semantics; POST isn't. Clients send an `Idempotency-Key`; the server stores key, request hash and result atomically with the business change; duplicates replay the result. Consumers record processed message IDs in the same transaction as their effect. Downstream providers receive our key so their side effects dedupe too.
*Deep:* Concurrency handling (two simultaneous requests — unique index serializes them), key scoping per client, retention windows, payload mismatch semantics, interaction with sagas and compensations, and why "exactly-once" is an effect, not a delivery guarantee.

**Consistency choice.**
*30 s:* I choose consistency per operation: strong for invariants like money and inventory; read-your-writes for user-facing edits; eventual for derived views like search, analytics and caches.
*2 min / Deep:* CAP during partitions, PACELC latency trade-offs, replica lag, cache staleness, and concrete mechanisms (primary reads, LSN waits, versioned writes, CDC).

### 15. Knowledge Check

**Conceptual**

1. Why does adding more API pods sometimes make a database outage worse?
2. What is the difference between a lock and a lease, and why do fencing tokens matter?
3. Explain why FastAPI `BackgroundTasks` is inappropriate for sending invoices.
4. A Kafka topic has 12 partitions. You scale the consumer group from 12 to 30 pods. What happens?
5. When is an L4 load balancer a poor choice for WebSocket traffic, and what mitigates imbalance?

**Code reading**

6. What is wrong here?
```python
@app.get("/user/{uid}")
async def get_user(uid: int):
    cached = redis_sync.get(f"user:{uid}")
    if cached: return json.loads(cached)
    user = await repo.get(uid)
    redis_sync.set(f"user:{uid}", json.dumps(user))
    return user
```
7. What does this Lua-free rate limiter get wrong across pods?
```python
count = await redis.get(key) or 0
if int(count) >= LIMIT: raise HTTPException(429)
await redis.set(key, int(count) + 1, ex=60)
```
8. What happens to the in-flight request when this pod receives SIGTERM, assuming Uvicorn defaults and no `preStop`?

**Debugging**

9. All endpoints on one pod become slow simultaneously, including `/livez`, while other pods are fine. CPU on that pod is at 100% of one core. What is the likely cause and how do you confirm it?
10. Orders occasionally remain in `PENDING_PAYMENT` forever. Payments show as succeeded at the provider. Diagnose.

**Design / trade-off**

11. Should a URL shortener redirect with 301 or 302? Defend it.
12. For an internal AI knowledge service with 20 QPS, pgvector or a dedicated vector database?

#### Knowledge Check Answers

1. More pods → more connections and more concurrent queries against a saturated DB; retries multiply; connection storms on recovery. The bottleneck is shared, so horizontal scaling of the stateless tier increases pressure on it.
2. A lock implies exclusive ownership until released; a lease expires after a time, so the holder can lose it without knowing (process pause). A fencing token, increasing with each grant and checked by the resource, lets the resource reject stale holders.
3. BackgroundTasks run in the same process after the response with no persistence; a crash, deploy or OOM loses the task; no retries or visibility. Invoices require a durable queue with retries and idempotency.
4. Only 12 consumers receive partitions; 18 sit idle. Parallelism is capped by partition count. Rebalancing also occurs as pods join.
5. L4 balances connections, not messages; long-lived connections accumulate unevenly, especially after deploys (new pods get no existing connections). Mitigate with connection-count-aware L7 balancing, periodic graceful reconnects, and client reconnection with jitter.
6. A synchronous Redis client blocks the event loop; no TTL (stale forever); returns a dict from cache but possibly an ORM object otherwise (inconsistent types); no stampede protection; no failure handling if Redis is down.
7. Read-then-write is not atomic: concurrent requests on different pods read the same count and all pass; also resets the TTL each request (fixed window becomes rolling indefinitely). Use `INCR` + `EXPIRE NX` or a Lua script.
8. Uvicorn stops accepting new connections and waits for in-flight requests (up to the graceful timeout if configured), but the LB may still route new requests to the pod briefly because endpoint removal is asynchronous → connection refused/502 for those. A `preStop` sleep and readiness flip mitigate.
9. Blocking/CPU-bound code on the event loop of that pod's worker (e.g. one large request doing CPU work). Confirm with `py-spy dump`/`top` showing the loop thread in a CPU-heavy function, event-loop-lag metrics, and slow-callback logs.
10. Missed or failed webhooks (signature verification failure, endpoint 5xx, dropped by provider retries exhausted), or webhook processing not idempotent and crashed. Check provider's webhook delivery log, our webhook endpoint error logs/traces; add a reconciliation job that queries provider for pending orders older than N minutes.
11. Usually 302 (or 307): allows changing destination, disabling malicious links and counting clicks; 301 is cached permanently by browsers. Choose 301 only if analytics and edits do not matter and you want to minimize traffic.
12. pgvector: modest scale, one transactional store, ACL filters via SQL joins/arrays, fewer systems to secure. Revisit at hundreds of millions of vectors, very high QPS, or specialized features.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "`async def` makes my endpoint faster." | It improves concurrency for I/O waits; it does not speed up CPU work and one blocking call stalls the whole loop. |
| "Add a queue and the problem is solved." | Unbounded queues hide overload and convert it into latency and memory exhaustion; queues need bounds, lag monitoring and consumer scaling. |
| "Kafka gives exactly-once." | Exactly-once semantics apply within Kafka transactions; side effects outside Kafka need idempotent consumers. |
| "Read replicas scale writes." | Replicas scale reads; writes still go to one primary. |
| "Redis locks guarantee mutual exclusion." | TTL locks can expire under pauses; correctness needs fencing or database-enforced invariants. |
| "We'll use microservices for scalability." | Microservices are an organizational scaling tool; they add network failure modes. A modular monolith scales surprisingly far. |
| "99.99% because we have two replicas." | Correlated failures (same AZ, same deploy) break independence assumptions. |
| "Rate limit by IP." | NAT and IP rotation make IP a poor identity; limit by API key/principal and use IP as a secondary signal. |
| "Cache everything." | Caches add staleness, security leakage risks (tenant keys) and cold-start hazards; cache what's measured to be hot and expensive. |
| "Retries make the system reliable." | Retries without jitter, budgets and idempotency amplify outages and duplicate side effects. |

### 17. Cheat Sheet

**Numbers.** 1 day ≈ 10⁵ s · 1M/day ≈ 12/s · 99.9% ≈ 43 min/month · 99.99% ≈ 4.3 min/month · Little: L = λW · fan-out tail: 1 − (1 − p)ⁿ.

**FastAPI scaling knobs.**
```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 \
  --limit-concurrency 1000 --backlog 2048 --timeout-keep-alive 5 \
  --timeout-graceful-shutdown 20 --proxy-headers --forwarded-allow-ips="*"
anyio.to_thread.current_default_thread_limiter().total_tokens = 100   # in lifespan
create_async_engine(url, pool_size=5, max_overflow=5, pool_timeout=2, pool_pre_ping=True)
```

**Redis.** `SET k v NX PX 3000` (lock) · `INCR` + `EXPIRE k 60 NX` (fixed window, Redis 7) · `EVALSHA` for atomic multi-step · hash tags `{tenant}` for Cluster.

**SQL.** `FOR UPDATE SKIP LOCKED` (job queue) · `ON CONFLICT DO NOTHING` (dedupe) · `UPDATE ... WHERE version = :v` (optimistic) · `pg_try_advisory_xact_lock(k)` · `SET LOCAL statement_timeout = '2s'` · `SELECT now() - pg_last_xact_replay_timestamp()` (replica lag).

**Patterns.** Cache-aside + delete-on-write + TTL jitter + single-flight · Outbox + idempotent consumer · Saga + compensation + reconciliation · Bulkheads per priority · Timeout → retry (jittered, budgeted, idempotent only) → circuit breaker → fallback.

**Design template.** Requirements → estimates → API → data → architecture → scale → failures → security → observability → trade-offs.

**Observability.** RED for services, USE for resources, saturation = earliest warning (pool wait, queue lag, loop lag). Alert on SLO burn rate.

### 18. Completion Checklist

- [ ] I can convert availability targets to error budgets and compute composite availability.
- [ ] I can apply Little's Law to size pools, workers and concurrency limits.
- [ ] I can explain the FastAPI process → event loop → thread pool model and its scaling implications.
- [ ] I can implement cache-aside with stampede protection and explain invalidation races.
- [ ] I can implement a Redis token bucket and choose fail-open vs fail-closed.
- [ ] I can explain why distributed locks need fencing and when to avoid them.
- [ ] I can implement an outbox relay and idempotent consumer and test duplicate delivery.
- [ ] I can explain replication lag, failover behavior and choose partition keys.
- [ ] I can instrument a FastAPI service with OpenTelemetry and define SLOs.
- [ ] I can produce all six designs using the template, with numbers and trade-offs.
- [ ] I can debug loop blocking, pool exhaustion, retry storms and hot partitions.
- [ ] I can identify when *not* to use Kafka, microservices, sharding or distributed locks.

### 19. Further Research

**Essential**
- FastAPI docs — "Concurrency and async/await", "Deployment" (workers, Docker, HTTPS), "Lifespan Events": the official explanation of `def` vs `async def` and deployment concerns. <https://fastapi.tiangolo.com/async/> · <https://fastapi.tiangolo.com/deployment/>
- Uvicorn settings and deployment docs: what each flag (`--limit-concurrency`, `--backlog`, graceful shutdown) does. <https://www.uvicorn.org/settings/>
- SQLAlchemy 2.0 "Connection Pooling" and asyncio extension docs: pool sizing, pre-ping, async engine semantics. <https://docs.sqlalchemy.org/en/20/core/pooling.html>
- PostgreSQL docs — High Availability, Load Balancing, and Replication; Table Partitioning; Explicit Locking (advisory locks, `SKIP LOCKED`). <https://www.postgresql.org/docs/current/high-availability.html> · <https://www.postgresql.org/docs/current/ddl-partitioning.html>
- Google SRE Book — chapters on SLOs, handling overload, addressing cascading failures. <https://sre.google/sre-book/table-of-contents/>
- AWS Builders' Library — "Timeouts, retries and backoff with jitter", "Avoiding insurmountable queue backlogs", "Making retries safe with idempotent APIs". <https://aws.amazon.com/builders-library/>
- OpenTelemetry Python docs and FastAPI instrumentation. <https://opentelemetry.io/docs/languages/python/>

**Deeper Study**
- Martin Kleppmann, *Designing Data-Intensive Applications* (2nd ed. in progress/2025–2026): replication, partitioning, consistency, stream processing — the canonical text.
- Kleppmann, "How to do distributed locking" (fencing tokens and Redlock critique). <https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html>
- Bronson et al., "Metastable Failures in Distributed Systems" (HotOS 2021): why retry storms persist.
- Marc Brooker's blog on retries, jitter and backpressure. <https://brooker.co.za/blog/>
- microservices.io patterns — transactional outbox, saga, idempotent consumer. <https://microservices.io/patterns/>
- Kafka documentation on consumer groups, delivery semantics and transactions. <https://kafka.apache.org/documentation/>

**Practice**
- ByteByteGo / *System Design Interview* (Alex Xu) volumes 1–2: URL shortener, notification system, chat — compare your designs to theirs critically.
- "System Design Primer" GitHub repository: estimation tables and practice problems. <https://github.com/donnemartin/system-design-primer>
- k6 and Locust documentation for load testing your implementations.
- Testcontainers for Python: integration tests with real Postgres/Redis/Kafka. <https://testcontainers-python.readthedocs.io/>

### Unit Completion Standard

Before moving on, you must be able to: **explain** scalability, availability, consistency and backpressure with numbers and per-operation reasoning; **implement** cache-aside with stampede protection, an atomic Redis rate limiter, an outbox relay with idempotent consumers, and bounded-concurrency load shedding in FastAPI; **test** these with real containers, concurrency tests and duplicate-delivery tests; **debug** event-loop blocking, pool exhaustion, retry storms, replica lag and hot partitions using traces, metrics and profilers; and **defend**, in a 45-minute interview, a complete design for any of the six practice systems — including estimates, data model, failure handling, security and trade-offs against simpler alternatives.
