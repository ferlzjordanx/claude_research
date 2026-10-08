# Part XIX — Interview Preparation

**What this part teaches.** Part XIX converts knowledge into interview performance across four tracks: Java and the Spring/backend ecosystem (Unit 39), algorithms and data structures (Unit 40), timed Spring implementation exercises (Unit 41) and AI/Forward-Deployed-Engineer scenarios (Unit 42). Each unit is organized for *drilling*: three-depth explanations, code reading, debugging, timed builds and scenario practice.

**Why it matters.** Interviews compress years of judgment into 45–60 minutes. Candidates rarely fail for lack of knowledge; they fail because they can't retrieve and communicate it under time pressure — rambling on easy questions, freezing on debugging, skipping clarification in design, or reciting definitions without evidence that they've actually built anything. This part trains retrieval, structure and evidence.

**Where it appears.** Recruiter and phone screens (quick questions), technical deep-dives (Java/Spring internals), coding rounds (algorithms), live or take-home builds (Spring APIs), system design rounds (Unit 38), and customer-facing scenario rounds for FDE roles (Unit 42).

**Connections.** Every earlier unit feeds this part; Unit 38 supplies design content; Units 33–37 supply AI production content; the Unit 43 capstone becomes the *evidence bank* you cite in every answer.

**How to practice every unit in this part.**

1. Answer aloud, timed; record yourself; review for filler, structure and accuracy.
2. Use the three depths: **30 seconds** (definition + the one insight that matters), **2 minutes** (mechanism + example + trade-off), **5 minutes** (internals, edge cases, production story, code).
3. For code questions, predict output *before* running; then verify; then explain why.
4. Track weak topics; revisit with spaced repetition (1, 3, 7, 14 days).
5. Attach **implementation evidence** to every answer: "In my capstone I…, measured…, broke it by…, fixed it with…".

## Unit 39 — Java Interview Track

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Explain** each core topic — Java language, collections, generics, streams, JVM, concurrency, Spring, Spring Boot, JPA, SQL, REST, security, testing, Kafka, microservices, Docker, AWS and system design — at 30-second, 2-minute and 5-minute depth.
2. **Implement** a small, correct code example for each topic on demand, without an IDE.
3. **Predict** the behavior of tricky code (equality, hashing, generics erasure, stream laziness, memory visibility, proxies, transactions, lazy loading) and **explain** why.
4. **Debug** common production failures for each topic using the right tools (thread dumps, heap dumps, JFR, `EXPLAIN ANALYZE`, Actuator, logs, traces).
5. **Compare** commonly confused alternatives and state when to use each.
6. **Use** implementation evidence from your own projects instead of memorized definitions, using a structured evidence format.
7. **Identify** version-dependent facts (Java 21/25, Spring Boot 3 vs 4, Jackson 2 vs 3) and state them precisely.

### 2. Prerequisite Knowledge

All earlier curriculum units on Java, Spring, data, messaging, deployment and security, plus Unit 38 (system design). This unit is not a first introduction: it reorganizes what you know into interview-ready answers and fills gaps. If a 2-minute answer here feels unfamiliar, return to the original unit before drilling.

**Version facts to state precisely (October 2026).** Java 25 is the current LTS (21 the previous LTS; 26 and 27 are non-LTS releases since). Spring Boot 4 (Framework 7, Jakarta EE 11, Jackson 3, Java 17 minimum, Java 21+ recommended) is current; Boot 3.5's open-source support ended in mid-2026. Virtual threads are final since Java 21; scoped values final in Java 25; structured concurrency still in preview in Java 25; generational ZGC is ZGC's only mode since Java 24; compact object headers are a product (opt-in) feature in Java 25.

### 3. Mental Model

Interview answers are **layered maps**, not scripts. Each topic has:

```
30 s    WHAT + WHY            "X is …; it exists to solve …; the key insight is …"
 ↓
2 min   HOW + EXAMPLE + TRADE-OFF
 ↓
5 min   INTERNALS + EDGE CASES + FAILURE STORY + CODE + EVIDENCE
```

Start at 30 seconds and let the interviewer pull you deeper. Signals of seniority: precise vocabulary, naming trade-offs unprompted, admitting version-dependence, and *evidence* — "I measured", "I broke", "I fixed".

**Evidence statement format (use everywhere):**

