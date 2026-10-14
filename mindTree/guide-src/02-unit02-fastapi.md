# Unit 2 — Backend Engineering with FastAPI and REST

## 1. What This Unit Teaches

Most FDE deliverables expose functionality through an HTTP API that a frontend, a partner system or an AI agent calls **[JD-Required]**. This unit teaches:

- the HTTP and REST semantics interviewers probe;
- how to design an API contract;
- how a request flows through FastAPI;
- how Pydantic validates data at the boundary;
- how dependency injection, a service layer and a repository layer keep code testable;
- how to map errors to correct status codes;
- how authentication differs from authorization, and how to implement both with JWTs and roles;
- what changes when the API goes to production.

## 2. Mental Model

```text
 Client (browser SPA, partner system, AI agent)
   │  HTTPS request: method + path + headers + body
   ▼
 API Gateway / Load Balancer   (TLS, routing, rate limits, WAF)
   ▼
 ASGI server (Uvicorn)         (sockets → ASGI events)
   ▼
 Middleware                    (CORS, request ID, timing, gzip)
   ▼
 FastAPI Router                (match method + path)
   ▼
 Dependencies + Validation     (Pydantic parses path/query/body)
   ▼
 Authentication                (who are you?   → 401 if unknown)
   ▼
 Authorization                 (may you do it? → 403 if not)
   ▼
 Service                       (business rules → domain errors)
   ▼
 Repository                    (persistence boundary)
   ▼
 Database
   ▲
 Response model serialization  (only declared fields leave)
 ← HTTP response: status + headers + JSON (or problem+json)
```

Each layer answers one question and fails with its own status code. The layers deliberately stop knowing about one another:

| Layer | Knows about | Does **not** know about |
|---|---|---|
| Route | HTTP (status codes, headers) | Business rules or SQL |
| Service | Business rules | HTTP or SQL |
| Repository | Storage | HTTP or business rules |

That separation is what lets you test business rules without HTTP, and swap in-memory storage for PostgreSQL (Unit 3) without touching routes.

## 3. Brief Theory

### 3.1 HTTP

**What it is.** HTTP is a request/response protocol: a method, a target URI, headers and an optional body go in; a status code, headers and a body come back. HTTP semantics are defined in RFC 9110 (2022), independently of the HTTP/1.1, HTTP/2 or HTTP/3 transports.

**Why it matters.** Status codes and method semantics are the contract that clients, proxies, caches and retry libraries rely on. Get them wrong and clients retry things they shouldn't, caches serve stale data, and monitoring can't tell user errors from outages.

**How it works.**

| Method | Safe (no side effects) | Idempotent (repeat = same effect) | Typical use |
|---|---|---|---|
| GET | Yes | Yes | Read a resource or collection |
| POST | No | **No** | Create or trigger an action |
| PUT | No | Yes | Replace a resource completely |
| PATCH | No | Not guaranteed | Partial update |
| DELETE | No | Yes | Remove a resource |

| Status | Meaning | Example |
|---|---|---|
| 200 / 201 / 204 | OK / Created (+ `Location`) / No Content | GET, POST, DELETE |
| 400 | Malformed request | Bad JSON |
| 401 | **Not authenticated** (missing or invalid credentials) | No token, expired token |
| 403 | **Authenticated but not allowed** | Viewer tries to delete |
| 404 | Resource doesn't exist (or is hidden from you) | Unknown ID |
| 409 | Conflicts with current state | Duplicate email |
| 422 | Well-formed but semantically invalid | Missing required field |
| 429 | Rate limited (send `Retry-After`) | Too many requests |
| 500 / 502 / 503 / 504 | Server bug / bad upstream / unavailable / upstream timeout | |

HTTP is **stateless**: each request carries everything needed to process it (for example the `Authorization` header). That is why servers can scale horizontally behind a load balancer.

### 3.2 REST and API contracts

**What it is.** REST is an architectural style:

- *resources* are identified by URIs (`/customers/42`);
- they are manipulated through *representations* (JSON) using uniform methods;
- requests are stateless and responses can be cached.

An **API contract** is the precise agreement about paths, inputs, outputs, errors, authentication and versioning. In FastAPI it is generated as **OpenAPI** from your code.

**Why it exists.** A shared contract lets frontend, partner and backend teams work in parallel, and lets tools generate clients, docs and tests.

**Design rules worth defending in interviews:**

