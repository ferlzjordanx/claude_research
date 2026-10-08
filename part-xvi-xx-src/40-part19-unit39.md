# Part XIX — Interview Preparation

**What this part teaches.** Part XIX turns the whole curriculum into interview performance. Unit 39 covers the Java and backend knowledge track, with every topic prepared at three depths. Unit 40 is the algorithms track with a fixed problem-solving procedure. Unit 41 is timed Spring Boot builds. Unit 42 covers AI/FDE interviews: agent architecture defense and scenario questions.

**Why it matters.** Interviews compress months of work into 45-minute samples. Knowledge you can't retrieve under pressure, explain at the right depth, or back with evidence of having built something doesn't count. The meta-skill is **calibrated explanation**: a crisp 30-second answer, a 2-minute expansion when invited, and a 5-minute deep dive anchored in code you actually wrote.

**Where it appears.** Phone screens (30-second answers), technical rounds (2–5-minute explanations), live coding (Units 40–41), system design (Unit 38), architecture defense of your capstone (Units 42–43), and FDE customer simulations.

**Connections.** Every earlier unit. The capstone (Unit 43) is your evidence bank: whenever this part says "implementation evidence", it means a specific class, test, trace or metric from your repository.

**Evidence over definitions.** Interviewers have heard the textbook definition many times. What distinguishes candidates is evidence:

```
Weak:   "HashMap is O(1)."
Strong: "Average O(1) for get/put. Since Java 8, a bucket with ≥ 8 entries (and table ≥ 64)
         becomes a red-black tree, so worst case is O(log n), not O(n). In my capstone
         I had a hot-key issue in a Caffeine cache, not HashMap. Here's how I measured it…"
```

