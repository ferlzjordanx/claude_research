# Unit 3 — Data Engineering for Application Developers

## 1. What This Unit Teaches

Every FDE system stores and retrieves data, and data mistakes are the most expensive to fix later **[JD-Required]**. This unit teaches:

- relational modeling and SQL on PostgreSQL;
- keys and constraints as executable business rules;
- joins, indexes and how to read a query plan;
- transactions and isolation levels, and the concurrency bugs they prevent;
- connection pooling;
- SQLAlchemy 2.x (Core and ORM, the session, N+1);
- migrations with Alembic;
- NoSQL options (document, key-value / Redis) and how to choose between SQL and NoSQL.

The emphasis is on what an application developer must get right, not database administration.

## 2. Mental Model

```text
 Application (FastAPI route → service)
     │  calls
     ▼
 Repository              builds SQL (via SQLAlchemy), returns objects
     │  borrows a connection
     ▼
 Connection Pool         reuses N open connections (TCP+TLS+auth
     │                   are expensive to create)
     ▼
 Database (PostgreSQL)
     │  planner chooses:  Index scan?  Seq scan?  Join strategy?
     ▼
 Index / Query           B-tree lookup vs reading the whole table
     │
     ▼
 Transaction             BEGIN … COMMIT | ROLLBACK
     │                   isolation decides what concurrent
     │                   transactions can see
     ▼
 Result                  rows → ORM objects → Pydantic → JSON
```

Read it as follows:

- The application never talks to the database directly. It goes through a repository, which borrows a pooled connection.
- The database decides *how* to execute each query (the plan). Indexes give the planner faster options.
- Transactions group statements so they succeed or fail together.
- Isolation decides what concurrent transactions can see of each other's work.

## 3. Brief Theory

### 3.1 Relational databases and SQL

**What it is.**

- A relational database stores data in **tables** (relations) of rows with typed columns. Relationships are expressed by **keys**.
- **SQL** is declarative: you describe *what* you want and the planner decides *how* to get it.
- **PostgreSQL** is the open-source default for application data. It has strong correctness (MVCC, real constraints, transactional DDL) and rich types (JSONB, arrays, ranges, full text). Extensions such as `pgvector` (Unit 10) add more.

**Why it matters.** Relational databases enforce integrity rules for *every* writer, answer ad-hoc questions with joins and aggregates, and give transactional guarantees that business data (orders, payments, inventory) requires.

**Essential SQL:**

```sql
-- Join + aggregate: revenue per customer in 2026
SELECT c.id, c.name, SUM(o.total) AS revenue, COUNT(*) AS orders
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.created_at >= '2026-01-01'
GROUP BY c.id, c.name
HAVING SUM(o.total) > 1000
ORDER BY revenue DESC
LIMIT 10;

-- LEFT JOIN keeps customers with no orders (orders = 0)
SELECT c.id, COUNT(o.id) AS orders
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id;

-- Window function: each customer's latest order
SELECT * FROM (
  SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id
                                 ORDER BY created_at DESC) AS rn
  FROM orders o) t
WHERE rn = 1;
```

| Join | Returns |
|---|---|
| INNER JOIN | Only rows that match in both tables |
| LEFT JOIN | All left rows; NULLs where the right side has no match |
| FULL OUTER JOIN | All rows from both sides |
| CROSS JOIN | Every combination (rarely intended) |

### 3.2 Schema design, primary and foreign keys, constraints

**What it is.** Choosing tables, columns, types and constraints so that the data is correct by construction.

**How to do it.**

- **Primary key (PK).** It uniquely identifies a row. Use surrogate keys (`bigint` identity or UUIDv7) for entities, and keep natural keys (email, SKU) as `UNIQUE` constraints.
- **Foreign key (FK).** It guarantees a referenced row exists (`orders.customer_id → customers.id`). Choose `ON DELETE` deliberately:
  - `RESTRICT` — you can't delete a customer who has orders;
  - `CASCADE` — deleting an order deletes its items;
  - `SET NULL`.
- **CHECK, NOT NULL and UNIQUE** turn business rules into guarantees (`stock >= 0`, `quantity > 0`). Application checks can race; constraints cannot.
- **Normalization.** Store each fact once (third normal form) to avoid update anomalies. **Denormalize** deliberately for read performance, and document who keeps the copies consistent.
- **Types.**
  - `numeric(12,2)` for money (never float);
  - `timestamptz` for instants (store UTC);
  - `text` or `varchar(n)` with validation;
  - `jsonb` for genuinely flexible attributes, not as a way to avoid design.

**Why it matters for an FDE.** Customers' data arrives messy. The schema is where you decide what is authoritative and what is guaranteed.

### 3.3 Indexes

**What it is.** An index is an auxiliary data structure — by default a **B-tree**, sorted and balanced — that lets the database find rows without scanning the whole table.

**How it works.**

- A B-tree lookup is O(log n) and can also return rows already *in index order*, which avoids a sort.
- **Composite indexes** follow the leftmost-prefix rule. `(customer_id, created_at)` serves `WHERE customer_id = ? ORDER BY created_at`, but not `WHERE created_at > ?` alone.
- **Covering indexes** (`INCLUDE (...)`) let index-only scans avoid reading the table.
- **Partial indexes** (`WHERE status = 'open'`) index only hot rows.
- **GIN indexes** serve JSONB, arrays and full-text search; pgvector adds ANN indexes for embeddings (Unit 10).

