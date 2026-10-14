# Capstone Starter — Acme Support Copilot

A production-shaped, AI-assisted support desk for a (fictional)
logistics company. It integrates every unit:

| Piece | Where | Unit |
|---|---|---|
| React + TS SPA, role-aware UI, AI draft review | `frontend/` | 4-5 |
| FastAPI API, JWT auth, object-level authz | `backend/app` | 2, 5 |
| SQLAlchemy + Alembic, Postgres in compose/CI | `backend/` | 3 |
| AI triage (structured output, rules, fallback) | `app/ai/triage.py` | 9 |
| Grounded reply drafts (bounded tool loop) | `app/ai/assistant.py` | 10 |
| Anthropic + OpenAI adapters, offline fake | `app/ai/llm.py` | 9-10 |
| JSON logs, request IDs, Prometheus metrics | `app/observability.py` | 11 |
| Docker images, compose, EKS manifests | `*/Dockerfile`, `k8s/` | 6 |
| CI/CD with OIDC, e2e gate, rollback | `.github/workflows/` | 7 |

```
browser ─► nginx (SPA + /api proxy) ─► FastAPI ─► Postgres
                                         ├─► LLM provider (or fake)
                                         └─► /metrics, JSON logs
```

## Your tasks

The plumbing works (auth, CRUD, SPA, Docker, CI). The parts that
make it SAFE and PRODUCTION-READY are TODOs (`grep -rn "TODO(" .`):

| # | File | Task |
|---|------|------|
| 1 | `backend/app/ai/triage.py` | business rules override the model |
| 2 | `backend/app/ai/triage.py` | timeout, bounded retries, fallback |
| 3 | `backend/app/ai/assistant.py` | stop repeated tool calls |
| 4 | `backend/app/ai/assistant.py` | reject ungrounded citations |
| 5 | `backend/app/services.py` | order tool sees owner's orders only |
| 6 | `backend/app/services.py` | requesters never see drafts |
| 7 | `backend/app/services.py` | a sent reply cannot be re-sent |
| 8 | `backend/app/observability.py` | metrics by route template |
| 9 | `frontend/src/pages/TicketDetailPage.tsx` | approve and send |
| 10 | `k8s/20-api.yaml` | readiness and liveness probes |

Done when backend (23), frontend (19) and e2e (3) tests pass.
Suggested order: 1-2, 5-7, 3-4, 8, 9, 10.

## Run locally (no Docker, no API keys)

```bash
# terminal 1: API (SQLite, fake LLM)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
uvicorn app.main:create_app --factory --reload

# terminal 2: SPA
cd frontend
npm install && cp .env.example .env && npm run dev
```

Open http://localhost:5173. Users: `agent / agent-password`,
`alice / alice-password`, `bob / bob-password`.

## Run the production-like stack

```bash
docker compose up --build      # postgres + migrations + api + web
open http://localhost:8080
```

## Use a real model

```bash
# backend/.env
APP_LLM_PROVIDER=anthropic
APP_ANTHROPIC_API_KEY=sk-ant-...
# or
APP_LLM_PROVIDER=openai
APP_OPENAI_API_KEY=sk-...
APP_OPENAI_MODEL=<a model your account can use>
```

## Test

```bash
cd backend && pytest -q && ruff check . && mypy   # 23 tests
cd frontend && npm test && npm run typecheck      # 19 tests
cd frontend && PYTHON=../backend/.venv/bin/python npm run e2e  # 3
```

## Verify by hand

1. alice: create "Express parcel late" with "ORD-1003 is late".
2. agent: the list shows `delivery · high`; open the ticket.
3. agent: "Draft reply with AI" -> the draft cites
   `[delivery-delays#…]` and mentions ORD-1003's status.
4. alice: no reply is visible until the agent approves and sends.
5. `curl localhost:8000/metrics | grep llm_calls_total`.
6. Stop the "model" (set `APP_LLM_PROVIDER=openai` with no key):
   the API refuses to start. That failure is deliberate:
   config errors should fail fast.
