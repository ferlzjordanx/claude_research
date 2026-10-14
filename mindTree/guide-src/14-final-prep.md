# Final Interview Preparation

This part condenses the whole guide into what you rehearse in the last week. Each answer is a *strong-answer skeleton*: say it in your own words, then add one concrete example from a unit project or from your own work (`<<personalize>>`). Unit references in brackets point to the full treatment.

How to practice:

1. Read the question, answer aloud for 60–90 seconds without looking.
2. Compare with the skeleton. Note what you missed.
3. Re-answer, adding one concrete example and one trade-off.

## Top 30 Theory Questions

**1. What happens between a user clicking a button and a row changing in the database?** [U5]
Event handler → state → API client adds auth and request-ID headers → DNS/TLS/proxy/load balancer → middleware (CORS, request ID) → routing and validation → dependencies (DB session, token verification) → business rules (role, object ownership) → transaction → serialization → response → UI state. Name one failure at each step.

**2. How does `asyncio` work, and when does it not help?** [U1]
One thread runs an event loop that switches between coroutines at `await` points. It is great for many concurrent I/O waits. It does not speed up CPU-bound work and breaks down if any coroutine blocks (sync I/O, `time.sleep`). Use processes or a worker pool for CPU work and `asyncio.to_thread` for unavoidable blocking calls.

**3. Explain retries done right.** [U1, U8]
Retry only transient failures (timeouts, 5xx, 429), with exponential backoff plus jitter, a cap on attempts and total time, and idempotency so a retry cannot duplicate side effects. Honor `Retry-After`. Use a retry budget or circuit breaker so retries do not amplify an outage.

**4. What does FastAPI's dependency injection give you?** [U2]
Declarative, per-request wiring of sessions, the current user, settings and services. It makes auth and resources reusable, testable (override dependencies in tests) and visible in the OpenAPI schema.