**Trade-offs.** Every index:

- costs storage;
- slows every `INSERT`, `UPDATE` and `DELETE`, because the index must be maintained;
- adds planner work.

Index for your real query patterns, measured with `EXPLAIN ANALYZE`. Unique constraints create indexes automatically.

### 3.4 Query behavior and query plans

`EXPLAIN` shows the plan. `EXPLAIN (ANALYZE, BUFFERS)` runs the query and shows actual times and pages touched. This is real output from the project's `scripts/explain_demo.py` on 500,000 orders:

```text
--- BEFORE index ---
Limit (actual time=10.259..13.248 rows=20 loops=1)
  ->  Gather Merge (actual time=10.257..13.244 rows=20 loops=1)
        Workers Planned: 2
        ->  Sort  Sort Key: created_at DESC
              ->  Parallel Seq Scan on demo_orders
                    Filter: (customer_id = 4242)
                    Rows Removed by Filter: 166649
Execution Time: 13.267 ms
--- AFTER index (customer_id, created_at DESC) ---
Limit (actual time=0.027..0.051 rows=20 loops=1)
  ->  Index Scan using ix_demo_customer_created on demo_orders
        Index Cond: (customer_id = 4242)
Execution Time: 0.065 ms
```

**How to read it:**

- **Before:** a sequential scan read every row (about 500,000 discarded by the filter), then sorted. That cost grows with table size.
- **After:** the index finds the customer's rows already sorted by date and stops after 20. That is roughly 200× faster, and it stays fast as the table grows.

**Red flags in plans:**

- `Seq Scan` on a large table for a selective filter;
- `Rows Removed by Filter` in the hundreds of thousands;
- an explicit `Sort` you could avoid;
- `Nested Loop` with huge row estimates;
- estimated rows far from actual rows, which means stale statistics (run `ANALYZE`).

**Common causes of slow queries:**

- a missing or unusable index (a function on the column, a type mismatch, a leading wildcard such as `LIKE '%x'`);
- N+1 queries from the ORM;
- `SELECT *` over wide rows;
- OFFSET pagination deep into a table.

### 3.5 Transactions (ACID)

**What it is.** A transaction groups statements into one unit:

| Property | Meaning |
|---|---|
| **Atomicity** | All statements apply or none do |
| **Consistency** | Constraints hold before and after |
| **Isolation** | Concurrent transactions don't see each other's partial work |
| **Durability** | Committed data survives crashes (write-ahead log) |

**Why it matters.** Placing an order touches several rows: decrement stock, insert the order, insert its items. A failure halfway must not leave stock decremented with no order.

**In SQLAlchemy:**

```python
with session.begin():          # BEGIN
    ...                        # any exception → ROLLBACK
                               # normal exit → COMMIT
```

### 3.6 Isolation levels and concurrency anomalies

| Level | Prevents | Still possible | PostgreSQL notes |
|---|---|---|---|
| Read Committed (**PG default**) | Dirty reads | Non-repeatable reads, phantoms, **lost updates** with read-modify-write | Each *statement* sees the latest committed data |
| Repeatable Read | + non-repeatable reads, phantoms (snapshot) | Write skew | The transaction sees one snapshot; conflicting writes raise a serialization error, so retry |
| Serializable (SSI) | All anomalies | — | May abort transactions; the application must retry |

**The classic bug — lost update (read-modify-write race):**

```text
T1: SELECT stock → 1         T2: SELECT stock → 1
T1: UPDATE stock = 0         T2: UPDATE stock = 0
→ two orders sold the last unit
```

**Three correct fixes:**

1. **Atomic conditional update.** Check and write in *one* statement. This is what the project does:

   ```sql
   UPDATE products SET stock = stock - :q
   WHERE sku = :sku AND stock >= :q
   RETURNING id, price;            -- no row ⇒ insufficient stock
   ```

2. **Pessimistic locking.** `SELECT ... FOR UPDATE` locks the row until commit, so other writers wait.
3. **Optimistic locking.** A `version` column: `UPDATE ... SET version = version + 1 WHERE id = ? AND version = ?`. Zero rows updated means someone else changed it, so return 409 or retry.

**Deadlocks** happen when two transactions lock rows in opposite orders. Lock in a **consistent order** (the project sorts SKUs), keep transactions short, and retry on deadlock errors.

### 3.7 Connection pooling

**What it is.** A set of reusable open database connections.

**Why it exists.** Opening a PostgreSQL connection costs a TCP handshake, TLS, authentication and a backend process (several milliseconds, plus memory on the server). Doing that per request is slow, and many clients can exhaust `max_connections`.

**How it works.**

- SQLAlchemy's `QueuePool` keeps `pool_size` connections and allows `max_overflow` extras. `pool_timeout` bounds the wait, and `pool_pre_ping` discards dead connections.
- **Capacity math:** total connections = replicas × workers × (pool_size + max_overflow). Ten pods × 2 workers × 15 = 300 connections, which may exceed the database limit.
- Use an external pooler (**PgBouncer**, **RDS Proxy**) for many clients or serverless workloads.

**Symptoms of exhaustion:**

