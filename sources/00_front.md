---
title: "Production Agentic Engineering and AI Evaluation & Operations"
subtitle: "Parts XV–XVI · Units 41–46 — A Technical Study and Implementation Guide"
author: "Claude Research Curriculum"
date: "October 2026"
---

# How to Use This Guide {.unnumbered}

This guide covers two curriculum parts and six units:

| Part | Unit | Title |
|---|---|---|
| XV — Production Agentic Engineering | 41 | Guardrails and Agent Security |
| | 42 | Structured Agent Output and Deterministic Boundaries |
| | 43 | Human-in-the-Loop and Approval Workflows |
| XVI — AI Evaluation and Operations | 44 | LLM, RAG and Agent Evaluation |
| | 45 | AI Observability and Tracing |
| | 46 | Safe Deployment, Drift and Resilience for AI |

Each unit follows the same 19-section structure (learning objectives → mental model → theory → internals → examples → comparisons → failure modes → practice → project → testing → scenarios → interview prep → three-level explanations → knowledge check → traps → cheat sheet → checklist → further research) and ends with a **Unit Completion Standard**.

## The Running Example: Northwind SupportOps {.unnumbered}

All six units build on one fictional system so that concepts accumulate rather than restart:

> **Northwind SupportOps** is a multi-tenant FastAPI service. Support staff (and, in a limited mode, end customers) chat with an agent that can search a knowledge base (RAG), look up orders, draft and send emails, update customer records, issue refunds up to policy limits, and delete accounts on request (GDPR/CCPA erasure).

```
                   ┌──────────────────────────── Northwind SupportOps ───────────────────────────┐
  Browser / CRM ─► │ FastAPI ─► AuthN ─► Agent Orchestrator ─► Model Provider (LLM)               │
                   │                         │                                                    │
                   │                         ├─► Policy Engine (deterministic)                    │
                   │                         ├─► Tool Executor ─► Orders API / Payments / Email   │
                   │                         ├─► Retriever ─► Vector index (KB articles)          │
                   │                         ├─► Approval Service ─► PostgreSQL (proposals/audit) │
                   │                         └─► OpenTelemetry ─► Collector ─► Traces/Metrics     │
                   └─────────────────────────────────────────────────────────────────────────────┘
```

* Unit 41 makes it **secure** (threat model, injection defenses, least privilege, secure logging, fail-closed).
* Unit 42 makes its decisions **typed and validated** (Pydantic discriminated unions, policy checks).
* Unit 43 puts **humans in front of risky actions** (persisted proposals, approvals, expiry, audit).
* Unit 44 **measures quality** (eval datasets, tool accuracy, retrieval metrics, regression gates).
* Unit 45 makes it **observable** (one OpenTelemetry trace from HTTP request to tool call, privacy-safe).
* Unit 46 makes it **safe to change** (versioning, drift, canaries, eval gates, circuit breakers, fallbacks).

## Conventions and Versions {.unnumbered}

* **Python** 3.12+ (3.13 and 3.14 are current at the time of writing; all examples avoid features newer than 3.12 unless noted).
* **FastAPI** 0.11x+, **Pydantic** v2, **SQLAlchemy** 2.x (typed `Mapped[...]` declarative style, `AsyncSession`), **pytest** 8+, **httpx**, **anyio** test plugin.
* **OpenTelemetry** Python SDK 1.x; the **GenAI semantic conventions** are still marked *Development* (experimental) and now live in their own repository (`open-telemetry/semantic-conventions-genai`). Attribute names can still change — pin and re-verify.
* Model-provider code is written against a small `ModelClient` protocol so that examples are provider-neutral. Where provider features matter (e.g. JSON-schema-constrained output, strict tool schemas) the text links to the official docs.
* Code labelled **"Illustrative"** omits non-essential plumbing; code labelled **"Runnable"** includes imports and a command to run it.

Status labels used in the text:

| Label | Meaning |
|---|---|
| **Current** | Recommended practice today |
| **Legacy** | Still encountered, do not choose for new work |
| **Deprecated** | Officially discouraged / scheduled for removal |
| **Experimental** | Spec or API not yet stable; expect change |
| **Version-dependent** | Behaviour differs across library/model versions |
