# Capstone — Acme Support Copilot

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