> **Context** (what system) → **Decision** (what I chose and the alternative) → **Mechanism** (how it works) → **Evidence** (test, metric, incident) → **Lesson** (what I'd do differently).

Example: "In my support-agent capstone I needed exactly-once refunds. I rejected a Redis lock and used a conditional `UPDATE … WHERE status='APPROVED'` claim plus a PSP idempotency key. An 8-thread concurrency test with duplicate Kafka events executed the refund once. Lesson: database constraints beat distributed locks for correctness."

### 4. Comprehensive Theory — Topic Drills at Three Depths

Each topic below gives the 30-second answer, the 2-minute answer, the 5-minute deep dive with an implementation example, and the common trap.

#### 4.1 Java Language (OOP, equality, immutability, records, sealed types, pattern matching, exceptions)

**30 seconds.** Java is a statically typed, object-oriented language compiled to bytecode and run on the JVM. Modern Java (17–25) adds data-oriented features — records, sealed types and pattern matching — that make domain models smaller and exhaustively checkable by the compiler.

**2 minutes.**
- `==` compares references (or primitive values); `equals` compares logical equality; `hashCode` must be consistent with `equals` (equal objects → equal hash codes) or hash-based collections break.
- Immutability: `final` fields, no setters, defensive copies of mutable components; thread-safe by construction. `final` on a reference doesn't make the object immutable.
- Records: transparent carriers with canonical constructor, accessors, `equals/hashCode/toString` generated; compact constructors for validation; shallowly immutable.
- Sealed interfaces + records + pattern matching `switch` (Java 21) → algebraic data types with exhaustive handling.
- Exceptions: checked (recoverable, part of API contract) vs unchecked (programming errors, or by framework convention); try-with-resources for `AutoCloseable`.

**5 minutes + implementation.** Discuss record compact constructors and defensive copying, why records can't extend classes, record patterns with nested deconstruction, exhaustiveness checking with sealed hierarchies, `switch` guards (`when`), and how pattern matching replaces visitor boilerplate. Mention flexible constructor bodies (Java 25, JEP 513: statements before `super(...)`), and that string templates were withdrawn after preview **[Version-dependent]**.

```java
import java.math.BigDecimal;
import java.util.List;
import java.util.Objects;

sealed interface Payment permits Card, BankTransfer, Wallet { }

record Card(String last4, BigDecimal amount) implements Payment {
    Card {                                        // compact constructor: validation
        Objects.requireNonNull(amount);
        if (amount.signum() <= 0) throw new IllegalArgumentException("amount must be positive");
        if (!last4.matches("\\d{4}")) throw new IllegalArgumentException("last4");
    }
}
record BankTransfer(String iban, BigDecimal amount) implements Payment { }
record Wallet(String provider, BigDecimal amount, List<String> tags) implements Payment {
    Wallet { tags = List.copyOf(tags); }          // defensive copy → truly immutable component
}

final class Fees {
    static BigDecimal fee(Payment p) {
        return switch (p) {                       // exhaustive: no default needed; adding a subtype breaks compilation
            case Card c when c.amount().compareTo(new BigDecimal("1000")) > 0 -> c.amount().multiply(new BigDecimal("0.015"));
            case Card c -> c.amount().multiply(new BigDecimal("0.02"));
            case BankTransfer(String iban, BigDecimal amount) -> new BigDecimal("0.50");   // record pattern
            case Wallet w -> w.amount().multiply(new BigDecimal("0.01"));
        };
    }
}
```

*Trap:* "Immutable means `final`." A `final List<String>` field can still be mutated through the list.

#### 4.2 Collections

**30 seconds.** The Collections Framework provides interfaces (`List`, `Set`, `Map`, `Queue`/`Deque`) and implementations with different performance and ordering guarantees; choosing correctly is about access patterns, ordering, concurrency and memory.

**2 minutes.**
- `ArrayList`: O(1) random access, amortized O(1) append, O(n) middle insert; grows ~1.5×. `LinkedList`: rarely the right choice (poor locality); use `ArrayDeque` for stacks/queues.
- `HashMap`: O(1) average get/put; `LinkedHashMap` keeps insertion (or access) order — LRU via `removeEldestEntry`; `TreeMap`: O(log n), sorted, navigable.
- `HashSet` is backed by `HashMap`. `PriorityQueue` is a binary heap: O(log n) offer/poll, O(1) peek.
- Immutable factories `List.of`, `Map.of` (no nulls, unmodifiable); `Collections.unmodifiableList` is a *view*.
- Sequenced collections (Java 21): `getFirst/getLast/reversed` on `List`, `Deque`, `LinkedHashSet/Map`.
- Concurrency: `ConcurrentHashMap`, `CopyOnWriteArrayList` (read-mostly), `BlockingQueue` variants.

**5 minutes + implementation.** HashMap internals: table of bins (power of two), hash spreading `h ^ (h >>> 16)`, index `(n - 1) & hash`, load factor 0.75 triggers resize (doubling, entries split between `i` and `i + oldCap`), bins become red-black trees at 8 entries when capacity ≥ 64 (back to lists at 6) — protecting against poor hash distributions, so worst case is O(log n) not O(n) *for comparable keys*. Mutable keys whose hash changes after insertion are "lost". `ConcurrentHashMap` (Java 8+): CAS for empty bins, `synchronized` on bin head for updates, lock-free reads, no null keys/values (ambiguity of `get` returning null), `compute`/`merge` atomic per key; size via striped counters.

```java
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

final class LruCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;
    LruCache(int capacity) { super(16, 0.75f, true); this.capacity = capacity; }   // accessOrder = true
    @Override protected boolean removeEldestEntry(Map.Entry<K, V> eldest) { return size() > capacity; }
}

final class WordCounter {
    private final ConcurrentHashMap<String, Long> counts = new ConcurrentHashMap<>();
    void add(String word) { counts.merge(word, 1L, Long::sum); }        // atomic; `get` + `put` would race
}
```

*Trap:* "HashMap is always O(1)." Average, with good hashing; resize costs O(n) occasionally; collisions degrade it.

#### 4.3 Generics

**30 seconds.** Generics give compile-time type safety and remove casts; they're implemented by type erasure, so type arguments mostly don't exist at runtime.

**2 minutes.**
- Erasure: `List<String>` and `List<Integer>` are both `List` at runtime; no `new T()`, no `new T[]`, no `instanceof List<String>`.
- Bounded types `<T extends Comparable<? super T>>`.
- Wildcards and PECS: *Producer Extends, Consumer Super* — read from `? extends T`, write into `? super T`.
- Invariance: `List<Integer>` is not a `List<Number>`; arrays are covariant (and fail at runtime with `ArrayStoreException`).
- Bridge methods preserve polymorphism after erasure.

**5 minutes + implementation.** Explain heap pollution and `@SafeVarargs`; type tokens (`Class<T>`, `ParameterizedTypeReference<T>` in Spring, `TypeReference<T>` in Jackson) to recover generic types at runtime via anonymous-subclass reflection; wildcard capture helper methods; recursive generics (`Comparable<T>`, builder `self()` patterns).

```java
import java.util.Collection;
import java.util.List;

final class Collections2 {
    // PECS: src produces T (extends), dst consumes T (super)
    static <T> void copy(List<? super T> dst, List<? extends T> src) {
        for (T item : src) dst.add(item);
    }

    static <T extends Comparable<? super T>> T max(Collection<? extends T> items) {
        T best = null;
        for (T t : items) if (best == null || t.compareTo(best) > 0) best = t;
        return best;
    }
}
// Spring: restClient.get().uri("/orders").retrieve().body(new ParameterizedTypeReference<List<OrderDto>>() {});
```

*Trap:* thinking `List<Object>` accepts a `List<String>` argument.

#### 4.4 Streams

**30 seconds.** Streams are a declarative pipeline over data — source, lazy intermediate operations, one terminal operation — good for transformations and aggregations; not a replacement for every loop.

**2 minutes.**
- Lazy: nothing runs until a terminal op; elements flow one at a time through fused stages; short-circuiting ops (`findFirst`, `anyMatch`, `limit`) stop early.
- Stateless (`map`, `filter`) vs stateful (`sorted`, `distinct`) operations.
- Collectors: `toMap` (throws on duplicate keys unless merge function), `groupingBy` with downstream collectors, `partitioningBy`, `teeing`.
- `Stream.toList()` (Java 16) returns an unmodifiable list; `Collectors.toList()` makes no such guarantee.
- Parallel streams use the common `ForkJoinPool`; beneficial only for large, CPU-bound, splittable, side-effect-free work.
- Gatherers (Java 24, JEP 485): custom intermediate operations (windowing, scanning).

**5 minutes + implementation.** Spliterators and characteristics (SIZED, ORDERED, …), why `limit` on parallel ordered streams is expensive, why side effects in lambdas are bugs, checked exceptions in lambdas, boxing costs (`IntStream`), and debugging with `peek` (only for debugging).

```java
import java.math.BigDecimal;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Gatherers;

record Order(String customerId, String status, BigDecimal total) { }

final class Reports {
    static Map<String, BigDecimal> revenueByCustomer(List<Order> orders) {
        return orders.stream()
                .filter(o -> o.status().equals("PAID"))
                .collect(Collectors.groupingBy(Order::customerId,
                        Collectors.reducing(BigDecimal.ZERO, Order::total, BigDecimal::add)));
    }

    static List<String> top3Customers(List<Order> orders) {
        return revenueByCustomer(orders).entrySet().stream()
                .sorted(Map.Entry.<String, BigDecimal>comparingByValue(Comparator.reverseOrder()))
                .limit(3).map(Map.Entry::getKey).toList();
    }

    static List<List<Integer>> slidingWindows(List<Integer> xs) {
        return xs.stream().gather(Gatherers.windowSliding(3)).toList();   // Java 24+
    }
}
```

*Trap:* "Parallel streams make it faster." Often slower (splitting/merging overhead, contention, blocking in the common pool).

#### 4.5 JVM (class loading, memory, JIT, GC)

**30 seconds.** The JVM loads bytecode, verifies it, interprets and JIT-compiles hot code to native, and manages memory with garbage collectors; understanding it matters for startup, latency, memory and diagnosing production issues.

**2 minutes.**
- Class loading: loading → linking (verification, preparation, resolution) → initialization; parent-delegation class loaders.
- Memory: heap (objects; generational for most collectors), stacks per thread, metaspace (class metadata), code cache, direct buffers.
- JIT: tiered compilation (interpreter → C1 → C2), inlining, escape analysis (scalar replacement), deoptimization.
- GC: G1 is the default (region-based, pause-time goals); ZGC (generational) for very low pauses with large heaps; Parallel for throughput batch jobs; Serial for tiny heaps.
- Containers: JVM is container-aware; size heap with `-XX:MaxRAMPercentage` (e.g., 70–75%) and leave room for non-heap.

**5 minutes + implementation.** GC mechanics (young collections, promotion, mixed collections in G1; concurrent marking; ZGC colored pointers and load barriers), memory leaks in managed languages (static caches, listeners, ThreadLocals in pools, unbounded maps), diagnostics (`jcmd <pid> GC.heap_info`, `jcmd <pid> Thread.print`, `jcmd <pid> JFR.start duration=60s filename=rec.jfr`, heap dumps with `jcmd <pid> GC.heap_dump`, analyzing with JDK Mission Control/Eclipse MAT), startup improvements (CDS, Java 24–25 AOT cache JEPs 483/514/515, Spring AOT/GraalVM native image) and compact object headers (Java 25, `-XX:+UseCompactObjectHeaders`) **[Version-dependent]**.

```text
# Typical container JVM flags for a Spring Boot service
JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+UseG1GC -XX:+ExitOnOutOfMemoryError
                   -Xlog:gc*:stdout:time,uptime -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/dumps"
# Investigate a latency spike
jcmd 1 JFR.start name=spike duration=120s filename=/dumps/spike.jfr settings=profile
```

*Trap:* "Java has no memory leaks because of GC." Reachable-but-unused objects leak.

#### 4.6 Concurrency

**30 seconds.** Concurrency is about correctness (visibility, atomicity, ordering under the Java Memory Model) and throughput (executors, non-blocking I/O, virtual threads); most bugs come from shared mutable state.

**2 minutes.**
- JMM: *happens-before* — unlock → subsequent lock, volatile write → subsequent read, thread start/join, final field semantics. Without it, threads may see stale values.
- Tools: `synchronized`, `ReentrantLock`, `volatile` (visibility, not atomic compound ops), `Atomic*`/`LongAdder`, concurrent collections, `ExecutorService`, `CompletableFuture`.
- Virtual threads (Java 21): cheap threads for blocking I/O; don't pool them; limit access to scarce resources with semaphores; pinning issues with `synchronized` resolved in Java 24.
- Structured concurrency (preview in 25) and scoped values (final in 25) for task lifetimes and context.
- Deadlock, livelock, starvation; lock ordering; timeouts.

**5 minutes + implementation.** Double-checked locking needs `volatile`; `ConcurrentHashMap.computeIfAbsent` for atomic memoization (but avoid long computations in it); `CompletableFuture` composition (`thenCompose` vs `thenApply`, `allOf`, timeouts with `orTimeout`, which executor runs callbacks); thread-dump reading for deadlocks (`Found one Java-level deadlock`); `ThreadLocal` leaks in pools; virtual threads vs reactive.

```java
import java.time.Duration;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;

final class PriceAggregator {
    private final Semaphore supplierLimit = new Semaphore(50);       // backpressure on a scarce downstream

    List<Quote> quotes(List<String> suppliers, SupplierClient client) throws Exception {
        try (ExecutorService exec = Executors.newVirtualThreadPerTaskExecutor()) {
            List<Future<Quote>> futures = suppliers.stream()
                    .map(s -> exec.submit(() -> {
                        supplierLimit.acquire();
                        try { return client.quote(s, Duration.ofSeconds(2)); }   // always time out remote calls
                        finally { supplierLimit.release(); }
                    }))
                    .toList();
            return futures.stream().map(PriceAggregator::getOrNull).filter(q -> q != null).toList();
        }   // close() waits for all tasks
    }

    private static Quote getOrNull(Future<Quote> f) {
        try { return f.get(); } catch (Exception e) { return null; }    // partial results acceptable here
    }

    interface SupplierClient { Quote quote(String supplier, Duration timeout) throws Exception; }
    record Quote(String supplier, java.math.BigDecimal price) { }
}
```

*Trap:* "`volatile` makes `count++` thread-safe." It doesn't; increment is read-modify-write.

#### 4.7 Spring Framework (IoC, beans, proxies, AOP)

**30 seconds.** Spring is an inversion-of-control container that creates and wires objects (beans) and applies cross-cutting behavior (transactions, security, caching) through proxies.

**2 minutes.**
- Startup: scanning/config → `BeanDefinition`s → `BeanFactoryPostProcessor`s modify definitions → instantiation → dependency injection → `BeanPostProcessor`s (where proxies are created) → init callbacks → context refreshed.
- Prefer constructor injection: immutable, explicit, testable, detects cycles.
- Scopes: singleton (default), prototype, request, session.
- Proxies: JDK dynamic proxies (interfaces) or CGLIB subclasses; Spring Boot defaults to CGLIB (`proxyTargetClass=true`).
- Self-invocation bypasses proxies (`this.method()`), so `@Transactional`, `@Cacheable`, `@Async`, `@PreAuthorize` don't apply.

**5 minutes + implementation.** `@Configuration` classes are CGLIB-enhanced so `@Bean` method calls return singletons (`proxyBeanMethods = false` for lite mode and faster startup); `@Conditional` and profiles; circular dependencies (prohibited by default since Boot 2.6); events (`ApplicationEventPublisher`, `@TransactionalEventListener`); Spring AOT for native images; JSpecify null-safety annotations in Framework 7 **[Version-dependent]**.

```java
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
class OrderService {
    private final OrderRepository orders;
    private final OrderService self;          // anti-pattern shown for explanation; prefer splitting beans

    OrderService(OrderRepository orders, @org.springframework.context.annotation.Lazy OrderService self) {
        this.orders = orders;
        this.self = self;
    }

    public void importAll(java.util.List<OrderDto> dtos) {
        for (OrderDto d : dtos) {
            // this.importOne(d) would run WITHOUT a transaction (proxy bypassed)
            self.importOne(d);                  // goes through the proxy → new transaction per order
        }
    }

    @Transactional(propagation = org.springframework.transaction.annotation.Propagation.REQUIRES_NEW)
    public void importOne(OrderDto d) { orders.save(Order.from(d)); }
}
```

Better design: move `importOne` into a separate `OrderImporter` bean.

*Trap:* "`@Transactional` on a private method works." Proxies can't intercept private methods (and self-calls).

#### 4.8 Spring Boot

**30 seconds.** Spring Boot is an opinionated layer over Spring that provides auto-configuration, starters, externalized configuration, embedded servers and production features (Actuator) so applications run with minimal setup. It doesn't replace Spring; it configures it.

**2 minutes.**
- Auto-configuration classes listed in `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, activated by `@ConditionalOnClass`, `@ConditionalOnMissingBean`, `@ConditionalOnProperty`; your beans win.
- Externalized config precedence (command line > env vars > profile-specific files > application files > defaults); `@ConfigurationProperties` (type-safe, validated) over scattered `@Value`.
- Actuator: health (liveness/readiness groups), metrics, info, and observability integration.
- Boot 4: modularized auto-configuration (smaller jars, renamed starters like `spring-boot-starter-webmvc`), Jackson 3, `@MockitoBean` replaces removed `@MockBean`, OpenTelemetry starter **[Version-dependent]**.

**5 minutes + implementation.** Debug auto-configuration with `--debug` (condition evaluation report) or `/actuator/conditions`; `@SpringBootTest` slices; `@ServiceConnection` for Testcontainers; graceful shutdown; layered jars and buildpacks; virtual threads via `spring.threads.virtual.enabled`; Docker Compose support for dev.

```java
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.time.Duration;

@Validated
@ConfigurationProperties("acme.payments")
public record PaymentsProperties(@NotBlank String baseUrl, Duration timeout, @Min(1) int maxRetries) { }
// Register with @ConfigurationPropertiesScan on the application class; invalid config fails startup (fail fast).
```

*Trap:* "Spring Boot replaces Spring."

#### 4.9 JPA / Hibernate

**30 seconds.** JPA maps objects to relational tables; Hibernate implements it with a persistence context that tracks managed entities and flushes changes as SQL. It's productive but you must understand the SQL it generates.

**2 minutes.**
- Entity states: transient, managed, detached, removed; dirty checking at flush.
- Persistence context = first-level cache, scoped to a transaction (or request with open-in-view).
- Lazy loading and the N+1 problem; fixes: fetch joins, `@EntityGraph`, batch fetching, DTO projections.
- Transactions: `@Transactional` boundaries; `readOnly = true` optimizations; flush before queries in AUTO mode.
- Locking: optimistic `@Version`; pessimistic `@Lock(PESSIMISTIC_WRITE)`.
- `spring.jpa.open-in-view` is true by default (with a warning) — disable for APIs to avoid lazy loading in views and long connection holds.

**5 minutes + implementation.** Equality for entities (id-based with care for transient), `@ManyToOne` default EAGER (make LAZY), cascades and orphan removal, bulk updates bypassing the persistence context, pagination with fetch joins (in-memory pagination warning `HHH90003004`), second-level cache trade-offs, `LazyInitializationException`, inspecting SQL (`spring.jpa.show-sql` for dev; better: datasource-proxy/p6spy or Hibernate statistics), Hibernate 7 / Jakarta Persistence 3.2 updates **[Version-dependent]**.

```java
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

interface OrderRepository extends JpaRepository<Order, Long> {

    // N+1 version: findAll() then order.getLines() per order → 1 + N queries
    @EntityGraph(attributePaths = "lines")
    List<Order> findByCustomerId(Long customerId);                  // one query with join

    // DTO projection: no entities, no dirty checking, only needed columns
    @Query("select new com.acme.orders.OrderSummary(o.id, o.status, o.total) from Order o where o.customerId = :c")
    List<OrderSummary> summaries(Long c);
}
```

*Trap:* "JPA means I don't need SQL." You need SQL to understand performance, locking and correctness.

#### 4.10 SQL and PostgreSQL

**30 seconds.** SQL is declarative; performance comes from indexes and query plans; correctness under concurrency comes from transactions, isolation and constraints.

**2 minutes.**
- B-tree indexes for equality/range/sort; composite index column order matters (equality columns first, then range); covering indexes (`INCLUDE`); partial indexes (`WHERE status = 'PENDING'`); GIN for arrays/JSONB/full-text.
- `EXPLAIN (ANALYZE, BUFFERS)` to see actual plans: seq scan vs index scan, row estimates vs actuals, join strategies (nested loop, hash, merge).
- Isolation: READ COMMITTED default; lost updates; `SELECT … FOR UPDATE`; serialization failures at higher levels.
- Constraints enforce invariants: `UNIQUE`, `CHECK`, `FOREIGN KEY`, exclusion constraints.
- Window functions for rankings, running totals, top-N per group.

**5 minutes + implementation.** MVCC (tuples versions, vacuum, bloat), index-only scans and visibility maps, statistics and `ANALYZE`, keyset pagination vs `OFFSET`, deadlocks and lock ordering, connection pooling (PgBouncer transaction mode caveats with prepared statements).

```sql
-- Top 3 orders per customer by total (window function)
SELECT customer_id, id, total
FROM (
  SELECT customer_id, id, total,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY total DESC) AS rn
  FROM orders WHERE status = 'PAID'
) ranked
WHERE rn <= 3;

