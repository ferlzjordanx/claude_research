# Unit 8 — Microservices and Distributed Systems

## 1. What This Unit Teaches

Once a system has more than one process that talks over a network, every call can be slow, fail, or succeed without you hearing about it. An FDE meets this on day one: the customer's ERP, a payment provider, an identity provider, an LLM API. This unit teaches how to design and build services that stay correct when their dependencies misbehave **[JD-Required: microservices, distributed systems, scalability, reliability]**, and how to move work through queues and events **[JD-Preferred: messaging/event-driven]**:

- monolith vs modular monolith vs microservices, and when *not* to split;
- service boundaries, bounded contexts and database-per-service;
- synchronous calls (REST, gRPC) vs asynchronous messaging (SQS/SNS, Kafka, RabbitMQ);
- the fallacies of distributed computing;
- timeouts, retries with exponential backoff and jitter, retry budgets;
- idempotency keys, so a retry never charges a customer twice;
- circuit breakers, bulkheads, rate limiting and backpressure;
- at-least-once delivery, idempotent consumers and dead-letter queues;
- the transactional outbox, sagas vs two-phase commit, eventual consistency, CAP/PACELC;
- gateways, discovery, service mesh, load balancing, caching, contract versioning and health checks.

The project builds two FastAPI services, **orders** and **payments**, that survive a payments outage without losing an order or double-charging anyone, plus an outbox relay and an idempotent event consumer.

## 2. Mental Model

```text
 POST /orders {customer, amount}
   │
   ▼
 orders ── BEGIN ─ INSERT order(pending, payment_key=K)
   │              INSERT outbox(OrderCreated)          ─ COMMIT
   │
   │  PaymentsClient.charge(K)       every attempt sends the SAME K
   │   ├─ breaker open?  → 503 now, no network call         (fail fast)
   │   ├─ POST /payments  Idempotency-Key: K   timeout 2s
   │   │    timeout / 5xx → backoff + jitter → retry      (≤ 3 tries)
   │   │    429           → wait Retry-After → retry
   │   │    4xx           → final answer, no retry
   │   ▼
 payments ── key K seen?  same body → replay stored answer
   │                       new body  → 422
   │          new         → charge once, store answer under K
   ▼
 orders ── BEGIN ─ UPDATE order SET status=paid
   │              INSERT outbox(OrderPaid)             ─ COMMIT
   ▼
 relay ── reads outbox ─► broker (at-least-once) ─► notifications
                                    duplicates? ──► dedupe by event id
```

Three ideas carry the whole unit:

1. **The network is a liar.** A timeout does not mean "it failed". It means "you don't know". Design every remote call for three outcomes: success, failure, and unknown.
2. **Make retries safe before you make them automatic.** Retries without idempotency turn an outage into duplicate charges. Idempotency keys on calls and dedupe on consumers make "do it again" harmless.
3. **Never write to two systems and hope.** Writing the database and then the broker (a "dual write") loses or invents events on crash. Write one transaction (the outbox) and let a relay deliver at least once.

## 3. Brief Theory

### 3.1 Monolith, modular monolith, microservices

**What it is.** A *monolith* is one deployable unit. A *modular monolith* is one deployable unit with strict internal modules (each owns its tables and exposes an interface). *Microservices* are independently deployable services, each owning its data, talking over the network.

**Why it exists.** Microservices let many teams ship independently and scale parts separately. They cost you network calls, partial failure, distributed data and much harder debugging.

**Why it matters.** "Should we split this into microservices?" is a common customer question and a common interview question. The strong answer is usually "not yet".

**How it works.**

| | Monolith | Modular monolith | Microservices |
|---|---|---|---|
| Deploy | one unit | one unit | many, independent |
| Calls between parts | function call | function call via module API | network (fails, slow) |
| Transactions | one DB transaction | one DB transaction | sagas, outbox, eventual consistency |
| Team scaling | painful past ~2 teams | good to several teams | good to many teams |
| Ops cost | low | low | high (CI/CD, tracing, mesh, on-call per service) |
| Best when | small team, new product | most business apps | many teams, very different scaling or compliance needs |

When **not** to split: one small team; the domain is still changing (boundaries will be wrong); no CI/CD, tracing or on-call maturity yet; the "services" would share one database; or the real problem is a slow query. Start with a modular monolith and extract a service when a module has a clear reason: a different scaling profile, a separate team, or a compliance boundary (payments, PII). See Martin Fowler's [MonolithFirst](https://martinfowler.com/bliki/MonolithFirst.html) **[External]**.

**Conway's law:** systems mirror the communication structure of the organization that builds them. Service boundaries that cut across team boundaries create constant cross-team coordination. Align services with teams (the "inverse Conway maneuver").

### 3.2 Service boundaries, bounded contexts and data ownership

**What it is.** A *bounded context* (from Domain-Driven Design) is a part of the business where a word has one meaning. "Order" in sales (what was bought) is not "order" in fulfilment (what to ship). A good service boundary follows a bounded context.

**Why it exists.** Boundaries drawn along technical layers ("the database service", "the validation service") create chatty, tightly coupled services that must deploy together: a *distributed monolith*.

**Why it matters.** Wrong boundaries are the most expensive microservices mistake. They show up as synchronous call chains five services deep and "we have to release these four together".

**How it works.**

- **Database per service.** Each service owns its tables. Nobody else reads or writes them directly; they use the service's API or its events. In this project orders and payments have separate stores, and the notifications consumer has its own `processed_events` table.
- **High cohesion, low coupling.** Things that change together live together. If two services always change together, merge them.
- **Data you need from another service:** call its API (fresh, but coupled at runtime), or keep a local read-only copy updated from its events (decoupled, but eventually consistent).
- **Shared libraries:** fine for cross-cutting helpers (this project shares `common/problems.py`). Sharing domain models couples release cycles.

### 3.3 Synchronous vs asynchronous communication