- Use nouns for resources and HTTP methods for verbs (`POST /customers`, not `/createCustomer`).
- Use **consistent errors**: RFC 9457 *Problem Details* (`type`, `title`, `status`, `detail`).
- **Paginate** every collection (`limit`/`offset`, or cursor pagination for large or changing data). Validate the bounds.
- **Version** deliberately (`/v1/...`, or a header) and evolve additively: adding optional fields is safe; removing or renaming fields is breaking.
- **Return only what clients need**: response models prevent leaking internal fields such as `password_hash`.
- **Make POSTs that create side effects safe to retry** with an `Idempotency-Key` header (Unit 8).

### 3.3 FastAPI and the request/response lifecycle

**What it is.** FastAPI is a Python web framework built on **Starlette** (ASGI toolkit) and **Pydantic** (validation). Type hints on your function parameters *are* the validation and documentation. **[Current: FastAPI 0.14x; still 0.x, so pin versions.]**

**How it works.**

1. Uvicorn (the ASGI server) receives bytes and creates an ASGI `scope`.
2. Middleware runs.
3. The router matches the method and path.
4. FastAPI resolves the endpoint's **dependency graph**:
   - path, query, header and body parameters, each validated by Pydantic;
   - `Depends(...)` providers, cached once per request.
5. It calls your function:
   - `async def` endpoints run on the event loop;
   - plain `def` endpoints run in a **threadpool**, so a blocking library doesn't freeze the loop.
6. The return value is validated and serialized through the declared response type (the return annotation or `response_model`).
7. Exceptions are converted to responses by registered exception handlers.

```text
 request ─► middleware ─► route match ─► solve dependencies
            ─► validate inputs ─► endpoint ─► validate output ─► JSON
                 │ fail → 422                      │ exception →
                 └────────────── exception handlers ◄┘ 4xx/5xx
```

### 3.4 Pydantic v2 and validation

**What it is.** Pydantic models are classes whose type-annotated fields are parsed and validated at runtime by a Rust core (`pydantic-core`). **[Current: v2; v1 APIs such as `.dict()` and `@validator` are legacy.]**

**Why it matters.** The API boundary is where untrusted data enters the system. Validate *once*, there, and the rest of the code works with typed, trusted objects.

**How it works.**

- **Field types and constraints:** `EmailStr`, `Annotated[str, StringConstraints(min_length=1)]`, `Field(ge=1, le=100)`.
- `model_config = ConfigDict(extra="forbid")` rejects unknown fields, which catches client typos and mass-assignment attempts.
- `@field_validator` and `@model_validator` add custom rules.
- `model_dump(exclude_unset=True)` tells you which fields the client actually sent. This is essential for PATCH.
- Separate models per purpose: `CustomerCreate`, `CustomerUpdate`, `CustomerOut`. The input contract and the output contract evolve independently.

### 3.5 Dependency injection

**What it is.** `Depends(provider)` tells FastAPI to call `provider` (resolving *its* dependencies first) and pass the result into your endpoint.

**Why it exists.** It wires settings, DB sessions, services and the current user into handlers without globals, and makes them replaceable in tests (`app.dependency_overrides[get_settings] = ...`).

**How it works.**

- Providers can be functions, classes or generators. A `yield` dependency runs cleanup after the response, which is how per-request DB sessions are opened and closed.
- Results are cached per request, so two dependencies that need the current user decode the token once.
- Dependencies can be parameterized factories: `require_role(Role.ADMIN)` returns a checker.

### 3.6 Service layer and persistence boundary

**What it is.**

- The **service** holds business rules (unique emails, allowed state transitions) and raises *domain* errors (`NotFoundError`, `ConflictError`).
- The **repository** is an interface over storage (`add`, `get`, `list`, `update`, `delete`).

**Why it exists.** Routes stay thin, rules are testable without HTTP or a database, and storage can change. The same service runs on an in-memory repository in Unit 2 and on SQLAlchemy/PostgreSQL in Unit 3.

### 3.7 Exception handling

Map domain errors to HTTP in one place (exception handlers), not in every route:

- `NotFoundError` → 404, `ConflictError` → 409, validation → 422 problem details.
- Unhandled exceptions → generic 500. Log the stack trace server-side; never return it to clients, because it leaks internals.

### 3.8 Authentication

**What it is.** Proving *who* the caller is.

**Common approaches:**

| Approach | How it works | Trade-offs |
|---|---|---|
| Session cookie | Server stores the session; browser sends the cookie | Simple and revocable for first-party web apps; needs CSRF protection; server-side state |
| **JWT bearer token** | A signed token carries claims (`sub`, `role`, `exp`, `aud`, `iss`); the API verifies the signature | Stateless and scalable; hard to revoke before `exp`, so keep lifetimes short and use refresh tokens |
| OAuth 2.0 / OIDC with an identity provider | The IdP (Cognito, Entra ID, Okta, Auth0) authenticates users and issues tokens; APIs only *validate* them | The production standard; your API never sees passwords |
| API keys / mTLS | Long-lived machine credentials | Good for service-to-service; keys need rotation and scoping |

