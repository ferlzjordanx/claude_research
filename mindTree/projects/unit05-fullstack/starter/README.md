# Unit 5 Starter — Support Desk (React SPA + FastAPI + SQL)

The Unit 4 SPA connected to a real FastAPI backend. Covers JWT login,
`/me` for the role, object-level authorization (requesters only see
their own tickets; only agents change status), CORS, request IDs that
connect browser and server logs, problem+json errors, a contract test,
and Playwright end-to-end tests that start both tiers.

```
browser ─► Vite :5173 ─/api proxy─► FastAPI :8000 ─► SQLite/Postgres
X-Request-ID: 9f2c…        log: [9f2c…] PATCH /tickets/1 -> 200
```

## Your tasks

Everything from Units 2–4 already works. Complete the TODOs that
make the two tiers work together safely (`grep -rn "TODO(" .`):

| # | File | Task |
|---|------|------|
| 1 | `backend/app/services.py` | requesters see only their own rows |
| 2 | `backend/app/services.py` | only agents change status (403) |
| 3 | `backend/app/main.py` | CORS: allow-list, headers, expose ID |
| 4 | `backend/app/main.py` | `GET /me` returns username + role |
| 5 | `backend/app/observability.py` | request-ID middleware + log |
| 6 | `frontend/src/api/client.ts` | send `X-Request-ID` |
| 7 | `frontend/src/api/client.ts` | prefer the server's ID on errors |
| 8 | `frontend/src/auth/AuthContext.tsx` | load role from `/me` |
| 9 | `frontend/src/components/TicketList.tsx` | read-only status |
| 10 | `frontend/e2e/tickets.e2e.ts` | enable the request-ID e2e test |

Done when `pytest -q`, `npm test` and `npm run e2e` are all green.
Order that works well: 1, 2, 4 (backend tests), 5, 3, then 6–10.

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
