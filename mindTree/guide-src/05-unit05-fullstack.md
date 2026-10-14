# Unit 5 — End-to-End Full-Stack Development

## 1. What This Unit Teaches

An FDE is rarely asked to "build an API" or "build a UI" alone. The real job is a working feature that crosses the browser, the network, the API, the database and the identity provider **[JD-Required: full-stack, frontend and backend integration, end-to-end ownership]**. This unit connects Units 2–4 into one product and teaches the seams where full-stack bugs live:

- the full request lifecycle, from a click to a SQL row and back;
- the API contract as the shared source of truth (OpenAPI, generated types, contract tests);
- CORS and when you do not need it at all (same-origin proxy);
- authentication *and* authorization end to end, including object-level rules;
- environment configuration for each tier;
- correlation (request) IDs that link browser errors to backend logs;
- a consistent error contract the UI can render;
- the full-stack testing pyramid, including Playwright end-to-end tests.

## 2. Mental Model

```text
 User clicks "Close ticket"
   │
   ▼
 React component ── onChange ──► useTickets.updateStatus(id, "closed")
   │
   ▼
 API client  adds: Authorization: Bearer <JWT>
                   X-Request-ID: 9f2c…   Content-Type: application/json
   │   (dev: Vite proxy /api → :8000, same origin, no CORS)
   │   (prod: CloudFront/ALB routes /api → service, or CORS)
   ▼
 FastAPI middleware: CORS → RequestId (log context) → route
   │
   ▼
 Dependencies: get_session → current_user (verify JWT) → TicketService
   │
   ▼
 Service rules:  role == agent?  ticket visible to this user?
   │
   ▼
 SQL: UPDATE tickets SET status='closed' WHERE id=1  (in a transaction)
   │
   ▼
 Response 200 TicketOut JSON + X-Request-ID   ─or─ problem+json 4xx/5xx
   │
   ▼
 SPA updates state → re-render.  On error: message + "ref 9f2c…"
```

Three ideas carry the whole unit:

1. **The contract is the product boundary.** The OpenAPI schema is what the frontend, tests, and other teams depend on. Change it on purpose, never by accident.
2. **The server is the only security boundary.** The UI hides buttons for convenience; the API enforces every rule, including *which rows* a user may see.
3. **Every request has an identity.** A request ID created in the browser travels through every log line, so "it failed for me at 10:42" becomes one search.

## 3. Brief Theory

### 3.1 The request lifecycle

**What it is.** The ordered path a user action takes: event handler → state → HTTP request → network (DNS, TLS, proxy, load balancer) → middleware → routing and validation → dependencies (auth, DB session) → business rules → database → serialization → response → UI state.

**Why it exists.** Each layer has one job. When something breaks, knowing the order tells you where to look first: a CORS error never reaches your route; a 422 never reaches your service; a 403 never reaches SQL.

**Why it matters.** Full-stack debugging is binary search over this path. Interviewers ask "walk me through what happens when…" to see whether you can.

**How it works.** In this project: `TicketList` → `useTickets` → `ticketsApi` → `createApiClient` → Vite proxy → `RequestIdMiddleware` → `CORSMiddleware` → FastAPI validation → `current_user` → `TicketService` → SQLAlchemy → `TicketOut`.

### 3.2 The API contract

**What it is.** The agreed shape of requests and responses: paths, methods, fields, types, status codes and error formats. FastAPI generates it as OpenAPI from your Pydantic models (`/openapi.json`).

**Why it exists.** Frontend and backend change at different speeds, often by different people. A written contract lets them work in parallel and detect breaks automatically.

**Why it matters.** Most "the UI is broken" incidents after a deploy are contract drift: a renamed field, a new required field, a changed enum value.

**How it works.**

| Technique | What it catches |
|---|---|
| Generate TS types: `npx openapi-typescript http://…/openapi.json -o src/api/schema.d.ts` **[External]** | Field renames become compile errors |
| Contract test in backend CI (this project: `test_contract_matches_frontend_expectations`) | Removing a field the SPA uses |
| `extra="forbid"` on input models | Clients sending fields the server ignores (e.g. `owner`) |
| Additive change rule: add optional fields, never rename/remove in place | Breaking older clients |
| Versioning (`/v2/…`) or expand-and-contract migration | Unavoidable breaking changes |

Consumer-driven contract testing (Pact **[External]**) formalizes this between many services; for one SPA and one API, a schema test plus generated types is usually enough.

### 3.3 Same-origin, CORS and the dev proxy