**JWT verification checklist:**

- verify the signature;
- **pin the algorithm list** (never accept `alg: none` or algorithm switching);
- check `exp`, `aud` (*this* API) and `iss` (the trusted issuer);
- keep tokens short-lived.

Passwords, if you must store them, are hashed with a slow, salted algorithm. **Argon2id** (via `pwdlib`) is what the FastAPI docs currently show; bcrypt is legacy but acceptable.

### 3.9 Authorization

**What it is.** Deciding *what* an authenticated caller may do.

| Model | Rule example |
|---|---|
| **RBAC** (role-based) | "admins can delete" |
| **ABAC** (attribute-based) | "a support agent can view tickets in their region during business hours" |
| **Object-level** | "users may read *their own* orders" |

Missing object-level checks is **OWASP API Security Top 10 risk #1**: Broken Object Level Authorization, where a user changes `/orders/41` to `/orders/42` and reads someone else's order.

**Rule:** authorization is enforced **server-side, in deterministic code**, after authentication. The frontend hides buttons for usability, but never for security.

### 3.10 OpenAPI

FastAPI serves `/openapi.json`, with Swagger UI at `/docs` and ReDoc at `/redoc`. Treat the spec as the contract:

- generate TypeScript clients from it (Units 4–5);
- review contract changes in pull requests;
- run contract tests in CI.

### 3.11 Async endpoints

Use `async def` when every call inside is non-blocking (an async DB driver, `httpx.AsyncClient`, an LLM SDK's async client). Use `def` when you call blocking libraries or do CPU-heavy work such as password hashing; FastAPI runs those in a threadpool. **Mixing a blocking call into `async def` is the classic FastAPI performance bug** (Unit 1).

### 3.12 Testing FastAPI

- `TestClient(app)` runs the ASGI app in-process; use it as a context manager to run the lifespan. `httpx.AsyncClient` with `ASGITransport` covers async tests.
- **Test pyramid:** service unit tests (no HTTP) → API tests with `TestClient` → a few integration tests against real dependencies.
- Override dependencies for isolation; build settings explicitly in fixtures.

### 3.13 Production deployment considerations

- **Process model.** Run Uvicorn with several workers, or one process per container with Kubernetes scaling the replicas. Put it behind a load balancer that terminates TLS. Use `--proxy-headers` so client IP and scheme are correct.
- **Configuration and secrets.** Read settings from the environment (`pydantic-settings`). Fail fast on missing secrets. Secrets come from a secret manager (Unit 6).
- **Cross-cutting concerns.**
  - CORS allow-lists (never `*` with credentials);
  - request size limits;
  - rate limiting (at the gateway);
  - timeouts on every outbound call;
  - structured logs with request IDs, plus metrics (Unit 11);
  - `/health` liveness and readiness endpoints (Unit 6).

## 4. Application in a Real System

| Component | Technology choice | Why | Without it | Alternatives |
|---|---|---|---|---|
| Public API | FastAPI | Typed, fast to build, async, auto OpenAPI | Hand-written validation and docs drift | Flask (sync, no built-in validation), Django REST Framework (batteries-included, ORM-centric), Litestar |
| Boundary validation | Pydantic v2 | One declarative schema for validation, docs and serialization | Ad-hoc `if` checks; injection risks | marshmallow, attrs + cattrs |
| Identity | OIDC provider + JWT validation | Centralized login, MFA, SSO, no password storage | Homemade auth bugs | Session cookies for a single first-party web app |
| Authorization | Role and object checks in dependencies and services | Deterministic, testable, auditable | Data leaks (BOLA) | Policy engines (OPA, Cedar) for complex rules |
| Error format | RFC 9457 problem details | Machine-readable, consistent | Every endpoint invents its own error shape | Custom envelope |

**Concrete architecture (AWS):**

```text
Route 53 → CloudFront (SPA) → ALB or API Gateway (TLS, WAF)
  → ECS/EKS tasks (Uvicorn + FastAPI)
  → RDS PostgreSQL (Unit 3)
  → Cognito (or the customer's IdP), which issues the JWTs
```

The API validates the tokens.

## 5. Implementation

### 5.1 Schemas as the contract

```python
class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")   # unknown field → 422
    name: Annotated[str, StringConstraints(strip_whitespace=True,
                                           min_length=1,
                                           max_length=120)]
    email: EmailStr
    company: str | None = None


class CustomerOut(BaseModel):                   # what leaves the API
    id: int
    name: str
    email: str
    status: CustomerStatus
```

### 5.2 A thin route

```python
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(body: CustomerCreate, service: ServiceDep,
                          _: AdminDep, response: Response) -> CustomerOut:
    customer = service.create(body)          # business rules in service
    response.headers["Location"] = f"/customers/{customer.id}"
    return CustomerOut.model_validate(customer, from_attributes=True)
```

- `body: CustomerCreate` means JSON is parsed and validated before the function runs, so invalid input produces an automatic 422.
- `service: ServiceDep` is `Annotated[CustomerService, Depends(...)]`, which is injected.
- `_: AdminDep` runs authentication and authorization. The underscore says "needed for its effect only."
- The return annotation is the **response model**: only declared fields are serialized.

### 5.3 Authentication and authorization dependencies

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)],
                     settings: SettingsDep) -> User:
    try:
        return decode_access_token(token, settings)   # 401 on failure
    except InvalidTokenError as exc:
        raise HTTPException(401, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) \
            from exc


