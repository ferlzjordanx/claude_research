---
title: "Parts XVI–XX — Production Agentic Engineering, AI Evaluation, Architecture, Interview Preparation and Final Capstone"
subtitle: "Units 33–43: A Self-Contained Study and Implementation Guide for Java/Spring Boot and Agentic Systems Engineers"
date: "October 2026"
---

# Scope of This Guide

**Part XVI — Production Agentic Engineering**

- Unit 33 — Agent Guardrails (input validation; direct and indirect prompt injection; excessive agency; sensitive-data leakage; tool misuse; output validation; least privilege; human approval; deterministic policy enforcement around every sensitive tool; adversarial testing)
- Unit 34 — Structured Agent Output (typed decisions; JSON Schema; Jackson 3 deserialization; Bean Validation; sealed decision hierarchies; malformed-output handling; controlled retry and failure; `AgentDecision` and `ToolRequest` records)
- Unit 35 — Human-in-the-Loop (risk classification; approval gates; low-risk automatic execution vs high-risk review; approval state machine; argument binding; persistence of proposed action, reviewer decision and audit evidence)

**Part XVII — AI Evaluation**

- Unit 36 — Agent Evaluation (evaluation datasets with expected tools, evidence, behavior and forbidden behavior; task success, tool accuracy, groundedness, retrieval quality, schema compliance, hallucination, safety, latency, tokens and cost; regression suites and baselines)
- Unit 37 — Agent Observability (tracing agent, LLM, retriever, tools and final response as one business workflow; OpenTelemetry and Micrometer in Spring Boot 4; GenAI semantic conventions; cost and token tracking; safe logging; failure attribution from a trace)

**Part XVIII — Architecture and System Design**

- Unit 38 — Java System Design (scalability, availability, reliability, consistency; load balancing, caching, queues, replication, partitioning, sharding, CDN, rate limiting; distributed locks, idempotency, backpressure; seven worked designs: URL shortener, notification system, payment service, order platform, document search, chat service, agentic workflow platform)

**Part XIX — Interview Preparation**

- Unit 39 — Java Interview Track (language, collections, generics, streams, JVM, concurrency; Spring, Boot, JPA, SQL, REST, security, testing, Kafka, microservices, Docker, AWS, system design — each at 30-second, 2-minute and 5-minute depth with implementation evidence)
- Unit 40 — Coding Interview Track (arrays/strings, maps/sets, two pointers, sliding window, stacks/queues, linked lists, binary search, trees, graphs, heaps, intervals, backtracking, dynamic programming — every problem worked as clarify → brute force → pattern → optimize → implement → test → complexity)
- Unit 41 — Spring Coding Interviews (60-minute Customer CRUD; 90-minute JWT, pagination, filtering; 120-minute Kafka, Redis, Testcontainers; narrating design choices while coding)
- Unit 42 — AI/FDE Interviews (agent vs workflow; deterministic boundaries; authorization and tool safety; RAG evaluation; retrieval failure; loop control; idempotency; state; tracing; safe deployment; architecture defense sessions)

**Part XX — Final Capstone**

- Unit 43 — Production Agentic Enterprise Application (Spring Boot, PostgreSQL/JPA, Redis, Kafka, OAuth2/JWT, Docker, Testcontainers, CI/CD, AWS; Spring AI, embeddings, pgvector, cited RAG, structured output, tools, single-agent and multi-step workflows; agent state, MCP, guardrails, human approval, OpenTelemetry, evals, cost measurement, graceful degradation; deliverables: repository, architecture documentation, demo script, evaluation report, technical walkthrough)

**Every unit contains the same 19 sections:** 1 Learning Objectives · 2 Prerequisite Knowledge · 3 Mental Model · 4 Comprehensive Theory · 5 Internal Mechanics · 6 Implementation Examples · 7 Comparative Analysis · 8 Failure Modes and Debugging · 9 Guided Practice · 10 Independent Implementation Project · 11 Testing Strategy · 12 Engineering Scenarios · 13 Interview Preparation · 14 Explain-It-at-Three-Levels · 15 Knowledge Check (+ Answers) · 16 Common Interview Traps · 17 Cheat Sheet · 18 Completion Checklist · 19 Further Research · Unit Completion Standard.