**What it is.** Browsers block JavaScript from reading responses from a different *origin* (scheme + host + port) unless the server opts in with CORS headers. `http://localhost:5173` and `http://localhost:8000` are different origins.

**Why it exists.** Without it, any website you visit could call your bank's API with your cookies and read the result.

**Why it matters.** "CORS error" is the most common full-stack integration failure, and it is purely a browser rule: curl and Postman never show it.

**How it works.**

```text
 Cross-origin "non-simple" request (JSON body, Authorization header):

 Browser ── OPTIONS /tickets ───────────────────────────► API
           Origin: http://localhost:5173
           Access-Control-Request-Method: POST
           Access-Control-Request-Headers: authorization,content-type
 Browser ◄── 200 ───────────────────────────────────────── API
           Access-Control-Allow-Origin: http://localhost:5173
           Access-Control-Allow-Headers: Authorization, Content-Type…
 Browser ── POST /tickets (the real request) ───────────► API
```

Rules worth memorizing:

- Allow-list exact origins. `allow_origins=["*"]` cannot be combined with credentials (cookies), and browsers reject it.
- List every custom request header (`Authorization`, `X-Request-ID`) in `allow_headers`.
- Response headers are hidden from JavaScript unless listed in `expose_headers` (that is why this project exposes `X-Request-ID`).
- CORS is not authentication. It protects users' browsers, not your API. Anyone can still call the API with curl.
- **Often you need no CORS at all:** the Vite dev proxy in development, and a single domain in production (CloudFront or an ALB routes `/api/*` to the service and everything else to the static SPA). Same origin removes a whole class of bugs.