**5. 401 vs 403 vs 404 for authorization?** [U2, U5]
401: not authenticated (missing or invalid token). 403: authenticated but not allowed to perform this action. 404: the user is not allowed to know the object exists (another tenant's record), to avoid leaking information.

**6. How do you validate input and return errors?** [U2]
Pydantic models at the boundary (types, lengths, `extra="forbid"`), a 422 with field locations, domain errors mapped to 404/409, and a consistent RFC 9457 problem+json body with a request ID. Never leak stack traces.

**7. How do JWTs work, and what are the pitfalls?** [U2]
A signed token with claims (`sub`, `exp`, `aud`, `iss`). The server verifies the signature and claims on every request. Pitfalls: not pinning algorithms, skipping `aud`/`iss` checks, long lifetimes with no revocation, storing tokens where XSS can read them, putting secrets in the payload (it is only encoded, not encrypted).

**8. Explain database transactions and isolation.** [U3]
A transaction is all-or-nothing. Isolation levels trade anomalies for concurrency: read committed (Postgres default) allows non-repeatable reads; repeatable read and serializable prevent more but can abort transactions that must be retried. For counters and stock, use atomic conditional updates (`UPDATE … WHERE stock >= :n RETURNING`) or row locks.

**9. What is the N+1 problem and how do you find and fix it?** [U3, U11]
Loading a list, then one query per item. Find it by counting queries in tests or in traces. Fix it with eager loading (`selectinload`), joins or batching.

**10. How do you choose an index?** [U3]
From the query patterns: equality columns first, then range or sort columns, in a composite index that matches `WHERE` and `ORDER BY`. Verify with `EXPLAIN ANALYZE`. Remember that indexes cost writes and storage.

**11. SQL vs NoSQL?** [U3]
SQL for relational data, constraints, transactions and flexible queries. Document stores for aggregates read and written as a unit with flexible schemas; key-value stores for caching and simple lookups. Most systems start with Postgres and add a cache or search engine for specific needs.

**12. Cache-aside: how does it work and what goes wrong?** [U3]
Read the cache; on a miss, read the DB and populate with a TTL; invalidate on writes after commit. Problems: stale data, stampedes on hot keys, caching per-user data under a shared key, treating cache failure as an outage instead of a miss.

**13. How does a SPA manage server data and loading states?** [U4]
Explicit states (loading, ready, error) modeled as a discriminated union, requests cancelled on unmount or input change (AbortController), one API client for headers and errors, server state kept in a data layer (TanStack Query or services), not duplicated across global stores.

**14. Where should a SPA store tokens?** [U4, U5]
In memory for most SPAs, refreshed via the IdP. Avoid `localStorage` for sensitive apps (XSS). Strongest: a backend-for-frontend that keeps tokens server-side and gives the browser an httpOnly, Secure, SameSite cookie, plus CSRF protection.

**15. What is CORS?** [U5]
A browser rule that blocks JavaScript from reading cross-origin responses unless the server opts in. Configure exact origins, allowed headers and exposed headers; never `*` with credentials. Prefer same origin via a proxy or CDN routing. It is not authentication.

**16. Containers vs VMs, and what makes a good image?** [U6]
Containers share the host kernel and isolate processes; VMs virtualize hardware. A good image is multi-stage, small (slim base), non-root, has pinned dependencies and no secrets, uses exec-form `CMD` for signal handling, and is referenced by digest in production.

**17. Liveness vs readiness vs startup probes?** [U6]
Liveness: restart me if I am stuck (no dependency checks). Readiness: send me traffic only when I can serve (dependencies OK, not draining). Startup: give slow starters time before liveness kicks in. A liveness probe that checks the database causes restart storms.

**18. How does a Kubernetes rolling update stay zero-downtime?** [U6]
New pods must pass readiness before old ones are removed (`maxUnavailable`, `maxSurge`). Old pods get SIGTERM, are removed from endpoints, and drain in-flight requests within the grace period (a `preStop` delay helps). PodDisruptionBudgets protect against voluntary evictions.

**19. ECS vs EKS vs Lambda?** [U6]
Lambda for event-driven, short, spiky workloads with no servers to manage. ECS/Fargate for containerized services with the least operational overhead on AWS. EKS when you need Kubernetes portability, its ecosystem, or the customer already runs it.

**20. Describe a good CI/CD pipeline.** [U7]
On every PR: lint, typecheck, unit and integration tests, build, scan, in minutes. On merge: build one immutable artifact (image digest), deploy to staging, smoke test, promote the same artifact to production with approval or progressive delivery, and roll back automatically on failed checks. Secrets via OIDC, not stored keys.

**21. Trunk-based development vs GitFlow?** [U7]
Trunk-based: short-lived branches merged daily behind feature flags; fits CI/CD and fast feedback. GitFlow: long-lived develop and release branches; fits scheduled releases but causes merge pain. Most modern teams use trunk-based development.

**22. Blue-green vs canary vs rolling?** [U7]
Rolling replaces instances gradually. Blue-green switches traffic between two full environments (instant rollback, double cost). Canary sends a small percentage to the new version and promotes based on metrics. Choose by risk and tooling.

**23. When do microservices make sense?** [U8]
When independent teams need to deploy and scale separately and domain boundaries are clear. Costs: network failures, distributed data, operational overhead. A modular monolith is often the right first step.

**24. How do you prevent double charges in a distributed system?** [U8]
Idempotency keys sent by the client and stored by the payment service, the same key reused on retries, at-least-once messaging with idempotent consumers, and an outbox so DB writes and events cannot diverge.

**25. What is a circuit breaker?** [U8]
A wrapper that stops calling a failing dependency after a threshold (open), fails fast for a cooldown, then lets a probe through (half-open) and closes on success. It protects both the caller's resources and the struggling dependency.

**26. Explain the transactional outbox.** [U8]
Write the business change and an outbox event row in the same DB transaction; a relay publishes outbox rows to the broker and marks them sent. Delivery is at least once, so consumers must be idempotent.

**27. Logs vs metrics vs traces?** [U11]
Logs: detailed events, best for "what exactly happened". Metrics: cheap aggregates over time, best for alerting and trends. Traces: one request's path across services with timings, best for "where is the time going". Correlate all three with trace and request IDs.

**28. What are SLIs, SLOs and error budgets?** [U11]
An SLI is a measured indicator (percentage of requests under 300 ms). An SLO is the target (99.5% over 30 days). The error budget is the allowed shortfall; when it burns fast, alert and slow down releases.

**29. How do LLM applications differ from deterministic software?** [U9]
Outputs are probabilistic, can be invalid or wrong, and cost money and latency per token. So you validate every output against a schema, keep business rules in code, bound retries, add fallbacks and human review, evaluate with golden sets, and monitor quality, cost and latency.

**30. What is RAG and why use it?** [U10]
Retrieval-augmented generation: retrieve relevant, permitted documents and give them to the model with instructions to answer only from them, with citations. It grounds answers in current, private data without fine-tuning, and enables access control and abstention.

## Top 30 Application / Experience Questions

Use the structure **Situation → Task → Action (technical detail) → Result (metric) → Reflection**. Fill the `<<personalize>>` slots with real experience. If you have none, use the *lab-honest* version from the unit project and say so plainly (see "How to Answer When Your Experience Is Limited" at the start of the guide).

| # | Question | What to cover | Unit project to draw on |
|---|---|---|---|
| 1 | Walk me through a system you built end to end. | Users, architecture diagram, your part, one hard problem, result | U5, Capstone |
| 2 | Tell me about a production incident you handled. | Detection, mitigation first, root cause, comms, prevention | U11 |
| 3 | Describe a time you worked directly with a customer. | Their goal, how you discovered real needs, delivery, feedback | U12 |
| 4 | Tell me about a time requirements were unclear. | Assumptions log, thin slice, demo early, converge | U12 |
| 5 | How did you design an API others depend on? | Contract first, versioning, errors, auth, docs | U2, U5 |
| 6 | Describe a performance problem you fixed. | Measure first, profile/trace, root cause, before/after numbers | U3, U11 |
| 7 | Tell me about a data model you designed. | Entities, constraints, indexes, migrations, trade-offs | U3 |
| 8 | How have you secured an application? | AuthN/Z, object-level checks, secrets, input validation, tests | U2, U5 |
| 9 | Describe your testing strategy on a recent project. | Pyramid, what you mocked and why, CI gate, flaky tests | U1–U5 |
| 10 | Tell me about a frontend you built or fixed. | Framework, state, API layer, a UI bug, tests | U4 |
| 11 | How did you containerize and deploy a service? | Dockerfile choices, config, probes, rollout, rollback | U6 |
| 12 | Describe a CI/CD pipeline you built or improved. | Stages, speed, security (OIDC), promotion, rollback | U7 |
| 13 | Tell me about integrating with a flaky third-party API. | Timeouts, retries, idempotency, breaker, monitoring | U1, U8 |
| 14 | Describe a distributed-systems bug you dealt with. | Duplicates, ordering, partial failure, the fix | U8 |
| 15 | Have you built anything with LLMs? | Use case, structured output, validation, eval, cost | U9 |
| 16 | How did you evaluate an AI feature? | Golden set, metrics, regression gate, human review | U9, U10 |
| 17 | Tell me about a RAG or agent system. | Retrieval, permissions, citations, bounded loop, approvals | U10 |
| 18 | Describe a time you had to learn a technology fast. | How you learned, what you shipped, what you'd do differently | Any |
| 19 | Tell me about a trade-off you made under a deadline. | Options, criteria, decision, consequences, follow-up | U12 |
| 20 | Tell me about a disagreement with a stakeholder or teammate. | Understand their goal, data, options, outcome, relationship | U12 |
| 21 | Describe a time you said no to a customer request. | Why, alternative offered, how it landed | U12 |
| 22 | How did you hand over a system to another team? | Docs, runbooks, ADRs, training, support period | U12 |
| 23 | Describe your debugging process on a hard bug. | Reproduce, isolate, hypothesis, evidence, fix, regression test | U11 |
| 24 | Tell me about improving observability. | What was blind, logs/metrics/traces added, alert outcome | U11 |
| 25 | Describe a migration (DB, cloud, framework). | Plan, expand-and-contract, rollback, verification | U3, U7 |
| 26 | Tell me about a mistake you made in production. | Own it, impact, fix, what changed afterwards | U11 |
| 27 | How do you prioritize when everything is urgent? | Impact vs effort, stakeholder alignment, communicate trade-offs | U12 |
| 28 | Describe working in a customer's restricted environment. | Access constraints, adapting tooling, security review | U12 |
| 29 | Tell me about mentoring or explaining tech to non-engineers. | Audience, analogy, outcome | U12 |
| 30 | Why FDE, and why this company? | Customer impact + engineering depth, specific product interest | `<<personalize>>` |

Skeleton for any of them:

```text
Situation  <<customer/team, scale, constraint>>            (1-2 lines)
Task       what I owned, the success measure                (1 line)
Action     3 concrete technical steps, 1 trade-off          (60% time)
Result     <<metric>>: latency, errors, time saved, adoption
Reflection what I'd do differently / what I reuse now
```

## Top 20 Troubleshooting Questions

Answer each with the loop **SYMPTOM → CHECK → CAUSES → CONFIRM → FIX → PREVENTION**. Lead with *mitigation* when users are affected.

| # | Symptom | First checks | Likely causes | Fix / prevention |
|---|---|---|---|---|
| 1 | API p99 latency jumped | Dashboards by route, traces of slow requests, recent deploys | N+1, missing index, blocking call in async, pool exhaustion, slow dependency | Fix the hot path; add query-count tests; timeouts; SLO alert [U11] |
| 2 | 5xx spike after deploy | Error logs by request ID, diff, config changes | Missing env var, migration not applied, contract change | Roll back first; smoke tests; config validation at startup [U7] |
| 3 | Pods restart in a loop | `kubectl describe pod`, `logs --previous`, events | Liveness probe too strict, OOMKilled, crash on missing secret | Fix probe/limits/config; startup probe [U6] |
| 4 | Service works locally, fails in the cluster | Env vars, DNS name of dependency, network policy, IAM | Wrong host, security group, missing IRSA role | Config per env; readiness checks dependency [U6] |
| 5 | CORS error in browser | Preflight response headers | Origin not allowed, header not allowed, error before middleware | Correct allow-list; same-origin proxy [U5] |
| 6 | Users see others' data | Query scoping, cache keys | Missing object-level authz, shared cache key | Central scoped queries, per-user cache keys, authz test matrix [U5] |
| 7 | Intermittent 401s | Token `exp`/`aud`/`iss`, clock skew, replicas' secrets | Expired tokens, mismatched config across pods | Refresh flow; shared JWKS/secret; leeway [U2] |
| 8 | Duplicate orders/charges | Idempotency keys, retry logs, consumer logs | Retries without idempotency, redelivered messages | Idempotency keys, dedupe consumer, outbox [U8] |
| 9 | Messages pile up in the queue | Consumer errors, throughput, poison messages | Slow consumer, crash loop on one message | Scale consumers, DLQ, fix handler [U8] |
| 10 | DB connections exhausted | Pool metrics, long transactions, leaked sessions | Sessions not closed, pool too small, slow queries | Session scoping, timeouts, PgBouncer [U3] |
| 11 | Deadlocks / lock timeouts | DB logs, lock waits | Inconsistent lock order, long transactions | Sorted lock order, short transactions, retries [U3] |
| 12 | Memory grows until OOM | Memory metrics over time, heap profile | Unbounded caches, global lists, large responses | Bounded caches, streaming, limits [U11] |
| 13 | CI is flaky | Which tests, timing, shared state | Order dependence, real time/network, shared DB | Isolate state, fake clocks, quarantine with owner and deadline—never just skip [U7] |
| 14 | UI shows stale or wrong data after quick clicks | Network waterfall | Race conditions, no cancellation | AbortController, keyed queries [U4] |
| 15 | LLM returns invalid JSON | Logs of raw outputs, schema, prompt version | No structured output mode, schema drift, truncation (`max_tokens`) | Structured outputs, validation + one repair, fallback [U9] |
| 16 | LLM costs suddenly tripled | Tokens per request, retries, prompt size | Retry loop, context growth, wrong model | Budgets, caching, token alerts, model routing [U9] |
| 17 | RAG answers are wrong or hallucinated | Retrieved chunks for the question, scores | Bad chunking, missing doc, no abstention, filter too strict | Fix ingestion, hybrid search, abstain threshold, eval set [U10] |
| 18 | Agent loops or takes a risky action | Agent trace, tool calls | No max turns, repeated calls, missing approval gate | Bounded loop, repeated-call detection, human approval [U10] |
| 19 | Slow every afternoon | Traffic pattern, batch jobs, autoscaling events | Scheduled job competing for DB, HPA max reached | Reschedule job, read replica, scale limits [U11] |
| 20 | Customer reports "it's broken" with no detail | Ask for time, user, screenshot with request ID | Anything | Request IDs in UI errors; structured intake questions [U5, U12] |

## Top 15 FDE Scenario Questions

For each, show: **clarify → protect the customer → act → communicate → prevent**. The numbered FDE scenarios in the units give worked examples.

1. **"The demo is tomorrow and the integration still fails."** Narrow to a demo-able slice, use a recorded or stubbed fallback for the flaky dependency, be transparent about what is live, and fix properly after. [Scenario 1]
2. **"Our data doesn't match what your system shows."** Reconcile one record end to end, find where the transformation differs, fix it with a test, and backfill. [Scenario 2]
3. **"Users can see other people's data."** Treat it as a security incident: contain, fix centrally, assess impact from logs, communicate facts. [Scenario 4]
4. **"Pods keep restarting in our cluster."** Use events, previous logs and probe config; work within their platform rules. [Scenario 5]
5. **"We need a hotfix but our change process takes a week."** Work with their change board: emergency-change path, minimal diff, evidence of tests, rollback plan. [Scenario 6]
6. **"Customers were charged twice."** Stop the bleeding, identify duplicates, refund, then add idempotency. [Scenario 7]
7. **"The AI feature costs too much and sometimes fails."** Measure tokens and failures, apply structured outputs, budgets, caching and model routing, and show an eval before/after. [Scenario 8]
8. **"The bot gave a wrong policy answer."** Trace retrieval, fix the content or ingestion, add citations and abstention, add the case to the eval set. [Scenario 9]
9. **"It's slow and our VP is upset."** Acknowledge, give a mitigation timeline, find the root cause with data, and report in plain language. [Scenario 10]
10. **"Stakeholders want conflicting things and the date is fixed."** Make the conflict visible, frame options with trade-offs, get a decision owner, document it. [Scenario 11]
11. **"Data can't leave our network."** Offer deployment options (their VPC, private endpoints, on-prem model), align with their security team early. [Scenario 12]
12. **"The pilot worked; go to production for 5,000 users next month."** Gap analysis: SSO, scale testing, monitoring, support model, runbooks, rollout plan. [Scenario 13]
13. **"Can you just add one more feature before launch?"** Assess impact on date and risk, offer to phase it, get explicit agreement on the trade-off. [U12]
14. **"Your engineer made a mistake in our environment."** Own it, fix it, explain what happened and what changes, without blaming. [U12]
15. **"We don't trust the AI's answers."** Show the eval results, add human review where stakes are high, expose citations and confidence, and agree on acceptance metrics. [U9, U10, U12]

## Top 15 AI / Agentic Questions

**1. How do you get reliable structured output from an LLM?**
Use the provider's structured-output feature with a JSON schema or Pydantic model, validate again in code, allow one repair attempt with the validation error, then fall back deterministically (for example, route to a human).

**2. What belongs in code versus in the prompt?**
Business rules, authorization, limits and anything that must always hold belong in code. The prompt guides interpretation, format and tone. Never rely on the prompt for security.

**3. How do you defend against prompt injection?**
Treat all user input, retrieved documents and tool outputs as untrusted data; delimit them; give tools least privilege; enforce authorization and approvals in code; filter what the model can see by permission; and monitor. No prompt-only defense is complete.

**4. How do you evaluate an LLM feature?**
A golden set of realistic inputs with expected outputs, automatic checks (schema, exact match, field accuracy), targeted LLM-as-judge with human calibration for open-ended outputs, a threshold in CI, and production sampling with human review.

**5. How does tool calling work?**
You give the model tool names, descriptions and JSON schemas. The model returns a request to call a tool with arguments; your code validates them, checks authorization, executes, and returns the result; the model continues. The model proposes, code disposes.

**6. What is an agent, and how do you keep it safe?**
An LLM calling tools in a loop until it decides it is done. Keep it safe with max turns, timeouts, token and cost budgets, repeated-call detection, least-privilege tools, idempotent side effects, and human approval for risky actions. Prefer fixed workflows when the steps are known.

**7. Chunking strategy for RAG?**
Split by document structure (headings, sections) with a size limit and small overlap, keep metadata (source, section, permissions, date), and evaluate retrieval recall with real questions; tune from data.

**8. Why hybrid search?**
Keyword search (BM25) catches exact terms (error codes, product names); vector search catches paraphrases. Fusing them (for example with Reciprocal Rank Fusion) is robust, and a reranker can improve the top results further.

**9. How do you handle permissions in RAG?**
Filter documents by the user's permissions *before* they reach the model (metadata filters in the index), never by asking the model to withhold information.

**10. How do you reduce LLM latency and cost?**
A smaller model for easy tasks, prompt caching for stable prefixes, shorter prompts and outputs, streaming for perceived latency, batching for offline work, caching answers when appropriate, and budgets and alerts.

**11. When would you fine-tune instead of using RAG or prompting?**
Rarely first. Fine-tune for consistent style or format, or for narrow classification at scale, when prompting and retrieval are not enough and you have quality labeled data. RAG is for knowledge; fine-tuning is for behavior.

**12. How do you compare the Anthropic and OpenAI SDKs?**
Both offer typed Python clients, async variants, structured outputs, tool calling, streaming and typed errors. Differences are in request shape (Anthropic: a top-level `system` parameter and Messages API content blocks; OpenAI: the Responses API with `instructions` and input and output items) and in tool-call wire formats. Wrap both behind one internal interface so you can switch or fall back. [U9]

**13. What do you log for LLM calls?**
Model, prompt version, token counts, latency, cost estimate, stop reason, validation outcome, fallback used, and a request ID. Log prompts and outputs only under data-handling rules, never secrets, and redact PII.

**14. How do you explain probabilistic behavior to a customer?**
Be clear that the system will sometimes be wrong. Show measured accuracy on their data, explain safeguards (validation, human review, citations), and agree on acceptance criteria and escalation paths up front.

**15. What is MCP and why does it matter?**
The Model Context Protocol is an open standard for connecting models and agents to tools and data sources through servers with a common interface. It reduces one-off integrations, but each server still needs authentication, least privilege and review like any integration.

## 15-Minute Rapid Review

Read this the morning of the interview.

```text
PYTHON      typed, async for I/O, timeouts + retries w/ jitter,
            TaskGroup, Protocols for seams, pytest + fakes
API         FastAPI factory, Depends, Pydantic boundary, 401/403/404,
            problem+json, JWT verify aud/iss/exp, object-level authz
DATA        transactions, atomic UPDATE..RETURNING, indexes from
            queries, EXPLAIN, N+1 -> selectinload, cache-aside, Alembic
SPA         UI = f(state), loading/ready/error, AbortController,
            one API client, token in memory, server enforces rules
FULL STACK  contract (OpenAPI) + types + contract test, CORS or same
            origin, request IDs end to end, Playwright for journeys
CLOUD       multi-stage non-root image, probes (live != ready),
            requests/limits, rolling update, HPA, ECR/EKS/ALB/RDS,
            secrets manager, IAM least privilege (IRSA/Pod Identity)
CI/CD       PR: lint/type/test fast; main: build once, deploy same
            digest, smoke, approve, canary/rollback; OIDC not keys
DISTRIBUTED timeouts, retries + idempotency keys, circuit breaker,
            outbox, at-least-once + idempotent consumers, sagas
LLM         schema-validated output, repair once, fallback, rules in
            code, budgets, eval set in CI, log tokens/cost/version
RAG/AGENTS  permission filter before generation, hybrid + RRF,
            citations, abstain; tools validated + authorized; loop
            bounded; human approval for risky actions
OBSERVE     logs/metrics/traces + request/trace IDs, RED/USE, SLOs,
            route-template labels, mitigate first, blameless review
FDE         discover goals, assumptions log, thin slice, demo early,
            BLUF updates, acceptance criteria, handover docs
```

Three sentences to have ready:

- *"The server is the only security boundary; the UI only adapts."*
- *"The model proposes, code disposes: everything it returns is validated, and anything risky needs approval."*
- *"I mitigate first, then find the root cause with data, then prevent it with a test or an alert."*

## Final Skills Map

Rate yourself 0–3 on each row (0 = never done, 1 = can explain, 2 = built in the labs, 3 = done in production). Aim for at least 2 across the board and 3 in your strongest areas.

| Area | Must be able to do | Project evidence | Self-rating |
|---|---|---|---|
| Production Python | Typed async code with timeouts, retries, tests | U1 quote aggregator | ☐ |
| REST APIs | Secure FastAPI service with validation and errors | U2 customers API | ☐ |
| Data | Schema, transactions, indexes, caching, migrations | U3 orders | ☐ |
| Frontend | React/TS SPA with API client and auth; Angular equivalents | U4 tickets SPA | ☐ |
| Full stack | Contract, CORS, authz end to end, e2e tests | U5 support desk | ☐ |
| Containers/K8s | Dockerfile, manifests, probes, AWS mapping | U6 | ☐ |
| CI/CD | GitHub Actions and Jenkins pipelines with deploy and rollback | U7 | ☐ |
| Distributed systems | Retries, idempotency, breaker, outbox | U8 | ☐ |
| LLM apps | Structured output, both SDKs, eval, cost | U9 | ☐ |
| RAG/agents | Hybrid retrieval, tools, bounded agent, approvals | U10 | ☐ |
| Observability | Logs, metrics, traces, debugging seeded bugs | U11 | ☐ |
| FDE delivery | Discovery, requirements, acceptance tests, demo, handover | U12 | ☐ |
| Integration | All of the above in one system | Capstone | ☐ |

## Interview Readiness Checklist

**Technical**

- [ ] I can draw the Units 1–5 system map from memory and explain each box.
- [ ] I can live-code a FastAPI endpoint with validation, auth dependency and a test in 20 minutes.
- [ ] I can write a SQL query with a join, group by and an index, and read an `EXPLAIN`.
- [ ] I can implement retry with backoff and jitter, and explain idempotency.
- [ ] I can build a React component that fetches data with loading, error and cancellation.
- [ ] I can write a Dockerfile and a Kubernetes Deployment with probes and resources.
- [ ] I can sketch a CI/CD pipeline with OIDC, promotion and rollback.
- [ ] I can implement a structured-output LLM call with validation and fallback, in either SDK.
- [ ] I can explain RAG with permission filtering and a bounded agent loop with approvals.
- [ ] I can debug a slow endpoint using logs, metrics and traces.

**Behavioral and FDE**

- [ ] Five stories ready (built, incident, customer, ambiguity, conflict), each with a metric.
- [ ] Honest framing for each gap, with lab evidence (see "How to Answer When Your Experience Is Limited").
- [ ] A 2-minute "tell me about yourself" connecting engineering depth and customer impact.
- [ ] Three thoughtful questions for the interviewer about their customers, deployments and team.

**Logistics**

- [ ] Projects run locally (`pytest`, `npm test`) in case you share your screen.
- [ ] Editor, terminal and a whiteboard tool ready; quiet environment; water.

## Highest-Priority Study Areas

If time is short, study in this order. Depth: **Deep** = be able to build and debug live; **Working** = explain clearly with examples and trade-offs; **Aware** = know what it is and when to use it.

| # | Area | Why it matters for this role | Depth | Skill to demonstrate |
|---|---|---|---|---|
| 1 | FastAPI + REST design and security | Core of every FDE deliverable; most likely live-coding topic | Deep | Endpoint with Pydantic validation, auth dependency, object-level authz, problem+json, tests |
| 2 | Production Python (async, errors, testing) | Judged in every coding round | Deep | Async fan-out with timeouts, retries with jitter, typed code, pytest with fakes |
| 3 | LLM integration with structured outputs | The JD's AI emphasis; differentiates FDE candidates | Deep | Validated structured output, repair and fallback, cost logging, both SDKs behind one interface |
| 4 | RAG, tool calling and bounded agents | Most customer AI projects are retrieval or agents | Working→Deep | Permission-filtered hybrid retrieval with citations; tool authz; loop limits; approvals |
| 5 | Debugging and observability | FDEs own production issues at customer sites | Working→Deep | Walk through a latency incident with logs, metrics and traces; fix N+1 or a blocking call |
| 6 | SQL and data modeling | Every integration touches customer data | Working→Deep | Schema with constraints, transaction for stock, index from a query, EXPLAIN |
| 7 | Customer-facing delivery | The "forward deployed" half of the job | Working | Discovery questions, assumptions log, acceptance criteria, BLUF status update, saying no well |
| 8 | Full-stack integration (SPA + API) | End-to-end ownership is explicit in the JD | Working | Explain the request lifecycle, CORS, token storage, contract testing |
| 9 | Docker, Kubernetes and AWS | Deploying into customer environments | Working | Dockerfile, probes, rolling update, service choice on AWS, IAM least privilege |
| 10 | CI/CD and distributed-systems patterns | Shipping safely and integrating with flaky systems | Working | Pipeline with promotion and rollback; idempotency keys, circuit breaker, outbox |