def require_role(minimum: Role):
    def checker(user: Annotated[User, Depends(get_current_user)]):
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise HTTPException(403, f"Requires role {minimum.value}")
        return user
    return checker
```

### 5.4 Verifying a JWT safely

```python
claims = jwt.decode(
    token,
    settings.jwt_secret.get_secret_value(),
    algorithms=["HS256"],             # pinned — never from the token
    audience=settings.jwt_audience,   # token must be for THIS API
    issuer=settings.jwt_issuer,       # and from OUR issuer
    options={"require": ["exp", "sub", "aud", "iss"]},
)
```

With an external IdP you would verify RS256/ES256 signatures against the provider's **JWKS** public keys (`jwt.PyJWKClient`), and you would not need a shared secret.

### 5.5 PATCH semantics: "not sent" vs "sent as null"

```python
changes = data.model_dump(exclude_unset=True)   # only fields sent
updated = customer.model_copy(update={**changes,
                                      "updated_at": datetime.now(UTC)})
```

### 5.6 Centralized error mapping

```python
@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        {"type": "about:blank", "title": exc.title,
         "status": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code,
        media_type="application/problem+json")
```

### 5.7 Testing with dependency control

```python
@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:    # runs lifespan
        yield c


def test_viewer_cannot_create(client, viewer_headers) -> None:
    r = client.post("/customers", json={"name": "A",
                    "email": "a@example.com"}, headers=viewer_headers)
    assert r.status_code == 403
```

## 6. How It Connects to the Rest of the System

```text
 React / Angular SPA (Unit 4)  ── calls with Bearer token ──┐
 Partner system / AI agent (Units 9–10) ────────────────────┤
                                                            ▼
                          FastAPI (this unit)
              validation · authN · authZ · errors · OpenAPI
                                   │
                         Service layer (rules)
                                   │
                  Repository ──► SQLAlchemy/PostgreSQL (Unit 3)
                                   │
         Docker image ──► Kubernetes/AWS (Unit 6) ──► CI/CD (Unit 7)
                                   │
           resilient calls to other services (Unit 8)
           logs · metrics · traces (Unit 11)