-- Index supporting "recent paid orders of a customer"
CREATE INDEX idx_orders_customer_paid_created ON orders (customer_id, created_at DESC) WHERE status = 'PAID';

-- Keyset pagination (stable, O(log n) per page)
SELECT id, created_at, total FROM orders
WHERE customer_id = :c AND (created_at, id) < (:lastCreatedAt, :lastId)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

*Trap:* "Add an index on every column." Indexes cost writes and memory, and composite order matters.

#### 4.11 REST API Design

**30 seconds.** REST models resources addressed by URLs, manipulated with HTTP methods whose semantics (safe, idempotent) clients and intermediaries rely on; good APIs are predictable, versioned and explicit about errors.

**2 minutes.**
- Methods: GET (safe), PUT/DELETE (idempotent), POST (not idempotent → Idempotency-Key), PATCH (partial; JSON Merge Patch or JSON Patch).
- Status codes: 200/201/202/204; 400 (malformed), 401 (unauthenticated), 403 (forbidden), 404, 409 (conflict), 412 (precondition failed), 422 (semantic validation), 429, 5xx.
- Errors as RFC 9457 Problem Details (`ProblemDetail` in Spring).
- Pagination (cursor/keyset for large sets), filtering, sorting; consistent naming.
- Versioning (URI `/v1`, header, media type) — Spring Framework 7 adds first-class API versioning support **[Version-dependent]**.
- Concurrency control with ETags (`If-Match`).