- requests hang, then time out with `QueuePool limit ... reached`;
- sessions are not closed (always use a `yield` dependency or a context manager);
- long transactions hold connections.

### 3.8 SQLAlchemy 2.x

**What it is.** The standard Python database toolkit.

- **Core:** a SQL expression language (`select`, `update`), engines, connections.
- **ORM:** maps classes to tables, with a **Session** that implements the *unit of work* (tracks changes, flushes them in order) and an *identity map* (one object per row per session).

**[Current: 2.0-style API — `select()`, `Mapped[...]`, `mapped_column`. The 1.x `session.query()` style is legacy but still widely seen. 2.1 is current and keeps the 2.0 API.]**

**Key mechanics:**

- `session.add()` stages an object. `flush()` sends the SQL without committing, so an id becomes available. `commit()` makes it durable.
- **Lazy loading:** accessing `order.items` triggers a query. In a loop over N orders that is **N+1 queries**. Fix it with eager loading:
  - `selectinload` — one extra `IN` query per relationship;
  - `joinedload` — a JOIN, suited to many-to-one.
- `expire_on_commit=False` keeps objects readable after commit. That is convenient in APIs, but you must reload deliberately when you need fresh data.
- Sync sessions block. Use them from `def` FastAPI endpoints (which run in the threadpool), or use `AsyncSession` with `asyncpg` or `psycopg` async, with `async def` throughout.

### 3.9 Migrations

**What it is.** Versioned, ordered scripts that evolve the schema (Alembic for SQLAlchemy).

**Why it exists.** Every environment (developer laptops, CI, staging, production) must reach the same schema reproducibly, with a reviewed history and a downgrade path.

**How to use it:**

- `alembic revision --autogenerate -m "msg"` compares the models with the database and writes a draft. **Always review it**: autogenerate can't infer renames and may miss some constraints.
- `alembic upgrade head` runs as a **deploy step** (a CI/CD job or a Kubernetes init Job), not at application import time.
- **Zero-downtime changes** use *expand/contract*:
  1. add the new nullable column;
  2. deploy code that writes both columns;
  3. backfill;
  4. switch reads;
  5. drop the old column in a later release.
- Build large indexes with `CREATE INDEX CONCURRENTLY` to avoid locking writes.

### 3.10 NoSQL

**What it is.** A family of non-relational stores, each optimized for specific access patterns:

| Type | Examples | Model | Strengths | Weaknesses |
|---|---|---|---|---|
| Document | MongoDB, Amazon DocumentDB, Firestore, Cosmos DB | JSON documents, nested | Flexible schema, aggregate-oriented reads, horizontal scaling | Cross-document joins and transactions are limited or costly; duplication must be managed |
| Key-value | Redis/Valkey, DynamoDB (also wide-column-like) | Key → value | Very fast lookups at massive scale, TTLs | Queries limited to known keys or indexes; design around access patterns |
| Wide-column | Cassandra, ScyllaDB | Partitioned rows | Huge write throughput, multi-region | Query-first modeling, eventual consistency |
| Search | OpenSearch, Elasticsearch | Inverted index | Full-text, relevance, aggregations | Not a system of record |
| Graph | Neo4j, Neptune | Nodes and edges | Relationship traversal | Niche |
| Vector | pgvector, OpenSearch k-NN, Pinecone | Embeddings | Similarity search (RAG) | Approximate; needs metadata filtering |

**Document database example (MongoDB, pymongo):**

```python
from pymongo import MongoClient, ASCENDING

client = MongoClient("mongodb://localhost:27017",
                     serverSelectionTimeoutMS=2000)
orders = client.shop.orders
orders.create_index([("customer_id", ASCENDING), ("created_at", -1)])
orders.insert_one({
    "customer_id": 1,
    "status": "placed",
    "items": [{"sku": "KB-01", "qty": 2, "unit_price": "89.00"}],
    "shipping": {"city": "Austin", "zip": "78701"},  # embedded, not joined
})
recent = orders.find({"customer_id": 1}).sort("created_at", -1).limit(20)
```

The order *with its items* is one document because it is always read together. This is aggregate-oriented modeling. The cost is that product names copied into items can go stale, which is a deliberate denormalization.

**DynamoDB** **[Provider-specific, AWS]**. Design the partition key and sort key from the access patterns (`PK=CUSTOMER#1`, `SK=ORDER#2026-10-14#123`), and add Global Secondary Indexes for other patterns. Reads are eventually consistent by default.

### 3.11 Redis

**What it is.** An in-memory data-structure server: strings, hashes, lists, sets, sorted sets and streams, with TTLs.

**Uses in FDE systems:**

- **cache-aside** for hot reads;
- rate limiting (`INCR` plus `EXPIRE`);
- distributed locks (with care);
- session storage;
- idempotency-key storage (Unit 8);
- lightweight queues and streams.

**Cache-aside:**

```text
read:  value = cache.get(k) → hit? return
                            → miss? value = db.get(); cache.set(k, ttl)
write: db.update(); then cache.delete(k)   # after COMMIT
```

**Pitfalls and fixes:**

| Pitfall | What goes wrong | Fix |
|---|---|---|
| **Stale data** | Readers see old values | Invalidate after commit; short TTLs |
| **Stampede** | Many concurrent misses hit the database at once | Locks, request coalescing, or jittered TTLs |
| **Cache as a single point of failure** | A Redis outage breaks reads | Treat Redis errors as misses (the project does this) |
| **Unbounded memory** | Redis fills up | `maxmemory` plus an eviction policy |

