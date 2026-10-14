# Unit 5 Project — Support Desk (React SPA + FastAPI + SQL)

The Unit 4 SPA connected to a real FastAPI backend. Covers JWT login,
`/me` for the role, object-level authorization (requesters only see
their own tickets; only agents change status), CORS, request IDs that
connect browser and server logs, problem+json errors, a contract test,
and Playwright end-to-end tests that start both tiers.

```
browser ─► Vite :5173 ─/api proxy─► FastAPI :8000 ─► SQLite/Postgres
X-Request-ID: 9f2c…        log: [9f2c…] PATCH /tickets/1 -> 200
```

## Run the backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload  # :8000/docs
pytest -q && ruff check . && mypy
```

## Run the frontend (second terminal)

```bash
cd frontend
npm install
cp .env.example .env        # real backend through the /api proxy
npm run dev                 # http://localhost:5173
npm test && npm run typecheck
```

Demo users: `agent / agent-password` (agent),
`alice / alice-password` and `bob / bob-password` (requesters).

## End-to-end tests

```bash
cd frontend
npx playwright install chromium          # once
PYTHON=../backend/.venv/bin/python npm run e2e
```

Playwright starts uvicorn (fresh in-memory DB) and Vite, then drives
three browser sessions: alice creates a ticket, bob cannot see it,
the agent closes it. Set `PW_CHROMIUM_PATH` to use a pre-installed
browser instead of downloading one.

## Verify by hand

1. Sign in as alice, create a ticket: the status dropdown is disabled.
2. Sign in as bob in a private window: alice's ticket is not listed.
3. `curl -i 127.0.0.1:8000/tickets/1 -H "Authorization: Bearer $BOB"`
   (with bob's token in `$BOB`) returns **404**, not 403: we do not
   reveal that the ticket exists.
4. In DevTools > Network, copy a request's `X-Request-ID`, then find
   the same ID in the uvicorn log line for that request.