**5 minutes + implementation.** DTO vs entity separation, validation with `@Valid`, centralized `@RestControllerAdvice`, HATEOAS trade-offs, long-running operations (202 + status resource), backward compatibility rules (additive changes; tolerant readers), OpenAPI generation.

```java
import jakarta.validation.Valid;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

@RestController
@RequestMapping("/api/v1/customers")
class CustomerController {
    private final CustomerService service;
    CustomerController(CustomerService service) { this.service = service; }

    @PostMapping
    ResponseEntity<CustomerResponse> create(@Valid @RequestBody CreateCustomerRequest req) {
        CustomerResponse created = service.create(req);
        var location = ServletUriComponentsBuilder.fromCurrentRequest().path("/{id}").buildAndExpand(created.id()).toUri();
        return ResponseEntity.created(location).body(created);
    }
}

@RestControllerAdvice
class ApiErrors {
    @ExceptionHandler(CustomerNotFoundException.class)
    ProblemDetail notFound(CustomerNotFoundException e) {
        ProblemDetail pd = ProblemDetail.forStatus(404);
        pd.setTitle("Customer not found");
        pd.setDetail(e.getMessage());
        return pd;
    }
}
```

*Trap:* returning 200 with `{"error": …}` or 500 for validation errors.

#### 4.12 Security (Spring Security, OAuth2, JWT)

**30 seconds.** Spring Security is a filter chain that authenticates requests and authorizes access; modern APIs act as OAuth2 resource servers validating JWTs from an identity provider, with authorization enforced at URL, method and object level.

**2 minutes.**
- `SecurityFilterChain` bean with lambda DSL; `authorizeHttpRequests`; `oauth2ResourceServer(jwt)`.
- JWT validation: signature (JWKS), `iss`, `aud`, `exp`/`nbf`; map scopes/roles to authorities.
- Authentication ≠ authorization; object-level authorization (BOLA) is your code's job.
- CSRF matters for cookie-based sessions; stateless bearer-token APIs typically disable it.
- CORS configured explicitly; password hashing via `DelegatingPasswordEncoder` (bcrypt/argon2).
- Method security: `@EnableMethodSecurity` + `@PreAuthorize` (proxy-based).

**5 minutes + implementation.** Filter chain order, `SecurityContextHolder` strategies and propagation to async threads, token lifetimes and revocation (short-lived access tokens, introspection for revocation-sensitive cases), JWT pitfalls (`alg: none`, accepting tokens for other audiences, storing tokens in localStorage), OAuth2 flows (authorization code + PKCE for apps; client credentials for services), multi-tenancy claims.

```java
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableMethodSecurity
class SecurityConfig {
    @Bean
    SecurityFilterChain api(HttpSecurity http) throws Exception {
        return http
                .csrf(csrf -> csrf.disable())                                  // stateless bearer tokens
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a
                        .requestMatchers("/actuator/health/**").permitAll()
                        .requestMatchers(org.springframework.http.HttpMethod.GET, "/api/v1/customers/**").hasAuthority("SCOPE_customers:read")
                        .requestMatchers("/api/v1/customers/**").hasAuthority("SCOPE_customers:write")
                        .anyRequest().authenticated())
                .oauth2ResourceServer(o -> o.jwt(Customizer.withDefaults()))
                .build();
    }
}
// application.yml: spring.security.oauth2.resourceserver.jwt.issuer-uri + audiences
```

*Trap:* "JWT makes the API secure." JWT is a token format; security comes from validation, authorization and object checks.

#### 4.13 Testing

**30 seconds.** Test pyramid: many fast unit tests, fewer integration tests against real infrastructure (Testcontainers), a few end-to-end tests; test behavior and contracts, not implementation details.

**2 minutes.**
- JUnit 5: `@Test`, `@ParameterizedTest`, `@Nested`, lifecycle, extensions.
- Mockito for collaborators; AssertJ for fluent assertions.
- Spring slices: `@WebMvcTest` (MVC + MockMvc), `@DataJpaTest` (JPA + rollback), `@JsonTest`; `@SpringBootTest` for full context.
- `@MockitoBean` (Boot 4; `@MockBean` removed).
- Testcontainers with `@ServiceConnection` for PostgreSQL, Kafka, Redis — real behavior instead of H2.
- Contract tests between services; mutation testing (PIT) to measure test quality.

**5 minutes + implementation.** Context caching (and how `@MockitoBean`/different properties create new contexts → slow suites), test data builders, deterministic time (`Clock`), concurrency tests with latches, flaky test diagnosis, Testcontainers reuse and singleton containers, `RestTestClient` (Framework 7) / `MockMvcTester` (AssertJ-based) **[Version-dependent]**.

```java
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;   // Boot 4 package; Boot 3: org.springframework.boot.test.autoconfigure.orm.jpa
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers
class OrderRepositoryTest {
    @Container @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:17-alpine");

    @Autowired OrderRepository repo;

    @Test
    void loadsLinesWithoutNPlusOne() {
        // seed, then assert lines are initialized and (optionally) count statements with Hibernate statistics
        assertThat(repo.findByCustomerId(1L)).allSatisfy(o -> assertThat(o.getLines()).isNotNull());
    }
}
```

(Boot 4 moved test auto-configuration annotations into per-technology modules; adjust imports to your version **[Version-dependent]**.)

*Trap:* "H2 is good enough for repository tests." Dialect, locking and constraint behavior differ.

#### 4.14 Kafka

**30 seconds.** Kafka is a distributed, partitioned, replicated commit log; producers append records to topic partitions, consumer groups read them with offsets, giving scalable pub/sub with replay and per-partition ordering.

**2 minutes.**
- Partition = unit of order and parallelism; key determines partition.
- Replication factor (typically 3), `min.insync.replicas=2`, producer `acks=all` for durability.
- Idempotent producer (default on since Kafka 3.0) prevents duplicates from producer retries per partition; transactions give exactly-once read-process-write *within Kafka*.
- Consumer groups: one consumer per partition per group; offsets committed after processing → at-least-once.
- KRaft mode (no ZooKeeper; Kafka 4.x is KRaft-only).
- Spring Kafka: `KafkaTemplate`, `@KafkaListener`, `DefaultErrorHandler`, DLT, `@RetryableTopic`.

**5 minutes + implementation.** Rebalancing and the new consumer group protocol (KIP-848), consumer lag, compaction for changelog topics, schema management (Avro/Protobuf + registry, compatibility modes), ordering vs retries, poison pills (`ErrorHandlingDeserializer`), outbox pattern, choosing partition counts.

```java
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.context.annotation.Bean;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.ExponentialBackOff;

class KafkaConfig {
    @Bean
    DefaultErrorHandler errorHandler(KafkaTemplate<Object, Object> template) {
        var backoff = new ExponentialBackOff(500, 2.0);
        backoff.setMaxElapsedTime(10_000);
        var handler = new DefaultErrorHandler(new DeadLetterPublishingRecoverer(template), backoff);
        handler.addNotRetryableExceptions(IllegalArgumentException.class);   // validation errors → DLT immediately
        return handler;
    }
}

class PaymentEventsListener {
    @KafkaListener(topics = "payments", groupId = "orders")
    void on(ConsumerRecord<String, String> rec) { /* idempotent handling keyed by event id */ }
}
```

