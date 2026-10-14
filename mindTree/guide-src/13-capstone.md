# Capstone — Acme Support Copilot

The capstone combines all twelve units into one system you can demo, deploy and defend in an interview. It is deliberately the kind of engagement an FDE gets: a real business problem, a vague request, a fixed date, and AI that must be useful without being trusted blindly.

## Business Scenario

*Acme Logistics* (fictional) ships parcels for 40,000 small businesses. Its 25 support agents handle about 1,800 tickets a day through email and a basic web form. Problems:

- tickets sit unclassified for hours, so urgent ones (lost parcels, fraud) wait behind routine questions;
- agents spend 6–8 minutes per reply looking up policy pages and order status in two different tools;
- answers are inconsistent: two agents quote different refund rules for the same situation.

## Stakeholder Request

> **Head of Customer Support:** "We want AI to answer our customers. Everyone else has a chatbot. Can you have something running in six weeks? Our CISO will need to sign off, and our agents are nervous about being replaced."

## Ambiguity to Resolve

The request hides decisions that must be made before building. Ask, then write down the answer (or your assumption) in an assumptions log:

| Question | Why it matters | Assumption used here |
|---|---|---|
| Should AI reply to customers directly or assist agents? | Risk, trust, legal exposure | **Assist agents.** Every AI reply is a draft that a human approves |
| What does "answer" draw on: policies, order data, past tickets? | Data access and grounding | Policy KB + the customer's own orders |
| Which decisions may the AI make on its own? | Safety | Triage suggestions only; no refunds, no status changes |
| What if the AI provider is down? | Availability | Ticket creation must never fail; triage falls back to "needs human" |
| Can customer data be sent to an external model? | Compliance, CISO sign-off | Yes under a DPA; provider is configurable, no training on data |
| How will we know it works? | Acceptance | Triage accuracy ≥ 85% on a golden set; drafts cite policy; time-to-first-reply measured |
| Who can see what? | Privacy | Customers see only their tickets and sent replies; agents see all |

## Requirements

**Functional**

1. Customers (requesters) sign in, create tickets, and see only their own tickets and the replies sent to them.
2. On creation, each ticket gets an AI triage: category, priority, one-line summary, confidence. Agents see it; customers do not.
3. Business rules override the model: fraud-like tickets are always high priority and flagged for a human; low confidence is flagged.
4. Agents can request an AI draft reply. The assistant may search the policy KB and look up the ticket owner's orders. Policy statements must cite KB chunks.
5. A draft is never visible to the customer until an agent approves it (optionally editing it). Approval is recorded.
6. Agents can change ticket status and re-run triage.

**Non-functional**

- AI outages degrade gracefully: tickets are still created (fallback triage).
- Bounded AI cost and latency: timeouts, bounded retries, max agent turns, repeated-call detection.
- Provider-neutral: Anthropic or OpenAI via configuration; an offline fake for development and tests.
- Observability: JSON logs with request IDs, Prometheus metrics for HTTP and LLM calls (outcomes and tokens).
- Security: JWT auth, object-level authorization, CORS allow-list, non-root containers, secrets from a secret manager, OIDC in CI.
- Deployable: Docker images, docker compose for local production-like runs, Kubernetes manifests for EKS, CI/CD with an e2e gate and rollback.

## Architecture

```text
            ┌──────────── Browser (React SPA) ─────────────┐
            │ tickets list · AI badges (agents) · detail    │
            │ "Draft reply with AI" → edit → Approve & send │
            └───────────────────────┬───────────────────────┘
                                    │ HTTPS, Bearer JWT, X-Request-ID
            ┌───────────────────────▼───────────────────────┐
            │ nginx: SPA static files + /api/ → api:8000     │
            └───────────────────────┬───────────────────────┘
            ┌───────────────────────▼───────────────────────┐
            │ FastAPI  (CORS → Observability → routes)       │
            │  auth: /auth/token /me                         │
            │  tickets: list/create/get/patch/retriage       │
            │  replies: list/add · draft · send (approve)    │
            │  ops: /health/live /health /version /metrics   │
            ├────────────────────────────────────────────────┤
            │ TicketService: visibility, roles, transactions │
            ├───────────────┬───────────────┬────────────────┤
            │ TriageService │ Assistant     │ KnowledgeBase  │
            │ structured +  │ bounded tool  │ BM25 over      │
            │ rules +       │ loop: search_ │ policy chunks  │
            │ fallback      │ kb, get_order │ (citations)    │
            ├───────────────┴───────┬───────┴────────────────┤
            │ LLM interface: AnthropicLLM | OpenAILLM | Fake │
            └───────────────────────┼────────────────────────┘
               SQLAlchemy ─► Postgres (Alembic)   LLM provider API

  DETERMINISTIC (code decides)        PROBABILISTIC (model suggests)
  auth, visibility, roles, approval   category/priority/summary
  schema validation, business rules   which tool to call, wording
  budgets, timeouts, fallbacks        draft reply text
  citation check vs retrieved chunks
```

