# Unit 4 Project (STARTER) — Support Tickets SPA (React + TypeScript)

Typed API client (auth header, timeout, problem+json errors, 401
handling), in-memory auth state, protected routes, loading/error
states, a validated controlled form, filtering and status updates.
Runs standalone against a built-in mock backend that speaks the same
HTTP contract as the Unit 5 FastAPI service.

## Run

```bash
npm install
cp .env.example .env       # VITE_USE_MOCK=true by default
npm run dev                # http://localhost:5173  (agent / agent-password)
npm test                   # Vitest + Testing Library
npm run typecheck && npm run build
```

Requires Node.js 22.12+ (or 24 LTS).

## Your tasks (STARTER)

Implement the TODOs in `src/api/client.ts`, `src/hooks/useTickets.ts`,
`src/components/TicketForm.tsx`, `src/auth/ProtectedRoute.tsx` and
`src/auth/AuthContext.tsx`. The tests in `src/**/*.test.ts(x)` are
the specification: `npm test` until all pass.