*Trap:* "Kafka guarantees global ordering." Only within a partition.

#### 4.15 Microservices

**30 seconds.** Microservices split a system into independently deployable services owning their data, trading in-process simplicity for team autonomy and independent scaling — at the cost of distributed-systems complexity.

**2 minutes.**
- Boundaries by business capability/bounded context; each service owns its database.
- Communication: sync (REST/gRPC) for queries needing immediate answers; async (events) for decoupling.
- Consistency across services: sagas (orchestration/choreography), outbox, idempotency.
- Cross-cutting: API gateway, service discovery (or platform DNS), config, resilience (timeouts, retries, circuit breakers), observability (distributed tracing).
- When not to: small teams, unclear domains — a modular monolith (e.g., Spring Modulith) first.

**5 minutes + implementation.** Distributed monolith anti-pattern (synchronous chains, shared DB), data duplication and read models, versioning and contract testing, deployment independence (CI/CD per service), team topology (Conway's law), migration via strangler fig.

```java
// Resilient synchronous call with RestClient + Resilience4j annotations (Spring Cloud Circuit Breaker or resilience4j-spring-boot)
@Service
class InventoryClient {
    private final org.springframework.web.client.RestClient client;
    InventoryClient(org.springframework.web.client.RestClient.Builder b) {
        this.client = b.baseUrl("http://inventory").build();         // timeouts configured on the request factory
    }

    @io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker(name = "inventory", fallbackMethod = "unknown")
    @io.github.resilience4j.retry.annotation.Retry(name = "inventory")   // only for idempotent GETs
    Availability availability(String sku) {
        return client.get().uri("/skus/{sku}/availability", sku).retrieve().body(Availability.class);
    }

    Availability unknown(String sku, Throwable t) { return Availability.unknown(sku); }   // graceful degradation
}
```

*Trap:* "Microservices are more scalable by default."

#### 4.16 Docker and Containers

**30 seconds.** Containers package an application with its runtime into an immutable image run in isolated processes; for Java, build small, layered, non-root images and make the JVM respect container limits.

**2 minutes.**
- Images are layered; order Dockerfile steps from least to most frequently changing to maximize cache hits.
- Multi-stage builds: build in a JDK image, run on a JRE/distroless image.
- Spring Boot layered jars (dependencies, spring-boot-loader, snapshot-dependencies, application) or buildpacks (`./gradlew bootBuildImage`).
- Run as non-root, read-only filesystem, health checks, resource limits; JVM `MaxRAMPercentage`.
- Config via environment; secrets from a secret manager, not baked into images.

**5 minutes + implementation.** Image scanning (Trivy/Grype), SBOMs, reproducibility, distroless vs alpine (musl) trade-offs, CDS/AOT cache for faster startup, signal handling (PID 1, `exec` form), graceful shutdown with orchestrator timeouts.

```dockerfile
# syntax=docker/dockerfile:1
FROM eclipse-temurin:25-jdk AS build
WORKDIR /src
COPY . .
RUN ./gradlew --no-daemon bootJar && \
    java -Djarmode=tools -jar build/libs/app.jar extract --layers --launcher --destination /extracted

FROM eclipse-temurin:25-jre
RUN useradd --system --uid 10001 app
WORKDIR /app
COPY --from=build /extracted/dependencies/ ./
COPY --from=build /extracted/spring-boot-loader/ ./
COPY --from=build /extracted/snapshot-dependencies/ ./
COPY --from=build /extracted/application/ ./
USER 10001
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError"
EXPOSE 8080
ENTRYPOINT ["java", "org.springframework.boot.loader.launch.JarLauncher"]
```

*Trap:* setting `-Xmx` equal to the container limit (no room for metaspace, threads, direct memory → OOMKilled).

#### 4.17 AWS for Java Services

**30 seconds.** A typical AWS deployment runs containers on ECS Fargate or EKS behind an Application Load Balancer, with RDS/Aurora PostgreSQL, ElastiCache, MSK or SQS/SNS, S3, IAM roles for credentials, Secrets Manager and CloudWatch/OTel for observability — all inside a VPC.

**2 minutes.**
- Networking: VPC with public subnets (ALB, NAT) and private subnets (services, databases); security groups as stateful firewalls.
- Compute: ECS Fargate (simpler, serverless containers) vs EKS (Kubernetes ecosystem, more control) vs Lambda (event-driven, short tasks; SnapStart for Java cold starts).
- Data: RDS Multi-AZ / Aurora; ElastiCache (Redis/Valkey); MSK (Kafka) or SQS/SNS/EventBridge.
- Identity: IAM task roles (no static keys); least-privilege policies; Secrets Manager/Parameter Store.
- Delivery: ECR images, CI/CD (GitHub Actions/CodePipeline), infrastructure as code (Terraform/CDK).

**5 minutes + implementation.** Multi-AZ design, autoscaling policies (target tracking on CPU/requests), blue/green with CodeDeploy, cost levers (Graviton, Savings Plans, right-sizing), private connectivity (VPC endpoints), observability (CloudWatch, X-Ray vs OTel → ADOT), disaster recovery (RPO/RTO, cross-region snapshots).

```hcl
# Terraform excerpt: ECS service behind an ALB with a task role (no static credentials)
resource "aws_ecs_task_definition" "api" {
  family                   = "orders-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 2048
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.orders_api_task.arn      # app permissions (S3, SQS, Secrets)
  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    portMappings = [{ containerPort = 8080 }]
    secrets      = [{ name = "SPRING_DATASOURCE_PASSWORD", valueFrom = aws_secretsmanager_secret.db.arn }]
    healthCheck  = { command = ["CMD-SHELL", "curl -f http://localhost:8080/actuator/health/liveness || exit 1"] }
  }])
}
```

*Trap:* storing AWS access keys in application properties.

#### 4.18 System Design

**30 seconds.** System design is structured trade-off reasoning: requirements and estimates → API → data model → architecture → scaling → failures → security → observability → trade-offs, starting simple and scaling on evidence.

**2 minutes.** Summarize Unit 38's template, key numbers (99.9% ≈ 43 min/month; Little's law), core mechanisms (cache-aside, outbox, idempotency keys, token buckets, sagas, read replicas) and the habit of naming the source of truth and failure modes.

**5 minutes + implementation.** Walk through one design (e.g., payment service) with estimates, idempotency and reconciliation, and cite your implemented toolkit (rate limiter, idempotency, outbox) as evidence.

*Trap:* jumping to microservices, Kafka and sharding before stating requirements.

### 5. Internal Mechanics — What Interviewers Probe Most

| Topic | "Go one level deeper" probe | What a strong answer includes |
|---|---|---|
| HashMap | "What happens on resize?" | Table doubles, entries split by the new hash bit, O(n) rehash cost amortized |
| ConcurrentHashMap | "Why no null values?" | Ambiguity between absent and null under concurrency |
| Streams | "When does `filter` run?" | Lazily, element by element, during the terminal operation |
| JVM | "Why did p99 spike every few minutes?" | GC pauses/allocation spikes; check GC logs, JFR; tune or reduce allocation |
| Concurrency | "Why is double-checked locking broken without volatile?" | Reordering may publish a partially constructed object |
| Spring | "When is the proxy created?" | `BeanPostProcessor` (`AbstractAutoProxyCreator`) after initialization |
| `@Transactional` | "Exception thrown, why no rollback?" | Checked exception (default rolls back only on unchecked) or self-invocation or caught inside |
| JPA | "Why `LazyInitializationException`?" | Accessing lazy association after the persistence context closed |
| SQL | "Why isn't my index used?" | Leading column not in predicate, function on column, low selectivity, stale stats, type mismatch |
| Security | "Where is the JWT validated?" | `BearerTokenAuthenticationFilter` → `JwtAuthenticationProvider` → `JwtDecoder` (signature, issuer, timestamps, audience if configured) |
| Kafka | "Duplicate processing after rebalance?" | Offsets committed after processing; uncommitted work replays → idempotent consumers |
| Docker | "Why OOMKilled with heap at 50%?" | Non-heap memory: metaspace, thread stacks, direct buffers, code cache, native libs |

### 6. Implementation Examples

#### Example 1 — Minimal: the "explain with code" drill

Pick any topic and, in under 5 minutes, write the smallest program that demonstrates its key insight. Examples:

```java
// Visibility without happens-before: may never terminate (JIT may hoist the read)
class StopFlag {
    static boolean running = true;           // add `volatile` to fix
    public static void main(String[] args) throws InterruptedException {
        Thread worker = new Thread(() -> { long n = 0; while (running) n++; System.out.println("stopped"); });
        worker.start();
        Thread.sleep(100);
        running = false;
        worker.join(1000);
        System.out.println("worker alive? " + worker.isAlive());
    }
}
```

```java
// Mutable key lost in a HashMap
import java.util.*;
class MutableKey {
    static final class Key { int v; Key(int v) { this.v = v; }
        @Override public boolean equals(Object o) { return o instanceof Key k && k.v == v; }
        @Override public int hashCode() { return Integer.hashCode(v); } }
    public static void main(String[] args) {
        Map<Key, String> m = new HashMap<>();
        Key k = new Key(1); m.put(k, "x"); k.v = 2;
        System.out.println(m.get(k) + " " + m.get(new Key(1)) + " " + m.size()); // null null 1
    }
}
```

#### Example 2 — Realistic: a 2-minute answer with evidence

> **Q: How do you prevent N+1 queries in JPA?**
> "N+1 happens when you load N parents and lazily access a collection on each, triggering one query per parent. I detect it with Hibernate statistics or datasource-proxy assertions in tests — in my capstone I had a test asserting a maximum statement count for the order-history endpoint. Fixes: a fetch join or `@EntityGraph` for that use case, batch fetching (`hibernate.default_batch_fetch_size`) for broad mitigation, or a DTO projection when I only need a few columns. Fetch joins with pagination are a trap — Hibernate paginates in memory — so for paged lists I page parent ids first, then fetch children with `IN`. The endpoint went from 41 queries to 2, and p95 from 180 ms to 25 ms in my load test."

#### Example 3 — Production-oriented: a 5-minute deep dive with a failure story

> **Q: Tell me about a concurrency bug you fixed.**
> Structure: context (approval executor in the capstone), symptom (duplicate refunds under duplicate Kafka events), investigation (traces showed two `execute_tool` spans with different consumer instances; code did `findById` then `if APPROVED` then execute — check-then-act), root cause (race between instances; Kafka at-least-once), fix (conditional `UPDATE … WHERE status='APPROVED'` claim; PSP idempotency key; unique constraint as a backstop), evidence (8-thread latch test; chaos test with duplicate events), lesson (prefer database atomicity over application checks and distributed locks), code (show the repository method).

### 7. Comparative Analysis

| Pair | Key difference | When to use | Interview trap |
|---|---|---|---|
| record vs class | Transparent immutable data carrier vs general-purpose type | Records for DTOs/values/events; classes for encapsulated mutable state, JPA entities | Records as JPA entities (no no-arg constructor, final fields, proxies) |
| interface vs abstract class | Contract (+ default methods, no state) vs partial implementation with state | Interfaces for capabilities/APIs; abstract classes for shared state/templates | "Interfaces can't have implementation" |
| `==` vs `equals()` | Reference vs logical equality | `equals` for values; `==` for identity/enums/primitives | `Integer` cache (−128..127) making `==` "work" |
| HashMap vs ConcurrentHashMap | Not thread-safe vs concurrent | CHM for shared mutable maps | `Collections.synchronizedMap` + compound ops still racy |
| checked vs unchecked | Must declare/handle vs not | Checked for recoverable conditions callers must handle; unchecked otherwise | Wrapping everything in `RuntimeException` loses meaning; or catching `Exception` broadly |
| composition vs inheritance | Has-a vs is-a | Prefer composition; inherit for true subtype relationships | Inheriting for code reuse |
| virtual threads vs reactive | Blocking style with cheap threads vs non-blocking streams with backpressure | VTs for typical I/O services; reactive for streaming/backpressure-heavy pipelines | "VTs make code faster" (they increase concurrency, not speed) |
| `@Component` vs `@Bean` | Scanned class vs factory method | `@Bean` for third-party classes or conditional construction | — |
| JPA vs JDBC (`JdbcClient`) | ORM with persistence context vs explicit SQL | JPA for aggregate CRUD; JDBC for reporting, bulk, complex SQL | "Always JPA" |
| REST vs messaging | Request/response vs async events | REST for queries and commands needing immediate answers; messaging for decoupling and fan-out | Using Kafka for request/reply by default |
| ECS vs EKS | Managed container service vs managed Kubernetes | ECS for simplicity on AWS; EKS for K8s ecosystem/portability | — |
| Unit vs integration tests | Isolated logic vs real infrastructure | Both; Testcontainers for persistence/messaging | Mock everything |

### 8. Failure Modes and Debugging (interview-style incidents)

| Incident | Investigation | Root cause | Fix |
|---|---|---|---|
| `OutOfMemoryError: Java heap space` after a week | Heap dump (`jcmd GC.heap_dump`), MAT dominator tree | Unbounded static cache map | Bounded Caffeine cache with eviction |
| Container OOMKilled, heap OK | Native memory tracking (`-XX:NativeMemoryTracking=summary`, `jcmd VM.native_memory`) | Too many threads/direct buffers; `-Xmx` too close to limit | `MaxRAMPercentage`, limit threads, cap direct memory |
| Requests hang, CPU idle | Thread dump | Deadlock or pool exhaustion waiting on DB/HTTP without timeouts | Lock ordering; timeouts; bulkheads |
| `@Transactional` not rolling back | Logs (`org.springframework.transaction` DEBUG) | Checked exception, self-invocation, or swallowed exception | `rollbackFor`, separate bean, rethrow |
| Slow endpoint after data growth | SQL logs + `EXPLAIN ANALYZE` | Missing composite index / N+1 | Index, fetch strategy, projection |
| 401 for valid tokens in prod | Security DEBUG logs | Issuer/audience mismatch, clock skew, JWKS unreachable | Correct config; allow small skew; network to JWKS |
| Consumer lag growing | Lag per partition, processing time | Poison message with blocking retries | DLT for non-retryable errors |
| Flaky integration tests | Test logs, ordering | Shared state between tests, time dependence | Isolate data, inject `Clock`, deterministic waits (Awaitility) |

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Three-depth cards.* For all 18 topics, write your own 30-second answer in ≤ 60 words and a 2-minute bullet list. Record yourself; cut filler. Hints: lead with the key insight; end with a trade-off.

*1.2 Predict the output.* Write 15 snippets (Integer cache, string interning, `List.of` immutability, stream laziness, `HashSet` with mutable elements, `finally` overriding return, `switch` exhaustiveness, `CompletableFuture` exception propagation). Predict, run, explain.

**Level 2 — Implementation**

*2.1 Implement from memory (no IDE, 10 minutes each):* LRU cache; thread-safe counter three ways; generic `max` with PECS; `groupingBy` report; `@ConfigurationProperties` record; `SecurityFilterChain`; `@DataJpaTest` with Testcontainers; Kafka `DefaultErrorHandler`; multi-stage Dockerfile. Then compile and fix.

*2.2 Evidence bank.* For each topic, write one evidence statement (context → decision → mechanism → evidence → lesson) from your capstone or earlier projects. If you have none for a topic, build a 1-hour spike to create one.

**Level 3 — Integration**

*3.1 Mock technical interview (60 min).* A partner picks 6 topics; for each, asks a 30-second question, then pulls to 2 and 5 minutes, then asks for code. Score: accuracy, structure, evidence, trade-offs.

*3.2 Code review drill.* Review a 150-line Spring service seeded with 10 issues (field injection, `@Transactional` on private method, N+1, `double` money, missing timeouts, swallowed exceptions, entity returned from controller, no validation, `synchronized` on a singleton bottleneck, `Optional.get()`); explain each in one sentence and fix.

**Level 4 — Debugging / Production Scenario**

*4.1 Diagnose from artifacts.* Given a thread dump excerpt with 200 threads `WAITING` in `HikariPool.getConnection` and one `RUNNABLE` in a slow query, explain and propose fixes.

*4.2 Diagnose from a heap histogram.* Top entries: `byte[]` 2 GB, `java.util.HashMap$Node` 40M instances, `com.acme.cache.SessionEntry` 40M. Explain and fix.

### 10. Independent Implementation Project

**Goal.** Build a **Java Interview Evidence Repository**: one repo with small, runnable demos for every topic plus your written three-depth answers and evidence statements.

**Requirements.**
1. `topics/<topic>/README.md` with 30-second, 2-minute, 5-minute answers and the trap.
2. `topics/<topic>/src/...` with a runnable demo and a JUnit 5 test proving the key behavior (e.g., N+1 statement count, visibility fix, `@Transactional` self-invocation demonstration, Kafka DLT routing).
3. `evidence.md` mapping topics → capstone artifacts (class, test, metric, incident).
4. `drills.md` with your recorded drill dates and scores.