```

The API is the **deterministic control point** of the whole system:

- the SPA renders what the API allows;
- AI agents call tools through it, so the API enforces authorization even when a model proposes an action (Unit 10);
- the database sees only validated data.

## FDE Scenario 1 — "Just give the partner access to our customer data"

**Stakeholder:** "Our logistics partner needs our customer list. Can you expose an endpoint by Friday?"

**Ask yourself:**

- *What is ambiguous?* Which fields (all PII or just a shipping address)? Which customers (all, or those with active shipments)? How fresh must the data be? Pull or push?
- *What is missing?* Data-sharing agreement and legal basis (GDPR/CCPA); expected volume; the partner's authentication capability; SLA.
- *What must be deterministic?* Authorization scoping (the partner sees only its customers); field filtering; audit logging.
- *Which data is authoritative?* The CRM or customer table, not a cached export.
- *Design:*
  - a dedicated `/partners/v1/shipments-contacts` endpoint with a minimal response model;
  - a machine client using OAuth client credentials with a `partner:read` scope;
  - per-partner object-level filtering, cursor pagination, rate limits and audit logs.
- *How to verify:* contract tests from the OpenAPI spec; a negative test proving the partner can't read other partners' customers; a sandbox demo with synthetic data.
- *How to communicate:* propose an MVP by Friday on synthetic data plus a security review, and make legal sign-off a precondition for production data.

## Comprehension Questions

1. Why does FastAPI use Pydantic models at application boundaries?
2. What is the difference between authentication and authorization, and which status code does each failure produce?
3. Why is POST not idempotent, and what can you add to make retries safe?
4. Why does the guide use separate `CustomerCreate`, `CustomerUpdate` and `CustomerOut` models?
5. What problem does `model_dump(exclude_unset=True)` solve in a PATCH endpoint?
6. Why should business rules live in a service rather than in route functions?
7. When should an endpoint be `def` instead of `async def`?
8. Why must the JWT verification code pin the accepted algorithm and check `aud` and `iss`?

## Comprehension Answers

1. The boundary is where untrusted input enters. Pydantic parses and validates it once, rejects bad input with 422, generates the OpenAPI schema, and hands the code typed objects.
2. Authentication establishes identity (failure → 401 with `WWW-Authenticate`). Authorization decides permission for an identified caller (failure → 403).
3. Each POST may create a new resource or trigger a new side effect, so repeating it can duplicate them. An `Idempotency-Key` stored with the result lets the server return the original result on retries.
4. Input and output contracts differ: clients must not set `id` or `status` on create, every field is optional on PATCH, and internal fields must never be returned. Separate models evolve independently and prevent mass assignment and data leaks.
5. It distinguishes fields the client omitted (leave unchanged) from fields explicitly sent (change, possibly to null), so a partial update doesn't wipe unsent fields.
6. Rules become testable without HTTP, reusable from other entry points (CLI, worker, agent tool), and independent of transport. Routes stay thin adapters.
7. When the endpoint calls blocking libraries or does CPU-heavy work (for example password hashing). FastAPI runs `def` endpoints in a threadpool so the event loop isn't blocked.
8. Without a pinned list, an attacker may choose a weaker algorithm (or `none`). `aud` prevents accepting tokens issued for another service, and `iss` prevents tokens from an untrusted issuer.

## Interview Questions — Theory-Based

**Q1. Walk me through what happens when a request hits a FastAPI endpoint.**

- *Strong answer:*
  1. Uvicorn parses the HTTP request into ASGI events.
  2. Middleware runs (CORS, request ID).
  3. The router matches the path and method.
  4. FastAPI resolves dependencies in order: path, query and body validated by Pydantic, then the `Depends` providers (DB session, current user, role check), each cached per request.
  5. The endpoint runs: on the event loop if `async def`, in the threadpool if `def`.
  6. The return value is validated and serialized through the response model.
  7. Exception handlers convert errors to HTTP responses, and `yield` dependencies clean up.
- *Testing:* depth beyond "it calls my function".
- *Follow-up:* "Where would you add request-ID logging?" (Middleware, so every request, including failures, gets an ID.)

**Q2. PUT vs PATCH vs POST.**

- *Strong answer:* PUT replaces the whole resource and is idempotent. PATCH applies a partial change; it can be idempotent if it sets values, but not if it increments. POST creates or triggers an action and is not idempotent. PATCH with `exclude_unset` keeps fields that were not sent.
- *Follow-up:* "How do you prevent lost updates when two clients PATCH concurrently?" (Optimistic concurrency: an `ETag` / `If-Match` or a version column, returning 409 or 412 on mismatch.)

**Q3. 401 vs 403 vs 404 for an object the user may not see.**

- *Strong answer:* 401 means no or invalid credentials. 403 means authenticated but not permitted. For objects the user shouldn't even know exist, many APIs return 404 to avoid leaking existence. Choose deliberately and consistently.

**Q4. How do JWTs work and what are their risks?**

- *Strong answer:* A JWT is a base64url header, payload and signature. The server verifies the signature with a shared secret (HS256) or a public key (RS256/ES256 via JWKS), then trusts the claims.
- *Risks:*
  - algorithm confusion (pin the algorithms);
  - missing `aud`/`iss` checks;
  - long lifetimes, since a JWT can't be revoked before expiry (keep access tokens short and use refresh tokens);
  - storing tokens where XSS can read them;
  - putting sensitive data in the payload, which is encoded, not encrypted.
- *Follow-up:* "Where would you store tokens in a SPA?" (Unit 4: in memory plus a refresh token in an httpOnly, Secure, SameSite cookie, or a backend-for-frontend pattern.)

**Q5. How do you design pagination?**

- *Strong answer:* Validate `limit` with a maximum. Offset pagination is simple but slow for deep pages and shifts when data changes. Cursor (keyset) pagination (`WHERE id > :last_id ORDER BY id LIMIT n`) is stable and uses the index. Return `next_cursor` or the total as appropriate.

**Q6. What is dependency injection in FastAPI and why does it help testing?**

- *Strong answer:* Providers declared with `Depends` are resolved and injected per request. They can be generators with cleanup and are cached per request. Tests replace them with `app.dependency_overrides` or by constructing the app with test settings, so no monkeypatching of globals is needed.

**Q7. How do you handle errors consistently across an API?**

- *Strong answer:* Raise domain exceptions in services and map them centrally to status codes with RFC 9457 problem details. Customize the validation error format. Use a catch-all 500 handler that logs the trace and returns a generic message. Include a request or trace ID in responses for support.

**Q8. What is BOLA and how do you prevent it?**

- *Strong answer:* Broken Object Level Authorization: the API trusts an ID from the client without checking ownership. Prevent it by scoping queries to the caller (`WHERE owner_id = :user`), centralizing object checks in the service, and writing negative tests that try other users' IDs.

## Interview Questions — Application / Experience-Based

**A1. Tell me about an API you built.**

- *Cover:*
  - the consumers and the contract;
  - the resource design;
  - validation, authentication and authorization;
  - error handling;
  - testing;
  - deployment;
  - one trade-off (pagination style, sync vs async, versioning).
- *Structure:* Situation → Requirement → Architecture → Implementation → Verification → Result → Lesson.
- *Personalize:* "`<<personalize: API purpose and consumers>>`. I designed `<<resources>>` with FastAPI and Pydantic, JWT validation against `<<IdP>>`, and role checks for `<<roles>>`. Errors followed problem details. I had `<<n>>` API tests in CI. Result: `<<adoption/latency/incident reduction>>`."
- *Honest lab version:* "In a hands-on project I built a secured customer CRUD API with role-based access; I verified it with 29 automated tests covering 401, 403, 404, 409 and 422 paths."
- *Follow-ups:* "How did you version it?" "What would you change for 10× traffic?"

**A2. How have you handled authentication and authorization?**

- *Cover:* the identity source (IdP or local), the token type and validation, where the role and object checks live, and how you tested negative paths. Mention least privilege.
- *Follow-ups:* "How do you revoke access quickly?" "How do machine clients authenticate?"

**A3. Describe a time an API change broke a consumer (or how you prevent it).**

- *Cover:* additive changes, deprecation windows, contract tests, OpenAPI diffs in CI, and communication.

**A4. Walk me through debugging a 500 error in an API.**

- *Cover:* the request ID → logs → stack trace → reproduce with a test → fix → regression test → check the error-rate dashboard.

**A5. How did you document your API for other teams?**

- *Cover:* OpenAPI and generated clients, examples, the error catalog, auth instructions, and a sandbox environment.

**A6. Tell me about integrating with a customer's existing system.**

- *Cover:* discovering its API and auth, rate limits, data mapping, error handling, retries and idempotency, and test environments.

## Troubleshooting Scenarios

**T1. The frontend receives 401 on every call.**

```text
SYMPTOM     SPA logs show 401 for all API calls after login
WHAT TO CHECK  is the Authorization header sent? "Bearer <token>"?
               token expired? aud/iss match API config? clock skew?
               CORS preflight dropping the header?
