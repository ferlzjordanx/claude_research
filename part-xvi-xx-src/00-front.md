---
title: "Parts XVI–XX — Production Agentic Engineering, AI Evaluation, System Design, Interview Preparation and Final Capstone"
subtitle: "Units 33–43: A Self-Contained Study and Implementation Guide for Java / Spring Boot and Agentic Systems Engineers"
date: "October 2026"
---

# Contents

**Part XVI — Production Agentic Engineering**

- Unit 33 — Agent Guardrails (input validation; direct and indirect prompt injection; excessive agency; sensitive-data leakage; tool misuse; output validation; least privilege; human approval; deterministic tool policy)
- Unit 34 — Structured Agent Output (typed decisions; JSON Schema; Jackson 3 deserialization; Bean Validation; `AgentDecision` and `ToolRequest` records; malformed-output handling; bounded retry and controlled failure)
- Unit 35 — Human-in-the-Loop (risk classification; approval gates; approval state machine; persisted proposed actions, reviewer decisions and audit evidence; idempotent execution after approval)

**Part XVII — AI Evaluation**

- Unit 36 — Agent Evaluation (evaluation datasets; expected tools, evidence and behavior; forbidden behavior; task success, tool accuracy, groundedness, retrieval quality, schema compliance, hallucination, safety, latency, tokens and cost; regression suites and baselines; offline vs online evaluation)
- Unit 37 — Agent Observability (one trace per business workflow; agent, LLM, retriever and tool spans; GenAI semantic conventions; tokens, cost, retries and loops; safe logging; failure attribution from a trace)

**Part XVIII — Architecture and System Design**

- Unit 38 — Java System Design (scalability, availability, reliability, consistency; load balancing; caching; queues; replication; partitioning and sharding; CDN; rate limiting; distributed locks; idempotency; backpressure; seven worked designs)

**Part XIX — Interview Preparation**

- Unit 39 — Java Interview Track (language, collections, generics, streams, JVM, concurrency, Spring, Boot, JPA, SQL, REST, security, testing, Kafka, microservices, Docker, AWS, system design — at three explanation depths)
- Unit 40 — Coding Interview Track (arrays/strings, maps/sets, two pointers, sliding window, stacks/queues, linked lists, binary search, trees, graphs, heaps, intervals, backtracking, dynamic programming)
- Unit 41 — Spring Coding Interviews (60/90/120-minute timed builds: CRUD + PostgreSQL + validation + errors + tests → JWT + pagination + filtering → Kafka + Redis + Testcontainers)
- Unit 42 — AI/FDE Interviews (agent vs workflow; deterministic boundaries; authorization and tool safety; RAG evaluation; loop control; idempotency; state; tracing; safe deployment; architecture defense)

**Part XX — Final Capstone**

- Unit 43 — Production Agentic Enterprise Application (full integration: Spring Boot, PostgreSQL/pgvector, Redis, Kafka, OAuth2/JWT, Spring AI, RAG with citations, structured output, tools, MCP, guardrails, human approval, OpenTelemetry, evals, cost and graceful degradation; deliverable templates)

**Every unit contains the same sections:** 1 Learning Objectives · 2 Prerequisite Knowledge · 3 Mental Model · 4 Comprehensive Theory · 5 Internal Mechanics · 6 Implementation Examples · 7 Comparative Analysis · 8 Failure Modes and Debugging · 9 Guided Practice · 10 Independent Implementation Project · 11 Testing Strategy · 12 Engineering Scenarios · 13 Interview Preparation · 14 Explain-It-at-Three-Levels · 15 Knowledge Check (+ Answers) · 16 Common Interview Traps · 17 Cheat Sheet · 18 Completion Checklist · 19 Further Research · Unit Completion Standard.

# How to Use This Guide

| Part | Units | Theme |
|---|---|---|
| XVI — Production Agentic Engineering | 33, 34, 35 | Wrapping a probabilistic model in deterministic controls: guardrails, typed decisions and human approval |
| XVII — AI Evaluation | 36, 37 | Proving that agent behavior is good (evaluation) and knowing what actually happened (observability) |
| XVIII — Architecture and System Design | 38 | Designing Java services that survive real load, real failure and real attackers |
| XIX — Interview Preparation | 39, 40, 41, 42 | Turning everything into crisp, evidence-backed interview answers |
| XX — Final Capstone | 43 | One production-style agentic Spring Boot application that integrates the whole curriculum |

**One running domain.** To keep the material coherent, Units 33–37 and the capstone share one domain: **SupportOps**, an internal customer-support agent for an e-commerce company. Support staff ask it questions ("why was order 8812 refunded twice?"), and it can search the knowledge base, read orders, draft and send emails, update customer records and issue refunds. That tool list deliberately includes read-only, reversible-write and irreversible-financial actions, so every guardrail, schema, approval gate, eval and trace in this guide has a concrete reason to exist.

**Suggested pacing.** Units 33–35: one week each, building the guardrail → structured output → approval layers in that order on the same codebase. Units 36–37: one week each, adding evals and tracing to that codebase. Unit 38: two weeks, one design per day on paper plus three small coding labs. Units 39–42: drill units; use a timer, record yourself, and repeat. Unit 43: 4–8 weeks, run as a real project with issues, pull requests, CI and a changelog.