**Key decisions (ADR summaries)**

| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| AI role | Agent assist with approval | Auto-reply bot | Risk, trust, CISO sign-off, agent buy-in |
| Triage timing | Synchronous on create, with timeout + fallback | Background queue | Simple for 1,800/day; the fallback keeps creation reliable. A queue is the next step at higher volume |
| Retrieval | BM25 over section chunks | Vector DB on day 1 | Small KB, deterministic, easy to evaluate; embeddings are a drop-in upgrade behind `search` |
| Order access | Pre-loaded snapshot of the owner's orders | Tool queries DB with an ID | Authorization by construction; no DB calls inside the async loop |
| Provider | Interface + two adapters + fake | One SDK directly | Customer choice, fallback, offline tests |
| Retries | App-level policy; SDK retries off | SDK defaults + app retries | Never stack retry layers |

## Acceptance Criteria

```text
AC-1  Given alice and bob have tickets
      When alice lists or fetches tickets
      Then she sees only hers; bob's ticket ID returns 404

AC-2  Given a new ticket "Parcel late, tracking shows a delay"
      When it is created
      Then the agent view shows ai.status=done, category=delivery
      And the requester view shows ai=null

AC-3  Given the LLM times out on every attempt
      When a ticket is created
      Then it is saved (201) with ai.status=fallback, needs_human=true
      And the LLM was called exactly 1 + max_retries times

AC-4  Given a ticket mentioning fraud
      When it is triaged
      Then priority=high and needs_human=true regardless of the model

AC-5  Given alice's ticket mentions her order ORD-1003
      When an agent requests a draft
      Then the draft states ORD-1003's status, cites a KB chunk that
      the tools returned, and has status=draft

AC-6  Given alice's ticket mentions bob's order ORD-1002
      When an agent requests a draft
      Then the draft reveals nothing about ORD-1002

AC-7  Given a draft exists
      When alice lists replies
      Then she sees nothing until an agent approves it; after
      approval she sees the (edited) text; re-sending returns 409

AC-8  Given a model that keeps calling the same tool
      When an agent requests a draft
      Then the loop stops (stop_reason=repeated_call) with a safe
      escalation message and no citations

AC-9  Given any request
      Then the response carries X-Request-ID, and /metrics counts it
      under its route template, plus LLM call outcomes and tokens
```

Each criterion maps to a test in `backend/tests/` (for example AC-3 → `test_llm_outage_never_blocks_ticket_creation`, AC-6 → `test_tool_cannot_read_another_customers_order`), and the main journey runs in Playwright.

## Milestones

| Week | Milestone | Demo to stakeholders |
|---|---|---|
| 1 | Discovery: assumptions log, golden set of 50 real tickets, ADRs | Walkthrough of the agreed scope and risks |
| 2 | Units 2–5 baseline: auth, tickets, SPA, authz tests | Customers file tickets; agents work them |
| 3 | AI triage with fallback + eval on the golden set | Accuracy report; outage demo (provider off, tickets still flow) |
| 4 | Grounded drafts + approval flow | Agent drafts, edits and sends a cited reply |
| 5 | Containers, compose, CI/CD, staging on EKS, dashboards | Pipeline run from PR to staging; Grafana board |
| 6 | Security review, load test, runbook, pilot with 5 agents | Go/no-go with metrics: accuracy, time-to-reply, cost per ticket |

## Project Structure

{{tree projects/capstone/solution}}

## Step-by-Step Tasks

1. **Run the starter** (README "Run locally"). Everything appears to work, but run `pytest -q`: 14 tests fail. Those failures are the safety and production gaps.
2. **TODO 1–2: triage rules and resilience.**
   - *Why:* the model can be wrong or down; code must decide.
   - *Test:* `pytest -q tests/test_tickets.py`.
3. **TODO 5–7: authorization for AI features.**
   - *Why:* new features create new data paths; BOLA applies to tools too.
   - *Test:* `pytest -q tests/test_replies.py -k "order or never or approval"`.