**Technical requirements.** Java 25, Gradle multi-project (or Maven modules), Spring Boot 4, Testcontainers, JUnit 5, AssertJ.

**Suggested structure.**

```
java-interview-evidence/
├── settings.gradle.kts
├── topics/
│   ├── language/ collections/ generics/ streams/ jvm/ concurrency/
│   ├── spring-core/ spring-boot/ jpa/ sql/ rest/ security/ testing/ kafka/
│   ├── microservices/ docker/ aws/ system-design/
│   └── (each) README.md, src/main/java, src/test/java
├── evidence.md
└── drills.md
```

**Milestones.** Week 1: language, collections, generics, streams. Week 2: JVM, concurrency. Week 3: Spring core/Boot, JPA, SQL. Week 4: REST, security, testing, Kafka. Week 5: microservices, Docker, AWS, system design; mock interviews.

**Testing requirements.** Every demo has at least one test that *fails* when the key insight is violated (e.g., removing `volatile`, adding self-invocation, removing the entity graph).

**Definition of Done.**
- [ ] 18 topic folders with answers, demo and test.
- [ ] Evidence statement for every topic.
- [ ] Three recorded mock interviews with improvement notes.

**Optional extensions.** JMH benchmarks (ArrayList vs LinkedList, boxing costs); JFR recording analysis write-up; GraalVM native image comparison.

### 11. Testing Strategy

How to test *your interview readiness*:

- **Retrieval tests:** random topic + random depth, timed; pass if accurate, structured and within time.
- **Code tests:** write from memory, then compile; track compile/logic errors.
- **Explain-the-test:** for each demo, explain why the test fails when the insight is violated.
- **Peer review:** a partner checks for imprecise statements (e.g., "HashMap is O(1)").
- **Spaced repetition log:** topics answered poorly return in 1/3/7 days.

### 12. Engineering Scenarios

**Scenario 1 — "Our Spring service is slow; where do you start?"** Expected reasoning: define slow (p50/p95/p99, which endpoints), check metrics and traces for the dominant span, DB time vs app time, connection pool waits, GC pauses (logs/JFR), thread dumps under load; form hypotheses, measure, fix the biggest contributor, verify with load test.

**Scenario 2 — "Should we migrate to virtual threads?"** Expected reasoning: what's the workload (blocking I/O heavy?), what are the scarce resources (DB pool, downstream limits), libraries that pin or use `ThreadLocal` heavily, observability support; pilot with load tests; add explicit backpressure; measure throughput and latency.

**Scenario 3 — FDE: customer's Java 11 / Spring Boot 2 legacy app needs to integrate with your agent platform.** Expected reasoning: clarify integration surface (REST/webhooks/Kafka), auth (OAuth client credentials), avoid forcing their upgrade for the integration; provide an OpenAPI contract and a thin client; note security/support risks of EOL versions and recommend an upgrade path separately.

**Scenario 4 — "Explain a production incident you caused."** Expected reasoning: own it, structure (impact, detection, mitigation, root cause, fixes, prevention), show learning and systemic fixes rather than blame.

### 13. Interview Preparation

#### Quick Questions (30–60 seconds)

1. **`equals`/`hashCode` contract?** Equal objects must have equal hash codes; hash codes may collide; both must use the same fields; mutable fields in hash-based keys are dangerous.
2. **Why are strings immutable?** Security (class loading, paths), thread safety, caching hash codes, string pool interning.
3. **`final` vs `finally` vs finalization?** Modifier; try block clause; deprecated-for-removal object finalization (use `Cleaner`/try-with-resources).
4. **What is a functional interface?** One abstract method; target for lambdas/method references.
5. **`Optional` best practice?** Return type for "may be absent"; not for fields/parameters; avoid `get()` without check — use `orElseThrow`, `map`, `orElse`.
6. **Bean scopes?** Singleton, prototype, request, session, application.
7. **`@Transactional` default rollback rule?** Unchecked exceptions and errors roll back; checked don't unless `rollbackFor`.
8. **What does `spring.jpa.open-in-view` do?** Keeps the persistence context open for the whole web request (lazy loading in controllers/views); default true with a warning; disable for APIs.
9. **401 vs 403?** Not authenticated vs authenticated but not allowed.
10. **Kafka ordering?** Per partition only.

#### Intermediate Questions

**Q: Explain how `@Transactional` works and three ways it silently fails.**
*Strong answer:* A `BeanPostProcessor` wraps the bean in a proxy; the `TransactionInterceptor` asks the `PlatformTransactionManager` to begin/join a transaction according to propagation, binds the connection to the thread, invokes the method, commits or rolls back based on rules. Silent failures: self-invocation, non-public methods, checked exceptions without `rollbackFor`, exceptions caught inside, work on other threads (`@Async`, executors) not joining the transaction, wrong transaction manager with multiple data sources.
*Why asked:* Tests understanding of proxies and transaction boundaries. *Trap:* "It just wraps the method in a transaction."

**Q: How does `ConcurrentHashMap` achieve thread safety?**
*Strong answer:* Fine-grained: CAS for inserting into empty bins, `synchronized` on the first node of a bin for updates, volatile reads for lock-free `get`, treeification for long bins, concurrent resize with forwarding nodes, striped counters for size. Atomic per-key operations via `compute`/`merge`. Compound operations across keys aren't atomic.

**Q: Explain the JVM memory areas and a time you diagnosed a memory problem.**
*Strong answer:* Heap (young/old or regions), metaspace, thread stacks, code cache, direct memory; then an evidence story with heap dump analysis or native memory tracking.

#### Advanced Questions

**Q: Virtual threads vs reactive programming — which would you choose for a new I/O-heavy service and why?**
*Strong answer:* Default to virtual threads with Spring MVC: simpler code, debuggable stack traces, works with blocking JDBC; add explicit backpressure. Choose reactive (WebFlux) when you need streaming with backpressure end to end, very high connection counts with mostly idle streams (SSE/WebSockets), or an existing reactive ecosystem. Mention pinning resolved in Java 24, `ThreadLocal` costs, and that neither makes CPU-bound work faster.

**Q: How would you find and fix a slow query in production?**
*Strong answer:* Identify via traces/APM or `pg_stat_statements`; reproduce with parameters; `EXPLAIN (ANALYZE, BUFFERS)`; check estimates vs actuals, seq scans, sorts spilling to disk; fix via index (correct column order, partial/covering), query rewrite, statistics, or data model change; verify with plan and latency; watch write overhead.

**Q: Design the error-handling strategy of a Spring REST API.**
*Strong answer:* Domain exceptions mapped centrally with `@RestControllerAdvice` to RFC 9457 Problem Details; validation errors with field details (422 or 400 by convention); no stack traces to clients; correlation/trace id in responses; consistent error codes; logging at the right level (4xx info/warn, 5xx error); idempotency and retry guidance (Retry-After).

#### Coding Questions

1. Implement a thread-safe, bounded, blocking queue using `ReentrantLock` and two `Condition`s.
2. Implement `groupingBy` manually with a `HashMap`, then with streams.
3. Write a JPA repository method avoiding N+1 for orders with lines; write a test that counts statements.
4. Implement a Spring `HandlerInterceptor` that adds a correlation id to MDC and response headers.
5. Write a Kafka listener that is idempotent with a processed-events table.

#### Scenario Questions

**Q: You join a team whose Spring Boot 3.3 app must move to Boot 4. Plan?** Inventory (Java version ≥ 17, Jakarta EE 11, Jackson 3 changes, removed APIs like `@MockBean`, renamed starters/modules, Spring Security 7 changes, Hibernate 7); upgrade to latest 3.5 first and fix deprecations; use OpenRewrite recipes; run full tests incl. contract tests for JSON changes (Jackson 3 defaults); staged rollout; monitor.

### 14. Explain-It-at-Three-Levels — Your Own Project

The most important three-level explanation in any Java interview is **your own system**:

- *30 seconds:* "I built a Spring Boot 4 support-agent platform: OAuth2-secured REST APIs, PostgreSQL/pgvector, Redis, Kafka; an LLM agent with typed decisions, a policy-enforcing tool gateway, human approvals, evals in CI and OpenTelemetry tracing."
- *2 minutes:* Request flow from JWT to response; where determinism lives (authZ, gateway, approvals); data stores and why; async parts (outbox → Kafka → workers); how you test (Testcontainers, scripted models, eval suite); one metric and one incident.
- *5 minutes:* Deep dive on one hard part chosen by the interviewer: exactly-once refund execution, retrieval quality and evaluation, trace-based debugging of a failed request, or performance under load — with code and evidence.

### 15. Knowledge Check