# How to Use This Guide

| Part | Units | Theme |
|---|---|---|
| XVI — Production Agentic Engineering | 33, 34, 35 | Wrapping a probabilistic model in deterministic, enforceable controls: guardrails, typed decisions and human approval |
| XVII — AI Evaluation | 36, 37 | Proving that AI behavior is good (evaluation) and seeing what actually happened (observability) |
| XVIII — Architecture and System Design | 38 | Designing Java services that survive real load, real failures and real attackers |
| XIX — Interview Preparation | 39, 40, 41, 42 | Converting knowledge into crisp, evidence-backed interview performance across Java, algorithms, timed Spring builds and AI/FDE scenarios |
| XX — Final Capstone | 43 | One production-style agentic Spring Boot application that integrates the entire curriculum and becomes your portfolio and interview anchor |

**Suggested pacing.** Units 33–37 are build-and-break units: implement each example, then attack it with the malicious and malformed inputs in the practice sections. Unit 38 is design-heavy: write a one-page design document for every worked design *before* reading the reference reasoning. Units 39–42 are drill units: use a timer and record yourself. Unit 43 is a 6–10 week build; run it like a real project with issues, pull requests, CI and a changelog.

## The Running Example Used Throughout

To keep code coherent across units, every unit uses the same fictional company and agent:

> **Acme Commerce** runs an online store. Its **Support Agent** helps customer-support staff (and, in a restricted mode, customers) answer questions about orders, shipping and policies, and can propose actions: look up an order, send an email to a customer, update a shipping address, issue a refund, or delete personal data on request. Policy documents (refund policy, shipping policy, privacy policy) live in a knowledge base used for retrieval-augmented generation (RAG).

The base package is `com.acme.support`. Tools are named `get_order`, `search_policies`, `send_email`, `update_address`, `issue_refund` and `delete_customer_data`. The same tools reappear in guardrails (Unit 33), typed decisions (Unit 34), approvals (Unit 35), evaluation datasets (Unit 36), traces (Unit 37), the agentic-platform design (Unit 38), interview defenses (Unit 42) and the capstone (Unit 43).

## Version Baseline (verified October 2026)

| Technology | Baseline used in this guide | Notes |
|---|---|---|
| Java | **Java 25 (LTS)**; Java 21 (LTS) still widely deployed | Records, sealed types, pattern matching for `switch`, virtual threads (21); stream gatherers (24); scoped values final, flexible constructor bodies, compact source files (25). Non-LTS 26 and 27 have since shipped. |
| Spring Boot | **4.0 / 4.1** | Built on Spring Framework 7 and Jakarta EE 11. Boot 3.5 / Framework 6.2 open-source support ended June 30, 2026 **[Legacy]**. Modularized auto-configuration and renamed starters (e.g. `spring-boot-starter-webmvc`). `@MockBean` is removed; use `@MockitoBean`. |
| Jackson | **Jackson 3** (`tools.jackson.*`) | Auto-configured by Boot 4. Annotations stay in `com.fasterxml.jackson.annotation`. Defaults changed: `FAIL_ON_UNKNOWN_PROPERTIES` is now **off**, `FAIL_ON_NULL_FOR_PRIMITIVES` and `FAIL_ON_TRAILING_TOKENS` are now **on**. Exceptions are unchecked (`JacksonException`). Jackson 2 **[Legacy]**. |
| Bean Validation | Jakarta Validation 3.1 / Hibernate Validator 9 | `jakarta.validation.*` (never `javax.validation.*` — **[Legacy]**). |
| Persistence | Hibernate ORM 7 / Jakarta Persistence 3.2, Spring Data JPA 4, PostgreSQL 16–18, Flyway | |
| Spring Security | **7.x** | Lambda DSL only; `authorizeHttpRequests`; method security via `@EnableMethodSecurity`. |
| Spring AI | **2.0.x GA** (June 12, 2026); 2.1 in development **[Version-dependent]** | Requires Boot 4. Tool loop unified into the `ChatClient` advisor chain (`ToolCallingAdvisor`; `internalToolExecutionEnabled` removed). Structured output via `.entity(...)` with optional `validateSchema()` self-correction and provider-native structured output. MCP annotations (`@McpTool`, `@McpResource`, `@McpPrompt`) are core. Spring AI 1.x **[Legacy]**. |
| MCP | Spec **2026-07-28** (stateless core) is the latest; **2025-11-25** is what the MCP Java SDK 2.0 bundled with Spring AI 2.0 implements **[Version-dependent]** | Check SDK support before relying on stateless features. |
| Messaging / cache | Apache Kafka 4.x (KRaft only), Spring for Apache Kafka 4, Redis 7+/Valkey 8+ | |
| Testing | JUnit 5 (Jupiter), AssertJ, Mockito, Testcontainers 2.x (artifacts renamed `testcontainers-*`, JUnit 4 support removed), `@ServiceConnection` | |
| Observability | OpenTelemetry; Boot 4 `spring-boot-starter-opentelemetry` (OTLP for traces/metrics/logs via Micrometer); OTel Java agent remains a first-class option | **GenAI semantic conventions are in *Development* status** — attribute names can change **[Experimental]**. |
| Security references | OWASP Top 10 for LLM Applications 2025; OWASP Top 10 for Agentic Applications 2026 (published December 2025) | |