### 3.12 SQL vs NoSQL: how to choose

| Question | Lean relational (PostgreSQL) | Lean NoSQL |
|---|---|---|
| Do you need multi-row/multi-entity transactions? | Yes (orders, payments, inventory) | Rarely |
| Are queries ad-hoc or evolving (reports, analytics, joins)? | Yes | No, the access patterns are known and fixed |
| Is the data shape stable with relationships? | Yes | Highly variable or nested aggregates |
| Scale | Vertical plus read replicas covers most apps | Massive write throughput or global distribution |
| Team skills and operations | SQL is ubiquitous | Managed services reduce operational work |

The **FDE default** is PostgreSQL as the system of record, Redis for cache and ephemeral state, and a search or vector index derived from the system of record. Add a document store when the access pattern clearly fits it.

## 4. Application in a Real System

```text
 FastAPI ──► Service ──► Repository ──► SQLAlchemy Session
                │                             │ pool
                │ cache-aside                 ▼
                └──► Redis (ElastiCache)   PostgreSQL (RDS/Aurora)
                                              │ logical replication / CDC
                                              ▼
                           Search/Vector index, data warehouse
                           (derived, rebuildable — not authoritative)
```

| Choice | Why | Without it | Alternatives |
|---|---|---|---|
| PostgreSQL (RDS / Aurora) | Integrity, transactions, rich SQL, managed backups and failover | Data corruption, hand-written consistency logic | MySQL (similar); DynamoDB (scale, access-pattern design) |
| SQLAlchemy ORM + Core | Productivity plus full SQL when needed | Hand-written SQL everywhere, or an ORM hiding SQL behind magic | Raw psycopg (more control), SQLModel (thin layer over SQLAlchemy + Pydantic) |
| Alembic | Reproducible schema history | "Works on my machine" schemas | Flyway / Liquibase (JVM ecosystem) |
| Redis cache | Cuts read latency and database load | Database overload on hot keys | In-process cache (per-replica, inconsistent), CDN for public data |
| Constraints in the database | Rules enforced for every writer | Race conditions, bad data from scripts | Application-only validation (insufficient) |

## 5. Implementation

### 5.1 Typed ORM models with constraints and an index

```python
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_products_stock_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"))
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan")
```

### 5.2 Engine, pool and a per-request session

```python
engine = create_engine(url, pool_size=5, max_overflow=10,
                       pool_pre_ping=True, pool_timeout=10)
factory = sessionmaker(engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    session = factory()
    try:
        yield session          # FastAPI injects this
    finally:
        session.close()        # connection returns to the pool
```

### 5.3 A transaction with an atomic, race-free stock decrement

```python
with session.begin():                       # COMMIT or ROLLBACK
    for sku in sorted(quantities):          # consistent lock order
        row = session.execute(
            update(Product)
            .where(Product.sku == sku, Product.stock >= quantities[sku])
            .values(stock=Product.stock - quantities[sku])
            .returning(Product.id, Product.price)
        ).one_or_none()
        if row is None:                     # raising → ROLLBACK
            raise InsufficientStockError(sku)
        ...
    session.add(order)
cache.delete(*keys)                         # after COMMIT
```

### 5.4 Avoiding N+1 with eager loading

```python
stmt = (select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(20)
        .options(selectinload(Order.items)
                 .selectinload(OrderItem.product)))
orders = session.scalars(stmt).all()        # 3 queries total
```

The project's test counts the SQL statements with an engine event listener and asserts exactly three. That turns a performance property into a regression test.

### 5.5 Letting the database enforce uniqueness

```python
try:
    with session.begin():
        session.add(Customer(name=..., email=email))
except IntegrityError as exc:               # UNIQUE violated
    raise ConflictError("Email already registered.") from exc
```

### 5.6 Cache-aside that survives a Redis outage

```python
def get(self, key: str) -> dict | None:
    try:
        raw = self._client.get(key)
    except redis.RedisError as exc:          # outage = cache miss
        log.warning("cache get failed: %s", exc)
        return None
    return json.loads(raw) if raw else None
```

### 5.7 Migrations

```bash
alembic revision --autogenerate -m "initial schema"   # draft
# review alembic/versions/0001_initial_schema.py
alembic upgrade head          # apply
alembic downgrade -1          # roll back one step
alembic history               # audit trail
```

## 6. How It Connects to the Rest of the System

```text
 Unit 2 API ─► service ─► repository (this unit) ─► pool ─► PostgreSQL
                 │                                      ▲
                 └─► Redis cache ◄────── invalidation ──┘
 Unit 6: RDS/Aurora + ElastiCache, secrets for DB credentials,
         readiness probe runs SELECT 1, migration Job before rollout
 Unit 7: CI runs migrations + tests against a real Postgres service
 Unit 8: idempotency keys and outbox tables live in this database
 Unit 10: pgvector stores embeddings next to authoritative records
 Unit 11: slow-query logs, pool metrics, DB spans in traces
```

## Cross-Unit System Map (Units 1–3)