LIKELY CAUSES  missing header in API client; wrong audience; expired
               token not refreshed; Authorization not in CORS
               allow_headers
HOW TO CONFIRM decode the token at jwt.io-like tool (no secrets!) to
               read claims; API logs show reason (expired/audience)
FIX         attach header in one API-client interceptor; refresh
            flow; correct aud; allow Authorization in CORS
PREVENTION  E2E test of login → protected call; log 401 reasons
```

*Strong answer:* "A 401 means authentication failed, not authorization. I'd check whether the header arrives at all, then the token's `exp`, `aud` and `iss` against the API config, then CORS for browser calls."

**T2. API latency suddenly increases.**

```text
SYMPTOM     p95 from 80ms to 2s after a deploy
CHECK       traces: which span grew? DB? external call? event loop?
CAUSES      blocking call in async def; N+1 queries; missing index;
            new outbound call without timeout; CPU-heavy hashing on
            the loop
CONFIRM     span timings; asyncio debug; EXPLAIN on slow query
FIX         make blocking code def/to_thread; add index/eager load;
            add timeout and cache
PREVENT     latency SLO alert, load test in CI/staging
```

**T3. Requests fail with 422 that the client says are valid.**

```text
CHECK       the problem+json "errors" array (loc, msg); content-type
            header; field names (camelCase vs snake_case); extra
            fields with extra="forbid"
FIX         align contract (OpenAPI-generated client), or add alias
            generator; document error format
```

**T4. CORS errors in the browser, but curl works.**

```text
CAUSE       browser preflight (OPTIONS) rejected: origin not allowed,
            or allow_credentials with "*" origin