**Conceptual**
1. Why must `hashCode` be overridden when `equals` is?
2. What problem do sealed interfaces solve when combined with pattern matching?
3. Why can't you create `new T[]` in a generic class?
4. What is a happens-before relationship? Give two examples.
5. What does Spring Boot auto-configuration do when you define your own `DataSource` bean?

**Code reading**
6. Output?
```java
Integer a = 127, b = 127, c = 128, d = 128;
System.out.println((a == b) + " " + (c == d));
```
7. Does this roll back? `@Transactional public void pay() throws IOException { repo.save(x); throw new IOException(); }`
8. What's wrong? `orders.stream().map(o -> { total += o.total(); return o; }).count();`

**Debugging**
9. A `@Scheduled` method runs on every instance in a cluster, causing duplicate emails. Options?
10. After upgrading to Boot 4, an API client complains that responses now include fields it didn't expect / dates changed format. What changed and how do you handle it?

**Design**
11. When would you choose a modular monolith over microservices?
12. ECS Fargate or EKS for a team of five shipping three services?

### Knowledge Check Answers

1. Hash-based collections use `hashCode` to choose a bucket before `equals`; equal objects with different hash codes land in different buckets and won't be found.
2. Closed hierarchies let the compiler check `switch` exhaustiveness and remove default branches, so adding a variant forces all handlers to be updated.
3. Due to erasure, `T` is unknown at runtime, so the array's runtime component type can't be determined (and arrays are reified/covariant); use `List<T>` or pass a `Class<T>`/`IntFunction<T[]>`.
4. A guarantee that memory effects of one action are visible to another: unlocking a monitor → subsequent lock of it; volatile write → subsequent volatile read; `Thread.start` → actions in the started thread; thread actions → `join` returning.
5. `@ConditionalOnMissingBean` backs off: auto-configuration doesn't create its own `DataSource`.
6. `true false` — `Integer.valueOf` caches −128..127; 128 creates distinct objects.
7. No — checked exceptions don't trigger rollback by default; use `rollbackFor = IOException.class`.
8. Side effects in a lambda (and `total` must be effectively final — this won't compile for a local; for a field it's a race in parallel streams). Also, since Java 9, `count()` may skip executing `map` entirely when the size is known from the source — side effects may never run. Use `mapToDouble(...).sum()`/`reduce`.
9. ShedLock (DB-based lock with `lockAtMostFor`), a single scheduler instance/leader election, move to a queue-based job with idempotent processing, or make the job idempotent with conditional updates.
10. Jackson 3 defaults (e.g., unknown-property handling, date formats as ISO strings by default, other JSTEP-2 changes) and Boot 4 configuration changes; add contract tests, configure `spring.jackson.*` explicitly or use the Jackson-2-compatible defaults property during migration, communicate API changes.
11. Small/medium team, unclear domain boundaries, need for fast iteration and simple operations; enforce module boundaries (Spring Modulith) and split later if scaling or team autonomy requires.
12. ECS Fargate — less operational overhead; choose EKS when you need Kubernetes ecosystem features, portability or already have platform expertise.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "Immutable means final." | Final prevents reassignment; immutability needs no mutation paths including components. |
| "HashMap is always O(1)." | Average with good hashing; resizes and collisions cost. |
| "Spring Boot replaces Spring." | It auto-configures Spring. |
| "JWT automatically makes an API secure." | Validation, authorization, object checks, lifetimes. |
| "`volatile` makes operations atomic." | Visibility and ordering only. |
| "Parallel streams are faster." | Only for large CPU-bound splittable work. |
| "Virtual threads make code faster." | They make blocking concurrency cheap; bottlenecks move. |
| "JPA removes the need for SQL." | You must read the SQL and plans. |
| "Kafka is exactly-once end to end." | Effects outside Kafka need idempotency. |
| "Microservices are best practice." | They're a trade-off; modular monoliths are often better. |

### 17. Cheat Sheet

- **Language:** records (compact ctor, defensive copies), sealed + `switch` patterns + `when`, `equals/hashCode` contract, checked vs unchecked.
- **Collections:** ArrayList 1.5× growth; HashMap load 0.75, treeify 8 (cap ≥ 64), untreeify 6; CHM: CAS + bin sync, no nulls; `List.of` unmodifiable, no nulls; `Stream.toList()` unmodifiable.
- **Generics:** erasure; PECS; type tokens.
- **Streams:** lazy; stateless vs stateful; `toMap` merge; parallel = common FJP; gatherers (24).
- **JVM:** G1 default; generational ZGC; `MaxRAMPercentage`; `jcmd Thread.print / GC.heap_dump / JFR.start`; compact headers (25, opt-in).
- **Concurrency:** happens-before; `volatile` ≠ atomic; `LongAdder`; VTs + semaphores; scoped values (25 final); structured concurrency (preview).
- **Spring:** BeanDefinition → BFPP → instantiate → inject → BPP (proxies) → init; constructor injection; self-invocation bypasses proxies.
- **Boot:** `AutoConfiguration.imports`; `@ConditionalOnMissingBean`; `--debug` conditions; Boot 4: modules, Jackson 3, `@MockitoBean`, OTel starter.
- **JPA:** states; dirty checking; N+1 → entity graph/fetch join/batch/DTO; open-in-view off; `@Version`.
- **SQL:** composite index order; `EXPLAIN (ANALYZE, BUFFERS)`; keyset pagination; window functions; READ COMMITTED default.
- **REST:** method semantics; status codes; ProblemDetail (RFC 9457); Idempotency-Key; cursor pagination; ETags.
- **Security:** `SecurityFilterChain`; resource server JWT (sig, iss, aud, exp); BOLA checks; CSRF for cookies; `@PreAuthorize` proxies.
- **Testing:** slices; Testcontainers + `@ServiceConnection`; `@MockitoBean`; context caching.
- **Kafka:** partition order; acks=all + min ISR; idempotent producer default; at-least-once consumers; DLT.
- **Docker:** multi-stage, layered jar extract (`-Djarmode=tools`), non-root, `MaxRAMPercentage`.
- **AWS:** VPC public/private, ALB, ECS Fargate/EKS, RDS/Aurora, ElastiCache, MSK/SQS, IAM task roles, Secrets Manager.
- **Evidence format:** context → decision → mechanism → evidence → lesson.

### 18. Completion Checklist

- [ ] I can answer every topic at 30 s, 2 min and 5 min within time.
- [ ] I can write each topic's demo code from memory and it compiles.
- [ ] I can predict and explain the tricky-code outputs.
- [ ] I have an evidence statement for every topic.
- [ ] I can debug memory, thread, transaction, query, security and Kafka incidents with the right tools.
- [ ] I can state version-dependent facts precisely.
- [ ] I completed three recorded mock interviews and improved on weak topics.

### 19. Further Research

**Essential**
- Java Language Specification and JEPs for features you cite (records 395, sealed 409, pattern matching for switch 441, virtual threads 444, gatherers 485, JEP 491, scoped values 506). <https://openjdk.org/jeps/0>
- Spring Framework reference: core container, AOP, transactions. <https://docs.spring.io/spring-framework/reference/>
- Spring Boot reference and Boot 4 migration guide. <https://docs.spring.io/spring-boot/>
- Spring Security reference: servlet architecture, resource server JWT. <https://docs.spring.io/spring-security/reference/>
- Hibernate ORM user guide (fetching, batching, locking). <https://hibernate.org/orm/documentation/>
- PostgreSQL docs: indexes, `EXPLAIN`, concurrency control. <https://www.postgresql.org/docs/current/>

**Deeper Study**
- *Effective Java* (Bloch, 3rd ed.) — equality, generics, concurrency items.
- *Java Concurrency in Practice* (Goetz et al.) — still the best foundation for the JMM and concurrent design.
- *High-Performance Java Persistence* (Mihalcea).
- JDK Mission Control and JFR documentation.

**Practice**
- Build the evidence repository; schedule weekly mock interviews; use OpenRewrite recipes on a sample Boot 3 app to practice upgrades.

### Unit Completion Standard

Before moving on, you must be able to: **explain** every topic in this unit — Java language, collections, generics, streams, JVM, concurrency, Spring, Spring Boot, JPA, SQL, REST, security, testing, Kafka, microservices, Docker, AWS and system design — at 30-second, 2-minute and 5-minute depth with correct, version-aware details; **implement** each topic's demonstration code from memory; **test** each key behavior with a JUnit 5 test that fails when the insight is violated; **debug** representative production incidents using thread dumps, heap dumps, JFR, `EXPLAIN ANALYZE`, security logs and consumer-lag metrics; and **defend** your answers in an interview with implementation evidence from your own projects rather than memorized definitions.