```text
 Client (curl / Swagger UI / future SPA)
   │ HTTPS + JSON + Bearer JWT
   ▼
 FastAPI app (Unit 2)
   ├─ Pydantic validation at the boundary
   ├─ authN (JWT) → authZ (roles)
   ▼
 Service layer (Unit 2) — business rules, domain errors
   │  typed Python, Protocols, exceptions, tests (Unit 1)
   ▼
 Repository (Unit 3) — SQLAlchemy 2.x
   ├─ connection pool
   ├─ transactions (atomic stock decrement)
   ▼
 PostgreSQL (constraints, indexes)      Redis (cache-aside)
```

Everything in this map is **deterministic**: the same input produces the same output, and correctness is enforced by types, validation, constraints and transactions. Later units add network failures (Unit 8) and probabilistic model behavior (Units 9–10) *around* this deterministic core. They never replace it.

## FDE Scenario 2 — "The numbers in the dashboard don't match the ERP"

**Stakeholder:** "Your new order dashboard shows 4% more revenue than our ERP. Finance is upset. Fix it today."

- *Clarify first:*
  - Which numbers (gross or net, with or without tax, refunds, currency)?
  - Which period and time zone ("today" in UTC or in local time)?
  - Which system is **authoritative** for revenue? Usually the ERP or ledger, not your operational database.
- *Investigate with evidence:*
  - reconcile one day order by order (`FULL OUTER JOIN` of both extracts on order ID);
  - classify the differences: missing refunds, duplicated orders from retries, time-zone boundary, currency conversion.
- *Likely causes:*
  - retries created duplicate orders (no idempotency key, Unit 8);
  - cancelled orders counted;
  - `created_at` stored without a time zone.
- *What must be deterministic:* the revenue definition, written down as an acceptance criterion with a SQL query both sides agree on.
- *Deliver:* a reconciliation report, a fix (unique constraint plus idempotency keys; a status filter), a regression test using the reconciliation query, and a short note to finance explaining the definition.
- *Communicate:* "Here's the exact cause for each difference, the fix, and the check we'll run daily so this can't recur silently."

## Comprehension Questions

1. Why should "stock can't go negative" be a database CHECK constraint even if the service already checks it?
2. A composite index on `(customer_id, created_at)` exists. Which of these does it help, and why: (a) `WHERE customer_id=7 ORDER BY created_at DESC`, (b) `WHERE created_at > now() - '1 day'`?
3. Why might an index improve one query but hurt write performance?
4. Explain the lost-update race, and two ways to prevent it.
5. What is the N+1 problem and how does `selectinload` fix it?
6. Why use a connection pool, and how can it be exhausted?
7. Why must cache invalidation happen after the transaction commits?
8. When would you choose a document database over PostgreSQL?

## Comprehension Answers

1. Application checks can race between concurrent requests and are bypassed by other writers (scripts, other services). The constraint is enforced atomically for every write.
2. (a) Yes. The leftmost column matches the equality filter and the second column provides the sort order, so it is an index scan with no sort. (b) Not efficiently: `created_at` is not the leftmost column. It needs its own index.
3. Reads can use it to avoid scans. Every INSERT, UPDATE or DELETE must also update the index, which costs CPU, I/O, WAL and storage.
4. Two transactions read the same value, then both write a value derived from that stale read, and one update is lost. Prevent it with an atomic conditional `UPDATE ... WHERE stock >= q`, `SELECT ... FOR UPDATE`, or optimistic locking with a version column.
5. Loading N parents and then lazily loading each parent's children issues 1 + N queries. `selectinload` loads all the children in one `IN (...)` query per relationship.
6. Creating connections is slow and limited by the database's `max_connections`. A pool reuses them. It is exhausted when sessions leak, transactions are long, or replicas × pool size exceeds what the database or traffic allows.
7. If you invalidate before commit, a concurrent reader can repopulate the cache with the old committed value, which is then stale until the TTL expires.
8. When data is naturally read and written as self-contained aggregates with flexible or nested shape, the access patterns are known, and cross-entity transactions or joins are rare — and when horizontal scale or a managed serverless model matters.

## Interview Questions — Theory-Based

**Q1. Explain ACID and give an example where atomicity matters.**