FastAPI reference: [CORS](https://fastapi.tiangolo.com/tutorial/cors/) **[Current]**.

### 3.4 Authentication and authorization end to end

**What it is.** *Authentication* proves who the caller is (login, token verification). *Authorization* decides what that caller may do: by role ("only agents change status") and by object ("requesters only see their own tickets").

**Why it exists.** Function-level checks alone are not enough. The OWASP API Security Top 10 lists **Broken Object Level Authorization (BOLA)** as API1 **[External]**: changing `/tickets/41` to `/tickets/42` in the URL is the most common real-world API breach.

**Why it matters.** Every customer system you touch will have multi-tenant or per-user data. Interviewers probe whether you put the check in the right place.

**How it works in this project.**

```text
 login form ─► POST /auth/token (form) ─► verify Argon2 hash ─► JWT
              {sub, role, aud="support-desk-spa", iss, exp}
 SPA keeps token in memory ─► GET /me ─► role used only to adapt UI
 Every call ─► current_user() verifies signature, aud, iss, exp
            ─► TicketService(session, user)
                 _visible(): requester → WHERE owner = :username
                 get(): not visible → 404 (do not reveal existence)
                 update_status(): role != agent → 403
```

Key design decisions:

- **Owner comes from the token, never the body.** The schema rejects an `owner` field (`extra="forbid"`).
- **The filter lives in the query** (`_visible()`), so list, get, and update all inherit it. A check after loading the row is easy to forget on the next endpoint.
- **404 vs 403:** return 404 for objects the user may not know exist; 403 when the user can see the object but not perform the action.
- **Production identity:** an IdP (Cognito, Entra ID, Okta, Auth0) with the OIDC Authorization Code flow + PKCE **[Current]**. The API verifies the IdP's tokens against its JWKS. A backend-for-frontend (BFF) that keeps tokens server-side in an httpOnly cookie is the most secure SPA pattern for sensitive data.

### 3.5 Configuration per environment

**What it is.** The same code runs in dev, test, staging and prod with different settings: API URL, DB URL, allowed origins, secrets, feature flags.

**Why it matters.** Config bugs are the most common "works on my machine" deploy failure.

**How it works.**

| Tier | Mechanism | Gotcha |
|---|---|---|
| Backend | `pydantic-settings`, env vars `APP_*`, `.env` in dev only | Validate at startup: a missing secret should crash the process, not the first request |
| Frontend (Vite) | `VITE_*` variables | Inlined at **build** time. One build per environment, or fetch `/config.json` at runtime to promote the same artifact |
| Secrets | AWS Secrets Manager / SSM, K8s Secrets (Unit 6) | Never in the SPA bundle: everything shipped to the browser is public |

### 3.6 Request IDs and the error contract

**What it is.** A unique ID per request (`X-Request-ID`) that the client sends or the server generates, echoes on the response, attaches to every log line and includes in error bodies.

**Why it matters.** A user's screenshot with "ref 9f2c…" leads straight to the backend log lines and, with tracing (Unit 11), to the slow SQL query. Without it you are guessing from timestamps.

**How it works.**

- The middleware accepts the incoming ID only if it matches a safe pattern (`^[A-Za-z0-9._-]{1,64}$`), which prevents log injection; otherwise it generates one.
- A `ContextVar` holds the ID for the duration of the request, and a logging filter stamps it on every record.
- Errors use RFC 9457 problem details plus `request_id`, so the UI renders `detail` and shows the reference.
- W3C Trace Context (`traceparent`) is the standard for distributed tracing; OpenTelemetry propagates it automatically (Unit 11). A request ID is the simple first step.

### 3.7 The full-stack testing pyramid

| Layer | Tool here | What it proves | Speed |
|---|---|---|---|
| Unit | pytest, Vitest | Pure logic: validation, client behavior | ms |
| API integration | pytest + `TestClient` + in-memory SQLite | Routes, auth, SQL, error format together | ~10 ms/test |
| Component | Testing Library + mock fetch | UI behavior against the contract | ~50 ms/test |
| Contract | OpenAPI schema test | Fields the SPA relies on still exist | ms |
| End to end | Playwright, both tiers running | The real browser, proxy, API and DB work together | seconds |

Keep end-to-end tests few and focused on critical journeys (here: create → authorization → resolve). Push everything else down the pyramid. Playwright's `webServer` option starts the backend and frontend before the tests ([docs](https://playwright.dev/docs/test-webserver) **[Current]**).

### 3.8 Deployment topology (preview of Unit 6)

```text
 Option A — same origin (recommended)
   app.example.com ─► CloudFront ─┬─ /*      → S3 (SPA build)
                                  └─ /api/*  → ALB → FastAPI (ECS/EKS)
 Option B — separate origins
   app.example.com (S3/CloudFront)   api.example.com (ALB → FastAPI)
   → needs CORS allow-list = ["https://app.example.com"]
```

Option A gives no CORS, cookies work simply, and there is one TLS certificate and domain. Option B is fine when the API serves several clients.

## 4. Application in a Real System

A customer wants an internal support desk: employees file tickets, IT agents triage them. The FDE delivers it in a week:

- **Day 1:** confirm roles and the visibility rule ("can employees see each other's tickets?" — no) and write it as an acceptance test before coding.
- **Days 2–3:** API with object-level authorization and integration tests; SPA against the mock in parallel.
- **Day 4:** switch the SPA to the real API via configuration; add the contract test; fix the two integration bugs found (CORS header, a field name).
- **Day 5:** Playwright journey in CI, request IDs in logs, and a demo where the customer's security reviewer tries `/tickets/{someone-else's id}` and gets 404.

## 5. Implementation

### 5.1 Object-level authorization in the query

```python
def _visible(self) -> Select[TicketRow]:
    stmt = select(TicketRow)
    if self._user.role is Role.REQUESTER:
        stmt = stmt.where(TicketRow.owner == self._user.username)
    return stmt

def get(self, ticket_id: int) -> TicketRow:
    row = self._session.scalar(
        self._visible().where(TicketRow.id == ticket_id)
    )
    if row is None:
        # 404, not 403: don't reveal that someone else's ticket exists
        raise NotFoundError(f"Ticket {ticket_id} not found.")
    return row
```

`update_status` calls `get` inside its transaction, so it inherits the rule for free.

### 5.2 CORS that matches the client

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # exact origins per env
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],       # readable by JavaScript
)
```

### 5.3 Request ID: browser to log line

```typescript
// frontend/src/api/client.ts
const requestId = newRequestId();          // crypto.randomUUID()
const headers = new Headers({
  Accept: "application/json",
  "X-Request-ID": requestId,
});
// … on error:
throw new ApiError(
  response.status,
  problem,
  response.headers.get("X-Request-ID") ?? requestId,
);
```

```python
# backend/app/observability.py (inside the middleware)
request_id = incoming if SAFE_ID.match(incoming) else uuid.uuid4().hex
token = request_id_var.set(request_id)
try:
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info("%s %s -> %s", request.method, request.url.path,
             response.status_code)
    return response
finally:
    request_id_var.reset(token)
```

The log line looks like this:

```text
2026-10-14 15:11:26 INFO [d1f30254…] access PATCH /tickets/1 -> 200 in 4.2ms
```

### 5.4 Role from the server, UI adapts

