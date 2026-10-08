---
title: "Parts X–XIV — DevOps and Cloud, LLM Application Engineering, Embeddings and RAG, AI Frameworks and Tool Calling, Agentic Systems"
subtitle: "Units 25–40: A Self-Contained Study and Implementation Guide for Python/FastAPI and Agentic Systems Engineers"
date: "October 2026"
---

# Contents

**Part X — DevOps and Cloud**

- Unit 25 — Docker and Local Production Environments
- Unit 26 — CI/CD and Engineering Automation
- Unit 27 — AWS for Python/FastAPI Engineers

**Part XI — LLM Application Engineering**

- Unit 28 — LLM Application Fundamentals in Python
- Unit 29 — LLM Client Architecture and Reliability

**Part XII — Embeddings and RAG**

- Unit 30 — Embeddings and Vector Search
- Unit 31 — Build RAG from Scratch (deliverable: framework-free FastAPI RAG service on PostgreSQL/pgvector with citations and evaluation tests)
- Unit 32 — Advanced RAG

**Part XIII — AI Frameworks and Tool Calling**

- Unit 33 — LangChain/LangGraph and Framework Abstractions
- Unit 34 — Function and Tool Calling

**Part XIV — Agentic Systems**

- Unit 35 — Build a Bounded Agent Manually (deliverable: framework-free Python agent with typed state, tools, limits, telemetry and automated tests)
- Unit 36 — Single-Agent Application with FastAPI
- Unit 37 — Agent State, Memory and Persistence
- Unit 38 — LangGraph and Durable Agent Workflows
- Unit 39 — Multi-Agent Systems
- Unit 40 — Model Context Protocol (MCP)

**Every unit contains the same sections:** 1 Learning Objectives · 2 Prerequisite Knowledge · 3 Mental Model · 4 Comprehensive Theory · 5 Internal Mechanics · 6 Implementation Examples · 7 Comparative Analysis · 8 Failure Modes and Debugging · 9 Guided Practice · 10 Independent Implementation Project · 11 Testing Strategy · 12 Engineering Scenarios · 13 Interview Preparation · 14 Explain-It-at-Three-Levels · 15 Knowledge Check (+ Answers) · 16 Common Interview Traps · 17 Cheat Sheet · 18 Completion Checklist · 19 Further Research · Unit Completion Standard.

# How to Use This Guide

| Part | Units | Theme |
|---|---|---|
| X — DevOps and Cloud | 25, 26, 27 | Packaging, automating and deploying a FastAPI stack reproducibly |
| XI — LLM Application Engineering | 28, 29 | Calling models safely and reliably as just another (unreliable, expensive) dependency |
| XII — Embeddings and RAG | 30, 31, 32 | Grounding answers in your own data, measured stage by stage |
| XIII — AI Frameworks and Tool Calling | 33, 34 | When frameworks help, and how to let a model request actions safely |
| XIV — Agentic Systems | 35–40 | Bounded agents, durable state, graphs, multi-agent systems and MCP |

**One running system.** All sixteen units build pieces of one application, **SupportDesk**: a customer-support assistant for an online retailer. It has a FastAPI API, a background worker, PostgreSQL with pgvector, Redis and Kafka. Part X packages and deploys it. Part XI adds a provider-neutral LLM client. Part XII adds a knowledge-base RAG service. Part XIII adds tools (customer lookup, orders, shipments, knowledge search, tickets). Part XIV turns those tools into a bounded, observable, durable agent, then a graph workflow with human approval, a small multi-agent system, and an MCP server. The package layout is shared across units:

```
supportdesk/
├── pyproject.toml   uv.lock   Dockerfile   compose.yaml   .github/workflows/
├── app/
│   ├── main.py                  FastAPI app factory + lifespan
│   ├── core/                    settings, logging, telemetry, security
│   ├── api/                     routers (health, ask, agent, tickets, admin)
│   ├── domain/                  pure models and rules (no I/O)
│   ├── services/                application services (use cases)
│   ├── repositories/            SQLAlchemy 2.x data access
│   ├── llm/                     provider-neutral LLM client (Units 28–29)
│   ├── rag/                     ingestion + retrieval (Units 30–32)
│   ├── tools/                   tool registry + tools (Unit 34)
│   ├── agent/                   bounded agent, state, memory (Units 35–37)
│   ├── graphs/                  LangGraph workflows (Units 33, 38, 39)
│   └── mcp_server/              MCP server (Unit 40)
├── worker/                      Kafka/queue consumers (ingestion, agent runs)
├── migrations/                  Alembic
└── tests/  unit/  integration/  contract/  eval/
```

**Suggested pacing.** Part X: one week per unit, ending with the stack deployed to AWS. Part XI: one week each. Part XII: two weeks for Unit 31 (deliverable), one each for 30 and 32. Part XIII: one week each. Part XIV: one to two weeks per unit, with Unit 35's deliverable as the foundation for 36–40.

**Version baseline (verified October 2026).**