- *Strong answer:* Atomicity means all statements apply or none do. Consistency means constraints hold. Isolation means concurrent transactions don't see partial work. Durability means committed data survives crashes, via the WAL. Example: placing an order decrements stock and inserts the order and its items. If the item insert fails, the stock decrement must roll back.
- *Testing:* the fundamentals beyond acronyms.
- *Follow-up:* "How do you make an operation atomic across two services?" (You can't with one database transaction. Use a saga or the outbox pattern; see Unit 8.)

**Q2. What isolation level does PostgreSQL use by default, and what anomalies can occur?**

- *Strong answer:* Read Committed. Each statement sees data committed before that statement started, so non-repeatable reads, phantoms and lost updates in read-modify-write code are possible. I prevent them with atomic updates or row locks, or use Repeatable Read or Serializable with retry logic when needed.
- *Follow-up:* "What does Serializable cost?" (Possible serialization failures that need retries, and some overhead.)

**Q3. How do you find and fix a slow query?**

- *Strong answer:*
  1. Identify it from slow-query logs, `pg_stat_statements` or APM traces.
  2. Run `EXPLAIN (ANALYZE, BUFFERS)` and look for sequential scans on selective filters, large "rows removed", sorts and bad estimates.
  3. Fix: add or adjust an index (column order matters), rewrite the query, avoid functions on indexed columns, fix N+1 in the ORM, update statistics, use keyset pagination.
  4. Verify with the same plan and with production-like data.
- *Follow-up:* "When would you not add an index?" (Write-heavy tables, low-selectivity columns, queries that touch most rows.)

**Q4. Explain connection pooling and how you'd size it.**

- *Strong answer:* A pool keeps reusable connections because creating one is expensive. Size it from concurrency needs and database limits: replicas × workers × (pool_size + overflow) must stay under `max_connections` with headroom. Add PgBouncer or RDS Proxy for many clients. Watch pool wait time, in-use connections and timeouts.

**Q5. ORM vs raw SQL: trade-offs?**

- *Strong answer:* An ORM gives productivity, type-safe models, the unit of work and portability. The risks are hidden queries (N+1) and inefficient SQL. Raw SQL gives full control and performance. SQLAlchemy lets me mix them: ORM for CRUD, Core or text for complex reports. Either way I read the generated SQL and the plans.

**Q6. How do you run schema migrations without downtime?**

- *Strong answer:* Use expand/contract. Make additive changes first (nullable columns, new tables), deploy code compatible with both schemas, backfill in batches, switch reads, then remove the old structures in a later release. Use `CREATE INDEX CONCURRENTLY`, avoid long locks, and run migrations as a separate deploy step with a rollback plan.

**Q7. SQL vs NoSQL for an order system?**

- *Strong answer:* Orders, payments and inventory need multi-entity transactions and constraints, so PostgreSQL is the system of record. Redis serves caching and rate limits. A document store or DynamoDB fits huge, simple key-based access such as session data or an event log by customer. Search and vector indexes are derived, not authoritative.

**Q8. What is cache-aside and what can go wrong?**

- *Strong answer:* Read from the cache; on a miss, load from the database and populate the cache with a TTL; on a write, update the database and then delete the key. What can go wrong: stale data (invalidation timing), stampedes on popular keys, cache outages taking down reads (treat errors as misses), unbounded memory, and caching per-user data under shared keys (a security leak).

## Interview Questions — Application / Experience-Based

**A1. Tell me about a schema you designed.**

- *Cover:* the entities and their relationships, keys and constraints, indexes chosen from the query patterns, how it evolved (migrations), and one trade-off (normalize vs denormalize, JSONB vs columns).
- *Structure:* Situation → Requirement → Architecture → Implementation → Verification → Result → Lesson.
- *Personalize:* "`<<personalize: domain>>`. Core tables were `<<...>>`, with FKs and a unique constraint on `<<natural key>>`. The hot query `<<...>>` got a composite index `<<...>>`, verified with EXPLAIN ANALYZE (`<<before → after>>`)."
- *Follow-ups:* "What would you change now?" "How did you handle a breaking change?"

**A2. Describe a performance problem caused by the database.**

- *Cover:* the symptom (latency or CPU), the evidence (plans, `pg_stat_statements`, traces), the root cause (missing index, N+1, lock contention), the fix and the measured result.

**A3. Have you dealt with concurrency or data-integrity bugs?**

- *Cover:* the race you found, how you reproduced it (a concurrency test), and the fix (atomic update, lock, constraint, idempotency).
- *Lab-honest version:* "In a project I wrote a test that fires eight concurrent purchases at the last unit; with an atomic conditional UPDATE exactly one succeeds."

**A4. How have you used Redis or another cache?**

- *Cover:* what you cached and why, TTL and invalidation, failure behavior, and measured impact.

**A5. Tell me about a data migration you ran.**

- *Cover:* the planning, batching, verification counts and checksums, rollback, and communication.

## Troubleshooting Scenarios

**T1. A database query suddenly becomes slow.**

```text
SYMPTOM     /customers/{id}/orders p95 from 30ms to 3s
WHAT TO CHECK  EXPLAIN ANALYZE now vs before; row count growth;
               recent deploy (new filter/sort?); stats freshness;
               lock waits (pg_stat_activity, pg_locks)
LIKELY CAUSES  index not used (type mismatch, function on column,
               changed ORDER BY), stale statistics, table bloat, N+1
               after a code change, lock contention from a migration
HOW TO CONFIRM plan shows Seq Scan + Sort; ANALYZE fixes estimates;
               query count per request in traces
FIX         add/adjust composite index; ANALYZE; eager loading;
            rewrite query; CREATE INDEX CONCURRENTLY in prod
PREVENTION  pg_stat_statements review, query-count tests, load tests
            with realistic data volumes
```

*Strong answer:* "I'd compare the current plan with the expected one. Most sudden slowdowns are a plan change (stats or data growth), an index the query can no longer use, or N+1 introduced by a code change. I'd verify the fix with EXPLAIN ANALYZE and protect it with a test."

**T2. Requests hang with "QueuePool limit reached".**

```text
CHECK       sessions closed? long transactions? replica × pool size
            vs max_connections? slow queries holding connections?
CAUSES      session leak (no close), awaiting an external API while
            holding a transaction, traffic spike
FIX         yield-dependency closes sessions; keep transactions short
            (no network calls inside); tune pool; add PgBouncer/RDS
            Proxy; set pool_timeout to fail fast
```

**T3. Duplicate rows appear after an outage.**

```text
CAUSE       client retried POST after timeout; no unique constraint /
            idempotency key → second insert succeeded
FIX         unique business key or Idempotency-Key table; dedupe data
PREVENT     every create endpoint idempotent (Unit 8)
```

**T4. Deadlock detected errors under load.**

```text
CAUSE       two transactions lock the same rows in opposite order
FIX         lock in a consistent order (sort keys), shorter
            transactions, retry on deadlock (SQLSTATE 40P01)
```

**T5. A migration locks a production table.**

```text
CAUSE       ALTER TABLE adding NOT NULL with default on old PG / index
            built without CONCURRENTLY / long-running transaction
FIX         expand/contract; CONCURRENTLY; lock_timeout; off-peak
```

## Unit Practice Project — Orders Data Layer

### Project Goal

Build the persistence layer of an order system on SQLAlchemy 2.x and PostgreSQL:

- a schema with real constraints and indexes;
- migrations;
- repositories;
- a transactional, race-free order placement;
- N+1-free reads;
- a Redis cache that degrades gracefully.

This proves you can make data correct under concurrency and fast under load, and prove both with tests.

### Architecture

```text
 FastAPI (sync def endpoints, threadpool)
   ├─ POST /customers ─► CustomerRepository ──┐
   ├─ GET  /products/{sku} ─► CatalogService ─┼─► Session ─► pool ─► DB
   │                           └─ cache-aside ─► Redis / in-memory
   ├─ POST /orders ─► OrderService (one transaction, atomic UPDATE)
   └─ GET  /customers/{id}/orders ─► OrderRepository (selectinload)
 Alembic migrations ──► schema    scripts/explain_demo.py ──► plans
```

### Requirements

1. Tables `customers`, `products`, `orders` and `order_items`, with:
   - PKs and FKs (`RESTRICT` on customer, `CASCADE` on items);
   - `UNIQUE(email)`, `UNIQUE(sku)`;
   - `CHECK(stock >= 0)`, `CHECK(price > 0)`, `CHECK(quantity > 0)`;
   - an index `(customer_id, created_at)`.
2. `POST /customers` returns 201. A duplicate email returns 409, enforced by the UNIQUE constraint.
3. `GET /products/{sku}` uses cache-aside and sets `X-Cache: HIT|MISS`. An unknown SKU returns 404.
4. `POST /orders` merges duplicate SKUs and performs everything in **one transaction**:
   - an unknown customer returns 404, and unknown SKUs return 422;
   - insufficient stock returns 409 and **nothing changes**;
   - stock is decremented atomically, and the total is computed from current prices;
   - product cache keys are invalidated after commit.
5. `GET /customers/{id}/orders` returns orders newest first, using exactly 3 SQL queries regardless of the number of orders.
6. A Redis outage never fails a request.
7. Alembic migration `0001` creates the schema. Upgrade and downgrade both work.
8. A concurrency test proves only one of eight concurrent buyers gets the last unit (PostgreSQL).

### Technical Requirements

- Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, psycopg 3, redis-py and pydantic-settings.
- SQLite in-memory for fast tests. PostgreSQL 14+ (docker compose provides 18) for the realistic tests.
- pytest; a `TEST_DATABASE_URL` switch for PostgreSQL.

### Project Structure

{{tree projects/unit03-data/solution}}

### Step-by-Step Implementation

1. **Run the starter on SQLite.** `pip install -r requirements-dev.txt`, `python -m app.seed`, then `pytest -q`.
   - *Why:* to see which behaviors are missing (failing tests).
2. **Review `models.py`.** Identify every constraint and index and the business rule each encodes.
   - *Test:* `pytest tests/test_constraints.py` passes already.
3. **Generate and review the migration.**
   - Start PostgreSQL with `docker compose up -d`.
   - Run `alembic revision --autogenerate -m "initial schema"`.
   - Read the file, run `alembic upgrade head`, then `alembic downgrade base` and `upgrade` again.
   - *Why:* migrations, not `create_all`, are how real environments get schemas.
4. **Implement the customer insert with IntegrityError translation** (`main.py`).
   - *Test:* `test_create_customer_and_duplicate_email`.
5. **Implement `RedisProductCache` and `CatalogService.get_product`.**
   - *Test:* `test_product_read_is_cached` and `test_redis_outage_degrades_to_cache_miss`.
6. **Implement `OrderRepository.list_for_customer` with `selectinload`.**
   - *Test:* `test_list_orders_avoids_n_plus_one` (asserts exactly 3 queries).
7. **Implement `OrderService.place_order`** (Counter merge, `session.begin()`, sorted atomic UPDATEs, invalidation after commit).
   - *Test:* the order tests in `test_api.py`, especially `test_insufficient_stock_rolls_back_everything`.
8. **Implement the concurrency test** and run it against PostgreSQL with `TEST_DATABASE_URL=... pytest -q`.
9. **Run `python -m scripts.explain_demo`** against PostgreSQL and explain the before and after plans in your own words.

### Starter Code

{{file projects/unit03-data/starter/app/services/orders.py}}

{{file projects/unit03-data/starter/app/repositories.py}}

{{file projects/unit03-data/starter/app/services/catalog.py}}

The starter's `app/cache.py` (`RedisProductCache` methods), the `create_customer` route in `app/main.py`, and `tests/test_concurrency.py` contain further TODOs. `alembic/versions/` is empty, because you generate the first migration.

### Practice Tasks

1. **Normal behavior:**
   - order creation decrements stock;
   - totals are correct (2 × 89.00 + 29.50 = 207.50);
   - listing is newest first;
   - cache HIT on the second read.
2. **Validation:** an empty `lines` list returns 422; `quantity < 1` returns 422; unknown fields return 422.
3. **Errors:** an unknown customer returns 404; an unknown SKU returns 422; insufficient stock returns 409; a duplicate email returns 409.
4. **Edge cases:**
   - duplicate SKUs in one order are merged;
   - a failure on the second SKU rolls back the first;
   - the cache is invalidated after an order;
   - a Redis outage is harmless.
5. **Tests:** the concurrency test on PostgreSQL. Optionally, a test for `ON DELETE RESTRICT` (deleting a customer with orders fails).

### Hints

1. `Counter[str]()` with `quantities[line.sku] += line.quantity` merges duplicates.
2. `with self._session.begin():` — raising any exception inside rolls back.
3. `update(Product).where(Product.sku == sku, Product.stock >= qty).values(stock=Product.stock - qty).returning(Product.id, Product.price)`, then `.one_or_none()`.
4. Build `OrderItem(product=products[sku], quantity=qty, unit_price=row.price)` and append it to `order.items`.
5. Eager loading: `.options(selectinload(Order.items).selectinload(OrderItem.product))`.
6. For the concurrency test, create **one session per thread**. Sessions are not thread-safe.

### Expected Behavior

```text
POST /orders {"customer_id":1,"lines":[{"sku":"KB-01","quantity":2},
                                       {"sku":"MS-01","quantity":1}]}
→ 201 {"id":1,"customer_id":1,"status":"placed","total":"207.50",
       "lines":[{"sku":"KB-01","quantity":2,"unit_price":"89.00"},
                {"sku":"MS-01","quantity":1,"unit_price":"29.50"}],...}

GET /products/KB-01 → 200  X-Cache: MISS   {"stock":23,...}
GET /products/KB-01 → 200  X-Cache: HIT

POST /orders ... {"sku":"MN-27","quantity":6} (stock 5)
→ 409 {"title":"Insufficient stock","detail":"Not enough stock for MN-27."}
  (and no stock changed for any other line)

POST /orders ... {"sku":"NOPE","quantity":1}
→ 422 {"title":"Unknown SKU","detail":"Unknown SKUs: NOPE"}
```

### Testing Requirements

- **Unit and integration tests** on SQLite (fast feedback) and PostgreSQL (real behavior).
- **Negative tests:** constraint violations, 404, 409, 422.
- **Transaction test:** a partial failure rolls everything back.
- **Performance regression test:** query count for the listing.
- **Concurrency test** (PostgreSQL): eight threads, one winner.

```bash
pytest -q                                   # SQLite
TEST_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders \
  pytest -q                                 # PostgreSQL (+ concurrency)
alembic upgrade head && alembic downgrade base && alembic upgrade head
```

### Final Runnable Solution

{{files projects/unit03-data/solution}}

### How to Run

```bash
cd projects/unit03-data/solution
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed && uvicorn app.main:create_app --factory --reload
pytest -q
# PostgreSQL + Redis:
docker compose up -d && cp .env.example .env
alembic upgrade head && python -m app.seed
uvicorn app.main:create_app --factory --reload
```

### Verify the Solution

1. `pytest -q` on SQLite gives **15 passed, 1 skipped** (the concurrency test).
2. Against PostgreSQL: **16 passed**, including `test_last_unit_is_sold_once`.
3. `curl -i localhost:8000/products/KB-01` twice gives `X-Cache: MISS`, then `HIT`.
4. Place the order shown above and check that `stock` dropped by 2.
5. Order 6 × MN-27: **409**. `GET /customers/1/orders` shows no new order (rollback).
6. Stop Redis (`docker compose stop redis`). Product reads still work, and the logs show "cache get failed".
7. `python -m scripts.explain_demo` shows a seq scan before and an index scan after.

### Project Interview Debrief

1. **Why an atomic `UPDATE ... WHERE stock >= q` instead of reading the stock first?**
   Reading and then writing is a race under Read Committed: two requests can both read stock 1. One conditional UPDATE checks and writes atomically under a row lock. The concurrency test proves it.
2. **What would break first at scale?**
   Hot rows (a popular SKU) serialize writers, and the connection count grows with replicas. Mitigations: keep transactions short, add PgBouncer or RDS Proxy, possibly use a reservation pattern or queue for flash sales, read replicas for listings, and keyset pagination.
3. **Why invalidate the cache instead of updating it?**
   Deleting after commit is simpler and avoids writing a value computed from a transaction that might not commit. The next read repopulates from the source of truth.
4. **What would you change for production?**
   Run migrations as a deploy step, use DB credentials from a secret manager, add pool metrics and slow-query logging, add idempotency keys on `POST /orders` (Unit 8), monitor with `pg_stat_statements`, run backups and restore drills.
5. **Why SQLite in tests if production is PostgreSQL?**
   Fast feedback for logic. But concurrency, locking and some SQL behavior differ, so CI also runs the suite against a real PostgreSQL service (Unit 7) — never SQLite alone.