4. **TODO 3–4: bound and ground the assistant.**
   - *Test:* `pytest -q -k "runaway or grounded"`.
5. **TODO 8: metrics cardinality.**
   - *Test:* `pytest -q tests/test_ops.py`.
6. **TODO 9: the approval UI.**
   - *Test:* `npm test`, then try it in the browser.
7. **TODO 10: Kubernetes probes.** Explain why readiness checks the DB and liveness does not.
8. **Run everything:** backend, frontend, e2e; then `docker compose up --build` if Docker is available.
9. **Real provider (optional):** set `APP_LLM_PROVIDER=anthropic` (or `openai`) with a key, create five tickets from the golden set, and compare with the fake.
10. **Write the 1-page handover** (Unit 12 template): architecture, runbook links, known limits, next steps.

## Starter Code

{{file projects/capstone/starter/backend/app/ai/triage.py}}

{{file projects/capstone/starter/backend/app/services.py}}

The starter also has TODOs in `backend/app/ai/assistant.py` (repeated calls, grounding), `backend/app/observability.py` (route template), `frontend/src/pages/TicketDetailPage.tsx` (approve and send) and `k8s/20-api.yaml` (probes). The task table is in the starter `README.md`.

## Testing

| Layer | Count | What it proves |
|---|---|---|
| Backend API + rules | 7 | Authz, triage saved/hidden, outage fallback, retry, business rule, retriage |
| Backend AI flows | 6 | Grounded drafts, scoped order tool, draft visibility, approval, runaway loop |
| Backend ops | 4 | Health, version, metrics labels and LLM counters, request IDs, CORS |
| Adapters (stub SDKs) | 6 | Anthropic and OpenAI request shapes, tool wire formats, error mapping |
| Frontend | 19 | Client, forms, routing, roles, AI draft review flow |
| E2E (Playwright) | 3 | Multi-user authz journey, AI draft → approval → customer sees reply, request IDs |

```bash
cd backend && pytest -q && ruff check . && mypy
cd frontend && npm test && npm run typecheck
cd frontend && PYTHON=../backend/.venv/bin/python npm run e2e
```

## Final Runnable Solution

{{files projects/capstone/solution}}

## Deployment

**Local, production-like.** `docker compose up --build` starts Postgres, runs `alembic upgrade head` as a one-shot `migrate` service, then the API (health-checked) and nginx serving the SPA on port 8080. The API is only reachable through nginx's `/api/` path: same origin, so no CORS in production.

**AWS (EKS) path.**

1. **Infrastructure** (Terraform or CDK, Unit 6):
   - VPC with private subnets;
   - EKS cluster with the AWS Load Balancer Controller;
   - RDS Postgres;
   - ECR repositories `support-api` and `support-web`;
   - Secrets Manager entries for `APP_JWT_SECRET`, `APP_DATABASE_URL` and the LLM API key;
   - External Secrets Operator syncing them into `support-api-secrets`;
   - an IAM role for the pods (IRSA or Pod Identity).
2. **CI/CD** (Unit 7, `.github/workflows/ci.yml`):
   - PRs run backend (with a Postgres service and a migration check), frontend and e2e.
   - `main` builds both images tagged with the commit SHA and pushes them to ECR via OIDC, with no stored keys.
   - It then rolls out to staging, smoke-tests `/api/health`, and runs `kubectl rollout undo` on failure.
   - Production is a second environment with required reviewers.
3. **Rollout order:**
   1. apply `00-namespace-config.yaml`;
   2. run `10-migrate-job.yaml` with the new tag (expand-and-contract migrations only);
   3. apply `20-api.yaml` and `30-web.yaml`;
   4. watch `kubectl rollout status`.
4. **Operate** (Unit 11):
   - scrape `/metrics`;
   - alert on 5xx rate, p95 latency, a rising `llm_calls_total{outcome="fallback"}` rate, and tokens per hour (cost);
   - ship JSON logs to CloudWatch or Loki, searchable by `request_id`.

## Verification Checklist

- [ ] Backend: 23 passed, ruff and mypy clean; `alembic check` reports no drift.
- [ ] Frontend: 19 passed; typecheck clean; `npm run build` succeeds.
- [ ] E2E: 3 passed.
- [ ] As bob, `GET /tickets/<alice's id>` returns 404.
- [ ] As alice, ticket JSON has `"ai": null`; as the agent it has the triage.
- [ ] With `FakeLLM(failures=[LLMTimeout()]*3)` (or the real provider blocked by the network), ticket creation still returns 201 with `ai.status = "fallback"`.
- [ ] A draft for an ORD-1003 ticket cites `delivery-delays#…` and is invisible to alice until sent.
- [ ] `/metrics` shows `route="/tickets/{ticket_id}"` (never a raw ID) and `llm_calls_total`.
- [ ] Every response has `X-Request-ID`, and JSON log lines contain the same ID.
- [ ] `docker compose up --build` serves the app on :8080 (where Docker is available).
- [ ] Manifests: probes, resource requests and limits, non-root, no `:latest` tags.
- [ ] The CI workflow has top-level `contents: read`; `id-token: write` only on AWS jobs; e2e gates the image build.