```typescript
const login = async (user: string, password: string) => {
  const token = await api.login(user, password);
  tokenRef.current = token.access_token;
  const me = await api.me();   // server says who we are
  setRole(me.role);
  setUsername(me.username);
};
// TicketList: <select disabled={!canEditStatus} …>
```

Disabling the control is UX. The 403 from the API is the security control, and a test proves it.

### 5.5 A contract test the frontend can rely on

```python
def test_contract_matches_frontend_expectations(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    ticket = set(schemas["TicketOut"]["properties"])
    assert {"id", "title", "description", "priority", "status",
            "created_at"} <= ticket
```

### 5.6 One Playwright journey across both tiers

```typescript
const alice = await browser.newPage();
await signIn(alice, "alice");
await alice.getByLabel("Title").fill(title);
await alice.getByRole("button", { name: "Create ticket" }).click();

const bob = await browser.newPage();          // separate session
await signIn(bob, "bob");
await expect(bob.getByText(title)).toHaveCount(0);   // BOLA check

const agent = await browser.newPage();
await signIn(agent, "agent");
const row = agent.getByRole("row").filter({ hasText: title });
await row.getByRole("combobox").selectOption("closed");
```

**Note on React StrictMode.** In development, React mounts effects twice to surface missing cleanups, so you will see two `GET /tickets` in the backend log on page load. That is expected in dev only, and the `AbortController` cleanup from Unit 4 handles it.

## 6. How It Connects to the Rest of the System

```text
 Unit 5 full-stack slice
   ├─ uses: Python patterns (U1), FastAPI auth/errors (U2),
   │        SQL + transactions (U3), SPA client/state (U4)
   ├─ packaged as 2 artifacts: API container + static SPA (U6)
   ├─ CI runs pytest, vitest, contract and e2e tests (U7)
   ├─ the API becomes one service among many; IDs propagate (U8)
   ├─ AI features plug in behind the same API + auth (U9-U10)
   ├─ request IDs grow into traces, metrics, dashboards (U11)
   └─ the demo + acceptance tests are FDE deliverables (U12)
```

## Cross-Unit System Map — Units 1–5

```text
                    ┌──────────────────────── Browser ───────────────┐
                    │ React SPA (U4/U5)                              │
                    │  components → hooks → API client               │
                    │  token in memory · X-Request-ID · problem UI   │
                    └───────────────┬────────────────────────────────┘
                                    │ HTTPS  JSON  Bearer JWT
                    ┌───────────────▼────────────────────────────────┐
                    │ FastAPI (U2/U5)                                │
                    │  CORS → RequestId → validation (Pydantic)      │
                    │  Depends: session, current_user, service       │
                    │  errors → RFC 9457 problem+json                │
                    ├────────────────────────────────────────────────┤
                    │ Service layer (U1 patterns: typed, testable)   │
                    │  roles · object-level authz · transactions     │
                    │  async fan-out with timeouts + retries (U1)    │
                    ├───────────────┬───────────────┬────────────────┤
                    │ SQLAlchemy    │ Cache (U3)    │ External APIs  │
                    │ Postgres (U3) │ Redis aside   │ (U1 retry)     │
                    └───────────────┴───────────────┴────────────────┘
  Tests: pytest unit/integration · Vitest/RTL · contract · Playwright
  Deterministic everywhere so far: same input → same output.
  (Units 9-10 add probabilistic components behind this same boundary.)
```

**How to use this map in an interview.** When asked "design a small internal tool", draw these boxes in this order, then say where authentication, authorization, validation, transactions, and logging live. That alone shows end-to-end ownership.

## FDE Scenario 4 — "Our security team found that users can see other people's tickets"

**Stakeholder (customer CISO, urgent):** "During a review, one of our people changed the number in the URL and saw another employee's HR ticket. We need this fixed today and we need to know who was affected."

- *Stay calm and scope:* acknowledge, confirm the exact reproduction (URL, user, time), and agree on a communication cadence (updates every 2 hours).
- *Investigate:*
  - reproduce with two test users;
  - read the endpoint: does `GET /tickets/{id}` filter by owner, or just by ID?
  - check every endpoint that takes an ID (GET, PATCH, attachments, exports): BOLA is rarely in just one place.