- **Python:** 3.14 is the current stable release. 3.15.0 was in its third release candidate, with final scheduled for 9 October 2026 after last-minute lazy-import blockers (PEP 790 originally planned 1 October). Code here targets **Python 3.12–3.14** and uses modern typing (`X | None`, `type` aliases, PEP 695 generics where helpful). 3.13's experimental free-threaded build became officially supported but optional in 3.14 (PEP 779). Most production FastAPI deployments still run the default GIL build. [Current] [Version-dependent]
- **FastAPI:** 0.14x (0.141.x seen in July 2026). Still pre-1.0, so **pin an exact version**. FastAPI dropped Pydantic v1 support in 0.126, removed the `pydantic.v1` compatibility path in 0.128, and dropped Python 3.9 in 0.129. `fastapi run` (production, no reload, binds 0.0.0.0) and `fastapi dev` come with `fastapi[standard]`. [Current]
- **Pydantic:** 2.13 (April 2026). 2.14 is in beta. Pydantic v1 patterns are legacy and are not taught as practice. [Current]
- **SQLAlchemy:** 2.0.x is the stable line (2.0.51, June 2026). 2.1.0 reached rc2 on 8 September 2026. Pin `sqlalchemy>=2.0,<2.1` until you have tested 2.1. Code here uses the 2.0-style API, which 2.1 keeps. [Version-dependent]
- **Packaging:** `uv` with `pyproject.toml` + `uv.lock`. Use `uv sync --locked` in CI and Docker so a stale lockfile fails the build. Pin the uv image version. [Current]
- **LangChain / LangGraph:** the 1.x lines (LangChain 1.0 went GA on 22 October 2025). `create_agent` replaces the deprecated `create_react_agent` prebuilt. Legacy chains and `AgentExecutor` moved to `langchain-classic`. Checkpointers are separate packages (`langgraph-checkpoint-postgres`). [Current] [Version-dependent]
- **MCP:** the specification revision **2026-07-28** is stateless: no `initialize` handshake or `Mcp-Session-Id`, and server-to-client requests become return-and-retry. The **MCP Python SDK v2** renamed `FastMCP` to `MCPServer` and added a first-class `Client`. The decorator API is unchanged, and v1 is in maintenance mode. Check whether your installed SDK is v1 or v2. [Version-dependent]
- **Model APIs:** examples use the Anthropic Messages API (raw HTTP and the `anthropic` Python SDK). The SDK 1.x is built on `httpx2` and retries 408/409/429/5xx by default. Current Claude models are `claude-opus-5-5` (default here), `claude-sonnet-5-5` and `claude-haiku-5-5`. On these models, sampling parameters such as `temperature` are **rejected** (depth is controlled with `output_config.effort`), and forced `tool_choice` (`any`/`tool`) returns a 400. Structured output uses `output_config.format` or `client.messages.parse(...)`. Other providers still expose `temperature`. Unit 28 explains why the concept still matters. [Current] [Version-dependent]
- **AWS:** Amazon Bedrock's **Converse API** (`bedrock-runtime` `converse`/`converse_stream`) gives one request shape across models. Bedrock AgentCore offers managed agent runtime services. [Current]
- **Data/infra:** PostgreSQL 17–18, pgvector 0.8.x (HNSW, iterative index scans for filtered queries), Redis 7/8 or Valkey 8, Apache Kafka 4.x (KRaft only), Docker Compose v2 (`compose.yaml`), OpenTelemetry (GenAI semantic conventions still in Development status).

Version-sensitive claims are flagged inline as **[Current]**, **[Legacy]**, **[Deprecated]**, **[Experimental]** or **[Version-dependent]**. Where an API changes quickly (LLM SDKs, LangGraph, MCP), the safety-critical logic (validation, authorization, limits, idempotency) is written in plain Python you own, and the framework appears only at the edge.

**Notation.** `→` synchronous call, `⇢` asynchronous message, `[ ]` component, `( )` data store, `{ }` external dependency.

## Sources Verified for Version-Sensitive Claims

- PEP 790 (Python 3.15 schedule) — <https://peps.python.org/pep-0790/>; Real Python news, October 2026 (3.15 rc3, final moved to 9 October) — <https://realpython.com/python-news-october-2026/>
- FastAPI release notes — <https://fastapi.tiangolo.com/release-notes/>; Pydantic v1 → v2 migration — <https://fastapi.tiangolo.com/how-to/migrate-from-pydantic-v1-to-pydantic-v2/>
- Pydantic v2.13 release — <https://pydantic.dev/articles/pydantic-v2-13-release>
- SQLAlchemy 2.1.0rc2 announcement — <https://www.sqlalchemy.org/blog/2026/09/08/sqlalchemy-2.1.0rc2-released/>
- uv Docker integration guide — <https://docs.astral.sh/uv/guides/integration/docker/>
- LangGraph v1 release notes — <https://docs.langchain.com/oss/python/releases/langgraph-v1>; `langgraph-checkpoint-postgres` — <https://pypi.org/project/langgraph-checkpoint-postgres>
- MCP Python SDK docs — <https://py.sdk.modelcontextprotocol.io/>; repository — <https://github.com/modelcontextprotocol/python-sdk>
- Amazon Bedrock Converse API (Python) — <https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started-api-ex-python.html>
- PEP 779 (free-threaded Python supported in 3.14) — <https://peps.python.org/pep-0779/>