FIX         CORSMiddleware with explicit allow_origins list,
            allow_headers incl. Authorization/Content-Type
NOTE        CORS protects browsers' users, it is NOT API security
```

**T5. Everything works locally, but the app crashes on startup in staging.**

```text
CHECK       logs at startup: pydantic ValidationError for Settings?
CAUSE       missing APP_JWT_SECRET env var (fail-fast by design)
FIX         provide secret via secret manager → env; never default it
```

## Unit Practice Project — Secured Customers API

### Project Goal

Build a REST API for managing customers. It must have strict validation, layered architecture (route → service → repository), JWT authentication, role-based authorization, consistent RFC 9457 errors, OpenAPI docs and thorough tests. This proves you can deliver the core of almost every FDE backend.

### Architecture

```text
 Client ── POST /auth/token (form) ──► routes_auth ─► user_repo
   │                                        └─ issues JWT
   └── Bearer JWT ──► routes_customers
                        │ deps: get_current_user → require_role
                        ▼
                  CustomerService (rules, domain errors)
                        ▼
                  CustomerRepository (Protocol)
                        ▼
                  InMemoryCustomerRepository (Unit 3: PostgreSQL)
```

### Requirements

1. `POST /auth/token` (form fields `username`, `password`) returns `{access_token, token_type, expires_in}`. Bad credentials return 401 with the same message for an unknown user and a wrong password.
2. `GET /customers?limit&offset&q` (viewer or admin) returns `{items, total, limit, offset}`. `limit` is 1–100 and `q` filters by name or company, case-insensitive.
3. `POST /customers` (admin) returns 201 with a `Location` header. Names are trimmed and emails lower-cased; a duplicate email returns 409.
4. `GET /customers/{id}` (viewer) returns 200, or 404.
5. `PATCH /customers/{id}` (admin) updates only the fields sent. Explicit null for name, email or status returns 422; taking another customer's email returns 409.
6. `DELETE /customers/{id}` (admin) returns 204, or 404.
7. Every error body is `application/problem+json` with `title`, `status` and `detail` (plus `errors` for 422).
8. `/health` needs no authentication; `/docs` shows the contract.

### Technical Requirements

- Python 3.12+, FastAPI, Pydantic v2, pydantic-settings, PyJWT, pwdlib (Argon2), python-multipart and email-validator.
- Configuration from `APP_*` environment variables. The app refuses to start without a ≥32-character JWT secret.
- pytest with FastAPI `TestClient`; ruff; mypy.

### Project Structure

{{tree projects/unit02-fastapi/solution}}

### Step-by-Step Implementation

1. **Set up and run the starter.** Run `pip install -r requirements-dev.txt`, `cp .env.example .env`, then `uvicorn app.main:create_app --factory --reload`.
   - *Why:* to confirm wiring before writing logic.
   - *Test:* `/health` returns ok, and `/docs` renders.
2. **Study the layers** (`config.py`, `models/`, `repositories/`). The repository and the in-memory implementation are complete.
   - *Connects to:* the service you will write.
3. **Implement the JWT functions** (`core/security.py`).
   - *Why:* tokens carry identity between requests.
   - *Test:* write a quick unit test that encodes a token and decodes it back, then run `pytest tests/test_auth.py` (some tests also need step 4).
4. **Implement `get_current_user` and `require_role`** (`api/deps.py`).
   - *Why:* centralized authentication (401) and authorization (403).
   - *Test:* `test_missing_token_is_401`, `test_tampered_token_is_401`, `test_viewer_cannot_create`.
5. **Implement the service rules** (`create`, `update`, `delete`).
   - *Why:* business rules independent of HTTP.
   - *Test:* `pytest tests/test_service.py`.
6. **Implement the remaining routes** (POST with `Location`, PATCH, DELETE).
   - *Test:* `pytest tests/test_customers.py`.
7. **Implement the PATCH null validator and the 422 problem-details handler.**
   - *Test:* `pytest tests/test_validation.py`.
8. **Write the TODO tests** (other-audience token; email stealing via PATCH).
9. **Run `ruff check .`, `mypy` and the full suite**, then exercise the API from `/docs`.

### Starter Code

These files contain the TODOs. Everything else in `starter/` is runnable as provided.

{{file projects/unit02-fastapi/starter/app/core/security.py}}

{{file projects/unit02-fastapi/starter/app/api/deps.py}}

{{file projects/unit02-fastapi/starter/app/services/customer_service.py}}

{{file projects/unit02-fastapi/starter/app/api/routes_customers.py}}

### Practice Tasks

1. **Normal behavior:**
   - login returns a token;
   - CRUD works for an admin;
   - a viewer can list and read;
   - pagination and filtering work.
2. **Validation:**
   - missing or empty name;
   - invalid email;
   - unknown fields;
   - out-of-range `limit` or `offset`;
   - non-integer ID;
   - explicit nulls in PATCH.
3. **Errors:**
   - 401 for missing, expired, tampered and wrong-audience tokens;
   - 403 for a viewer writing;
   - 404 for unknown IDs;
   - 409 for duplicate emails.
4. **Edge cases:**
   - email case-insensitivity;
   - whitespace trimming;
   - deleting twice (204 then 404);
   - PATCH that changes nothing but `status`.
5. **Tests:** the two TODO tests, plus at least one of your own (for example, a viewer cannot DELETE).

### Hints

1. `jwt.encode(claims, secret, algorithm=...)` accepts `datetime` objects for `iat` and `exp`.
2. `jwt.decode(..., algorithms=[...], audience=..., issuer=..., options={"require": [...]})` raises a subclass of `jwt.PyJWTError` on any problem.
3. In `require_role`, compare `ROLE_RANK[user.role] < ROLE_RANK[minimum]`.
4. PATCH: `data.model_dump(exclude_unset=True)`, then `customer.model_copy(update=...)`.
5. `Response` injected into a route lets you set headers while still returning a model.
6. The validator can loop over `("name", "email", "status")` and check `name in self.model_fields_set`.

### Expected Behavior

```text
POST /auth/token   username=admin&password=admin-password
→ 200 {"access_token":"eyJ...","token_type":"bearer","expires_in":1800}

