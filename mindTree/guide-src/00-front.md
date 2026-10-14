---
title: "Forward Deployed Engineer / Full-Stack Developer"
subtitle: "Training, Implementation and Interview-Preparation Guide — Python · FastAPI · SQL/NoSQL · React/Angular · AWS · Docker · Kubernetes · CI/CD · Distributed Systems · LLMs, RAG and Agents"
date: "October 2026"
---

# How to Use This Guide

This guide teaches you to **build, operate and explain** the kind of system a Forward Deployed Engineer (FDE) delivers. It is organized into **twelve units of related engineering concepts** (not weeks), a **final capstone**, and a **final interview-preparation section**.

Every unit follows the same pattern:

1. **What this unit teaches.**
2. **Mental model.** An ASCII diagram of the flow before any detail.
3. **Brief theory.** What it is, why it exists, why it matters, how it works.
4. **Application in a real system.** Where it appears, why it was chosen, alternatives and trade-offs.
5. **Implementation.** Short, explained code.
6. **How it connects.** A map of the unit's place in the whole system.
7. **Comprehension questions**, with answers in a separate subsection.
8. **Interview questions.** Theory-based, plus application/experience-based.
9. **Troubleshooting scenarios.**
10. **A unit practice project.** Step-by-step instructions, starter code, tasks, hints, expected behavior, tests, the complete final solution, how to run it, how to verify it, and an interview debrief.

**FDE scenarios** appear throughout. **Cross-unit system maps** appear after Units 3, 5, 8 and 10.

## The Code That Accompanies This Guide

All code lives next to this document:

```text
mindTree/
├── FDE_FullStack_Interview_Guide.docx   ← this document
├── README.md
├── guide-src/                           ← Markdown sources + build script
└── projects/
    ├── unit01-python/        {starter, solution}
    ├── unit02-fastapi/       {starter, solution}
    ├── unit03-data/          {starter, solution}
    ├── unit04-spa/           {starter, solution}
    ├── unit05-fullstack/     {starter, solution}
    ├── unit06-cloud-native/  {starter, solution}
    ├── unit07-cicd/          {starter, solution}
    ├── unit08-distributed/   {starter, solution}
    ├── unit09-llm/           {starter, solution}
    ├── unit10-rag-agents/    {starter, solution}
    ├── unit11-observability/ {starter, solution}
    ├── unit12-fde-delivery/  {starter, solution}
    └── capstone/             {starter, solution}
```

- **`starter/`** is what you receive before solving the project. It runs, or at least imports and builds, and it contains `TODO` markers where you must implement meaningful logic. Some of its tests fail on purpose: they are the specification.
- **`solution/`** is the complete, runnable implementation, and its tests pass. Every solution file is printed in full in the "Final Runnable Solution" section of its unit. The guide's build script inserts the code straight from disk, so the document and the code cannot drift apart.

Work on a copy of `starter/`. Compare with `solution/` only after you have tried the hints.

## Source of Truth and Labels

The guide is built from the job-description requirements you supplied (the technology and responsibility list in the request), used here **as a proxy for the full job description**. No separate job-description text or résumé was provided. As a result:

- Content is labeled **[JD-Required]**, **[JD-Preferred]** or **[External]** (knowledge added because production work or interviews need it, even though the job description does not name it).
- **No candidate experience is invented.** Experience-based interview questions come with answer *frameworks* and clearly marked `<<personalize: ...>>` placeholders.

### Job-Description Analysis

| Area | Classification | Expected interview depth | Implementation skill expected |
|---|---|---|---|
| Python (OOP, typing, async, testing, debugging, performance, production code) | JD-Required | Deep: mechanisms and trade-offs | Write idiomatic, typed, tested code live |
| FastAPI, REST, HTTP, validation, authN/authZ, service architecture | JD-Required | Deep | Build a secured CRUD service with tests |
| JavaScript/TypeScript, SPA, React, Angular, frontend–backend integration | JD-Required (React *or* Angular) | Moderate–deep on concepts, moderate on framework APIs | Build a typed SPA that calls an API with auth, loading and error states |
| Relational databases, SQL, NoSQL, schema design, transactions, indexes | JD-Required | Deep on SQL/transactions/indexes; moderate on NoSQL | Design a schema, write queries, use SQLAlchemy and migrations |
| Cloud (AWS/Azure/GCP), Docker, Kubernetes, config, secrets, scaling, health | JD-Required (one cloud) | Moderate–deep | Containerize, write Kubernetes manifests, explain AWS architecture |
| Git, CI/CD (Jenkins/GitHub Actions), deployments, rollback, verification | JD-Required | Moderate | Write a pipeline with test/build/deploy/verify stages |
| Microservices, distributed systems, timeouts, retries, idempotency, consistency | JD-Required | Deep on failure behavior | Implement resilient calls and idempotent endpoints |
| LLM APIs, structured output, tool calling, RAG, agents, harnesses, evaluation, guardrails | JD-Required | Deep and practical | Call model APIs, validate outputs, build RAG and a bounded agent |
| Machine learning, data engineering, MLOps | JD-Preferred (exposure) | Conceptual | Explain pipelines and model lifecycle |
| FDE engineering: discovery, stakeholders, requirements, delivery, Agile | JD-Required (core of the role) | Deep, scenario-based | Turn ambiguity into testable requirements and a working demo |

**Likely interview loop for this role** [External]:

- A recruiter screen.
- A technical deep-dive (Python, APIs, data).
- A coding exercise (often a small API or data task).
- A system-design discussion that includes an AI component.
- A customer-scenario or FDE round (requirements, communication, trade-offs).
- Behavioral and experience questions.

## Version Baseline (verified October 2026)

| Technology | Version used / referenced | Notes |
|---|---|---|
| Python | Code targets **3.12+**, tested on 3.13 | 3.14 is current stable. 3.15.0 was reported released in October 2026 (verify on python.org). The code uses PEP 695 generics (3.12+) and `asyncio.TaskGroup` / `asyncio.timeout` (3.11+). |
| FastAPI | 0.143.x | Still 0.x and releases often; pin a minor version. |
| Pydantic | 2.14.x | v1 APIs are **legacy**. |
| SQLAlchemy | 2.1.x | The 2.0-style API (`select()`, `Mapped[]`) is current; 1.x `Query` style is **legacy**. |
| Alembic / psycopg | 1.20 / 3.3 | psycopg 3 is current; psycopg2 is legacy but common. |
| pytest / HTTPX | 9.1 / 0.28 | |
| PostgreSQL | 18 current; examples are compatible with 14+ | Tested locally on 16. |
| Redis | 7+/8 (or Valkey) | |
| Node.js | 22/24 LTS | |
| TypeScript | 7.0 (native compiler) | 5.x code is compatible for our purposes. |
| React | 19.x; React Router 7/8; Vite 8 | Class components are **legacy**. |
| Angular | 22 | Standalone components are the default. Signals are current. Zoneless change detection is the default for new apps since v21. NgModule-first apps are **legacy but encountered**. |
| Docker Engine | 29 | |
| Kubernetes | 1.36 stable | ingress-nginx has been retired in favor of **Gateway API**. |
| Anthropic Python SDK | `anthropic` 1.13: Messages API, `messages.parse()`, tool use | Default model `claude-opus-5-5`. |
| OpenAI Python SDK | `openai` 3.31: **Responses API** (`responses.create` / `responses.parse`) | Chat Completions is **legacy but still supported**. Set the model ID with `OPENAI_MODEL` from OpenAI's models page. |
| AWS Bedrock | Converse API (provider-neutral); Anthropic models also via the Mantle client | |

Version-sensitive statements in the text are flagged **[Current]**, **[Legacy]**, **[Deprecated]**, **[Experimental]**, **[Provider-specific]** or **[Framework-specific]**.

## How to Answer When Your Experience Is Limited

Interviewers value honest, precise answers over inflated ones. Separate four kinds of evidence and say which one you are using:

| Evidence type | Example wording |
|---|---|
| **Professional experience** | "In production at `<<company>>`, I owned..." |
| **Project experience** | "In a project I built end to end, I implemented..." |
| **Training/lab experience** | "In hands-on labs, including the projects in this guide, I implemented X and tested Y..." |
| **Theoretical understanding** | "I haven't implemented this yet. My understanding of how it works is..." |

**Template for a gap:**

> "I have not used **X** extensively in production. My direct experience is with **Y**, which shares these underlying concepts: **<<list>>**. I have also implemented **X** in hands-on project work, where I **<<what you built and how you verified it>>**. If I had to deliver it here, I would approach it by **<<steps>>**, and I'd verify it with **<<evidence>>**."

Never claim production ownership of something you only built in a lab. The interview follow-ups ("What broke? What did the dashboards show? What did you change after the incident?") reveal the difference quickly.

## The Standard Answer Framework for Experience Questions

```text
Situation → Requirement → Architecture → Implementation
          → Verification → Result → Lesson
```

Keep each element to one or two sentences. End with evidence: a metric, a test, a demo, an incident that was resolved. Then the lesson: what you'd do differently.

## Useful Primary References

- Python documentation: <https://docs.python.org/3/> · PEP index: <https://peps.python.org/>
- FastAPI: <https://fastapi.tiangolo.com/> · Pydantic: <https://docs.pydantic.dev/latest/>
- SQLAlchemy 2.x: <https://docs.sqlalchemy.org/en/21/> · Alembic: <https://alembic.sqlalchemy.org/>
- PostgreSQL: <https://www.postgresql.org/docs/current/> · MongoDB: <https://www.mongodb.com/docs/> · Redis: <https://redis.io/docs/latest/>
- MDN JavaScript: <https://developer.mozilla.org/en-US/docs/Web/JavaScript> · TypeScript: <https://www.typescriptlang.org/docs/>
- React: <https://react.dev/> · Angular: <https://angular.dev/>
- Docker: <https://docs.docker.com/> · Kubernetes: <https://kubernetes.io/docs/home/>
- AWS: <https://docs.aws.amazon.com/> · AWS Well-Architected: <https://aws.amazon.com/architecture/well-architected/>
- Git: <https://git-scm.com/doc> · GitHub Actions: <https://docs.github.com/en/actions> · Jenkins: <https://www.jenkins.io/doc/>
- Anthropic API: <https://docs.claude.com/> · OpenAI API: <https://platform.openai.com/docs> · Amazon Bedrock: <https://docs.aws.amazon.com/bedrock/>
- OpenTelemetry: <https://opentelemetry.io/docs/> · OWASP Top 10 for LLM Applications: <https://genai.owasp.org/llm-top-10/>
- HTTP semantics (RFC 9110): <https://www.rfc-editor.org/rfc/rfc9110> · Problem Details (RFC 9457): <https://www.rfc-editor.org/rfc/rfc9457>