- *Contain:* ship the minimal fix first: the owner filter in a shared query function, 404 for non-owners, plus tests for each endpoint. Deploy it behind the normal pipeline, not by hand.
- *Assess impact:* use request IDs and access logs to find requests where `user != ticket.owner` for the affected endpoints. Give the customer a factual list, not a guess.
- *What must be deterministic:* authorization. Never "the UI hides it."
- *Prevent:* an authorization test matrix (role × endpoint × own/other's object) in CI; code review checklist item; consider row-level security in Postgres as defense in depth.
- *Communicate:* a short written incident summary: what happened, impact, fix, verification, and prevention. Separate facts from hypotheses.

## Comprehension Questions

1. List, in order, the layers a "close ticket" click passes through before a row changes in the database.
2. Why does a CORS error appear in the browser but never in curl?
3. What does `expose_headers` do, and why does this project need it?
4. Why must the ticket owner come from the token rather than the request body?
5. Why put the visibility filter inside the query instead of checking after loading the row?
6. When do you return 404 instead of 403?
7. Why are `VITE_*` variables a problem for "build once, deploy everywhere"?
8. What does a request ID give you that timestamps alone do not?

## Comprehension Answers

1. Component event → state/hook → API client (headers) → network/proxy → middleware (request ID, CORS) → validation → dependencies (session, JWT verification) → service rules (role, visibility) → SQL transaction → serialization → response → UI state.
2. CORS is enforced by browsers to protect users. curl is not a browser, so it ignores CORS and simply shows the response.
3. Browsers only let JavaScript read a few "safe" response headers. `expose_headers` adds others; the SPA needs to read `X-Request-ID` to show it on errors.
4. The body is controlled by the client, so anyone could file tickets as someone else. The token is signed by the server and identifies the caller.
5. Every code path that uses the query (list, get, update, export) inherits the rule automatically. A post-load check must be remembered in each endpoint, and forgetting one is a data leak.
6. When the user is not allowed to know the object exists (another user's ticket). Use 403 when they can see it but may not perform the action.
7. Vite inlines them at build time, so each environment needs its own build. Use runtime config (`/config.json`) or a same-origin `/api` path to promote one artifact.
8. An exact join key across browser, proxy, API logs and traces, even with concurrent requests and clock skew.

## Interview Questions — Theory-Based

**Q1. Walk me through what happens when a user submits a form in your SPA until the data is saved.**

- *Strong answer:* walk the lifecycle from §3.1 and name a failure mode at each step: client validation, the request with auth and request-ID headers, DNS/TLS/proxy, the CORS preflight if cross-origin, middleware, Pydantic validation (422), the JWT dependency (401), role and object checks (403/404), the transaction (409 on conflict), serialization, then UI state update or a problem+json message.
- *What it tests:* end-to-end understanding and debugging instinct.
- *Follow-up:* "Where would you look first if it takes 5 seconds?" (Browser Network timing to split client vs server time, then server logs and traces by request ID, then SQL.)

**Q2. What is CORS and how do you configure it correctly?**

- *Strong answer:* a browser rule that blocks reading cross-origin responses unless the server opts in. Preflight `OPTIONS` for non-simple requests. Configure exact origins per environment, the headers you send, `expose_headers` for those you read, never `*` with credentials. Prefer same origin via a proxy or CDN routing. CORS is not authentication.
- *Follow-up:* "Postman works but the browser fails — why?" (Postman ignores CORS.)

**Q3. What is BOLA/IDOR and how do you prevent it?**

- *Strong answer:* Broken Object Level Authorization: the API checks that you are logged in but not that the object belongs to you. Prevent it by scoping queries by owner or tenant in one shared place, deriving ownership from the token, returning 404 for invisible objects, testing a role × object matrix, and optionally Postgres row-level security as defense in depth.
- *What it tests:* security awareness for customer data.

**Q4. How do you keep frontend and backend in sync?**

- *Strong answer:* OpenAPI as the contract, generated TypeScript types, a contract test in CI, additive-only changes with expand-and-contract for breaking ones, and versioning when clients cannot upgrade together.

**Q5. Where should a SPA keep its access token?**

- *Strong answer:* in memory for most SPAs (lost on refresh, mitigated by a silent refresh via the IdP). Not `localStorage` for sensitive apps (XSS-readable). The strongest pattern is a BFF: the server holds tokens and gives the browser an httpOnly, Secure, SameSite cookie, with CSRF protection.

**Q6. How do you design end-to-end tests that are not flaky?**

- *Strong answer:* few tests on critical journeys; fresh data per run (in-memory DB or unique names); role and label locators instead of CSS selectors; Playwright auto-waiting and web-first assertions instead of sleeps; traces on failure; no dependence on test order.

**Q7. How do you configure the same app for several environments?**

- *Strong answer:* env vars validated at startup for the backend; secrets from a secret manager; for the SPA, either a build per environment or runtime config; and a same-origin `/api` path so the frontend needs almost no config.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a feature you delivered end to end.**

- *Cover:* the user need, the contract you defined, backend and frontend pieces, auth, testing layers, deployment, and one integration problem you hit.
- *Structure:* situation → contract and design → build → integration issue → verification → result.
- *Personalize:* "`<<personalize: feature, users>>`. I defined the API contract first, `<<backend stack>>` with `<<authz approach>>`, and `<<frontend>>`. The hardest part was `<<integration issue>>`. Result: `<<metric>>`."
- *Lab-honest version:* "In a project I built a support desk with a React SPA and FastAPI: JWT login, per-user visibility enforced in SQL, request IDs from browser to logs, and a Playwright journey that runs both tiers."
- *Follow-ups:* "How did you test authorization?" "What broke when you connected the two tiers?"

**A2. Describe a time you debugged an issue that spanned frontend and backend.**

- *Cover:* the symptom, how you split the problem (Network tab, request IDs, logs), root cause, fix, regression test.

**A3. How have you handled authentication and authorization in a full-stack app?**

- *Cover:* IdP or local, token flow, where tokens live, how the API verifies them, role and object rules, and tests for both.

**A4. How do you work when frontend and backend are built by different people or teams?**

- *Cover:* contract first, mock server, generated types, contract tests, versioning, a shared Slack channel and changelog.

**A5. Tell me about a time a deploy broke the UI.**

- *Honest framing if you have none:* "I haven't caused one in production, but here is how I prevent it: contract tests, additive changes, a smoke test after deploy, and the ability to roll back the frontend artifact independently."

## Troubleshooting Scenarios

**T1. The browser console shows a CORS error on POST, but GET works.**

```text
SYMPTOM     GET ok; POST blocked "No 'Access-Control-Allow-Origin'"
CHECK       DevTools: is there an OPTIONS preflight? its status/headers?
            backend allow_methods / allow_headers include POST,
            Content-Type, Authorization?
CAUSES      preflight rejected (header not allowed); exception before
            CORS middleware adds headers; origin not in allow-list
CONFIRM     curl -i -X OPTIONS -H "Origin: …" -H
            "Access-Control-Request-Method: POST" …
FIX         allow the method/header; correct origin per environment;
            or route through same-origin proxy
PREVENTION  test_cors_preflight_allows_spa_origin in CI
```

**T2. Users see an error but support cannot find it in the logs.**

```text
SYMPTOM     screenshot "Something went wrong", no matching log line
CHECK       does the UI show a request ID? does the API echo it?
            do log lines contain it? is the request reaching the API
            at all (load balancer logs)?
CAUSES      no correlation ID; error happened in the proxy/LB; logs
            sampled or at the wrong level
FIX         X-Request-ID end to end; show "ref <id>" in error UI;
            include request_id in problem+json
PREVENTION  test that error bodies carry request_id
```

**T3. One user sees another user's data.**

```text
SYMPTOM     data from another account visible
CHECK       endpoint query: filtered by owner/tenant? ID from URL
            trusted? caching keyed without user? (CDN, Redis)
CAUSES      missing object-level authz; cache key lacks user/tenant;
            frontend state not cleared on logout
CONFIRM     two test users, same ID; check cache keys
FIX         scope queries centrally; 404 for invisible objects;
            per-user cache keys; Cache-Control: private
PREVENTION  authz test matrix; security review checklist
```

**T4. The UI breaks after a backend deploy: fields show "undefined".**

```text
CHECK       Network response vs TS types; recent API diff
CAUSES      renamed/removed field; enum value changed
FIX         restore field (expand-and-contract); regenerate types
PREVENTION  contract test + generated types fail CI first
```

**T5. Login works locally but fails in staging with 401 on every call.**

```text
CHECK       token aud/iss vs API config in staging; clock skew;
            proxy stripping Authorization header; different secret
            per replica
FIX         align APP_JWT_AUDIENCE/ISSUER; share secret/JWKS; forward
            Authorization at the proxy
```

**T6. The Playwright test passes locally but fails in CI.**

```text
CHECK       trace viewer (trace: retain-on-failure); webServer logs;
            leftover state from a previous test; timing assumptions
CAUSES      shared DB between runs; hard-coded waits; port already used
FIX         fresh DB per run; web-first assertions; reuseExistingServer
            false in CI; unique test data
```

## Unit Practice Project — Support Desk (Full Stack)

### Project Goal

Connect the Unit 4 SPA to a real FastAPI + SQL backend and make the integration production-shaped:

- employees (requesters) file tickets and see only their own;
- agents see all tickets and change status;
- request IDs connect browser errors to backend logs;
- a contract test and Playwright end-to-end tests protect the integration.

### Architecture

```text
 frontend/ (Vite :5173)                    backend/ (uvicorn :8000)
  AuthProvider ─ login → /auth/token        main.py create_app()
              └ /me → role                   ├ CORSMiddleware
  useTickets → ticketsApi → client           ├ RequestIdMiddleware
     X-Request-ID, Bearer ──/api proxy──►    ├ /auth/token  /me
  TicketList (status disabled unless agent)  ├ /tickets GET POST
                                             └ /tickets/{id} GET PATCH
  e2e/ Playwright starts both servers        services.TicketService
                                              └ _visible(): owner filter
                                             db.py SQLAlchemy (SQLite/PG)
```

### Requirements

1. `POST /auth/token` returns a JWT with `sub`, `role`, `aud`, `iss`, `exp`. `GET /me` returns username and role.
2. `GET /tickets?status=&limit=&offset=` lists visible tickets, newest first, with `total`.
3. `POST /tickets` creates a ticket owned by the caller. A body containing `owner` is rejected (422).
4. Requesters only see their own tickets. Another user's ticket returns **404**.
5. Only agents can `PATCH /tickets/{id}`; requesters get **403**.
6. Every response has `X-Request-ID`. A well-formed client ID is echoed; a malformed one is replaced. Error bodies include `request_id`.
7. CORS allows only configured origins and exposes `X-Request-ID`.
8. The SPA sends a request ID on every call, shows "ref …" on action errors, loads the role from `/me`, and disables status changes for requesters.
9. A contract test fails if `TicketOut` or `TicketCreate` change in a way the SPA depends on.
10. Playwright covers: requester creates → other requester cannot see → agent closes → requester sees the closed ticket; plus a request-ID round trip.

### Technical Requirements

- Backend: Python 3.12+, FastAPI, SQLAlchemy 2.1, PyJWT, pwdlib (Argon2), pydantic-settings; SQLite by default, Postgres-ready.
- Frontend: Node 22.12+, React 19, Vite 8, TypeScript strict, Vitest.
- E2E: `@playwright/test` with `webServer` for both tiers.

### Project Structure

{{tree projects/unit05-fullstack/solution}}

### Step-by-Step Implementation

1. **Run both tiers from the starter.** Backend: `uvicorn app.main:create_app --factory --reload`. Frontend: `npm run dev`. Sign in as alice.
   - *Why:* see the baseline: everything "works", but alice can see bob's tickets and change status.
2. **TODO 1–2: authorization in `TicketService`.**
   - *Test:* `pytest -q tests/test_tickets_api.py`.
3. **TODO 4: `GET /me`.**
   - *Test:* `pytest -q -k me`.
4. **TODO 5: request-ID middleware.**
   - *Test:* `pytest -q tests/test_cross_cutting.py -k request_id`; watch the uvicorn log show `[<id>]`.
5. **TODO 3: CORS.** Set `VITE_API_BASE_URL=http://127.0.0.1:8000` to call cross-origin and watch the preflight in DevTools.
   - *Test:* `pytest -q -k cors`.
6. **TODO 6–7: send and surface the request ID in the client.**
   - *Test:* `npx vitest run src/api/client.test.ts`.
7. **TODO 8–9: role from `/me`, read-only status for requesters.**
   - *Test:* `npm test`.
8. **TODO 10: end to end.** Remove `.fixme`, run `npm run e2e`.
9. **Finish:** `pytest -q && ruff check . && mypy`, then `npm test && npm run typecheck`.

### Starter Code

{{file projects/unit05-fullstack/starter/backend/app/services.py}}

{{file projects/unit05-fullstack/starter/backend/app/observability.py}}

The starter also has TODOs in `backend/app/main.py` (CORS, `/me`), `frontend/src/api/client.ts` (send and surface the request ID), `frontend/src/auth/AuthContext.tsx` (`/me`), `frontend/src/components/TicketList.tsx` (read-only status) and `frontend/e2e/tickets.e2e.ts`. The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** both roles, create, filter, close.
2. **Validation:** short title, `owner` in the body, unknown status value, `limit=1000`.
3. **Errors:**
   - expired or tampered token → 401 and back to login;
   - backend stopped → "Network error" in the UI;
   - a 403 shows a message with "ref …".
4. **Security edge cases:**
   - requester guesses IDs with GET and PATCH;
   - forged `X-Request-ID` containing a newline;
   - an origin not in the allow-list.
5. **Extend:**
   - add `GET /tickets/{id}` detail page in the SPA;
   - make agents' updates record `updated_by` from the token;
   - generate TS types with `openapi-typescript` and replace `types.ts`.

### Hints

1. In `_visible()`, return a `Select` and let callers add `.where(...)`, `.order_by(...)` and so on.
2. `get()` already raises `NotFoundError` when the row is missing; with the filter, "not yours" becomes "missing" automatically.
3. For the middleware, set the `ContextVar` before `call_next` and reset it in `finally`; log *before* the reset so the filter sees the ID.
4. Starlette adds CORS headers only to responses that pass through `CORSMiddleware`; register it with `add_middleware`, and check it with an `OPTIONS` request in a test.
5. In the client, the server's `X-Request-ID` header is authoritative if the server replaced yours.
6. In Playwright, `browser.newPage()` creates an isolated context per user, so three users can be signed in at once.

### Expected Behavior

```text
alice: POST /tickets {"title":"Printer jam"}  → 201 owner=alice
alice: POST /tickets {"title":"x","owner":"bob"} → 422
bob:   GET /tickets/1                        → 404 problem+json
alice: PATCH /tickets/1 {"status":"closed"}  → 403 "Only agents…"
agent: PATCH /tickets/1 {"status":"closed"}  → 200 status=closed
GET /health  X-Request-ID: abc-123           → X-Request-ID: abc-123
GET /health  X-Request-ID: "bad\nid"         → new 32-hex ID
OPTIONS /tickets Origin: https://evil.example → no ACAO header
SPA alice: status dropdown disabled; agent: enabled
```

### Testing Requirements

- **Backend integration (13):** owner from token, visibility and 404, agent-only PATCH, status filter, validation problem details, `/me`, 401, request-ID echo/replace/in-error, CORS allowed/rejected, contract.
- **Frontend (17):** Unit 4 tests plus request-ID client test and requester read-only view.
- **E2E (2):** the multi-user journey and the request-ID round trip.

```bash
cd backend && pytest -q && ruff check . && mypy
cd frontend && npm test && npm run typecheck
cd frontend && PYTHON=../backend/.venv/bin/python npm run e2e
```

### Final Runnable Solution

{{files projects/unit05-fullstack/solution}}

### How to Run

```bash
# terminal 1
cd projects/unit05-fullstack/solution/backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
uvicorn app.main:create_app --factory --reload

# terminal 2
cd projects/unit05-fullstack/solution/frontend
npm install && cp .env.example .env
npm run dev            # http://localhost:5173

# end to end (stops your dev servers first, or reuses them)
npx playwright install chromium
PYTHON=../backend/.venv/bin/python npm run e2e
```

### Verify the Solution

1. Backend: **13 passed**, ruff and mypy clean.
2. Frontend: **17 passed**, typecheck clean.
3. E2E: **2 passed**.
4. Manual: alice creates a ticket (dropdown disabled); bob does not see it; the agent closes it; alice filters "Closed" and sees it.
5. Copy an `X-Request-ID` from DevTools and find it in the uvicorn log.
6. With bob's token, `curl` alice's ticket ID: **404**.

### Project Interview Debrief

1. **Why 404 instead of 403 for other users' tickets?**
   A 403 confirms the ticket exists, which leaks information (ticket IDs, volume, sometimes titles via other endpoints). 404 treats "not yours" as "not there". Agents get 403 for actions they can see but not perform.
2. **Why is the role fetched from `/me` instead of decoded from the JWT in the browser?**
   The server is the authority; decoding works but couples the SPA to the token format (which changes when you move to an IdP). Either way the UI only adapts; the API enforces.
3. **How do you know the tiers stay compatible?**
   The contract test in backend CI, generated or mirrored TS types with strict compilation, and one Playwright journey running the real servers.
4. **Why does the dev setup use a proxy instead of CORS?**
   Same origin removes preflights and cookie complexity, and mirrors the recommended production topology (CloudFront routing `/api`). CORS is still configured and tested for deployments that need separate origins.
5. **What would you add for production?**
   OIDC with an IdP and JWKS verification, Alembic migrations, Postgres with row-level security as defense in depth, rate limiting on login, OpenTelemetry traces, containerized deploy with health checks (Unit 6) and CI running all three test layers (Unit 7).