Use **STAR-T** for experience questions: Situation, Task, Action, Result, **Trade-off** (what you'd do differently, and what you rejected).

## Unit 39 — Java Interview Track

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Explain** each of 18 topics (Java language, collections, generics, streams, JVM, concurrency, Spring, Boot, JPA, SQL, REST, security, testing, Kafka, microservices, Docker, AWS, system design) at three depths: 30 seconds, 2 minutes, and 5 minutes with an implementation example.
2. **Retrieve** precise facts under pressure (complexities, defaults, version differences) and **flag** version-dependent claims correctly (Java 17/21/25, Spring Boot 3 vs 4).
3. **Back** each answer with implementation evidence from your own code: class names, tests, metrics, traces, incidents.
4. **Diagnose** common interview traps (immutability vs `final`, `HashMap` complexity, `@Transactional` self-invocation, N+1, JWT "security", Kafka "exactly-once") and **answer** with the correct mental model.
5. **Debug** classic Java/Spring problems verbally: memory leaks, deadlocks, lazy-loading exceptions, connection-pool exhaustion, consumer lag.
6. **Build** a personal question bank with timed self-recordings and an evidence map linking each topic to capstone artifacts.

### 2. Prerequisite Knowledge

The whole curriculum. This unit is a structured review and rehearsal, not new material. If any 2-minute answer below feels shaky, return to the original unit and rebuild the implementation evidence before rehearsing.

**Version baseline to state confidently (October 2026):** Java 25 is the current LTS (21 and 17 are previous LTS releases; 27 is the latest feature release). Spring Boot 4.x on Spring Framework 7 (Jakarta EE 11, Jackson 3, Java 17+ baseline), with Boot 3.5 as the last 3.x line. Hibernate ORM 7. JUnit Jupiter (JUnit 6 managed by Boot 4). Kafka 4.x (KRaft only).

### 3. Mental Model

Treat each topic as a **three-layer card**:

```
┌────────────────────────────────────────────────────────────┐
│ 30 s  — definition + why it exists + one sharp fact          │  ← phone screen
├────────────────────────────────────────────────────────────┤
│ 2 min — how it works + main trade-off + a common mistake     │  ← technical round
├────────────────────────────────────────────────────────────┤
│ 5 min — internals + production behavior + YOUR code/incident │  ← deep dive / senior bar
│         + what you'd do differently                          │
└────────────────────────────────────────────────────────────┘
```

Start at 30 seconds, then **ask** "Want me to go deeper into X or Y?" Let the interviewer choose the depth. Over-answering a quick question wastes time and signals poor calibration. Under-answering a senior question signals shallow knowledge.

### 4. Comprehensive Theory — The 18 Topic Cards

Each card gives the three levels and the implementation evidence you should have ready. Code is minimal and focused on what you'd sketch in an interview.

#### 4.1 Java Language

**30 s.** Java is a statically typed, object-oriented language compiled to bytecode that runs on the JVM. Modern Java (17–25) adds records, sealed types, pattern matching for `switch`/`instanceof`, text blocks, `var`, virtual threads and structured concurrency (preview in JDK 25), making data-oriented, concise code idiomatic.

**2 min.** Key modern features and why they matter:

- **Records** are transparent data carriers. The compiler generates the canonical constructor, accessors, `equals`/`hashCode`/`toString`. They're shallowly immutable (final fields), so a `List` component must be defensively copied.
- **Sealed interfaces** + **pattern matching `switch`** give closed hierarchies with exhaustiveness checking. The compiler errors if you miss a case. This is algebraic data types in Java.
- **`equals`/`hashCode` contract:** equal objects must have equal hash codes. Break it and `HashMap`/`HashSet` silently misbehave.
- **Immutability ≠ `final`:** `final` prevents reassignment of the reference, not mutation of the object.
- **Exceptions:** checked (must be declared/handled; recoverable conditions) vs unchecked (`RuntimeException`; programming errors). Modern APIs lean unchecked (Jackson 3 made its exceptions unchecked).

**5 min + evidence.** Show a domain model from your capstone:

```java
public sealed interface PolicyDecision permits Allow, Deny, RequireApproval {}
public record Allow() implements PolicyDecision {}
public record Deny(String code, String reason) implements PolicyDecision {}
public record RequireApproval(RiskLevel risk, String reason) implements PolicyDecision {}

String describe(PolicyDecision d) {
    return switch (d) {                       // exhaustive: no default needed
        case Allow a -> "allowed";
        case Deny(String code, var reason) -> "denied: " + code;          // record deconstruction
        case RequireApproval r when r.risk() == RiskLevel.CRITICAL -> "needs 2 approvals";
        case RequireApproval r -> "needs approval";
    };
}
```

Discuss: adding a new permitted type breaks compilation at every `switch`, which is a feature (Unit 33's policy engine). Record compact constructors for normalization. Why `BigDecimal` for money (`new BigDecimal("0.1")`, never `new BigDecimal(0.1)`), and `compareTo` vs `equals` on `BigDecimal` (scale matters for `equals`).

**Traps.** "Records are deeply immutable." "String concatenation in loops is always slow" (javac uses `invokedynamic` `StringConcatFactory`, but loops still create garbage; use `StringBuilder` in hot loops). "`==` compares strings" (it compares references; interned literals make it *seem* to work).

#### 4.2 Collections

**30 s.** The Collections Framework provides `List`, `Set`, `Map`, `Queue`/`Deque` interfaces with implementations of different trade-offs: `ArrayList` (array-backed), `HashMap` (hash table), `TreeMap` (red-black tree, sorted), `LinkedHashMap` (insertion/access order), `ArrayDeque` (stack/queue), `PriorityQueue` (binary heap).

**2 min.** Complexities: `ArrayList` get O(1), add amortized O(1), insert/remove middle O(n). `HashMap` get/put average O(1); since Java 8, bins with ≥ 8 entries (table ≥ 64) treeify, so the worst case is O(log n). `TreeMap` O(log n) with ordered navigation (`ceilingKey`, `headMap`). `PriorityQueue` offer/poll O(log n), peek O(1). `LinkedList` is rarely the right choice (cache-unfriendly; use `ArrayDeque`). Java 21 added **sequenced collections** (`getFirst`, `getLast`, `reversed()`). Unmodifiable vs immutable: `List.of` is unmodifiable and rejects nulls; `Collections.unmodifiableList` is a *view* over a mutable list.

**5 min + evidence.** HashMap internals: array of bins, `hash = h ^ (h >>> 16)` to spread high bits, index = `hash & (n − 1)` (power-of-two table), load factor 0.75 → resize doubles and splits bins. Mutable keys whose `hashCode` changes after insertion become unreachable. `ConcurrentHashMap`: lock-free reads, CAS + per-bin synchronization for writes, no null keys/values, `computeIfAbsent` atomic per key (don't do long work inside it). Evidence: "In Unit 38's cache lab I used `ConcurrentHashMap.computeIfAbsent` for request coalescing and saw contention when the loader did I/O inside the mapping function, so I switched to Caffeine's `AsyncLoadingCache`."

**Traps.** "HashMap is always O(1)." "`ConcurrentHashMap` makes compound operations atomic" (only its own methods, such as `merge`/`compute`, are). Modifying a collection while iterating → `ConcurrentModificationException` (fail-fast, best effort).

#### 4.3 Generics

**30 s.** Generics give compile-time type safety for reusable code. They're implemented by **type erasure**: type arguments are checked at compile time and erased in bytecode, so `List<String>` and `List<Integer>` are the same class at runtime.

**2 min.** Consequences of erasure: no `new T()`, no `T.class`, no `instanceof List<String>`, and no overloads that differ only by type argument. Bridge methods preserve polymorphism. **Variance:** generics are invariant (`List<Integer>` is not a `List<Number>`). Use wildcards: **PECS** (Producer `extends`, Consumer `super`). `Collections.copy(List<? super T> dest, List<? extends T> src)`. Arrays are covariant and checked at runtime (`ArrayStoreException`), while generics are checked at compile time.

**5 min + evidence.**

```java
// From the capstone's ToolRegistry: a type token preserves the argument type despite erasure.
public record ToolDefinition<A>(String name, Class<A> argsType, ToolHandler<A> handler) {
    public String invoke(Object args, AgentContext ctx) {
        return handler.handle(argsType.cast(args), ctx);   // checked cast via the token
    }
}
static <T extends Comparable<? super T>> T max(Collection<? extends T> items) { ... }
```

Explain the `Comparable<? super T>` bound: it lets `max` work for `java.sql.Timestamp`, which extends `java.util.Date`, which implements `Comparable<Date>` (not `Comparable<Timestamp>`). Heap pollution and `@SafeVarargs`. Jackson's `TypeReference<List<Order>>` captures generic types via a superclass type argument, which survives erasure in class metadata.

**Traps.** "Generics exist at runtime." "`List<Object>` accepts a `List<String>`."

#### 4.4 Streams

**30 s.** Streams are lazy, declarative pipelines over data: a source, intermediate operations (`map`, `filter`, `flatMap`, `sorted`), and one terminal operation (`collect`, `reduce`, `forEach`). Nothing runs until the terminal operation, and a stream can be consumed only once.

**2 min.** Laziness and short-circuiting (`findFirst`, `anyMatch`, `limit`). Stateless vs stateful operations (`sorted`, `distinct` buffer data). Collectors: `groupingBy`, `partitioningBy`, `toMap` (throws on duplicate keys unless you pass a merge function), `teeing`. `Stream.toList()` (Java 16) returns an unmodifiable list. **Gatherers** (Java 24, JEP 485) allow custom intermediate operations such as windowing (`Gatherers.windowFixed`). Parallel streams use the common ForkJoinPool. They're rarely a win in request-handling code, and harmful with blocking I/O or shared mutable state.

**5 min + evidence.**

```java
// Unit 36 Scorecard: per-tag pass rate
Map<String, Double> byTag = results.stream()
    .flatMap(r -> r.evalCase().tags().stream().map(tag -> Map.entry(tag, r.passRate())))
    .collect(Collectors.groupingBy(Map.Entry::getKey, TreeMap::new,
             Collectors.averagingDouble(Map.Entry::getValue)));
```

Discuss when *not* to use streams (complex control flow, checked exceptions, debugging), side effects in `map`/`peek` (avoid), boxing costs (`IntStream`), and the fact that streams aren't faster than loops by default.

**Traps.** "Parallel streams make it faster." "`peek` is for logic." "`toMap` handles duplicates."

#### 4.5 JVM

**30 s.** The JVM loads bytecode, verifies it, interprets it, and JIT-compiles hot code (C1 then C2 tiered compilation) to native code. It manages memory with garbage collectors: G1 by default, ZGC for low latency.

**2 min.** Memory areas: heap (objects; young/old generations for generational collectors), thread stacks, metaspace (class metadata), code cache, direct buffers. Class loading (bootstrap, platform, application loaders; parent delegation). GC choice: G1 (balanced, region-based, pause goals), ZGC (concurrent, sub-millisecond pauses; generational mode added in JDK 21, made the default in JDK 23, and the only mode from JDK 24), Parallel (throughput). **[Version-dependent]** JDK 25 made compact object headers a product feature (JEP 519, opt-in), shrinking object headers to 8 bytes. JDK 27 makes G1 the default in all environments. Containers: the JVM is container-aware and sizes the heap from the cgroup memory limit (`-XX:MaxRAMPercentage`). Leave room for non-heap memory.

**5 min + evidence.** Diagnose a memory problem: `jcmd <pid> GC.heap_info`, `jcmd <pid> GC.class_histogram`, heap dump (`jcmd <pid> GC.heap_dump /tmp/h.hprof`) analyzed in Eclipse MAT (dominator tree, leak suspects). JFR for allocation and latency (`jcmd <pid> JFR.start duration=60s filename=rec.jfr`, then JDK Mission Control). Common leaks: unbounded static caches, `ThreadLocal`s in pools, listeners not removed, unbounded queues. Evidence: "I found a leak in my eval runner, where a transcript cache grew without bound. The class histogram showed `Transcript` instances growing, and I replaced the cache with a bounded Caffeine cache."

**Traps.** "Java is slow because it's interpreted" (JIT). "`System.gc()` fixes memory issues." "Set `-Xmx` equal to the container limit" (you'll get OOM-killed by the kernel).

#### 4.6 Concurrency

**30 s.** Java concurrency is threads sharing memory, coordinated through the Java Memory Model's happens-before rules. You use high-level tools (executors, concurrent collections, `CompletableFuture`, virtual threads) rather than raw `wait`/`notify`.

**2 min.** Visibility and atomicity: `volatile` gives visibility and ordering, not atomicity (`count++` on a volatile is still a race). `synchronized`/`ReentrantLock` give mutual exclusion plus visibility. Atomics (`AtomicLong`, `LongAdder` for contended counters). Executors: fixed pools for CPU work, **virtual threads** (Java 21) for blocking I/O. Millions are cheap, and they unmount from carrier threads when blocking (JDK 24's JEP 491 removed pinning on `synchronized`). Virtual threads don't need pooling, but you must bound *resources* (semaphores). Deadlock needs mutual exclusion, hold-and-wait, no preemption and circular wait; prevent it with lock ordering or `tryLock` with a timeout. **Structured concurrency** (`StructuredTaskScope`) was still a preview API in JDK 25; check its status in later releases before relying on it [Experimental]. **Scoped values** finalized in JDK 25 (JEP 506) as a `ThreadLocal` alternative for virtual threads.

**5 min + evidence.**

```java
// Fan-out with virtual threads and a deadline (capstone retrieval + order lookup in parallel)
try (var exec = Executors.newVirtualThreadPerTaskExecutor()) {
    Future<List<Doc>> docs = exec.submit(() -> retriever.search(query, ctx));
    Future<OrderView> order = exec.submit(() -> orders.get(orderId, ctx));
    return new Context(docs.get(2, SECONDS), order.get(2, SECONDS));
} // close() waits for tasks; on timeout, cancel and degrade
```

Discuss context propagation (`SecurityContext`, tracing) when hopping threads (Units 33, 37), thread dumps to find deadlocks (`jcmd <pid> Thread.print`, which reports "Found one Java-level deadlock"), and the Unit 35 concurrency test (8 virtual threads executing the same approval) as evidence of thinking about races at the DB level, not only in memory.

**Traps.** "`volatile` makes it thread-safe." "Virtual threads make code faster" (they increase concurrency for blocking I/O, not CPU speed). "`ConcurrentHashMap` everywhere fixes races."

#### 4.7 Spring Framework

**30 s.** Spring is an inversion-of-control container that creates and wires objects (beans) and adds cross-cutting behavior (transactions, security, caching) through proxies, so business code stays plain Java.

**2 min.** Startup: configuration parsing → component scanning → `BeanDefinition`s → `BeanFactoryPostProcessor`s (modify definitions) → instantiation with **constructor injection** → `BeanPostProcessor`s (which create AOP proxies) → ready. Scopes: singleton (default), prototype, request/session. Proxies: JDK dynamic proxies (interfaces) or CGLIB subclasses (classes; the Boot default). `@Transactional`, `@Cacheable`, `@Async`, `@PreAuthorize` work **only through the proxy**: self-invocation (`this.method()`), private methods and final methods aren't intercepted. Spring Framework 7 [Version-dependent]: JSpecify null-safety annotations, built-in resilience (`@Retryable`, `@ConcurrencyLimit`), API versioning support in MVC, Jakarta EE 11.

**5 min + evidence.** Walk `@Transactional`: `TransactionInterceptor` → `PlatformTransactionManager.getTransaction` (propagation: REQUIRED joins, REQUIRES_NEW suspends) → binds the connection to the thread via `TransactionSynchronizationManager` → your method → commit or rollback (by default rollback on unchecked exceptions and `Error`, not on checked ones unless `rollbackFor`). Evidence: Unit 35's `ApprovalService.decide()` must be called from the controller, not internally. Show the test that would fail with self-invocation.

**Traps.** "Field injection is fine" (it hides dependencies and hurts testability; prefer constructors). "`@Transactional` on a private method works." "Spring Boot replaces Spring."

#### 4.8 Spring Boot

**30 s.** Spring Boot is opinionated auto-configuration plus starters, embedded servers and production features (Actuator, externalized config) on top of Spring, so applications run with minimal setup. It configures Spring; it doesn't replace it.

**2 min.** Auto-configuration: `@SpringBootApplication` → `@EnableAutoConfiguration` imports candidates listed in `META-INF/spring/org.springframework.boot.autoconfigure.AutoConfiguration.imports`, each guarded by conditions (`@ConditionalOnClass`, `@ConditionalOnMissingBean`, `@ConditionalOnProperty`), so your beans win. Externalized config precedence (command line > env vars > profile-specific files > application.yml). `@ConfigurationProperties` with records for typed config. Actuator health, metrics, info. **Boot 4** [Version-dependent]: modularized auto-configuration and smaller starters (`spring-boot-starter-webmvc`), Jackson 3, the `spring-boot-starter-opentelemetry` starter, removal of 3.x deprecations. Boot 4.1 added Spring gRPC support and SSRF mitigation for HTTP clients.

**5 min + evidence.** Debug auto-config: `--debug` or `/actuator/conditions` shows which auto-configurations matched and why. Evidence: "In the capstone I defined a dedicated `JsonMapper` bean `agentJson` and had to make sure Boot's auto-configured mapper still existed for HTTP. `@ConditionalOnMissingBean` keys on type, so I qualified mine and verified through `/actuator/conditions` and a test."

**Traps.** "Boot is a different framework." "Auto-configuration is magic" (it's conditional `@Configuration` classes you can read).

#### 4.9 JPA / Hibernate

**30 s.** JPA is the Jakarta persistence specification and Hibernate its main implementation. It maps entities to tables and manages them in a persistence context (first-level cache, unit of work) that tracks changes and flushes SQL at commit.

**2 min.** Entity states: transient, managed, detached, removed. **Dirty checking** at flush. Fetching: `@ManyToOne` is EAGER by default (make it LAZY), `@OneToMany` is LAZY. **N+1** queries: loading N parents then lazily each child collection. Fix with `JOIN FETCH`, `@EntityGraph`, batch fetching (`hibernate.default_batch_fetch_size`) or DTO projections. `LazyInitializationException`: accessing a lazy association after the persistence context closed. Fix by fetching what you need in the transaction, not by enabling open-session-in-view (Boot warns about `spring.jpa.open-in-view=true`; disable it). Optimistic locking with `@Version`.

**5 min + evidence.** Show the SQL. Enable `spring.jpa.show-sql` only in dev, or better, use a datasource proxy and count queries in tests. Use `EXPLAIN ANALYZE` for the generated SQL. Hibernate 7 [Version-dependent] is on Jakarta Persistence 3.2. Evidence: "My approval queue endpoint had N+1 on `ApprovalDecision`. A query-count assertion in the test caught it (51 queries for 50 proposals), and I fixed it with an entity graph." Bulk operations should bypass entity loading (`@Modifying @Query` updates), but they also bypass the persistence context and `@Version` unless handled, which is why Unit 35's `claimForExecution` increments the version explicitly.

**Traps.** "JPA means I don't need SQL." "`save()` always issues an INSERT" (merge/persist semantics). "Open session in view solves lazy loading."

#### 4.10 SQL (PostgreSQL)

**30 s.** SQL is declarative. The planner chooses how to execute a query (index vs sequential scan, join algorithm) based on statistics, and indexes, constraints and transaction isolation determine performance and correctness.

**2 min.** B-tree indexes for equality/range/order-by, composite index column order (leftmost prefix), partial indexes (`WHERE status='PENDING'`), covering (`INCLUDE`), GIN for jsonb/full-text/arrays, HNSW/IVFFlat (pgvector) for vectors. Read the plan: `EXPLAIN (ANALYZE, BUFFERS)`, then compare estimated vs actual rows. Isolation: PostgreSQL defaults to Read Committed, Repeatable Read (snapshot) prevents non-repeatable reads, and Serializable (SSI) can abort with serialization failures that you must retry. MVCC: readers don't block writers. `SELECT … FOR UPDATE [SKIP LOCKED]`. Window functions (`ROW_NUMBER() OVER (PARTITION BY …)`).

**5 min + evidence.**

```sql
-- Reviewer queue (Unit 35) and its supporting partial index
CREATE INDEX action_proposal_queue ON action_proposal (tenant_id, required_role, created_at)
  WHERE status = 'PENDING';
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, tool_name, risk_level FROM action_proposal
 WHERE tenant_id = $1 AND required_role = ANY($2) AND status = 'PENDING'
 ORDER BY created_at LIMIT 50;
-- Expect: Index Scan using action_proposal_queue … (no Sort node; rows ~ 50)
```

Discuss lost updates (read-modify-write in Read Committed) and fixes (atomic `UPDATE … SET x = x - 1 WHERE x >= 1`, `FOR UPDATE`, optimistic version). Keyset pagination vs `OFFSET`.

**Traps.** "Indexes always speed up queries" (writes slow down; low-selectivity indexes are ignored). "Serializable is too slow, so use Read Committed and hope."

#### 4.11 REST

**30 s.** REST is an architectural style using resources identified by URIs, standard HTTP methods with defined semantics, stateless requests and representations such as JSON. Good APIs use correct status codes, idempotency and consistent errors.

**2 min.** Method semantics: GET safe and idempotent; PUT and DELETE idempotent; POST not, so add `Idempotency-Key` for retries; PATCH (partial; JSON Merge Patch or JSON Patch). Status codes: 200/201 (+ `Location`)/202/204, 400 vs 422 (validation), 401 (unauthenticated) vs 403 (unauthorized), 404, 409 (conflict/version), 429, 503. Errors as **RFC 9457 Problem Details** (`ProblemDetail` in Spring). Pagination (cursor/keyset for large sets), filtering, versioning (URI, header or media type; Spring Framework 7 adds first-class API versioning). Caching with `ETag`/`If-None-Match`. Optimistic concurrency with `If-Match`.

**5 min + evidence.** Show a controller from the capstone with `@Valid` DTO records, `ProblemDetail` advice, 201 with `Location`, and `If-Match` → 412 on version mismatch. Explain DTO/domain separation (no entities in responses: lazy loading, over-exposure, coupling).

**Traps.** "PUT and POST are interchangeable." "Return 200 with `{error: …}`." "403 when not logged in."

#### 4.12 Security

**30 s.** Authentication proves who you are. Authorization decides what you may do. In Spring Security a filter chain authenticates requests (for example validating a JWT as an OAuth2 resource server) and authorization rules run at the URL level and the method level.

**2 min.** `SecurityFilterChain` bean with the lambda DSL (Spring Security 7 removed the older non-lambda style, and `WebSecurityConfigurerAdapter` has been gone since 6). Resource server: validates JWT signature (JWKS), `iss`, `aud`, `exp`; maps `scope` claims to `SCOPE_` authorities. Method security: `@EnableMethodSecurity` + `@PreAuthorize`. **JWT isn't automatically secure**: you must validate audience and issuer, use short lifetimes, handle revocation (short TTL plus refresh tokens, or introspection), avoid storing secrets in claims, and still authorize every resource access (IDOR). CSRF matters for cookie-based sessions, not for stateless bearer-token APIs. CORS is a browser policy, not authorization. OWASP Top 10: broken access control is #1.

**5 min + evidence.**

```java
@Bean
SecurityFilterChain api(HttpSecurity http) throws Exception {
    http
      .authorizeHttpRequests(auth -> auth
          .requestMatchers("/actuator/health/**").permitAll()
          .requestMatchers(HttpMethod.POST, "/api/approvals/**").hasAuthority("SCOPE_approvals:decide")
          .anyRequest().authenticated())
      .oauth2ResourceServer(rs -> rs.jwt(Customizer.withDefaults()))
      .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
      .csrf(AbstractHttpConfigurer::disable);   // stateless bearer API only
    return http.build();
}
```

Evidence: Unit 33's tool policy shows authorization beyond scopes (ownership, tenant, amount), and Unit 35's four-eyes rule. Mention testing with `jwt()` post-processors and an IDOR test.

**Traps.** "JWT makes the API secure." "We check roles in the frontend." "Disable CSRF everywhere."

#### 4.13 Testing

**30 s.** A layered test strategy: fast unit tests for logic, slice tests for Spring layers, integration tests with real dependencies via Testcontainers, and a few end-to-end tests, all automated in CI.

**2 min.** JUnit Jupiter (`@Test`, `@ParameterizedTest`, `@Nested`, `@TestFactory`), AssertJ, Mockito (mock collaborators at boundaries, not value objects). Spring slices: `@WebMvcTest` (MVC layer only, with `MockMvcTester` [Version-dependent: Spring Framework 6.2+]), `@DataJpaTest` (JPA with a DB). Boot 4 moved test autoconfigure packages into the new modules. `@MockitoBean` replaces the removed `@MockBean`. **Testcontainers** with `@ServiceConnection` for real PostgreSQL/Kafka/Redis. Test the behavior, not the implementation. Avoid over-mocking, which makes tests pass while production fails.

**5 min + evidence.** Show the testing pyramid of your capstone with numbers (for example 600 unit, 80 slice, 40 Testcontainers ITs, 5 E2E, 1 eval suite). Explain the "compromised model" tests (Unit 33), the concurrency IT (Unit 35), the eval gate (Unit 36), and test speed tactics (reusable containers, singleton containers per JVM, parallel test execution).

**Traps.** "100% coverage means well tested." "H2 is fine for integration tests" (dialect differences hide bugs).

#### 4.14 Kafka

**30 s.** Kafka is a distributed, partitioned, replicated append-only log. Producers write to topic partitions, and consumer groups read them, tracking offsets. It's used for event streaming, decoupling and replay.

**2 min.** Ordering only within a partition (key determines partition). Replication factor, ISR, `acks=all` + `min.insync.replicas=2` for durability. Idempotent producer (default on in modern clients) prevents duplicates from producer retries. Consumer groups: one consumer per partition maximum. Offsets are committed after processing (at-least-once), so consumers must be idempotent. Transactions give exactly-once for read-process-write *within Kafka*. Kafka 4.x runs on KRaft only (ZooKeeper removed). Spring Kafka: `@KafkaListener`, `DefaultErrorHandler`, `DeadLetterPublishingRecoverer`, `@RetryableTopic`.

**5 min + evidence.** Outbox → Kafka → idempotent consumer with dedupe table (Unit 38 Lab A). Partition key choice (`orderId`), consumer lag monitoring (`kafka-consumer-groups.sh --describe`), rebalances due to slow processing (`max.poll.interval.ms`), poison messages to the DLT, and schema evolution (Avro/Protobuf + schema registry, or JSON with versioning and tolerant readers).

**Traps.** "Kafka is a queue." "Kafka guarantees global ordering." "Exactly-once means no duplicates in my database."

#### 4.15 Microservices

**30 s.** Microservices split a system into independently deployable services that own their data, communicating via APIs and events. They trade simpler individual services for distributed-systems complexity.

**2 min.** Benefits: independent deploys and scaling, team autonomy, fault isolation. Costs: network failures, latency, distributed transactions (sagas + outbox), data duplication, observability needs, versioning. Patterns: API gateway, service discovery, circuit breakers, bulkheads, the database-per-service rule, CQRS for read models. Start with a **modular monolith** (Spring Modulith verifies module boundaries) and extract services where scaling or team boundaries justify it.

**5 min + evidence.** Show your capstone's module boundaries and why some modules stayed in-process: the approval and agent modules share a transaction boundary for the outbox, while evaluation runs as a separate job. Discuss a saga with compensation (Unit 38 order platform) and how you trace across services (Unit 37).

**Traps.** "Microservices are always better." "Shared database between services is fine." "Sync REST chains everywhere" (latency multiplies, availability multiplies down).

#### 4.16 Docker

**30 s.** Docker packages an application and its runtime into an image built from layers, and runs it as an isolated container (namespaces + cgroups) that shares the host kernel.

**2 min.** Multi-stage builds (build with the JDK, run with a JRE or distroless image), layer caching (copy dependency manifests first), Spring Boot layered jars (`java -Djarmode=tools -jar app.jar extract --layers`) or `spring-boot:build-image` (Cloud Native Buildpacks). Run as non-root, pin base image digests, scan images. JVM in containers: heap from the cgroup limit (`-XX:MaxRAMPercentage=75`), CPU count from quota. Health checks map to Actuator probes in Kubernetes. Images are immutable artifacts promoted across environments, and config comes from the environment.

**5 min + evidence.**

```dockerfile
FROM eclipse-temurin:25-jdk AS build
WORKDIR /src
COPY mvnw pom.xml ./
COPY .mvn .mvn
RUN ./mvnw -q dependency:go-offline
COPY src src
RUN ./mvnw -q -DskipTests package && java -Djarmode=tools -jar target/app.jar extract --layers --destination extracted

FROM eclipse-temurin:25-jre
RUN useradd -r -u 10001 app
WORKDIR /app
COPY --from=build /src/extracted/dependencies/ ./
COPY --from=build /src/extracted/spring-boot-loader/ ./
COPY --from=build /src/extracted/snapshot-dependencies/ ./
COPY --from=build /src/extracted/application/ ./
USER 10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=75", "-jar", "app.jar"]
```

(The extract layout depends on the Boot version; verify the folder names it produces.) Also cover image size, startup time (CDS/AOT cache: JDK 24+ AOT class loading and linking, JEP 483 [Version-dependent]), and secrets never baked into images.

**Traps.** "Containers are lightweight VMs." "`latest` tag in production." "`-Xmx` = container limit."

#### 4.17 AWS

**30 s.** On AWS, a typical Spring Boot deployment uses containers on ECS Fargate or EKS behind an ALB, RDS/Aurora PostgreSQL, ElastiCache (Redis/Valkey), MSK (Kafka) or SQS/SNS, S3, Secrets Manager, CloudWatch/X-Ray or OpenTelemetry, all secured with IAM roles and VPC networking.

**2 min.** Compute choices: ECS Fargate (simplest containers), EKS (Kubernetes ecosystem), Lambda (event-driven; Java cold starts mitigated with SnapStart). Data: RDS Multi-AZ (failover ~1–2 min) vs Aurora (shared storage, faster failover, read replicas). Networking: VPC with private subnets for apps/DB, public ALB, security groups as allowlists, VPC endpoints. IAM: task roles (no access keys in containers), least privilege. Secrets: Secrets Manager with rotation. Observability: CloudWatch metrics/logs, the ADOT collector for OpenTelemetry. Infrastructure as code: Terraform/CDK.

**5 min + evidence.** Present your capstone deployment diagram (Unit 43): ALB → ECS service (min 2 tasks across 2 AZs, autoscaling on CPU and request count) → Aurora PostgreSQL with pgvector → ElastiCache → MSK Serverless or SQS; Bedrock or a direct provider via a NAT/egress proxy; Secrets Manager; ADOT → CloudWatch/Grafana. Include cost estimates and the failure behavior of each managed service.

**Traps.** "Multi-AZ = multi-region." "Put access keys in environment variables." "Serverless is always cheaper."

#### 4.18 System Design

**30 s.** System design is turning requirements into an architecture that meets scalability, availability, consistency, security and cost targets, while making trade-offs explicit and planning for failure.

**2 min.** The method from Unit 38: requirements with numbers → estimates → API/data → architecture → deep dive on the hard part → failures, security, observability → trade-offs. Core tools: caching, queues, replication, partitioning, rate limiting, idempotency, backpressure.

**5 min + evidence.** Walk one of your Unit 38 designs (or the agentic platform) end to end and defend a decision with numbers and a rejected alternative.

**Traps.** Jumping to boxes before requirements. No numbers. No failure discussion.

### 5. Internal Mechanics — The "Below the Annotation" Drill

Interviewers probe whether you understand mechanisms. Be ready to narrate these chains without notes:

```
Java:    source → javac → bytecode (.class) → class loading (load, link: verify/prepare/resolve, init)
         → interpreter → profiling → C1 → C2 (tiered JIT) → deoptimization if assumptions break
         → objects on heap (TLAB allocation) → GC (G1: young/mixed collections, remembered sets)

Spring:  SpringApplication.run → environment + property sources → ApplicationContext
         → component scan → BeanDefinitions → BeanFactoryPostProcessors (e.g. @Configuration CGLIB)
         → instantiate (constructor injection) → BeanPostProcessors (AOP proxies: tx, cache, security)
         → SmartInitializingSingleton → ApplicationReadyEvent → embedded server accepting

HTTP:    Tomcat connector → (virtual) thread → filter chain (security, observation) → DispatcherServlet
         → HandlerMapping → HandlerAdapter (arg resolvers: @RequestBody → HttpMessageConverter/Jackson,
           @Valid → Validator) → controller → return value handler → message converter → response

JPA tx:  @Transactional proxy → TransactionManager → EntityManager bound to thread → queries/dirty
         tracking → flush (SQL in dependency order) → commit → connection back to Hikari

Kafka:   producer.send → serializer → partitioner(key) → batch (linger.ms, batch.size) → leader broker
         → replicate to ISR → ack (acks=all) → consumer poll → deserialize → listener → commit offset
```

### 6. Implementation Examples

#### Example 1 — Minimal: Your evidence map

Create `interview/evidence-map.md` in your capstone repo:

| Topic | Claim you'll make | Evidence (file / test / metric) |
|---|---|---|
| Records + sealed | Closed decision types with exhaustive switches | `policy/PolicyDecision.java`, `ToolPolicyTest` |
| Concurrency | Exactly-once execution under concurrency | `ConcurrentExecutionIT` (8 virtual threads) |
| JPA | Fixed N+1 in reviewer queue | `ApprovalQueryIT` query-count assertion |
| SQL | Partial index for queue | `V3__approvals.sql`, EXPLAIN screenshot in `docs/` |
| Security | Delegated authorization beyond scopes | `ToolPolicy`, `UnauthorizedToolRequestTest` |
| Kafka | Idempotent consumer | `PaymentCapturedListener`, redelivery IT |
| Observability | Failure attribution | `docs/observability.md` failed-trace write-up |
| Testing | Model-independent security tests | `CompromisedModelTest` |

#### Example 2 — Realistic: A 5-minute answer with code (`@Transactional` self-invocation)

**Question:** "Why didn't my transaction roll back?"

```java
@Service
public class TransferService {
    public void transferAll(List<Transfer> ts) {
        for (Transfer t : ts) transfer(t);        // self-invocation → no proxy → NO transaction
    }
    @Transactional
    public void transfer(Transfer t) { debit(t); credit(t); }
}
```

*Answer flow:* (1) The 30-second diagnosis: self-invocation bypasses the proxy. (2) The mechanism: Spring wraps the bean in a CGLIB proxy, and `this.transfer` calls the target directly. (3) Fixes: move `transfer` to another bean, or put `@Transactional` on `transferAll` if all-or-nothing is the desired semantics, or use `TransactionTemplate` for programmatic boundaries. (4) Other reasons rollback might not happen: checked exception without `rollbackFor`; exception swallowed; a different `DataSource` or transaction manager; `REQUIRES_NEW` inner transaction committing independently. (5) Evidence: the test that proves it, which counts rows after a forced exception.

#### Example 3 — Production-oriented: Mock-interview harness

A tiny Java CLI that runs a timed drill from your question bank:

```java
package com.example.interview;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.*;

public final class Drill {
    record Card(String topic, String level, String question) {}

    public static void main(String[] args) throws Exception {
        List<Card> cards = Files.readAllLines(Path.of(args.length > 0 ? args[0] : "interview/questions.tsv"))
            .stream().filter(l -> !l.isBlank() && !l.startsWith("#"))
            .map(l -> l.split("\t")).map(p -> new Card(p[0], p[1], p[2])).toList();
        var rnd = new Random();
        var scanner = new Scanner(System.in);
        for (int i = 0; i < 10; i++) {
            Card c = cards.get(rnd.nextInt(cards.size()));
            Duration budget = switch (c.level()) {
                case "30s" -> Duration.ofSeconds(30);
                case "2m" -> Duration.ofMinutes(2);
                default -> Duration.ofMinutes(5);
            };
            System.out.printf("%n[%s | %s | %ds] %s%nPress Enter when done…", c.topic(), c.level(),
                              budget.toSeconds(), c.question());
            Instant start = Instant.now();
            scanner.nextLine();
            long used = Duration.between(start, Instant.now()).toSeconds();
            System.out.printf("Used %ds (%s). Self-score 1–5 for: accuracy, depth fit, evidence: ",
                              used, used > budget.toSeconds() ? "OVER" : "ok");
            System.out.println(scanner.nextLine());
        }
    }
}
```

Record yourself (audio is enough). Review for filler, missing evidence and over-long answers.

### 7. Comparative Analysis — High-Frequency Comparisons

| Pair | One-line difference | Trap |
|---|---|---|
| record vs class | Record = transparent immutable data carrier with generated members; class = full control | Records aren't deeply immutable |
| interface vs abstract class | Interface = capability contract (+ default methods, no state); abstract class = shared state/implementation | "Interfaces can't have code" |
| `==` vs `equals()` | Reference identity vs logical equality | String literals interning hides bugs |
| `HashMap` vs `ConcurrentHashMap` | Not thread-safe vs concurrent with atomic per-key ops | Compound ops still need `compute`/`merge` |
| checked vs unchecked | Must be declared vs not | Swallowing checked exceptions |
| composition vs inheritance | Has-a vs is-a; composition is more flexible | Inheritance for code reuse |
| platform vs virtual thread | OS thread vs JVM-scheduled, cheap, for blocking I/O | Pooling virtual threads; unbounded resources |
| `synchronized` vs `ReentrantLock` | Intrinsic vs explicit (tryLock, fairness, conditions) | Forgetting `unlock` in `finally` |
| `@Component` vs `@Bean` | Class-level scanning vs factory method in config | Both can create duplicates |
| JPA vs JDBC/`JdbcClient` | ORM with persistence context vs explicit SQL | Using JPA for bulk updates |
| `@WebMvcTest` vs `@SpringBootTest` | MVC slice vs full context | Slow suites from full contexts everywhere |
| REST vs messaging | Sync request/response vs async events | Sync chains everywhere |
| Kafka vs SQS | Replayable partitioned log vs managed queue | "Kafka is a queue" |
| ECS vs EKS | Simpler AWS-native vs Kubernetes ecosystem | Choosing EKS without platform team |
| JWT vs opaque token | Self-contained, local validation vs introspection, easy revocation | "JWT is encrypted" (usually just signed) |

### 8. Failure Modes and Debugging (Verbal Drills)

For each, practice the SYMPTOM → CAUSE → INVESTIGATE → FIX → PREVENT narrative in under 2 minutes.

1. **OutOfMemoryError: Java heap space** → class histogram, heap dump, MAT dominator tree → bounded caches, streaming instead of loading all rows → memory alerts, load tests.
2. **OOMKilled in Kubernetes, no Java OOM** → non-heap usage (metaspace, threads, direct buffers) or `-Xmx` too close to the limit → NMT (`-XX:NativeMemoryTracking=summary`, `jcmd VM.native_memory`) → `MaxRAMPercentage` 70–75%.
3. **Deadlock** → `jcmd Thread.print` shows the lock cycle → consistent lock ordering → tests with timeouts.
4. **`LazyInitializationException`** → access after the transaction ended → fetch joins/DTO projections in the service → disable open-in-view, query-count tests.
5. **Slow endpoint** → trace critical path → `EXPLAIN ANALYZE` → index/rewrite, or cache → SLO alerts.
6. **Hikari pool exhausted** → `hikaricp.connections.pending`, long transactions, external calls inside transactions → shorten transactions, bulkheads → alert.
7. **Kafka consumer lag growing** → slow processing or a poison message blocking → per-partition lag, DLT, scale consumers up to the partition count → lag alerts.
8. **401s after deploy** → JWKS/issuer/audience misconfig, clock skew → check decoded token claims and logs → config tests.
9. **Flaky tests** → shared state, time, ordering, real network → isolate fixtures, inject `Clock`, Testcontainers → quarantine policy with tracking (never silently skip).

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**1.1** Write 30-second answers for all 18 topics on index cards (or in `questions.tsv`). Time each aloud and cut anything over 35 seconds.
*Hints:* Definition + why + one sharp fact. No history lessons.

**1.2** For each topic, write one "trap" statement and its correction.

#### Level 2 — Implementation

**2.1** For five topics without evidence in your capstone, build a 50–150-line demo with a test: (a) N+1 detection with a query-count assertion; (b) deadlock reproduction and thread-dump analysis; (c) `@Transactional` self-invocation test; (d) a virtual-thread fan-out with deadline; (e) a Kafka idempotent consumer test.
*Hints:* Each demo should produce a screenshot or log excerpt you can describe.

**2.2** Write the `SecurityFilterChain` for a resource server with two scopes and a method-security rule from memory, then compare it against the docs.

#### Level 3 — Integration

**3.1** Mock interview, 45 minutes: a partner picks 6 topics, asking 30 s → 2 min → 5 min on two of them, plus one debugging drill. Record and score (accuracy, calibration, evidence, clarity).

**3.2** Build the evidence map (Example 1) with at least one artifact per topic.

#### Level 4 — Debugging / Production Scenario

**4.1** Explain verbally what's wrong and how you'd find it:

```java
@Entity class Customer { @OneToMany(mappedBy = "customer", fetch = FetchType.EAGER) List<Order> orders; }
@GetMapping("/customers") List<Customer> all() { return repo.findAll(); }
```

*Hints:* Eager collections, N+1 or Cartesian product, entity serialization (infinite recursion), no pagination, data over-exposure.

**4.2** "The service's memory grows 200 MB per day until it's OOM-killed." Walk through the investigation in under 5 minutes.

### 10. Independent Implementation Project — Interview Knowledge Base

**Goal.** Create an interview knowledge base and drill system tied to your capstone.

**Requirements.**

1. `interview/questions.tsv` with ≥ 150 questions across all 18 topics, tagged with levels 30s/2m/5m.
2. `interview/answers/*.md`: for each topic, your three-level answers in your own words, and a "trap" section.
3. `interview/evidence-map.md` with ≥ 1 artifact per topic (link to code, test or doc in your capstone).
4. Five standalone demos for weak topics (Level 2.1) under `interview/demos/`, each with tests.
5. `Drill` CLI and a log of ≥ 10 recorded sessions with self-scores and improvement notes.

**Technical requirements.** Java 25, JUnit Jupiter, Testcontainers where needed, Markdown.

**Suggested structure.**

```
interview/
├── questions.tsv
├── answers/  java-language.md, collections.md, … system-design.md
├── evidence-map.md
├── demos/    nplus1/, deadlock/, tx-self-invocation/, vt-fanout/, kafka-idempotent/
├── drill/    src/main/java/com/example/interview/Drill.java
└── sessions/ 2026-10-12.md …
```

**Milestones.** Week 1: 30-second cards + questions file. Week 2: 2-minute answers + 3 demos. Week 3: 5-minute answers + evidence map + 2 demos. Week 4: 10 recorded drills + 2 mock interviews.

**Definition of done.** You can answer a random 30 s/2 m/5 m question from any topic within budget, cite evidence for the 5-minute level, and correct each listed trap.

**Optional extensions.** Spaced repetition (export to Anki). Peer mock exchange. Track your scores over time in a small chart.

### 11. Testing Strategy (for interview readiness)

- **Timed recall tests:** random cards, strict time budgets.
- **Explain-back tests:** explain to a non-expert, then to an expert; note where each gets lost.
- **Evidence tests:** for each 5-minute answer, can you open the file and run the test in under a minute?
- **Adversarial follow-ups:** a partner asks "why?" three times or "what would break this?"
- **Regression:** re-drill weak topics weekly and track scores.

For technical claims, the demos' JUnit tests *are* the tests. For example, the self-invocation demo asserts that rows persist after the exception, proving no transaction applied.

### 12. Engineering Scenarios

**Scenario 1 — "Tell me about a hard bug."** *Expected reasoning:* Pick a real bug from the capstone (for example the double execution prevented by the conditional claim, or the lost `SecurityContext` on async tool execution). STAR-T: symptom, how you investigated (trace, thread dump, test), root cause, fix, prevention (test, ArchUnit, alert), and what you'd do differently.

**Scenario 2 — FDE: customer's Java team pushes back.** A customer's senior engineer says "We don't use JPA; we only use JDBC." *Expected reasoning:* Clarify their reasons (performance, control, past N+1 pain). Adapt: `JdbcClient` for the integration, keep the SQL explicit and reviewed, provide migration scripts and EXPLAIN plans. Show you know both tools and choose by context.

**Scenario 3 — Version questions.** "Should we upgrade to Spring Boot 4 now?" *Expected reasoning:* Inventory blockers (Jackson 3 migration, removed deprecations, Jakarta EE 11, third-party library support such as Spring AI 2.0 requiring Boot 4). Upgrade path via 3.5 first, run tests and the eval suite, roll out incrementally.

### 13. Interview Preparation — Question Bank (selection)

#### Quick Questions (30–60 s)

- What's the difference between `final`, `finally` and finalization? (*Strong:* modifier; block always runs; `finalize()` deprecated for removal, use `Cleaner`/try-with-resources.)
- Why must `hashCode` be overridden with `equals`?
- What does `volatile` guarantee?
- What's a virtual thread, and when shouldn't you use one? (*Strong:* CPU-bound work; when you need thread affinity; don't pool them.)
- What's the default isolation level in PostgreSQL?
- What's the difference between 401 and 403?
- What does `@SpringBootApplication` combine?
- What's an ISR in Kafka?
- What does a multi-stage Docker build achieve?
- What's an ALB target group health check used for?

#### Intermediate Questions

**Q: Explain how `@Transactional` works and three reasons it might not.**
*Strong answer:* Proxy + interceptor + transaction manager binding a connection to the thread. Fails on self-invocation, on private/final methods, on checked exceptions without `rollbackFor`, on swallowed exceptions, with the wrong transaction manager, or on a different thread.
*Why asked:* Tests whether you know annotations are proxies. *Trap:* "Spring wraps the method in a transaction automatically."

**Q: How do you fix N+1 queries?**
*Strong answer:* Detect with query counts or logs. Fix with fetch joins/entity graphs for specific use cases, batch fetching, or DTO projections. Beware of Cartesian products with multiple collection fetches and pagination with fetch joins.

**Q: How does HashMap work, and what changed in Java 8?**
*Strong answer:* As in card 4.2, including treeification and the resize split.

**Q: How do virtual threads change how you build Spring services?**
*Strong answer:* Thread-per-request with blocking code scales for I/O, so reactive stacks are no longer needed just for scalability. You must add explicit bounds (bulkheads, pool sizes), watch for pinning in native or legacy code, and propagate context (`ThreadLocal`s still work but are copied per virtual thread; consider scoped values).

#### Advanced Questions

**Q: A Spring Boot service's p99 latency spikes every few minutes. Walk me through it.**
*Strong answer:* Correlate with GC logs/JFR (pauses), Hikari pending, downstream traces, CPU throttling in containers (CFS quota), cache expiry cycles, scheduled jobs, and Kafka rebalances. Use exemplars from the latency histogram to traces. Hypothesis → measurement → fix → verify.

**Q: How would you guarantee a message is processed exactly once?**
*Strong answer:* You can't guarantee exactly-once delivery across external effects. Make the effect idempotent (dedupe table in the same transaction, conditional updates, idempotency keys downstream). Use Kafka transactions for Kafka-to-Kafka flows.

**Q: Design the persistence for a high-write audit log in PostgreSQL.**
*Strong answer:* Append-only table, time partitioning, BRIN index on time, minimal secondary indexes, batch inserts, `REVOKE UPDATE/DELETE`, hash chain if tamper-evidence is needed, archival to S3 by dropping old partitions.

#### Coding Questions

1. Implement an LRU cache (`LinkedHashMap` with `accessOrder=true` and `removeEldestEntry`, then from scratch with a hash map + doubly linked list).
2. Implement a thread-safe bounded blocking queue with `ReentrantLock` and two `Condition`s.
3. Write a `@RestControllerAdvice` returning `ProblemDetail` for validation errors with field paths.
4. Write a JPA repository method with an entity graph and a test asserting the query count.

#### Scenario Questions

**Q: You join a team where the main service has no tests and deploys are scary. What do you do in your first month?**
*Strong answer:* Characterize the current behavior with integration tests on critical flows (Testcontainers). Add CI with fast feedback. Add observability for the critical paths. Introduce small, safe refactors behind tests. Agree a definition of done with the team. Use risk-based priority, and don't rewrite.

### 14. Explain-It-at-Three-Levels — Worked Examples and Method

The whole unit uses this format. Two complete examples follow to calibrate depth.

**Concept: Garbage collection (G1)**

- *30 seconds:* G1 is the JVM's default collector. It splits the heap into regions, collects young regions frequently, and incrementally collects the old regions with the most garbage, aiming for a pause-time goal (200 ms by default).
- *2 minutes:* Generational hypothesis; eden/survivor/old regions; young GCs (stop-the-world, parallel copying); concurrent marking when the heap occupancy threshold is reached; mixed collections; humongous objects for large allocations; `-XX:MaxGCPauseMillis`. When to choose ZGC instead: large heaps with strict latency requirements.
- *Deep (5 min):* Remembered sets and card tables track cross-region references. SATB marking. Evacuation failures. Reading GC logs (`-Xlog:gc*`). Tuning by measurement (allocation rate with JFR, avoiding humongous allocations by changing buffer sizes). Container sizing. Evidence: "My eval runner allocated large transcript strings; JFR showed humongous allocations; I streamed transcripts to disk instead."

**Concept: Kafka consumer groups**

- *30 seconds:* A consumer group splits a topic's partitions among its members so each partition is processed by one consumer, enabling parallelism with per-partition ordering. Each group tracks its own offsets, so different groups independently read the same data.
- *2 minutes:* Assignment strategies (cooperative sticky), rebalances and why they hurt, offset commits after processing (at-least-once), max parallelism = partitions, lag as a scaling signal, and the new consumer protocol in Kafka 4.x.
- *Deep (5 min):* Poll loop internals (`max.poll.records`, `max.poll.interval.ms`, heartbeats), static membership to avoid rebalances on restarts, error handling (DefaultErrorHandler, DLT, retry topics and their ordering consequences), idempotent processing with a dedupe table, and evidence from Lab A.

**Method to build the rest:** for each topic, write the 30-second version first, expand the 2-minute version with "how" and one trade-off, then build the 5-minute version around one artifact you can show.

### 15. Knowledge Check

1. What's the worst-case complexity of `HashMap.get` in Java 8+ and why?
2. Why doesn't `volatile` make `count++` safe?
3. Name three reasons a `@Transactional` method might not roll back.
4. Why should `@ManyToOne` usually be LAZY?
5. When is CSRF protection unnecessary in a Spring API?
6. *Code reading:* What does this print, and why? `Integer a = 127, b = 127, c = 128, d = 128; System.out.println((a == b) + " " + (c == d));`
7. *Code reading:* What's wrong with `List<Number> nums = new ArrayList<Integer>();`?
8. *Code reading:* What's the bug? `map.entrySet().stream().collect(Collectors.toMap(e -> e.getValue(), e -> e.getKey()));`
9. *Debugging:* Pod OOM-killed, no `OutOfMemoryError` in logs, `-Xmx` equals the container limit. Explain.
10. *Debugging:* `LazyInitializationException` in a Jackson serialization of a response. Root cause and fix?
11. *Design:* ECS Fargate or EKS for a 3-service capstone? Defend it.
12. *Design:* JWT or opaque tokens for an internal admin API needing instant revocation?

#### Knowledge Check Answers

1. O(log n), because bins treeify into red-black trees after 8 collisions (with table size ≥ 64). Without treeification it would be O(n).
2. `count++` is read-modify-write. `volatile` gives visibility and ordering, not atomicity. Use `AtomicInteger`/`LongAdder` or a lock.
3. Self-invocation (no proxy), checked exception without `rollbackFor`, exception caught and swallowed, wrong transaction manager, private/final method, work on another thread.
4. EAGER loads the associated entity on every load (extra joins/queries), causing N+1 or over-fetching. Fetch explicitly when needed.
5. Stateless APIs authenticated by bearer tokens in headers (not cookies), because browsers don't attach them automatically.
6. `true false`. `Integer` caches −128..127, so `a` and `b` are the same object. 128 creates distinct objects. `==` compares references.
7. Generics are invariant, so this doesn't compile. Use `List<? extends Number>` (read-only) or `List<Number>`.
8. Duplicate values become duplicate keys → `IllegalStateException`. Provide a merge function, or group.
9. Non-heap memory (metaspace, thread stacks, code cache, direct buffers, GC structures) pushes the process past the cgroup limit, so the kernel kills it before the JVM throws. Set `MaxRAMPercentage` ~75% and measure with NMT.
10. The entity's lazy association is accessed during serialization after the transaction closed. Return DTOs built inside the transaction (with the needed fetches), and don't serialize entities or enable open-in-view.
11. Fargate for simplicity (no cluster management, AWS-native integration) unless you need Kubernetes-specific tooling or portability. Defend with team size and operational load.
12. Opaque tokens with introspection (or very short-lived JWTs plus a denylist), because JWTs can't be revoked before expiry without extra state.

### 16. Common Interview Traps

- "Immutable means `final`." `final` stops reassignment, not mutation.
- "HashMap is always O(1)." Average O(1); worst case O(log n) since Java 8.
- "Spring Boot replaces Spring." Boot configures Spring.
- "JWT automatically makes an API secure." You still validate issuer/audience/expiry and authorize every resource.
- "`@Transactional` always works." Only through the proxy, and only for the right exceptions.
- "Virtual threads make everything faster." They scale blocking I/O concurrency; bound your resources.
- "JPA means you don't need SQL." Read the generated SQL and the plans.
- "Kafka guarantees exactly-once processing." Only within Kafka transactions; side effects need idempotency.
- "Containers are VMs." They share the host kernel; isolation comes from namespaces and cgroups.
- "Microservices are the modern default." A modular monolith first; split with reasons.

### 17. Cheat Sheet

- **Java 25 LTS** features: records, sealed, pattern `switch` + record patterns, virtual threads, scoped values (final in 25), compact object headers (opt-in), structured concurrency (preview). JDK 27: G1 default everywhere.
- **Complexities:** ArrayList get O(1)/insert O(n); HashMap avg O(1), worst O(log n); TreeMap O(log n); PriorityQueue O(log n) offer/poll; ArrayDeque O(1) ends.
- **Concurrency:** `volatile` = visibility; `synchronized`/locks = atomicity + visibility; atomics/LongAdder; virtual threads for I/O + semaphores for resources.
- **Spring:** constructor injection; proxies for tx/cache/security/async; self-invocation pitfall; rollback on unchecked by default.
- **Boot 4:** modular starters, Jackson 3, OTel starter, Java 17 baseline, `/actuator/conditions` for auto-config debugging.
- **JPA:** LAZY by default for to-one; N+1 fixes; no open-in-view; `@Version`.
- **SQL:** composite index leftmost prefix; partial/covering indexes; `EXPLAIN (ANALYZE, BUFFERS)`; Read Committed default; `FOR UPDATE SKIP LOCKED`.
- **REST:** method semantics, 401 vs 403, 409/412/422/429, `ProblemDetail` (RFC 9457), `Idempotency-Key`, keyset pagination.
- **Security:** lambda DSL `SecurityFilterChain`; resource server JWT (iss/aud/exp); `@EnableMethodSecurity`; IDOR checks.
- **Testing:** unit → slices → Testcontainers ITs → few E2E; `@MockitoBean`; `@ServiceConnection`.
- **Kafka:** partition = ordering unit; acks=all + min.insync.replicas; idempotent producer; at-least-once + idempotent consumer; DLT; KRaft.
- **Docker/AWS:** multi-stage, non-root, layered jars, `MaxRAMPercentage`; ECS/EKS, RDS/Aurora, ElastiCache, MSK/SQS, Secrets Manager, IAM task roles.

### 18. Completion Checklist

- [ ] I can give a 30-second answer for every one of the 18 topics within time.
- [ ] I can give 2-minute answers with mechanism + trade-off + mistake for every topic.
- [ ] I can give 5-minute answers with internals and my own implementation evidence for every topic.
- [ ] I have an evidence map with at least one artifact per topic.
- [ ] I can correct every trap in Section 16 with the right mental model.
- [ ] I can run the five verbal debugging drills in under 2 minutes each.
- [ ] I have completed at least two recorded mock interviews and acted on the feedback.

### 19. Further Research

**Essential**

- Java SE 25 documentation and JEP index — <https://openjdk.org/projects/jdk/25/> and <https://openjdk.org/jeps/0>. Exact feature status per release.
- Spring Framework reference (core, AOP, transactions) — <https://docs.spring.io/spring-framework/reference/>. What annotations do underneath.
- Spring Boot reference — <https://docs.spring.io/spring-boot/reference/>. Auto-configuration, Actuator, testing, Docker images.
- Hibernate ORM 7 user guide — <https://docs.hibernate.org/orm/7.0/userguide/html_single/>. Fetching, flushing, locking.
- PostgreSQL documentation: indexes, EXPLAIN, concurrency control — <https://www.postgresql.org/docs/current/>.

**Deeper Study**

- Brian Goetz et al., *Java Concurrency in Practice*. Still the reference for the memory model and safe publication.
- Joshua Bloch, *Effective Java* (3rd ed.). Idioms behind many interview questions.
- Vlad Mihalcea's blog — <https://vladmihalcea.com/>. JPA/Hibernate performance details.
- Aleksey Shipilëv's JVM anatomy quarks — <https://shipilev.net/jvm/anatomy-quarks/>. Short JVM internals pieces.

**Practice**

- Spring Guides — <https://spring.io/guides>. Rebuild small examples from memory.
- JMH samples — <https://github.com/openjdk/jmh/tree/master/jmh-samples>. Learn to back performance claims with benchmarks.

### Unit Completion Standard

Before moving on, you must be able to:

- **Explain** all 18 topics at 30-second, 2-minute and 5-minute depth, with correct version-sensitive facts.
- **Implement** small demos proving key behaviors (N+1, self-invocation, deadlock, virtual-thread fan-out, idempotent consumer) and point to capstone artifacts for each topic.
- **Test** your readiness with timed drills, recorded mock interviews and adversarial follow-ups, and track improvement.
- **Debug** verbally the classic Java/Spring production problems (memory, deadlock, lazy loading, pool exhaustion, lag, auth misconfig) in a structured narrative.
- **Defend** your answers with implementation evidence rather than memorized definitions, and correct the common traps confidently.