**Version baseline (verified October 2026).**

- **Java:** JDK 25 is the current LTS (September 2025); JDK 27 reached GA in September 2026 and is a non-LTS feature release. Examples target **Java 25** and use records, sealed interfaces, pattern-matching `switch` and virtual threads. [Current]
- **Spring:** Spring Boot **4.1.x** (4.1.0 shipped 10 June 2026; 4.1.1 in August 2026) on Spring Framework **7.0**, Spring Security **7.x**, Jakarta EE 11, Hibernate ORM 7. Boot 4 keeps a Java 17 baseline. Boot 4 uses **Jackson 3** (package `tools.jackson.*`; annotations stay in `com.fasterxml.jackson.annotation`) and splits starters into smaller modules (for example `spring-boot-starter-webmvc`). Everything deprecated in Boot 3.x was removed in 4.0. [Current] [Version-dependent]
- **Spring AI:** **2.0.x** (GA 12 June 2026; 2.0.1 August 2026), requires Boot 4.0/4.1. The tool-calling loop now lives in the advisor chain (`ToolCallingAdvisor`, auto-registered by `ChatClient`); `StructuredOutputValidationAdvisor` adds schema validation with self-correcting retries; MCP support ships with the MCP Java SDK and `@McpTool`/`@McpResource`/`@McpPrompt` annotations. Migration from 1.1.x is not drop-in. [Current] [Version-dependent]
- **MCP:** The specification revision **2026-07-28** (stateless; no `initialize` handshake or session pinning) is the latest. Spring AI 2.0 GA shipped against the **2025-11-25** revision. Check your SDK's supported revision before you rely on stateless behavior. [Version-dependent]
- **OpenTelemetry GenAI semantic conventions:** still **Development** status (none stable). In June 2026 they moved from the main semantic-conventions repository to `open-telemetry/semantic-conventions-genai`. Treat attribute names such as `gen_ai.operation.name`, `gen_ai.usage.input_tokens` and the `invoke_agent`/`execute_tool` operations as provisional. [Experimental]
- **Spring Boot observability:** Boot 4 adds `spring-boot-starter-opentelemetry` (Micrometer instrumentation exported over OTLP). The OpenTelemetry Java agent and the OpenTelemetry Spring Boot starter remain valid alternatives. [Current]
- **Security references:** OWASP Top 10 for LLM Applications **2025** and OWASP Top 10 for **Agentic Applications 2026** (published December 2025, categories ASI01–ASI10). [Current]
- **Data/infra:** PostgreSQL 17–18, pgvector 0.8.x, Redis 7/8 (or Valkey 8), Apache Kafka 4.x (KRaft only, no ZooKeeper), Testcontainers 2.x, JUnit Jupiter (JUnit 6 is the version managed by Boot 4; the Jupiter programming model is unchanged from JUnit 5).

Version-sensitive claims are flagged inline as **[Current]**, **[Legacy]**, **[Deprecated]**, **[Experimental]** or **[Version-dependent]**. Where a framework API changes frequently (Spring AI, MCP, OpenTelemetry GenAI), the examples keep the safety-critical logic in plain Java that you own (validation, policy, approval, idempotency) and use the framework only for model transport. The examples stay correct when the framework changes, and each guardrail is explicit code that you can test without calling a model.

**Notation used in diagrams.** `→` synchronous call, `⇢` asynchronous message, `[ ]` component, `( )` data store, `{ }` external dependency.

## Sources Verified for Version-Sensitive Claims

- Spring AI 2.0.0 GA announcement — <https://spring.io/blog/2026/06/12/spring-ai-2-0-0-GA-available-now/>
- Self-correcting structured output in Spring AI 2.0 — <https://spring.io/blog/2026/06/23/spring-ai-self-correcting-structured-output/>
- Spring AI 2.0.1 release notes (tool-call limit in `ToolCallingAdvisor`) — <https://spring.io/blog/2026/08/21/spring-ai-2-0-1-available-now/>
- Spring Boot 4.1.0 announcement — <https://spring.io/blog/2026/06/10/spring-boot-4/> and 4.1.1 — <https://spring.io/blog/2026/08/20/spring-boot-4-1-1-available-now/>
- OpenTelemetry with Spring Boot (Spring blog) — <https://spring.io/blog/2025/11/18/opentelemetry-with-spring-boot/>
- JDK 27 GA coverage — <https://www.infoq.com/news/2026/09/java-news-roundup-sep14-2026/>
- OpenTelemetry GenAI semantic conventions — <https://opentelemetry.io/docs/specs/semconv/gen-ai/> and <https://github.com/open-telemetry/semantic-conventions-genai>
- OWASP Top 10 for LLM Applications 2025 — <https://genai.owasp.org/llm-top-10/>
- OWASP Top 10 for Agentic Applications 2026 — <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
- MCP specification and changelog — <https://modelcontextprotocol.io/specification/latest>
