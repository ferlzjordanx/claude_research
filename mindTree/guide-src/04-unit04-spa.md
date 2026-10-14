# Unit 4 — JavaScript, TypeScript and SPA Development

## 1. What This Unit Teaches

A full-stack FDE must be able to build or fix the user-facing part of a solution and integrate it with the backend **[JD-Required: JavaScript, TypeScript, SPA, React, Angular]**. This unit teaches what you need for that, not every framework feature:

- modern JavaScript, the browser event loop, promises and async/await, and modules;
- TypeScript types for API models;
- SPA architecture: components, state, events, forms and routing;
- a robust API client with loading and error states;
- authentication state;
- React in depth and Angular through side-by-side equivalents, so the concepts transfer.

## 2. Mental Model

```text
 Browser
   │  loads index.html + JS bundle once
   ▼
 SPA (router decides which page component to show — no full reload)
   ▼
 Component tree   (UI = f(state))
   │  user event (click, submit, select)
   ▼
 State update  ──► re-render affected components
   │  needs data?
   ▼
 API client      (base URL, auth header, timeout, error parsing)
   ▼
 Backend API     (FastAPI — Units 2/5)
   ▼
 Response  ──► state: loading → ready | error  ──► UI update
```

The core idea is that **UI = f(state)**:

- You never manipulate the DOM by hand. You change state, and the framework re-renders.
- Every remote call moves through explicit states: *loading → ready* or *loading → error*.
- The API client is the single place that knows URLs, tokens and error formats.

## 3. Brief Theory

### 3.1 Modern JavaScript

**What it is.** JavaScript (ECMAScript, a yearly standard) is the language of the browser and of Node.js.

| Feature | Example | Why it matters |
|---|---|---|
| `const` / `let` | `const api = …` | Block scope; `const` prevents rebinding (not mutation) |
| Arrow functions | `(t) => t.id` | Concise; lexical `this` |
| Destructuring / spread | `const { id, ...rest } = t; [...items, x]` | Immutable updates for state |
| Template literals | `` `/tickets/${id}` `` | String building |
| Optional chaining / nullish | `user?.name ?? "anon"` | Safe access to possibly missing data |
| ES modules | `import { x } from "./y"` | Explicit dependencies, tree-shaking |
| Closures | A function remembers the variables in its scope | Callbacks, hooks |

**Equality.** Always use `===`. `==` performs type coercion.

**The browser event loop.** JavaScript runs on one thread with a call stack, a task (macrotask) queue for timers and I/O, and a microtask queue for promise callbacks, which drains before the next task. This is the same cooperative model as Python's asyncio: long synchronous work freezes the UI, and `await` yields.

### 3.2 Promises and async/await

**What it is.** A `Promise` represents a future value: it is pending, then fulfilled or rejected. `async` functions return promises, and `await` pauses the function until the promise settles, without blocking the thread.

```ts
async function loadTicket(id: number): Promise<Ticket> {
  const res = await fetch(`/api/tickets/${id}`);
  // fetch does NOT throw on 4xx/5xx: check res.ok yourself
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as Ticket;
}

// Run in parallel, fail fast:
const [a, b] = await Promise.all([loadTicket(1), loadTicket(2)]);
// Keep partial results:
const results = await Promise.allSettled([loadTicket(1), loadTicket(99)]);
```

**Pitfalls:**

- **`fetch` only rejects on network failure.** You must check `res.ok`.
- **Unhandled rejections** go unnoticed.
- **Forgotten cancellation** lets stale responses overwrite newer ones. Use `AbortController`.

### 3.3 TypeScript