POST /customers    Authorization: Bearer <admin>
{"name":"Jorge","email":"jorge@example.com"}
→ 201 Created   Location: /customers/1
{"id":1,"name":"Jorge","email":"jorge@example.com","company":null,
 "status":"active","created_at":"...","updated_at":"..."}

POST /customers    {"name":"Jorge"}
→ 422 application/problem+json
{"title":"Validation failed","status":422,
 "errors":[{"loc":["body","email"],"msg":"Field required",
            "type":"missing"}], ...}

POST /customers    Authorization: Bearer <viewer>
→ 403 {"detail":"Requires role admin"}

GET /customers/999 → 404 {"title":"Not found","status":404,...}
GET /customers     (no token) → 401  WWW-Authenticate: Bearer
```

### Testing Requirements

- **Unit tests:** service rules and schema validation.
- **API tests:** each endpoint's success path and Location header.
- **Negative tests:** 401 (missing, expired, tampered, wrong audience), 403, 404, 409 and 422.
- **Contract test:** OpenAPI contains the paths and schemas.

```bash
pytest -q
pytest -q tests/test_auth.py -k expired
mypy && ruff check .
```

### Final Runnable Solution

{{files projects/unit02-fastapi/solution}}

### How to Run

```bash
cd projects/unit02-fastapi/solution
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload
pytest -q
```

### Verify the Solution

1. `curl localhost:8000/health` returns `{"status":"ok"}`.
2. Log in as admin:
   `curl -X POST localhost:8000/auth/token -d username=admin -d password=admin-password`
3. Create a customer with the token and see **201** plus a `Location` header.
4. Repeat the POST and see **409** with problem+json.
5. POST without an email and see **422** with an `errors` array.
6. Log in as viewer and try the POST: **403**.
7. `pytest -q` shows **29 passed**. `mypy` is clean.
8. Open `/docs` and confirm every endpoint, schema and the padlock (auth) are documented.

### Project Interview Debrief

1. **Why separate routes, services and repositories?**
   Each changes for a different reason: transport, business rules, storage. The same service is tested without HTTP and will run on PostgreSQL in Unit 3 with no route changes.
2. **What security issue would you address next?**
   Replace local passwords with an OIDC provider (JWKS validation, short-lived tokens and refresh), add rate limiting on `/auth/token`, add an audit log for writes, and add object-level authorization if customers become tenant-scoped.
3. **What breaks first at scale?**
   The in-memory store (one process, no persistence), and offset pagination over large tables. Then Argon2 CPU on login bursts, which I'd mitigate with an IdP, rate limits or more workers.
4. **How would you deploy it?**
   Containerize (Unit 6), with configuration and secrets from the environment via a secret manager. Run several replicas behind a load balancer, with health probes and CI/CD with tests (Unit 7).
5. **Why return 409 for a duplicate email instead of 400 or 422?**
   The request is valid on its own but conflicts with the current server state. That's exactly what 409 means, and it tells the client the problem is the data, not the format.