Version-sensitive claims are flagged inline with **[Current]**, **[Legacy]**, **[Deprecated]**, **[Experimental]** or **[Version-dependent]**. When a Spring AI API is shown, check the reference documentation for your exact minor version: Spring AI has moved fast, and several names changed between 1.0, 1.1 and 2.0. Wherever possible the examples isolate framework calls behind small interfaces (`LlmClient`, `ToolGateway`, `Retriever`) so the guardrail, validation, approval, evaluation and tracing logic is framework-independent and testable.

**Notation used in diagrams.** `→` synchronous call, `⇢` asynchronous message, `[ ]` component, `( )` data store, `{ }` external dependency.

## Sources Verified for Version-Sensitive Claims

- Spring AI 2.0.0 GA announcement — <https://spring.io/blog/2026/06/12/spring-ai-2-0-0-GA-available-now/>
- Spring AI 2.0.0-RC1 notes (ToolCallingAdvisor, removal of `internalToolExecutionEnabled`) — <https://spring.io/blog/2026/06/06/spring-ai-2-0-0-RC1-available-now/>
- Self-correcting structured output in Spring AI 2.0 — <https://spring.io/blog/2026/06/23/spring-ai-self-correcting-structured-output/>
- Spring AI reference: structured output, tool calling, evaluation testing — <https://docs.spring.io/spring-ai/reference/>
- Introducing Jackson 3 support in Spring — <https://spring.io/blog/2025/10/07/introducing-jackson-3-support-in-spring/>
- Jackson 3.0.0 GA release notes (changed defaults, JSTEP-2) — <https://cowtowncoder.medium.com/jackson-3-0-0-ga-released-1f669cda529a>
- OpenTelemetry with Spring Boot (Spring blog) — <https://spring.io/blog/2025/11/18/opentelemetry-with-spring-boot/>
- Spring Boot 4 tracing reference — <https://docs.spring.io/spring-boot/4.0/reference/actuator/tracing.html>
- OpenTelemetry GenAI semantic conventions — <https://opentelemetry.io/docs/specs/semconv/gen-ai/>
- MCP 2026-07-28 release — <https://blog.modelcontextprotocol.io/posts/2026-07-28/>; MCP 2025-11-25 authorization — <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization>
- OWASP Top 10 for LLM Applications 2025 — <https://genai.owasp.org/llm-top-10/>
- OWASP Top 10 for Agentic Applications 2026 — <https://genai.owasp.org/>
- Testcontainers 2 dependency renames — <https://docs.openrewrite.org/recipes/java/testing/testcontainers/testcontainers2dependencies>