## Capstone Interview Questions

**C1. Walk me through the architecture and one request end to end.**
Use the architecture diagram. Trace "agent clicks Draft reply":
- JWT check, role check and ticket visibility;
- release the DB transaction;
- the bounded tool loop (KB search, owner-scoped order lookup);
- the citation check;
- save as draft;
- the agent edits and approves;
- the customer sees it.
Mention the request ID and metrics along the way.

**C2. Where exactly is the boundary between deterministic and probabilistic behavior?**
- *The model suggests:* the triage fields, tool choice and draft wording.
- *Code enforces:* authentication, visibility, roles, the approval gate, schema validation, business-rule overrides, budgets and timeouts, and the citation check.
- Nothing the model outputs can change who sees what or send anything by itself.

**C3. What happens when the LLM provider has an outage?**
Each attempt has a timeout. Transient errors are retried with backoff (bounded), and then the ticket is saved with `ai.status=fallback` and `needs_human=true`. The metric `llm_calls_total{outcome="fallback"}` rises and alerts, and agents keep working from the normal queue. Drafts return a safe escalation message. The SDKs' own retries are disabled so retries do not multiply.

**C4. How do you prevent the assistant from leaking another customer's data?**
The order tool receives a snapshot containing only the ticket owner's orders, so authorization holds by construction. The model cannot ask for anything outside it. Retrieved policy text is public, and a test (AC-6) proves the leak cannot happen. For internal documents, I would filter the KB by permission metadata before retrieval.

**C5. How would you measure whether this is working for the business?**
- *Model quality:* triage accuracy on a golden set in CI, and the share of drafts sent with no or minor edits.
- *Operations:* time to first reply, tickets per agent-hour, and the share of urgent tickets handled within SLA.
- *Cost:* tokens per ticket, from metrics.
- *Trust:* agent satisfaction.
Agree on targets with the stakeholder before the pilot.

**C6. Why synchronous triage instead of a queue?**
At about 1,800 tickets a day, a synchronous call with a timeout and a fallback is simpler and gives agents triage immediately. At higher volume, or with slow models, I would move triage to a queue (SQS) with the outbox pattern (Unit 8). The ticket would start as `ai.status=pending` and the UI would update when triage lands. The data model already supports `pending`.

**C7. What would you change before 5,000 users and 200 agents?**
- SSO via the customer's IdP (OIDC);
- triage in a queue;
- an async DB driver, or keeping the thread-pool pattern with tuned pools;
- hybrid retrieval with embeddings and a reranker;
- prompt caching for the stable system prompt;
- per-tenant rate limits;
- load testing;
- OpenTelemetry traces;
- a canary deployment;
- a formal evaluation pipeline with human review sampling;
- a support runbook and on-call rotation.

**C8. How did you test code that calls an LLM?**
- A provider-neutral interface with a deterministic fake that can be scripted to fail (timeouts, rate limits, runaway loops).
- Adapter tests with stub SDK clients that assert the exact request shapes for Anthropic and OpenAI.
- An eval script against a golden set for real model quality, separate from unit tests.
- Playwright for the full journey with the fake provider.

**C9. A stakeholder asks to let the AI send replies automatically for "easy" tickets. What do you say?**
I would not refuse outright, and I would not agree blindly either. I would propose criteria: categories with high measured accuracy, high confidence, citations present, and no money or account changes. I would start with a shadow mode, comparing auto-drafts with agent replies, and set an error budget, sampling audits and a kill switch. The deterministic gate stays in code and the decision is documented in an ADR.

**C10. What was the hardest trade-off in this design?**
One option: keeping a database transaction out of the LLM call. The simplest code reads the ticket, calls the model, then writes, all in one transaction. That holds a connection and locks during a slow external call, so the design releases the read transaction before the call. Another option: retrieval quality versus simplicity, where BM25 misses synonyms ("broken" vs "damaged"). Name the trade-off, how you would detect it (the eval set), and the upgrade path.