**What it is.** A typed superset of JavaScript that compiles to JavaScript. Types are erased at runtime. **[Current: TypeScript 7.0 ships the new native (Go-based) compiler, which is about 10× faster; language semantics are unchanged for this guide's code.]**

**Why it matters.** API responses, props and state get compile-time checking, so a renamed backend field breaks the build instead of production.

**Key concepts:**

- **Structural typing.** Shape matters, not names, like Python Protocols.
- **`interface` vs `type`.** Both describe object shapes. `type` can also express unions and other compositions.
- **Union and literal types.** `type Priority = "low" | "medium" | "high"`.
- **Discriminated unions.** Model mutually exclusive states:

  ```ts
  type LoadState =
    | { kind: "loading" }
    | { kind: "error"; message: string }
    | { kind: "ready"; tickets: Ticket[] };
  // switch(state.kind) narrows the type in each branch
  ```

- **Generics.** `request<T>(path): Promise<T>`.
- **`unknown` over `any`.** `unknown` forces you to narrow before use.
- **Strict mode** (`"strict": true`, plus `noUncheckedIndexedAccess`) catches null bugs.
- **A type assertion (`as T`) is a promise you make, not a check.** Data from the network is still unverified at runtime. Validate untrusted input with a schema library (Zod or Valibot) when correctness matters.

### 3.4 API models

Mirror the backend contract in TypeScript types (`Ticket`, `TicketCreate`, `Problem`). Generate them from the FastAPI OpenAPI spec with tools such as `openapi-typescript` or `orval`, so the frontend and backend cannot drift. Keep wire formats explicit: dates arrive as ISO strings and money as strings, not floats.

### 3.5 SPA architecture

**What it is.** A Single-Page Application loads one HTML page and a JavaScript bundle, then renders views and handles navigation in the browser, fetching data as JSON.

| Rendering model | How | When |
|---|---|---|
| CSR (classic SPA) | The browser builds the UI from JSON | Internal tools, dashboards, authenticated apps (typical FDE work) |
| SSR / SSG (Next.js, Angular SSR) | The server sends HTML, then hydrates it | SEO, fast first paint for public sites |

**Building blocks:**

- **Components** are reusable UI functions or classes that receive *props* (inputs) and emit events (outputs).
- **State:** local (`useState`/signals), shared (context or services), server state (data from APIs, with caching), URL state (route and query params).
- **Events** are user actions that update state.
- **Forms** may be *controlled* (state is the source of truth) or *uncontrolled* (the DOM holds the value). Validate on the client for UX and on the server for correctness.
- **Routing** maps the URL to components, with guards for auth and parameters (`/tickets/:id`).
- **API integration** goes through one client module. Libraries such as TanStack Query (React) or Angular's `httpResource` add caching, retries and deduplication.

### 3.6 Loading and error states

Every async view needs:

- a **loading** indicator;
- an **error** message with a retry;
- an **empty** state;
- the **data**.

Ignore responses from cancelled or stale requests. Map server field errors (422 problem details) onto form fields. Show a generic message for 5xx responses, and log the details.

### 3.7 Authentication state in a SPA

| Token storage | XSS risk | CSRF risk | Notes |
|---|---|---|---|
| `localStorage` | **High** (any injected script can read it) | None | Common but discouraged |
| Memory (JS variable) | Lower (not persistent) | None | Lost on refresh; pair with refresh |
| httpOnly, Secure, SameSite cookie | Script can't read it | Needs SameSite or CSRF tokens | Best for browser sessions |
| Backend-for-Frontend (BFF) | Tokens never reach the browser | Cookie-based | Most secure pattern for SPAs |

On a **401**, clear the auth state and redirect to login (or refresh the token). On a **403**, show "not allowed". Client-side route guards are UX only: **the API must enforce authorization**.

### 3.8 React

**What it is.** A library for building UIs from components written as functions returning JSX. **[Current: React 19.x; class components are legacy.]**

**How it works:**

- Calling `setState` schedules a re-render. React re-runs the component function, diffs the virtual tree and updates the real DOM minimally.
- **Hooks:**
  - `useState` — local state;
  - `useEffect` — synchronize with external systems such as fetching, *with cleanup*;
  - `useContext` — shared state;
  - `useMemo` / `useCallback` — memoize values and functions;
  - `useRef` — mutable values that don't trigger renders.
- **Rules of hooks:** call them at the top level of components or custom hooks, never conditionally.
- **Keys** in lists let React track items across renders.
- **StrictMode** (development) runs effects twice to expose missing cleanup.
- React 19 adds **Actions**, `useActionState` and `useOptimistic` for form submissions and optimistic UI.

### 3.9 Angular

**What it is.** A full framework (from Google) with components, dependency injection, routing, forms, HTTP and testing built in. It uses TypeScript throughout. **[Current: Angular 22. Standalone components are the default (NgModules are legacy but encountered). Signals are the reactive primitive. Zoneless change detection is the default for new apps since v21. The `@if` / `@for` control flow replaces `*ngIf` / `*ngFor`.]**

**How it works:**

- Components are classes with a template.
- **Services** (classes marked `@Injectable({providedIn: 'root'})`) hold shared logic and are injected with `inject()`.
- `HttpClient` returns RxJS Observables. **Interceptors** add cross-cutting HTTP behavior (auth headers, error handling).
- **Signals** (`signal`, `computed`, `effect`) drive fine-grained change detection.
- **Reactive forms** (`FormGroup`, `Validators`) give typed, testable forms.
- **Route guards** (`CanActivateFn`) protect navigation.

### 3.10 React vs Angular — transferable concepts

| Concept | React | Angular | Transferable idea |
|---|---|---|---|
| Component | Function returning JSX | Class with template (`@Component`) | UI = f(inputs, state) |
| Inputs/outputs | Props, callback props | `input()`, `output()` | One-way data flow, events up |
| Local state | `useState` | `signal()` | State change → re-render |
| Derived state | Compute in render / `useMemo` | `computed()` | Don't store what you can derive |
| Side effects | `useEffect` + cleanup | `effect()`, RxJS `takeUntilDestroyed` | Sync with external systems; clean up |
| Shared state / DI | Context, custom hooks | Services + `inject()` | Inject dependencies, don't import globals |
| HTTP | `fetch` + your client / TanStack Query | `HttpClient` + interceptors / `httpResource` | One API layer; cross-cutting in one place |
| Forms | Controlled inputs / libraries (React Hook Form) | Reactive forms | Validation and state in code |
| Routing | React Router | `@angular/router` | URL → component, guards |
| Opinionation | Library; you choose the pieces | Batteries included | Consistency vs flexibility |
| Typical fit | Product teams, fast iteration | Large enterprise apps, strict structure | Choose by team and existing codebase |

**FDE stance:** use whatever framework the customer already runs. The concepts transfer; the syntax is a few days' work.

## 4. Application in a Real System

```text
 CloudFront (CDN) ── serves index.html + hashed JS/CSS from S3
      │  browser runs SPA
      ▼
 SPA ── fetch /api/... with Bearer token ──► ALB/API Gateway ─► FastAPI
      ▲                                                       │
      └──────────── JSON / problem+json ◄─────────────────────┘
 Identity: Cognito/Entra hosted login (OIDC, Authorization Code + PKCE)
```

| Choice | Why | Without it | Alternatives |
|---|---|---|---|
| TypeScript | Contract safety, refactoring | Runtime "undefined is not a function" | JS + JSDoc types |
| Central API client | One place for auth, timeouts, errors | Duplicated, inconsistent fetch code | Axios, Angular HttpClient, generated clients |
| Discriminated-union load state | No impossible states | Spinners stuck forever, stale errors | Data libraries (TanStack Query) |
| Vite | Fast dev server, simple build | Slow builds | Angular CLI (esbuild-based), Next.js |
| Static hosting (S3 + CloudFront) | Cheap, global, scalable | Server needed just for HTML | Amplify Hosting, Vercel, Nginx container |

## 5. Implementation

### 5.1 The API client: one place for cross-cutting concerns

```ts
export class ApiError extends Error {
  constructor(readonly status: number, readonly problem: Problem) {
    super(problem.detail ?? problem.title);
  }
}

async function request<T>(path: string, o: RequestOptions = {}) {
  const headers = new Headers({ Accept: "application/json" });
  const token = opts.getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const controller = new AbortController();               // timeout +
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  o.signal?.addEventListener("abort", () => controller.abort());
  try {
    const res = await fetchImpl(`${opts.baseUrl}${path}`, {
      method: o.method ?? "GET", headers, signal: controller.signal });
    if (res.status === 401) opts.onUnauthorized?.();      // → login
    if (!res.ok) throw new ApiError(res.status, await res.json());
    return res.status === 204 ? (undefined as T) : await res.json();
  } finally {
    clearTimeout(timer);
  }
}
```

The full version also handles network errors and non-JSON error bodies.

### 5.2 Fetching with cancellation and explicit states (React)

```ts
useEffect(() => {
  const controller = new AbortController();
  setState({ kind: "loading" });
  api.list(filter, controller.signal)
    .then((page) => setState({ kind: "ready", tickets: page.items }))
    .catch((err) => {
      if (!controller.signal.aborted)
        setState({ kind: "error", message: String(err.message) });
    });
  return () => controller.abort();   // filter changed / unmounted
}, [api, filter]);
```

### 5.3 Rendering by state

```tsx
{state.kind === "loading" && <p aria-busy="true">Loading…</p>}
{state.kind === "error" && (
  <div role="alert">
    {state.message} <button onClick={reload}>Retry</button>
  </div>)}
{state.kind === "ready" && <TicketList tickets={state.tickets} />}
```

### 5.4 Auth state with the token in memory

```tsx
const tokenRef = useRef<string | null>(null);   // not localStorage
const api = useMemo(() => ticketsApi(createApiClient({
  baseUrl, getToken: () => tokenRef.current, onUnauthorized: logout,
})), [baseUrl, logout]);
```

### 5.5 A protected route (UX only)

```tsx
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  if (!isAuthenticated)
    return <Navigate to="/login" replace
                     state={{ from: location.pathname }} />;
  return <>{children}</>;
}
```

### 5.6 The same features in Angular

A service with `HttpClient`:

```ts
@Injectable({ providedIn: "root" })
export class TicketsService {
  private http = inject(HttpClient);
  list(status?: TicketStatus) {
    const params = status ? { status } : undefined;
    return this.http.get<TicketPage>("/api/tickets", { params });
  }
  create(data: TicketCreate) {
    return this.http.post<Ticket>("/api/tickets", data);
  }
}
```

A functional interceptor (auth header plus 401 handling):

```ts
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.token();                       // a signal
  const authed = token
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;
  return next(authed).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401) auth.logout();
      return throwError(() => err);
    }),
  );
};
// app.config.ts
// providers: [provideHttpClient(withInterceptors([authInterceptor]))]
```

A component with signals and the modern control flow:

```ts
@Component({
  selector: "app-tickets",
  template: `
    @if (loading()) { <p>Loading…</p> }
    @else if (error()) { <p role="alert">{{ error() }}</p> }
    @else {
      @for (t of tickets(); track t.id) { <li>{{ t.title }}</li> }
      @empty { <p>No tickets.</p> }
    }`,
})
export class TicketsComponent {
  private api = inject(TicketsService);
  tickets = signal<Ticket[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  constructor() {
    this.api.list().pipe(takeUntilDestroyed()).subscribe({
      next: (p) => { this.tickets.set(p.items); this.loading.set(false); },
      error: (e) => { this.error.set(e.message); this.loading.set(false); },
    });
  }
}
```

A route guard and a reactive form:

```ts
export const authGuard: CanActivateFn = () =>
  inject(AuthService).isAuthenticated()
    ? true
    : inject(Router).createUrlTree(["/login"]);

form = new FormGroup({
  title: new FormControl("", { nonNullable: true,
    validators: [Validators.required, Validators.minLength(3),
                 Validators.maxLength(120)] }),
  priority: new FormControl<Priority>("medium", { nonNullable: true }),
});
```

Compare with the React project:

- the interceptor plays the role of `createApiClient`;
- signals play the role of `useState`;
- `takeUntilDestroyed` plays the role of the effect cleanup;
- `authGuard` plays the role of `ProtectedRoute`;
- the `FormGroup` validators play the role of `validate()`.

## 6. How It Connects to the Rest of the System

```text
 SPA (this unit)
   ├─ API models ⇐ generated from FastAPI OpenAPI (Unit 2)
   ├─ API client ─► REST API (Unit 2/5) ─► service ─► DB (Unit 3)
   ├─ auth state ⇐ IdP tokens; 401/403 semantics from Unit 2
   ├─ built as static assets ─► S3 + CloudFront or Nginx container
   │                           (Unit 6), CI builds + tests (Unit 7)
   ├─ correlation ID header ─► traces across front & back (Unit 11)
   └─ AI features: streaming responses, human approval UIs (Units 9-10)
```

## FDE Scenario 3 — "The new portal is slow and sometimes shows the wrong customer"

**Stakeholder:** "Agents say the portal sometimes shows the previous customer's tickets after switching quickly, and it feels slow."

- *Hypothesis from evidence:* a race between requests. A slow response for customer A arrives after the request for customer B and overwrites the state, because there is no cancellation. Slowness could come from sequential requests, a missing backend index, or no loading feedback.
- *Investigate:*
  - browser DevTools Network tab: timing, waterfall, request order;
  - reproduce with network throttling;
  - check backend traces for the endpoints.
- *What must be deterministic:* the UI must only render data for the currently selected customer. That is a correctness bug, potentially a privacy issue, not cosmetics.
- *Fix:*
  - `AbortController` cleanup in the effect, or a data library with keyed queries;
  - show loading states;
  - run independent requests in parallel with `Promise.all`;
  - add the backend index if the traces show slow queries.
- *Verify:* an automated test with delayed mock responses proving that stale responses are ignored, plus a before/after timing demo.
- *Communicate:* explain the root cause in plain language, and confirm no data left the authorized scope, because the API enforces authorization. This was a display race, not a data leak.

## Comprehension Questions

1. Why doesn't `fetch` throw on a 404, and what must your client do about it?
2. What does `useEffect`'s cleanup function protect against when fetching data?
3. Why model load state as a discriminated union instead of three booleans?
4. Why is a client-side protected route not a security control?
5. Compare storing a JWT in `localStorage`, in memory and in an httpOnly cookie.
6. Why validate a form on the client *and* on the server?
7. What are the Angular equivalents of React's `useState`, `useEffect` cleanup and a central fetch client?
8. Why generate TypeScript API models from the OpenAPI spec?

## Comprehension Answers

1. `fetch` resolves whenever a response arrives; it rejects only on network failure. The client must check `response.ok` and convert error responses (ideally problem+json) into typed errors.
2. Stale or late responses updating state after the inputs changed or the component unmounted, which shows wrong data and wastes work. Abort the request and ignore its result.
3. Booleans allow impossible combinations (loading *and* error *and* data). A union makes each state explicit, and TypeScript narrows the available fields per state.
4. Anyone can call the API directly or modify the JavaScript. Authorization must be enforced by the server; the guard only improves UX.
5. `localStorage` persists but is readable by any XSS. Memory is safer but lost on refresh. An httpOnly cookie is unreadable by scripts but needs CSRF protection via SameSite or tokens. A BFF keeps tokens off the browser entirely.
6. Client validation gives immediate feedback. The server must validate because clients can be bypassed and because only the server knows state-dependent rules (for example uniqueness).
7. `signal()`; `takeUntilDestroyed` / `DestroyRef` cleanup or `effect` cleanup; `HttpClient` with interceptors in an injectable service.
8. The frontend's types stay in sync with the backend contract, so breaking API changes become compile errors.

## Interview Questions — Theory-Based

**Q1. Explain the JavaScript event loop.**

- *Strong answer:* JavaScript runs on one thread with a call stack. Async work (timers, network) completes outside it and queues callbacks. Promise callbacks go to the microtask queue, which drains completely after each task, before rendering and the next macrotask. Long synchronous code blocks rendering and input. Same idea as Python's asyncio.
- *Follow-up:* "Order of `setTimeout(0)` vs `Promise.resolve().then`?" (The microtask runs first.)

**Q2. How does React decide what to re-render?**

- *Strong answer:* A state update re-runs the component, and by default its children. React diffs the new element tree against the previous one and patches the DOM minimally. Keys identify list items. `memo`, `useMemo` and `useCallback` skip work when inputs are unchanged. The React Compiler can automate memoization.
- *Follow-up:* "Why do keys matter?" (Without stable keys, state and DOM can attach to the wrong item when lists reorder.)

**Q3. When would you use `useEffect`, and what's the most common bug?**

- *Strong answer:* To synchronize with external systems: fetching, subscriptions, timers. The common bugs are missing dependencies (stale data), missing cleanup (races, leaks), and using effects for derived state that should be computed during render.

**Q4. React vs Angular?**

- *Strong answer:* React is a UI library; you pick routing, data and forms libraries. Angular is a batteries-included framework with DI, a router, forms, HttpClient and a CLI. Both are component-based with one-way data flow. Modern Angular uses signals, similar in spirit to React state. I choose based on the customer's stack and team, and the concepts transfer.

**Q5. How do you handle authentication in a SPA securely?**

- *Strong answer:*
  - OIDC Authorization Code flow with PKCE via the IdP;
  - access tokens in memory (or a BFF with httpOnly cookies);
  - short lifetimes and refresh;
  - attach the token in one interceptor or client;
  - on 401, refresh or log out;
  - never trust client-side checks for authorization;
  - prevent XSS (no `dangerouslySetInnerHTML` with untrusted HTML, a CSP).

**Q6. What does TypeScript guarantee at runtime?**

- *Strong answer:* Nothing — types are erased. They catch mistakes at compile time, but API responses are unchecked unless validated (Zod or Valibot), or unless they come from trusted, generated contracts plus tests.

**Q7. How do you structure state in a SPA?**

- *Strong answer:*
  - local UI state in components;
  - shared client state in context or services;
  - server state in a data-fetching layer with caching and invalidation;
  - URL state for filters and pagination (shareable links);
  - avoid duplicating server data in global stores.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a frontend you built or significantly changed.**

- *Cover:* the users, the framework, structure (components, state, API layer), auth, testing, performance, and one trade-off.
- *Personalize:* "`<<personalize: app and users>>` in `<<React/Angular>>`. I introduced a central API client with typed models generated from OpenAPI, explicit loading and error states, and `<<test approach>>`. Result: `<<metric>>`."
- *Lab-honest version:* "In a project I built a React and TypeScript SPA with protected routes, an API client handling timeouts and 401s, and 15 component and integration tests."

**A2. How did you integrate a frontend with a backend API?**

- *Cover:* the contract source (OpenAPI), types, CORS or a proxy, auth headers, error mapping (problem details to form errors), and environments.

**A3. Describe a hard UI bug you fixed.**

- *Cover:* reproduction (DevTools, throttling), root cause (race, stale closure, missing key), fix, regression test.

**A4. Have you worked in Angular, or only React (or vice versa)?**

- *Honest framing:* "My production experience is in `<<X>>`. I've implemented the same patterns in `<<Y>>`: services with DI, an HTTP interceptor for auth, signals for state and a route guard. The mental model maps one-to-one: `<<examples>>`."

**A5. How do you test frontend code?**

- *Cover:* unit tests (validation), component tests (Testing Library: query by role or label, simulate users), mocked HTTP (mock fetch or MSW), and a few E2E tests (Playwright).

## Troubleshooting Scenarios

**T1. The frontend receives 401 after login works.**

```text
SYMPTOM     login succeeds, next call returns 401
CHECK       is Authorization header present (DevTools → Network)?
            token stored where the client reads it? CORS preflight
            missing Authorization in allowed headers? aud/iss mismatch?
CAUSES      client reads token before state updates; interceptor not
            registered; backend CORS; token for wrong audience
FIX         read token via ref/signal at request time; register
            interceptor; allow header in CORS; fix IdP audience
PREVENT     integration test: login → protected call
```

**T2. Wrong data briefly flashes after changing filters quickly.**

```text
CAUSE       out-of-order responses; no AbortController/cleanup
FIX         abort previous request in effect cleanup / switchMap in
            RxJS; key server state by filter
TEST        mock with delayed responses, assert final UI
```

**T3. CORS error in the browser, but Postman works.**

```text
CAUSE       browser enforces same-origin; backend lacks CORS headers
            for this origin, or uses "*" with credentials
FIX         backend CORSMiddleware allow_origins=[exact origins];
            or dev proxy (Vite server.proxy) so origin is the same
```

**T4. The production build shows a blank page.**

```text
CHECK       browser console; asset 404s (wrong base path); env var
            missing at build time (Vite inlines VITE_* at BUILD time)
FIX         set base / CDN path; inject config at build or via
            /config.json fetched at runtime; SPA fallback to
            index.html for deep links (CloudFront/Nginx)
```

**T5. An infinite render or request loop.**

```text
CAUSE       effect depends on an object/function recreated every
            render; setState inside render
FIX         stable deps (useMemo/useCallback), move derived data to
            render, correct dependency array
```

## Unit Practice Project — Support Tickets SPA

### Project Goal

Build a React + TypeScript SPA where support agents sign in, list tickets, filter by status, create tickets with validation and change ticket status. It must have:

- a robust API client (auth header, timeout, problem+json errors, 401 handling);
- explicit loading and error states;
- in-memory auth and protected routes.

It runs standalone against a built-in mock backend that speaks the same HTTP contract as the Unit 5 FastAPI service.

### Architecture

```text
 main.tsx ─ BrowserRouter ─ AuthProvider(fetchImpl = mock | real)
                              │ provides api + auth state
   App routes: /login → LoginPage
               /tickets → ProtectedRoute → TicketsPage
                                            ├─ TicketForm (validate)
                                            ├─ filter select
                                            └─ TicketList (status)
   useTickets(filter) ─► ticketsApi ─► createApiClient ─► fetch
                                             └─► mockServer (dev/tests)
```

### Requirements

1. `/login` signs in with username and password (form-encoded `POST /auth/token`). Errors are shown to the user. On success, navigate to the originally requested page or `/tickets`.
2. Visiting `/tickets` unauthenticated redirects to `/login`.
3. `/tickets` lists tickets, newest first, with loading, error-with-retry and empty states.
4. The filter `all | open | in_progress | closed` refetches. Stale responses must never overwrite newer ones.
5. Create form:
   - title 3–120 characters (trimmed), description ≤ 2000, priority select;
   - client validation errors shown and the submit is blocked;
   - server 422 field errors mapped onto the fields;
   - the new ticket appears at the top.
6. Changing a ticket's status sends `PATCH /tickets/{id}` and updates the row.
7. Any 401 logs the user out. Sign-out clears auth state.
8. The token is kept in memory only.

### Technical Requirements

- Node 22.12+ or 24 LTS, Vite 8, React 19, React Router 7, TypeScript (strict).
- Vitest, jsdom, Testing Library (React, user-event, jest-dom).
- Environment-driven mode: `VITE_USE_MOCK` (default true) or `VITE_API_BASE_URL`.

### Project Structure

{{tree projects/unit04-spa/solution}}

### Step-by-Step Implementation

1. **Install and run.** `npm install`, then `npm run dev`. Open the app.
   - *Why:* to see the shell. Login fails until you implement `login`.
2. **Implement `createApiClient.request`** (`src/api/client.ts`).
   - *Why:* every later feature depends on correct HTTP behavior.
   - *Test:* `npx vitest run src/api/client.test.ts`.
3. **Implement `login` in `AuthContext`** (token in `tokenRef`, set the username).
   - *Test:* the "bad credentials" App test, then manual login.
4. **Implement `ProtectedRoute`.**
   - *Test:* "redirects anonymous users to the login page."
5. **Implement the `useTickets` effect** (loading → ready or error, with abort cleanup).
   - *Test:* the "logs in, lists…" App test; switch filters quickly in the browser with network throttling.
6. **Implement `validate` and the server-error mapping in `TicketForm`.**
   - *Test:* `npx vitest run src/components/TicketForm.test.tsx`.
7. **Run everything:** `npm test`, `npm run typecheck` and `npm run build`.
8. **Optional:** point `VITE_API_BASE_URL=/api` and `VITE_USE_MOCK=false` at the Unit 5 backend.

### Starter Code

{{file projects/unit04-spa/starter/src/api/client.ts}}

{{file projects/unit04-spa/starter/src/hooks/useTickets.ts}}

The starter also has TODOs in `src/components/TicketForm.tsx` (`validate` and server-error mapping), `src/auth/ProtectedRoute.tsx` and `src/auth/AuthContext.tsx` (`login`).

### Practice Tasks

1. **Normal behavior:** login, list, filter, create and status change.
2. **Validation:** short or long title, long description, server field errors.
3. **Errors:**
   - wrong password message;
   - network failure or timeout shows the error state with Retry;
   - 401 logs out.
4. **Edge cases:**
   - fast filter switching (no stale data);
   - empty filter results;
   - double-submit prevention (button disabled while saving).
5. **Tests:** add one for the empty state and one for "Retry after error" (make `fetchImpl` fail once).

### Hints

1. Combine the timeout and the caller's cancellation by aborting one `AbortController` from both sources.
2. Distinguish a caller abort (`options.signal?.aborted`) from a timeout (`controller.signal.aborted`).
3. FastAPI's default errors put a string in `detail`; problem details have `title` and `detail`.
4. In the effect, check `controller.signal.aborted` before setting the error state.
5. The last element of a server error's `loc` array is the field name.
6. Use `useRef` for the token so the API client always reads the current value without being recreated.

### Expected Behavior

```text
/tickets (not signed in)       → redirected to /login
login agent / wrong            → "Incorrect username or password"
login agent / agent-password   → /tickets, "Signed in as agent",
                                 "VPN drops every hour" listed
create title "ab"              → "Title must be 3-120 characters."
                                 (no request sent)
create "Laptop will not boot"  → appears at top of the list
filter "In progress"           → only "Request new monitor"
status of #1 → Closed          → PATCH /tickets/1, row shows Closed
token rejected (401)           → back to /login
```

### Testing Requirements

- **Unit:** the API client (headers, form encoding, problem parsing, 401 callback, timeout, 204) and form validation.
- **Component:** form behavior and server error mapping.
- **Integration:** the full flow through the router, auth provider and mock backend.

```bash
npm test                  # all tests
npx vitest run src/App.test.tsx
npm run typecheck
npm run build
```

### Final Runnable Solution

{{files projects/unit04-spa/solution}}

### How to Run

```bash
cd projects/unit04-spa/solution
npm install
cp .env.example .env
npm run dev          # http://localhost:5173  → agent / agent-password
npm test
npm run build && npm run preview
```

### Verify the Solution

1. `npm test` shows **15 passed** (3 files).
2. `npm run typecheck` and `npm run build` succeed.
3. In the browser: sign in, create a ticket, filter, change a status.
4. In DevTools → Network (mock mode shows no requests; switch to real mode with Unit 5 to see them), confirm `Authorization: Bearer …` on API calls.
5. Throttle the network to "Slow 3G" and switch filters quickly. The final list always matches the selected filter.

### Project Interview Debrief

1. **Why a mock backend that returns real `Response` objects?**
   The API client and components are exercised exactly as in production. Switching to the real API is configuration, not code. It also lets frontend work proceed before the backend exists.
2. **Why keep the token in memory?**
   It reduces XSS token theft compared with `localStorage`. The trade-off is that a refresh logs you out; production would add a refresh token in an httpOnly cookie or a BFF.
3. **What happens if two filter requests race?**
   The effect cleanup aborts the old request, and the error path ignores aborted requests, so only the latest response updates state. The integration tests cover the flow, and throttled manual testing confirms it.
4. **What would you change for production?**
   OIDC login (PKCE), generated API types, TanStack Query for caching and retries, error monitoring (Sentry or OpenTelemetry web), accessibility review, E2E tests (Playwright), CSP headers, and CDN hosting with SPA fallback.
5. **How would this look in Angular?**
   A `TicketsService` with `HttpClient`, an `authInterceptor` for the header and 401, signals for the state, `@if`/`@for` templates, a `CanActivateFn` guard and a reactive `FormGroup`. Same architecture, different syntax.