**What it is.** *Synchronous*: the caller waits for an answer (REST over HTTP, [gRPC](https://grpc.io/docs/) over HTTP/2). *Asynchronous*: the sender puts a message on a queue or stream and moves on; a consumer processes it later.

**Why it exists.** Sync is simple and gives an immediate answer. Async decouples availability (the producer works while the consumer is down), absorbs bursts, and fans out one event to many consumers.

**Why it matters.** Every sync call adds the callee's latency *and* its failure rate to yours. A chain of five services at 99.9% each is at best 99.5% available.

**How it works.** Use sync when the caller needs the answer now (authorize a payment, read a price). Use async when the work can finish later (send a receipt, update search, recompute analytics).

| | Amazon SQS / SNS | Apache Kafka | RabbitMQ |
|---|---|---|---|
| Model | SQS: queue (each message to one consumer). SNS: pub/sub fan-out to queues, HTTP, email | Partitioned, replicated append-only log; consumer groups track offsets | Broker with exchanges routing to queues (AMQP) |
| Delivery | At-least-once (standard); FIFO queues add ordering and deduplication within a 5-minute window | At-least-once by default; idempotent producer and transactions give exactly-once *within Kafka* | At-least-once with manual acks and publisher confirms |
| Ordering | None (standard); per message group (FIFO) | Per partition (choose the key) | Per queue, single consumer |
| Replay | No (deleted after ack) | Yes, by offset, for the retention period | No (deleted after ack); streams add replay |
| Ops | Fully managed **[Provider-specific]** | Heavy self-hosted; managed: Amazon MSK, Confluent | Moderate; managed options exist |
| Typical use | Task queues, decoupling on AWS, fan-out | Event streaming, event sourcing, analytics, CDC | Task queues, flexible routing, RPC-ish patterns |

References: [SQS](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html), [SNS](https://docs.aws.amazon.com/sns/latest/dg/welcome.html), [Kafka](https://kafka.apache.org/documentation/), [RabbitMQ reliability](https://www.rabbitmq.com/docs/reliability) **[External]**.

### 3.4 The fallacies of distributed computing

**What it is.** Eight false assumptions (Deutsch and others, Sun Microsystems, 1990s): the network is reliable; latency is zero; bandwidth is infinite; the network is secure; topology doesn't change; there is one administrator; transport cost is zero; the network is homogeneous.

**Why it matters.** Nearly every pattern in this unit answers one of them. Timeouts and retries answer "reliable" and "zero latency". Service discovery answers "topology doesn't change". mTLS answers "secure". Interviewers love asking which fallacy a bug came from.

### 3.5 Timeouts everywhere

**What it is.** An upper bound on how long you wait for any remote operation: connect, read, the whole request, and the end-to-end deadline of the user request.

**Why it exists.** Without a timeout, a slow dependency holds your threads, connections and memory until you run out. Then *you* are down too: a cascading failure.

**Why it matters.** Most default HTTP clients wait far too long or forever. `httpx` defaults to 5 seconds ([timeouts](https://www.python-httpx.org/advanced/timeouts/)); `requests` has no default at all.

**How it works.**

- Set a timeout on every call (`httpx.Timeout(2.0)` in this project). Base it on the dependency's p99 latency plus margin, not a guess.
- Budget the deadline: if the user request has 3 s, retries must fit inside it. Propagate the remaining deadline downstream (gRPC deadlines do this natively).
- A timeout is an **unknown outcome**. The server may still finish the work. That is why the project's retries reuse the same idempotency key.
- Time out at every layer: client, load balancer, gateway, database (`statement_timeout`), and queue visibility.

### 3.6 Retries, exponential backoff, jitter and retry budgets

**What it is.** Trying a failed call again, after a delay that grows with each attempt (*exponential backoff*), randomized (*jitter*), with a cap on how many retries the whole system may add (*retry budget*).

**Why it exists.** Many failures are transient: a pod restarting, a dropped connection, brief overload. One retry often succeeds.

**Why it matters.** Retries are also the most common cause of retry storms. Three layers each retrying 3 times turn one user request into up to 27 calls to an already struggling service.

**How it works.**

```text
 attempt n ceiling = min(max_delay, base * 2^(n-1))
 full jitter:  sleep = random(0, ceiling)

 base=0.2s max=2s:  n=1 → 0..0.2s   n=2 → 0..0.4s   n=3 → 0..0.8s
 without jitter, 1,000 clients that failed together retry together
 with jitter they spread out and the service can recover
```

| Retry | Do not retry |
|---|---|
| Connection errors, timeouts (only if the call is idempotent) | 400, 401, 403, 404, 409, 422: the same request will fail the same way |
| 500, 502, 503, 504 | Business declines (402 "card declined") |
| 429, after waiting `Retry-After` ([RFC 9110](https://www.rfc-editor.org/rfc/rfc9110#field.retry-after)) | Anything non-idempotent without a key |

- Retry at **one** layer, usually the one closest to the failing call. Others pass the error up.
- **Retry budget:** allow retries only while they are a small share of traffic (for example, at most 10% of requests). Envoy and gRPC implement this ("retry throttling") **[External]**.
- Cap `Retry-After` too: a server asking for 600 s should not hold your request for 10 minutes.

The AWS Builders' Library article [Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/) is the classic reference **[External]**.

### 3.7 Idempotency keys

**What it is.** An operation is *idempotent* if doing it twice has the same effect as doing it once. An *idempotency key* is a client-generated unique ID sent with a non-idempotent request (`POST /payments`) so the server can recognize a repeat and return the first result instead of acting again.

**Why it exists.** `GET`, `PUT` and `DELETE` are idempotent by HTTP semantics; `POST` is not. Yet `POST` is exactly what you need to retry after a timeout.

**Why it matters.** It is the difference between "a customer was charged twice" and "a retry was harmless". Stripe requires it ([idempotent requests](https://docs.stripe.com/api/idempotent_requests)), and the IETF is standardizing the `Idempotency-Key` header ([draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)) **[External]**.

**How it works.**

```text
 key K, body hash H
 K unknown              → claim K (in progress), do the work,
                          store (status, body) under K, respond
 K known, same H, done  → replay stored response (no new work)
 K known, other H       → 422  (key reused for a different request)
 K known, in progress   → 409  (concurrent duplicate: retry later)
 missing / malformed K  → 400
```

- **The client generates the key once per logical operation** and reuses it for every retry. This project stores it on the order row (`payment_key`), so even a retry hours later reuses it.
- **Store the response, including failures that are final** (a decline). A replay of a decline must not suddenly succeed.
- **Claim atomically:** a `UNIQUE` constraint on the key and `INSERT … ON CONFLICT DO NOTHING`, not "select then insert".
- **Expire keys** after a window (Stripe: 24 hours) and expire stuck "in progress" claims.
- Natural keys work too: "one payment per order_id" is a unique constraint.

### 3.8 Circuit breakers and bulkheads

**What it is.** A *circuit breaker* wraps calls to a dependency and, after repeated failures, stops calling it for a while, failing fast instead. A *bulkhead* isolates resources (connection pools, threads, concurrency limits) per dependency so one slow dependency cannot use them all.

**Why it exists.** Retrying a dead service wastes your resources and its recovery time. Failing fast keeps your service responsive and gives the dependency room to recover.

**Why it matters.** Breakers turn "every request waits 6 s then fails" into "every request fails in 1 ms with a clear message", which is better for users, threads and on-call engineers.

**How it works.**

```text
           failures ≥ threshold
  CLOSED ─────────────────────────► OPEN ── calls fail fast (503)
    ▲                                 │
    │ probe succeeds                  │ reset timeout elapsed
    │                                 ▼
    └──────────────────────────── HALF-OPEN ── one probe call
                probe fails ──► OPEN (timer restarts)
```

- Count only failures that mean "the dependency is unhealthy": timeouts, connection errors, 5xx. A 4xx is a healthy service saying no. A 429 is backpressure, not a fault.
- Allow exactly **one** probe in half-open, or a recovering service gets the full load at once.
- Use the breaker state in dashboards and readiness *reports* (not readiness *failures*, see §3.17).
- Bulkheads in Python: a separate `httpx` connection pool per dependency (`limits=httpx.Limits(max_connections=20)`) and an `asyncio.Semaphore` around calls.

References: [Fowler: CircuitBreaker](https://martinfowler.com/bliki/CircuitBreaker.html), Azure patterns: [circuit breaker](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker), [bulkhead](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead) **[External]**.

### 3.9 Rate limiting, backpressure and load shedding

**What it is.** *Rate limiting* caps how many requests a client may make (token bucket, sliding window) and answers `429 Too Many Requests` with `Retry-After`. *Backpressure* is any signal that tells producers to slow down (429, a full bounded queue, TCP flow control). *Load shedding* rejects work early when the service is over capacity.

**Why it matters.** A service that accepts everything under overload gets slower for everyone and finally falls over. Rejecting 10% of requests quickly keeps the other 90% fast. See Google SRE: [Handling overload](https://sre.google/sre-book/handling-overload/) **[External]**.

**How it works.** Rate limit at the edge (API gateway, per API key or tenant) and inside services for expensive operations. Use bounded queues and concurrency limits. Clients honor `Retry-After` (this project's client does, with a cap).

### 3.10 Delivery semantics and idempotent consumers

**What it is.** *At-most-once*: a message may be lost, never duplicated. *At-least-once*: never lost, may be duplicated. *Exactly-once*: neither, which across systems with side effects is not achievable by the transport alone.

**Why it exists.** A consumer can crash after doing the work but before acknowledging the message. The broker must choose: redeliver (duplicate) or drop (loss). Almost every production broker redelivers.

**Why it matters.** "We use Kafka exactly-once" does not stop your consumer from sending an email twice. Exactly-once *effects* come from at-least-once delivery plus an **idempotent consumer**.

**How it works.**

- Every event carries a unique `event_id`. The consumer inserts it into `processed_events` **in the same transaction** as its side effect. A duplicate violates the primary key and is skipped.
- Ack (or commit the offset) only **after** the transaction commits.
- SQS hides an in-flight message for the *visibility timeout*; no ack in time and it comes back ([docs](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html)). This project's in-memory broker does the same.
- After N failed deliveries, move the message to a **dead-letter queue (DLQ)** and alert. A poison message must not block the queue forever.
- External side effects (email, a partner API) need their own idempotency key, for example the event id.

### 3.11 The transactional outbox

**What it is.** Instead of writing the database and then publishing to the broker, the service writes the event into an `outbox` table **in the same transaction** as the business change. A separate relay reads unpublished rows, publishes them, and marks them sent.

**Why it exists.** The *dual-write problem*: commit then publish, and a crash in between loses the event; publish then commit, and a rollback leaves an event for an order that never existed.

**Why it matters.** Lost "OrderPaid" events mean no receipt, no shipment, wrong analytics, and nobody notices until a customer complains.

**How it works.**

```text
 BEGIN
   INSERT INTO orders ...                     ┐ both or neither
   INSERT INTO outbox (id, type, payload) ... ┘
 COMMIT
 relay loop:  SELECT … WHERE published_at IS NULL ORDER BY created_at
              publish(event) → UPDATE … SET published_at = now()
              crash between the two → published again → consumer dedupes
```

- Multiple relay replicas on Postgres: `SELECT … FOR UPDATE SKIP LOCKED`.
- Alternative: **change data capture** (CDC) tails the database log, for example [Debezium](https://debezium.io/documentation/) **[External]**.
- Pattern reference: [microservices.io: transactional outbox](https://microservices.io/patterns/data/transactional-outbox.html).

### 3.12 Sagas vs two-phase commit

**What it is.** *Two-phase commit (2PC)* coordinates one atomic transaction across several databases (prepare, then commit). A *saga* splits a business transaction into local transactions, each publishing an event or command; if a later step fails, earlier steps are undone by **compensating actions** (refund, release stock).

**Why it exists.** 2PC blocks when the coordinator fails, needs every participant to support it, and couples availability. Most cloud services and brokers do not support it.

**Why it matters.** "Place order → charge → reserve stock → ship" spans services. You need a story for "the charge succeeded but stock is gone".

**How it works.**

| | Orchestration | Choreography |
|---|---|---|
| Control | A coordinator tells each service what to do next | Each service reacts to others' events |
| Visibility | The flow is in one place; easy to see state | The flow is spread across services |
| Coupling | Coordinator knows every step | Services know only events |
| Good for | Longer flows, complex compensation (AWS Step Functions, Temporal **[External]**) | Short flows with few steps |

Compensations are business operations, not rollbacks: a refund is visible on the customer's statement. Design them, make them idempotent, and log them. Reference: [microservices.io: saga](https://microservices.io/patterns/data/saga.html).

### 3.13 Eventual consistency, CAP and PACELC

**What it is.** *Eventual consistency*: replicas or services may disagree for a while, but converge if no new updates arrive. **CAP**: during a network **P**artition you must choose **C**onsistency (refuse some requests) or **A**vailability (answer, possibly with stale data). **PACELC** adds: **E**lse, in normal operation, you trade **L**atency against **C**onsistency.

**Why it matters.** The order is "paid" in the orders service before the receipt exists in notifications. The UI and the business must accept that window or the design must avoid it.

**How it works.** Make the window visible and short: show "payment pending", poll or push status, read your own writes from the owning service, and give every event a timestamp and version. Strong consistency inside one service's database is still the default; eventual consistency is for data that crosses service boundaries.

### 3.14 API gateway, service discovery, service mesh and load balancing **[External]**

- **API gateway**: a single entry point for clients that handles TLS, authentication, rate limits, routing and request size limits (AWS API Gateway, Kong, Kubernetes [Gateway API](https://gateway-api.sigs.k8s.io/)). Keep business logic out of it.
- **Service discovery**: how `orders` finds `payments`. On Kubernetes a [Service](https://kubernetes.io/docs/concepts/services-networking/service/) gives a stable DNS name (`http://payments:8001`, the same name docker-compose gives in this project). Elsewhere: AWS Cloud Map, Consul.
- **Load balancing**: round robin, least connections or consistent hashing, at L4 (TCP) or L7 (HTTP). Kubernetes Services balance across ready pods only, which is why readiness matters.
- **Service mesh** ([Istio](https://istio.io/latest/docs/), Linkerd): a sidecar or node proxy that adds mTLS, retries, timeouts, circuit breaking and telemetry without code changes. Powerful, but it adds operational weight, and mesh retries plus code retries multiply. Decide which layer owns retries.

### 3.15 Caching and consistency

**What it is.** Keeping a copy of data closer to the reader (in process, Redis, CDN) to cut latency and load.

**Why it matters.** A cache is a second copy, so it can be stale. "Two hard things in computer science: cache invalidation and naming things."

**How it works.** Cache-aside with a TTL is the default (Unit 3). Invalidate or update on the owning service's events (`OrderPaid` → delete `order:42`). Key caches by tenant and user where data is private. Protect against stampedes (one rebuild per key, jittered TTLs). Never cache authorization decisions longer than you can tolerate a revoked user keeping access.

### 3.16 Versioning events and contracts

**What it is.** Services and consumers deploy independently, so old and new versions run side by side. Contracts (APIs, event schemas) must stay compatible.

**How it works.**

- Additive changes only: add optional fields; never rename or remove in place. Consumers ignore unknown fields ("tolerant reader").
- Put a `version` on every event (this project's `Message.version`). A consumer that does not support a version fails loudly and the message goes to the DLQ instead of being misread.
- Breaking change: publish v2 alongside v1, migrate consumers, then retire v1 (expand and contract).
- Schema registries (Confluent, AWS Glue) and consumer-driven contract tests (Pact) automate the checks **[External]**.

### 3.17 Health and dependency checks

**What it is.** *Liveness*: is the process alive (restart it if not)? *Readiness*: can it serve traffic now (remove it from the load balancer if not)? *Startup*: has it finished starting? See [Kubernetes probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/).

**Why it matters.** If orders' readiness checked payments, a payments outage would mark every orders pod unready, and the load balancer would have nowhere to send traffic, even for requests that do not need payments. That is a cascading failure built by a health check.

**How it works.** Liveness checks only the process (`GET /health`). Readiness checks what *this* service owns, its database (`GET /health/ready`), and *reports* dependency state (circuit open, outbox backlog) without failing on it. Dependency health belongs in dashboards and alerts.

## 4. Application in a Real System

A retail customer runs an order service that calls a payment provider. During a provider incident, latency jumped to 8 seconds, the order service's 5-second timeout fired, and a retry loop posted the charge again with no idempotency key. Some customers were charged two or three times. The FDE engagement, in one week:

- **Day 1:** reproduce in a test. A fake transport lets the request reach payments and then drops the response. The test fails: two charges.
- **Day 2:** add `Idempotency-Key` handling to the payments facade, generate the key once per order and store it on the order row. The test passes: one charge, two requests.
- **Day 3:** retries only on retryable errors with full jitter; a circuit breaker so the next outage fails fast; 503 problem+json with the order ID so the UI shows "payment pending" instead of an error.
- **Day 4:** move "send receipt" from an inline call to an outbox event and an idempotent consumer, so a crash no longer loses or duplicates receipts.
- **Day 5:** a fault-injection drill in staging (`APP_FAULT_ERROR_RATE=0.5`), dashboards for retries, breaker state and outbox lag, and a written incident summary.

**Alternatives and trade-offs.** A queue in front of payments (async charging) removes the user's wait but requires a "pending" UX and a saga for failures. A service mesh can add retries and breakers without code, but it cannot add idempotency: that needs application knowledge.

## 5. Implementation

### 5.1 An idempotent payments endpoint

```python
replay = store.begin(idempotency_key, fingerprint(body.model_dump()))
if replay is not None:
    return _respond(replay, replayed=True)    # Idempotent-Replayed
try:
    stored = _process(body, settings, ledger)  # charge or 402 decline
except Exception:
    store.abandon(idempotency_key)  # nothing was charged: free the key
    raise
store.complete(idempotency_key, stored)
return _respond(stored, replayed=False)
```

`store.begin` holds the rules from §3.7 under a lock:

```python
with self._lock:
    entry = self._entries.get(key)
    if entry is None:
        self._entries[key] = _Entry(body_hash, None)   # claim
        return None
    if entry.fingerprint != body_hash:
        raise IdempotencyMismatch(...)                 # 422
    if entry.response is None:
        raise IdempotencyInProgress(...)               # 409
    return entry.response                              # replay
```

The fingerprint is a SHA-256 of the body serialized with sorted keys, so `{"a":1,"b":2}` and `{"b":2,"a":1}` match.

### 5.2 Backoff and "is this retryable?"

```python
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

def backoff(self, attempt: int, rng: Callable[[], float]) -> float:
    ceiling = min(self.max_delay_s,
                  self.base_delay_s * 2.0 ** (attempt - 1))
    return rng() * ceiling                      # full jitter

def is_retryable(response, error) -> bool:
    if error is not None:     # timeouts, connection errors
        return isinstance(error, httpx.TransportError)
    return response.status_code in RETRYABLE_STATUS
```

`rng` and `sleep` are injected, so tests pass `lambda: 0.5` and a fake sleep that records delays. No test waits.

### 5.3 The retry loop: one key, breaker-aware

```python
send_headers = {**(headers or {}), "Idempotency-Key": key}
for attempt in range(1, self.policy.max_attempts + 1):
    if not self.breaker.allow_request():
        raise CircuitOpenError("payments circuit is open")
    try:
        response = await self._http.post(
            "/payments", json=body, headers=send_headers)
    except httpx.HTTPError as exc:
        error = exc
    if ok(response):
        self.breaker.record_success(); return response.json()
    if not is_retryable(response, error):
        self.breaker.record_success()       # healthy service said no
        raise PaymentRejected(...)
    delay = self.policy.backoff(attempt, self._rng)
    if is_429(response):                    # backpressure, not a fault
        delay = retry_after(response)       # capped
    else:
        self.breaker.record_failure()
    if attempt < self.policy.max_attempts:
        await self._sleep(delay)
raise PaymentsUnavailable(f"gave up after {n} attempts: {last}")
```

(Condensed; the full version is in `orders/payments_client.py`.) The order service maps `PaymentsUnavailable` and `CircuitOpenError` to **503 problem+json** with `order_id`, `order_status: "pending"` and `Retry-After`. The order is not lost; `POST /orders/{id}/pay` retries later with the same key.

### 5.4 Circuit breaker with an injectable clock

```python
@property
def state(self) -> BreakerState:
    if (self._state is BreakerState.OPEN
            and self._clock() - self._opened_at
            >= self.reset_timeout_s):
        self._state = BreakerState.HALF_OPEN   # lazily, on read
        self._probe_in_flight = False
    return self._state

def allow_request(self) -> bool:
    state = self.state
    if state is BreakerState.CLOSED:
        return True
    if state is BreakerState.HALF_OPEN and not self._probe_in_flight:
        self._probe_in_flight = True           # exactly one probe
        return True
    return False
```

Tests move a `FakeClock` forward 30 seconds instead of sleeping.

### 5.5 Order and outbox in one transaction

```python
with self._sessions.begin() as session:   # commit or roll back
    order = OrderRow(..., status="pending",
                     payment_key=f"order-{uuid.uuid4().hex}")
    session.add(order)
    session.flush()                       # order.id assigned
    session.add(new_outbox_event(str(order.id), "OrderCreated",
                                 {"order_id": order.id, ...}))
```

The relay publishes then marks each row; a crash between the two re-publishes (at-least-once):

```python
for row in rows:                  # WHERE published_at IS NULL
    broker.publish(TOPIC, Message(row.id, row.event_type,
                                  row.version,
                                  json.loads(row.payload)))
    row.published_at = utcnow()
    session.commit()
```

### 5.6 An idempotent consumer

```python
try:
    with self._sessions.begin() as session:
        session.add(ProcessedEvent(event_id=message.id))
        session.flush()        # duplicate id → IntegrityError
        session.add(NotificationRow(order_id=..., kind="receipt"))
except IntegrityError:
    return False               # already processed: skip
return True
# consume_once(): handle(...) then broker.ack(delivery)
```

The dedupe record and the side effect commit together. Ack happens only after the commit.

### 5.7 Testing "charged, but the response was lost"

```python
class Recorder(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        self.requests.append(request)
        response = await self.inner.handle_async_request(request)
        if self.lose_responses > 0:      # request DID reach payments
            self.lose_responses -= 1
            raise httpx.ReadTimeout("response lost", request=request)
        return response

recorder = Recorder(httpx.ASGITransport(app=payments_app),
                    lose_responses=1)
# POST /orders → status "paid", 2 requests, 1 key, 1 charge
```

`httpx.ASGITransport` runs the real payments app in-process, and `httpx.MockTransport` scripts failures ([transports](https://www.python-httpx.org/advanced/transports/)). Together they test distributed failure in milliseconds.

## 6. How It Connects to the Rest of the System

```text
 Unit 8 resilient services
   ├─ uses: async + typed Python (U1), FastAPI factories and
   │        problem+json (U2), SQL transactions (U3)
   ├─ the SPA shows "payment pending" for 503 + order_id (U4/U5)
   ├─ each service is a container; probes = /health, /health/ready;
   │  Service DNS replaces docker-compose names (U6)
   ├─ CI runs the fault tests on every change (U7)
   ├─ LLM APIs are dependencies too: timeouts, retries on 429/529,
   │  breakers, idempotent tool calls (U9-U10)
   ├─ retries, breaker state, outbox lag, DLQ depth become
   │  metrics, traces and alerts (U11)
   └─ incident communication and drills are FDE work (U12)
```

## Cross-Unit System Map — Units 1–8

```text
 ┌──────────────── Browser: React SPA (U4/U5) ────────────────┐
 │ API client · JWT · X-Request-ID · problem+json UI   [F1]   │
 └─────────────────────────────┬──────────────────────────────┘
                               │ HTTPS
 ┌─────────────────────────────▼──────────────────────────────┐
 │ Edge: CDN + API gateway / Gateway API (U6/U8)              │
 │ TLS · token check · rate limit 429 · routes · timeout [F2] │
 └─────────────────────────────┬──────────────────────────────┘
                               │ REST + deadline
 ┌─────────────────────────────▼────────┐
 │ orders (FastAPI, U2/U5/U8)           │  REST + Idempotency-Key
 │ timeout · retry+jitter · breaker [F3]│─────────────┐
 │ order + outbox, one transaction  [F4]│             │
 └───────┬────────────────┬─────────────┘  ┌──────────▼───────────┐
         │ SQL            │ relay          │ payments (U8)        │
 ┌───────▼──────┐  ┌──────▼─────────────┐  │ key → replay    [F5] │
 │ orders DB    │  │ broker: SQS/Kafka/ │  │ own DB: ledger       │
 │ Postgres(U3) │  │ RabbitMQ      [F6] │  └──────────────────────┘
 └──────────────┘  └──────┬─────────────┘
  Redis cache (U3):       │ at-least-once
  cache-aside, TTL,       ▼
  evict on events    consumers: notifications, inventory
                     dedupe by event id · DLQ after N tries [F7]

 Platform (U6): every box is a container on Kubernetes.
   Deployment + Service (DNS discovery, load balancing to ready
   pods) · probes /health and /health/ready · HPA · Secrets → APP_*
 Delivery (U7): lint → test (incl. fault tests) → build image →
   deploy → smoke test → automatic rollback on failed checks
 Observability (U11 preview): request ID → trace across services;
   metrics: retries, breaker state, p99, outbox lag, DLQ depth

 Where failures are handled
   [F1] show message + ref ID; "payment pending" on 503
   [F2] reject early (401/429); per-route timeouts
   [F3] bounded retries on retryable errors; fail fast when open
   [F4] no lost and no phantom events
   [F5] a retry never charges twice
   [F6] redelivery instead of loss
   [F7] duplicates are no-ops; poison messages park in the DLQ
```

**How to use this map in an interview.** For any "design an e-commerce / booking / payments system" question, draw these boxes, then walk one request and say at each arrow: the timeout, who retries, what makes the retry safe, and what the user sees if it still fails. That is the reliability conversation interviewers want.

## FDE Scenario 7 — "Customers were charged twice during yesterday's outage"

**Stakeholder (customer VP of Operations, with Finance on the call):** "During yesterday's payment provider slowdown, support got 140 tickets about double charges. Finance needs a list of affected customers by noon, and I need to know it cannot happen again."

- *Stay calm and scope:* acknowledge the impact, separate the two asks (a refund list today; a permanent fix), agree on an update cadence and on who owns customer communication.
- *Investigate with data, not guesses:*
  - query the payments ledger: `GROUP BY order_id HAVING COUNT(*) > 1` in the incident window;
  - reconcile against the provider's settlement report (the source of truth for money);
  - read orders' logs by request ID: timeouts, then retries;
  - read the client code: a new key per attempt, or no key at all?
- *Contain:* until the fix ships, disable automatic payment retries (fail to "pending" instead) or lower attempts to one. Turn off any reconciliation job that re-posts charges.
- *Remediate:* give Finance the reconciled list (order, customer, duplicate charge IDs, amounts). Refund through the provider's API with an idempotency key per refund, so the refund job itself is safe to re-run.
- *Fix:* one idempotency key per order stored with the order; payments replays on a repeated key; retries only on retryable errors with jitter; a breaker; a regression test that drops the response after the charge.
- *What must be deterministic:* money movement. A given order may be charged at most once, whatever the network does. Prove it with a test, not a promise.
- *Prevent:* an alert on "more than one charge per order"; a fault-injection drill in staging each quarter; a runbook for provider incidents.
- *Communicate:* a written summary that separates facts (count, amounts, timeline) from hypotheses, with the fix, its verification and the follow-ups.

## Comprehension Questions

1. Why is a read timeout more dangerous than a connection error for a payment call?
2. Why use full jitter instead of plain exponential backoff?
3. Why does the circuit breaker treat a 4xx response as a success?
4. Why must the client reuse the same idempotency key on every retry, and where does this project keep it?
5. What goes wrong if orders commits the order and then publishes `OrderPaid` straight to the broker?
6. Why does the consumer acknowledge a message only after its transaction commits?
7. Why must orders' readiness probe not fail when payments is down?
8. Why does payments reject the same key with a different body instead of processing it?

## Comprehension Answers

1. A connection error usually means the request never reached the server, so a retry is safe. A read timeout means the request may have been processed and only the response was lost: the outcome is unknown. Retrying without an idempotency key can charge twice.
2. Plain exponential backoff keeps clients that failed together in lockstep, so they retry together and overload the recovering service again. Full jitter spreads retries uniformly over the backoff window.
3. A 4xx means the dependency is up and gave a definite answer ("declined", "invalid"). The breaker measures dependency health, not business outcomes. Counting declines would open the circuit on a busy shopping day.
4. The key is how payments recognizes a repeat. A new key per attempt makes each retry look like a new payment. This project generates `payment_key` when the order is created and stores it on the order row, so later retries (even `POST /orders/{id}/pay` hours later) reuse it.
5. A crash between commit and publish loses the event (no receipt, no shipment). If you publish first and the transaction then rolls back, consumers act on an order that does not exist. The outbox commits the event with the order.
6. If it acked first and then crashed, the message would be gone and the work never done (at-most-once). Acking after commit means a crash causes a redelivery, which the dedupe table turns into a no-op.
7. Kubernetes would remove every orders pod from the Service. All traffic would fail, including reads that do not need payments, and recovery would be slower. Readiness covers what the service owns; dependency state is reported and alerted on.
8. Reusing a key for a different request is a client bug. Replaying the old answer would hide it (the new amount is silently ignored); processing it would break the key's guarantee. A 422 makes the bug visible.

## Interview Questions — Theory-Based

**Q1. When would you not use microservices?**

- *Strong answer:* when one small team owns the product, the domain is still moving, there is no CI/CD, tracing or on-call maturity, or the services would share a database. Microservices trade code complexity for operational and distributed-data complexity. Start with a modular monolith with enforced module boundaries; extract a service when there is a concrete reason (a team boundary per Conway's law, different scaling, a compliance boundary).
- *What it tests:* judgment over fashion.
- *Follow-up:* "How would you split a monolith later?" (Strangler fig: route one capability at a time to the new service behind the same API, move its data ownership, keep the old path until traffic is zero.)

**Q2. How do you choose between a synchronous call and a message queue? Between SQS, Kafka and RabbitMQ?**

- *Strong answer:* sync when the caller needs the answer to continue; async when work can finish later, must survive the consumer being down, absorbs bursts or fans out. SQS/SNS for managed queues and fan-out on AWS; Kafka for high-throughput ordered streams with replay, event sourcing and CDC; RabbitMQ for flexible routing and classic task queues. All are at-least-once in practice, so consumers must be idempotent.
- *What it tests:* communication-pattern trade-offs.
- *Follow-up:* "How do you keep per-customer ordering in Kafka?" (Partition key = customer ID; one consumer per partition in a group.)

**Q3. Explain retries with exponential backoff and jitter. What can go wrong?**

- *Strong answer:* retry only transient errors (timeouts, connection errors, 5xx, 429 after `Retry-After`), never other 4xx; only idempotent operations or with an idempotency key; exponential growth with a cap and full jitter; a small attempt count; retries at one layer; a retry budget. What goes wrong: retry storms that keep a service down, multiplication across layers, retries that blow the user's deadline, and duplicate side effects.
- *What it tests:* whether you know retries can cause outages.
- *Follow-up:* "Three services each retry 3 times. Worst case?" (Up to 3³ = 27 calls to the bottom service per user request.)

**Q4. Design idempotency for a payments API.**

- *Strong answer:* client sends `Idempotency-Key` (a UUID per logical operation). The server atomically claims it (unique constraint), stores a hash of the request and, when done, the response. Same key and body: replay. Different body: 422. In progress: 409. Store final failures too. Keys expire after a window, stuck claims time out, and keys are scoped per client or tenant.
- *What it tests:* correctness under retries and concurrency.
- *Follow-up:* "Two replicas get the same key at the same time?" (The unique constraint lets exactly one insert win; the other gets 409 or waits and replays.)

**Q5. How do timeouts, circuit breakers and bulkheads work together?**

- *Strong answer:* timeouts bound how long one call can hold resources. Retries handle brief faults. The breaker stops calling a dependency that keeps failing and fails fast, with one probe in half-open. Bulkheads cap the resources (pool size, concurrency) any one dependency can take, so a slow one cannot starve others. Together they prevent cascading failure.
- *Follow-up:* "What should the user see when the circuit is open?" (A fast, clear response: 503 with `Retry-After`, or a degraded result such as "payment pending" or cached data.)

**Q6. Can you get exactly-once delivery? How do you avoid losing events?**

- *Strong answer:* not end to end across systems with side effects. Use at-least-once delivery plus idempotent consumers (dedupe by event ID in the same transaction as the side effect, ack after commit), and a DLQ for poison messages. To avoid losing events at the source, use a transactional outbox or CDC instead of dual writes. Kafka's exactly-once covers read-process-write inside Kafka, not your email provider.
- *What it tests:* delivery semantics beyond buzzwords.

**Q7. Saga or two-phase commit? Orchestration or choreography?**

- *Strong answer:* 2PC gives atomicity across resources but blocks on coordinator failure, needs XA support, and couples availability; it is rare in cloud microservices. Sagas use local transactions plus compensations (refund, release stock) and accept eventual consistency. Orchestration puts the flow in one coordinator (Step Functions, Temporal) for visibility; choreography uses events for loose coupling in short flows.
- *Follow-up:* "Payment succeeded but stock reservation failed. Now what?" (Compensate: idempotent refund, order marked cancelled, customer notified; all steps logged and retryable.)

**Q8. Explain CAP and PACELC. Where does eventual consistency show up in a system you would build?**

- *Strong answer:* under a partition, choose consistency or availability. Else, trade latency against consistency. Inside one service, use a strongly consistent database. Across services, data shared by events is eventually consistent: a read model, a cache, the notifications service. Make the window visible ("pending"), read your own writes from the owner, version events.
- *What it tests:* practical reasoning, not just the acronym.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a system you built or worked on that had several services.**

- *Cover:* the services and why they were split; sync vs async calls; how data ownership worked; one failure mode and how you handled it.
- *Structure:* Situation → Requirement → Architecture → Implementation → Verification → Result → Lesson.
- *Personalize:* "`<<personalize: system and its users>>`. It had `<<n>>` services: `<<names>>`. `<<service A>>` called `<<service B>>` synchronously with `<<timeout/retry policy>>`, and `<<events>>` went through `<<broker>>`. The hardest problem was `<<failure mode>>`, which we solved with `<<pattern>>`. Result: `<<metric>>`."
- *Lab-honest version:* "In a hands-on project I built orders and payments services in FastAPI. Orders calls payments with a timeout, jittered retries and a circuit breaker; payments enforces idempotency keys; events go through a transactional outbox to an idempotent consumer. I proved with 43 tests, including one that drops the response after the charge, that a retry never charges twice."
- *Follow-ups:* "Why did you split there?" "How did you test failures?"

**A2. Describe an incident caused by a dependency failing or slowing down.**

- *Cover:* detection, impact, the timeline, the root cause (missing timeout, retry storm, health check cascade), the fix, and prevention.
- *Personalize:* "`<<personalize: dependency and symptom>>`. We noticed through `<<alert/dashboard>>`. The root cause was `<<cause>>`. We contained it by `<<action>>` and fixed it with `<<pattern>>`."
- *Lab-honest version:* "I have not run that incident in production. In a lab I rehearsed it with fault injection: a payments error rate, a response lost after charging, and a slow dependency. I verified that orders failed fast once the circuit opened and stayed ready."
- *Follow-ups:* "What did the dashboards show?" "What would you change in the runbook?"

**A3. How have you made an integration with an external API reliable?**

- *Cover:* timeouts from measured latency, retry policy and which errors, idempotency keys or natural keys, rate limits and `Retry-After`, circuit breaking, reconciliation against the provider's records, and alerting.
- *Personalize:* "`<<personalize: provider>>` had `<<limits/quirks>>`. I `<<approach>>` and reconciled with `<<report/API>>`."
- *Lab-honest version:* point to the project's client and tests, and say what you would add for a real provider (reconciliation job, per-tenant rate limits, metrics).
- *Follow-ups:* "The provider has no idempotency support. What then?" (Use a natural key and check-before-retry: query the provider by your reference before charging again; serialize attempts per order.)

**A4. Tell me about an event-driven design you built.**

- *Cover:* events and their schemas, the producer guarantee (outbox or CDC), consumer idempotency, ordering needs, DLQ handling, schema versioning, how you observed lag.
- *Personalize:* "`<<personalize: domain>>`: `<<events>>` on `<<broker>>`. We used `<<outbox/CDC>>`; consumers deduped by `<<key>>`. Lag was monitored with `<<metric>>`."
- *Lab-honest version:* "In a project I implemented an outbox relay and a consumer that dedupes by event ID; tests show a duplicate delivery and a lost ack each produce exactly one notification, and a v2 event goes to the dead-letter list."
- *Follow-ups:* "How do you replay events after fixing a consumer bug?"

**A5. Tell me about a time you argued against an architecture choice (for example, splitting into microservices).**

- *Cover:* the proposal, your concerns backed by evidence (team size, ops maturity, shared data), the alternative you offered (modular monolith, one extracted service), how it was decided, and the outcome.
- *Personalize:* "`<<personalize: situation>>`. I proposed `<<alternative>>` because `<<evidence>>`. We agreed to `<<decision>>`; `<<result>>`."
- *Lab-honest version:* explain how you would frame it with the trade-off table in §3.1, and what evidence would change your mind.
- *Follow-ups:* "What would make you split now?"

## Troubleshooting Scenarios

**T1. Customers report duplicate charges after a provider slowdown.**

```text
SYMPTOM     two or more charges per order during an incident window
CHECK       ledger: GROUP BY order_id HAVING COUNT(*) > 1
            client logs: timeouts followed by retries? key per attempt?
            server: is Idempotency-Key required and stored atomically?
CAUSES      retries on timeout without a key; new key per attempt;
            key stored after the charge (race); keys expired too soon
CONFIRM     test: transport delivers the request, then drops the
            response (ReadTimeout) -> count charges
FIX         one key per logical operation, stored with the order;
            server claims key atomically and replays responses
PREVENTION  regression test; alert on >1 charge per order; refunds
            also idempotent
```

**T2. The dependency recovered, but it falls over again every time.**

```text
SYMPTOM     payments comes back, then 5xx spike, then down again
CHECK       request rate to payments right after recovery; retry
            counts per layer; backoff jitter present?
CAUSES      synchronized retries (no jitter); retries at 3 layers;
            breakers all closing at once; queue backlog flushed at once
CONFIRM     traces show many attempts per user request
FIX         full jitter; retry at one layer; retry budget; one probe
            in half-open; drain backlogs with a concurrency limit
PREVENTION  load test the recovery path; dashboards for retries/s
```

**T3. The circuit breaker opens on a healthy day.**

```text
SYMPTOM     breaker open, payments looks healthy, users get 503
CHECK       which responses count as failures? (4xx? 429?)
            threshold vs traffic; timeout lower than real p99?
CAUSES      declines (402) or validation errors counted as failures;
            timeout too tight; threshold too low for the volume
CONFIRM     log the status codes that called record_failure()
FIX         count only timeouts, connection errors and 5xx; set the
            timeout from measured p99; failure rate over a window
PREVENTION  unit tests for breaker classification; alert on flapping
```

**T4. Queue depth keeps growing; one message fails forever.**

```text
SYMPTOM     consumer lag rising; same event id in error logs repeatedly
CHECK       DLQ configured? max receive count? the failing message's
            version and payload; consumer error rate
CAUSES      poison message retried forever; unsupported event version;
            visibility timeout shorter than processing time (dupes)
CONFIRM     inspect the message; replay it in a test
FIX         DLQ after N deliveries; fix or skip the bad version;
            visibility timeout > p99 processing time
PREVENTION  alert on DLQ depth > 0 and on lag; contract tests for
            event schemas
```

**T5. Orders are paid but receipts never arrive.**

```text
SYMPTOM     order status "paid", no notification sent
CHECK       outbox: rows with published_at IS NULL and their age;
            relay logs and liveness; broker depth; consumer errors
CAUSES      relay not running or crashing; event published before
            commit and rolled back; consumer acks before commit
CONFIRM     GET /ops/events: outbox_pending > 0 or broker_pending
            growing
FIX         run and monitor the relay; outbox in the same transaction;
            ack only after the consumer commits
PREVENTION  alert on outbox lag (oldest unpublished row age)
```

**T6. During a payments outage, all orders pods go unready.**

```text
SYMPTOM     kubectl shows 0/3 ready for orders; even GET /orders fails
CHECK       what /health/ready checks; probe timeouts and thresholds
CAUSES      readiness calls payments; liveness checks dependencies and
            restarts healthy pods in a loop
CONFIRM     curl the readiness endpoint with payments stopped
FIX         readiness = own DB only; report breaker state in the body;
            liveness = process only
PREVENTION  test that readiness stays 200 with the circuit open
```

## Unit Practice Project — Orders + Payments (Resilient Microservices)

### Project Goal

Build two FastAPI services that survive a payments outage without losing an order or charging anyone twice:

- **payments** enforces `Idempotency-Key` and can simulate outages;
- **orders** writes an order and an outbox event atomically, then charges through a resilient client (timeout, retries with full jitter, one key per order, circuit breaker);
- an **outbox relay** publishes events to an at-least-once broker and an **idempotent consumer** sends each receipt once.

### Architecture

```text
 orders/ (:8000)                          payments/ (:8001)
  main.py create_app()                     main.py create_app()
   POST /orders, /orders/{id}/pay           POST /payments
   GET /orders/{id}, /health,               GET /payments, /health
       /health/ready, /ops/events          store.py  IdempotencyStore
  service.py OrderService                            Ledger
   create_pending(): order + outbox tx     faults.py X-Fault, APP_FAULT_*
   pay(): client → status + outbox tx
  payments_client.py  retry/backoff ──HTTP + Idempotency-Key──►
  breaker.py          CircuitBreaker
  outbox.py  relay_once() ─► messaging/broker.py InMemoryBroker
                                 │ at-least-once, visibility, DLQ
                                 ▼
                          notifications/consumer.py (dedupe)
 common/problems.py  RFC 9457 errors for both services
 Dockerfile (one image) + docker-compose.yml (two services)
```

### Requirements

1. `POST /payments` requires an `Idempotency-Key` (8–128 chars of `A-Z a-z 0-9 _ -`); missing or malformed → **400**.
2. Same key + same body → the stored status and body, with `Idempotent-Replayed: true`, and no new charge. Same key + different body → **422**. Same key still in progress → **409**.
3. Amounts above `APP_DECLINE_OVER_CENTS` → **402** decline, stored and replayed like a success.
4. Fault injection: `APP_FAULT_ERROR_RATE`, `APP_FAULT_LATENCY_MS`, and an `X-Fault` header (`error`, `throttle`, `slow`, `after-charge`) that is ignored in prod.
5. `POST /orders` inserts the order (`pending`) and an `OrderCreated` outbox row in **one** transaction, then charges payments.
6. The client: per-call timeout; up to `APP_RETRY_MAX_ATTEMPTS` attempts with full-jitter backoff on timeouts, connection errors and 5xx; 429 waits `Retry-After` (capped); no retry on other 4xx; the **same** key on every attempt.
7. A circuit breaker (threshold, reset timeout, one half-open probe, injectable clock). When open, `POST /orders` returns **503 problem+json** immediately, with `order_id`, `order_status: "pending"` and `Retry-After`.
8. Outcome: `paid` + `OrderPaid`, or `payment_failed` + `PaymentFailed`, each written with its status change in one transaction. Unknown outcome: stays `pending`; `POST /orders/{id}/pay` retries with the same key.
9. The relay publishes unpublished outbox rows in order and marks them sent. The consumer dedupes by event id in the same transaction as its side effect and acks after commit; failures are nacked and go to dead letters after `max_deliveries`.
10. `GET /health` (liveness) and `GET /health/ready` (own DB; reports breaker state and outbox backlog; stays 200 when payments is down).

### Technical Requirements

- Python 3.12+, FastAPI, Pydantic v2, pydantic-settings (`APP_` prefix), SQLAlchemy 2.x (SQLite by default), HTTPX.
- Each service is an app factory: `uvicorn orders.main:create_app --factory --port 8000` and `uvicorn payments.main:create_app --factory --port 8001`.
- Tests: pytest + pytest-asyncio, `httpx.ASGITransport` and `httpx.MockTransport`, a fake clock and a fake sleep. No real network, no real sleeps.
- `docker-compose.yml` for both services, validated by tests (no Docker daemon needed).
- Ruff (line length 76), mypy strict.

### Project Structure

{{tree projects/unit08-microservices/solution}}

### Step-by-Step Implementation

1. **Run the starter.** Start payments and orders in two terminals and `POST /orders`. You get a 500 from a `NotImplementedError`: the wiring works, the logic is missing.
   - *Why:* see the system's shape before filling it in.
2. **TODO 4: idempotency in `payments/store.py`.** Claim, replay, mismatch, in progress.
   - *Test:* `pytest -q tests/test_payments.py`.
3. **TODO 1: backoff and `is_retryable`.**
   - *Test:* `pytest -q tests/test_resilience.py -k backoff`.
4. **TODO 3: breaker transitions.**
   - *Test:* `pytest -q tests/test_resilience.py -k breaker`.
5. **TODO 2: the retry loop.** Same key, breaker check before each attempt, 429 handling, no sleep after the last attempt.
   - *Test:* `pytest -q tests/test_resilience.py`.
6. **TODO 5: order + outbox in one transaction.**
   - *Test:* `pytest -q tests/test_messaging.py -k "outbox or neither"` then `pytest -q tests/test_orders_api.py`.
7. **TODO 6: consumer dedupe.**
   - *Test:* `pytest -q tests/test_messaging.py`.
8. **Rehearse an outage by hand.** Send two `X-Fault: error` orders, then a normal one: it fails fast with "circuit is open". Wait 30 s and pay the pending order.
9. **Finish:** `pytest -q && ruff check . && ruff format --check . && mypy`.

### Starter Code

{{file projects/unit08-microservices/starter/orders/payments_client.py}}

{{file projects/unit08-microservices/starter/orders/breaker.py}}

{{file projects/unit08-microservices/starter/payments/store.py}}

The starter also has TODOs in `orders/service.py` (order + outbox transaction) and `notifications/consumer.py` (dedupe by event id). The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** create paid orders; list charges with `GET :8001/payments?order_id=1`; watch `/ops/events` count one receipt per paid order.
2. **Validation:** `amount_cents: 0`, an unknown currency, an extra field, a missing or short `Idempotency-Key`.
3. **Errors:**
   - `X-Fault: error` → 503 with `order_id`; pay it later;
   - `X-Fault: throttle` → the client waits `Retry-After`;
   - `X-Fault: after-charge` → the retry replays; one charge;
   - `APP_FAULT_LATENCY_MS=3000` → timeouts, then a pending order.
4. **Edge cases:**
   - two concurrent `POST /orders/{id}/pay` for one order;
   - a duplicate event and a lost ack in the consumer;
   - a v2 event reaching a v1 consumer.
5. **Extend:**
   - accept a client `Idempotency-Key` on `POST /orders` so a double-click creates one order;
   - add a retry budget (retries ≤ 10% of calls in the last minute);
   - add an `asyncio.Semaphore` bulkhead around payments calls;
   - replace the in-memory store with a SQLAlchemy table and a unique constraint;
   - add an inventory consumer and a compensating refund (a saga).

### Hints

1. Full jitter is one line: `rng() * min(cap, base * 2.0 ** (attempt - 1))`.
2. `httpx.TimeoutException` and `httpx.ConnectError` are both subclasses of `httpx.TransportError`.
3. Build the headers dict once, before the loop; that is how the key stays the same.
4. Call `breaker.allow_request()` before *every* attempt, not once per `charge()`: the breaker may trip in the middle of your retries.
5. In the breaker, read the state through the `state` property so the OPEN → HALF_OPEN timer is applied.
6. `session.flush()` sends the INSERT inside the open transaction, which assigns `order.id` without committing.
7. For dedupe, let the database decide: insert the event id and catch `IntegrityError`; a "select, then insert" check races with a second consumer.

### Expected Behavior

```text
POST :8001/payments  (no Idempotency-Key)          → 400
POST :8001/payments  key K, body B                 → 201 captured
POST :8001/payments  key K, body B again           → 201, replayed
POST :8001/payments  key K, body B'                → 422
POST :8000/orders {"customer_id":"c-1",...}        → 201 status=paid
POST :8000/orders {... amount_cents: 500000}       → 201 payment_failed
POST :8000/orders  X-Fault: error                  → 503 problem+json
                     order_id=2 order_status=pending Retry-After: 5
POST :8000/orders  (circuit open)                  → 503 in ~1 ms,
                     "payments circuit is open", Retry-After: 30
GET  :8000/health/ready (payments down)            → 200, circuit open
POST :8000/orders/2/pay (after recovery)           → 200 status=paid
GET  :8001/payments?order_id=2                     → exactly 1 charge
```

### Testing Requirements

- **Payments (9):** first charge, replay with reordered body, mismatch 422, missing/short key 400 (×2), decline replay, outage frees the key, throttle `Retry-After`, concurrent claim 409.
- **Resilience (15):** backoff growth and cap, retries then success, same key on every attempt, no retry on 4xx (×4), 429 `Retry-After`, `Retry-After` over cap, timeouts retried then reported, breaker opens at threshold, success resets the count, half-open single probe closes, failed probe reopens, open breaker fails fast without network.
- **Orders API (7):** paid with events, decline, lost response does not double charge, outage 503 then later payment, timeouts leave the order pending, circuit opens/fails fast/recovers (readiness stays 200), validation and 404.
- **Messaging (7):** outbox written with the order, failure writes neither, relay publishes in order and marks sent, duplicate delivery processed once, lost ack redelivers and dedupes, poison message to dead letters, end to end with a relay re-publish.
- **Deployment (5):** compose services and ports, service DNS name and `service_healthy`, healthchecks, non-root Dockerfile, every file ≤ 76 columns.

```bash
pytest -q && ruff check . && ruff format --check . && mypy
```

### Final Runnable Solution

{{files projects/unit08-microservices/solution}}

### How to Run

```bash
cd projects/unit08-microservices/solution
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env

# terminal 1
uvicorn payments.main:create_app --factory --port 8001
# terminal 2
uvicorn orders.main:create_app --factory --port 8000

# or both in containers
docker compose up --build
APP_FAULT_ERROR_RATE=0.5 docker compose up   # rehearse an outage
```

### Verify the Solution

1. `pytest -q`: **43 passed**; `ruff check .`, `ruff format --check .` and `mypy` are clean.
2. The starter as shipped: **33 failed, 10 passed** (deployment, validation, missing-key, throttle and dead-letter tests do not depend on the TODOs).
3. Manual: a normal order is `paid`; `GET :8001/payments?order_id=1` shows one charge.
4. `X-Fault: error` returns 503 with `order_id`; `POST /orders/{id}/pay` then pays it, still with one charge.
5. Two failing orders trip the breaker (5 failures); the next order fails in milliseconds; `/health/ready` is 200 with `"payments_circuit": "open"`.
6. After a second or two, `/ops/events` shows `outbox_pending: 0` and one notification per paid order.

### Project Interview Debrief

1. **Why does a lost response not cause a second charge?**
   The key is generated once per order and stored on the order row. Every attempt, and every later `POST /orders/{id}/pay`, sends it. Payments claims the key atomically and replays the stored response, so the second request returns the first charge. A test proves it by dropping the response after the charge.
2. **Why is the order created before the payment call, and why 503 instead of 500 when payments is down?**
   Creating it first means the customer's intent is never lost, and the outbox records it. A 503 with `order_id`, `order_status: "pending"` and `Retry-After` tells the client the truth: the outcome is not confirmed, try later. A 500 would say "we broke", and the client might create a new order.
3. **What does the circuit breaker count as a failure?**
   Timeouts, connection errors and 5xx. A 4xx (a decline, a validation error) means payments is healthy. A 429 is backpressure: the client waits `Retry-After` and does not count it.
4. **The relay can publish the same event twice. Is that a bug?**
   No, it is the at-least-once contract. If the relay crashes after publishing but before marking the row, it publishes again. The consumer dedupes by event id in the same transaction as its side effect, so the customer still gets one receipt.
5. **What would you change for production?**
   A Postgres-backed idempotency table with a unique key and expiry; Postgres for orders with `FOR UPDATE SKIP LOCKED` in the relay; SQS, Kafka or RabbitMQ instead of the in-memory broker, with the consumer as its own deployment; a retry budget and a bulkhead; OpenTelemetry traces and metrics for retries, breaker state, outbox lag and DLQ depth (Unit 11); and Kubernetes probes on `/health` and `/health/ready` (Unit 6).
