---
title: "Forward Deployed Engineer / Full-Stack Developer"
subtitle: "Training, Implementation and Interview-Preparation Guide — Python · FastAPI · SQL/NoSQL · React/Angular · AWS · Docker · Kubernetes · CI/CD · Distributed Systems · LLMs, RAG and Agents"
date: "October 2026"
---

# How to Use This Guide

This guide teaches you to **build, operate and explain** the kind of system a Forward Deployed Engineer (FDE) delivers. It is organized into **twelve units of related engineering concepts** (not weeks), a **final capstone**, and a **final interview-preparation section**.

Every unit follows the same pattern:

1. **What this unit teaches.**
2. **Mental model.** An ASCII diagram of the flow before any detail.
3. **Brief theory.** What it is, why it exists, why it matters, how it works.
4. **Application in a real system.** Where it appears, why it was chosen, alternatives and trade-offs.
5. **Implementation.** Short, explained code.
6. **How it connects.** A map of the unit's place in the whole system.
7. **Comprehension questions**, with answers in a separate subsection.
8. **Interview questions.** Theory-based, plus application/experience-based.
9. **Troubleshooting scenarios.**
10. **A unit practice project.** Step-by-step instructions, starter code, tasks, hints, expected behavior, tests, the complete final solution, how to run it, how to verify it, and an interview debrief.

**FDE scenarios** appear throughout. **Cross-unit system maps** appear after Units 3, 5, 8 and 10.

## The Code That Accompanies This Guide

All code lives next to this document:

```text
mindTree/
├── FDE_FullStack_Interview_Guide.docx   ← this document
├── README.md
├── guide-src/                           ← Markdown sources + build script
└── projects/
    ├── unit01-python/        {starter, solution}
    ├── unit02-fastapi/       {starter, solution}
    ├── unit03-data/          {starter, solution}
    ├── unit04-spa/           {starter, solution}
    ├── unit05-fullstack/     {starter, solution}
    ├── unit06-cloud-native/  {starter, solution}
    ├── unit07-cicd/          {starter, solution}
    ├── unit08-distributed/   {starter, solution}
    ├── unit09-llm/           {starter, solution}
    ├── unit10-rag-agents/    {starter, solution}
    ├── unit11-observability/ {starter, solution}
    ├── unit12-fde-delivery/  {starter, solution}
    └── capstone/             {starter, solution}
```

- **`starter/`** is what you receive before solving the project. It runs, or at least imports and builds, and it contains `TODO` markers where you must implement meaningful logic. Some of its tests fail on purpose: they are the specification.
- **`solution/`** is the complete, runnable implementation, and its tests pass. Every solution file is printed in full in the "Final Runnable Solution" section of its unit. The guide's build script inserts the code straight from disk, so the document and the code cannot drift apart.

Work on a copy of `starter/`. Compare with `solution/` only after you have tried the hints.

## Source of Truth and Labels

The guide is built from the job-description requirements you supplied (the technology and responsibility list in the request), used here **as a proxy for the full job description**. No separate job-description text or résumé was provided. As a result:

- Content is labeled **[JD-Required]**, **[JD-Preferred]** or **[External]** (knowledge added because production work or interviews need it, even though the job description does not name it).
- **No candidate experience is invented.** Experience-based interview questions come with answer *frameworks* and clearly marked `<<personalize: ...>>` placeholders.

### Job-Description Analysis

| Area | Classification | Expected interview depth | Implementation skill expected |
|---|---|---|---|
| Python (OOP, typing, async, testing, debugging, performance, production code) | JD-Required | Deep: mechanisms and trade-offs | Write idiomatic, typed, tested code live |
| FastAPI, REST, HTTP, validation, authN/authZ, service architecture | JD-Required | Deep | Build a secured CRUD service with tests |
| JavaScript/TypeScript, SPA, React, Angular, frontend–backend integration | JD-Required (React *or* Angular) | Moderate–deep on concepts, moderate on framework APIs | Build a typed SPA that calls an API with auth, loading and error states |
| Relational databases, SQL, NoSQL, schema design, transactions, indexes | JD-Required | Deep on SQL/transactions/indexes; moderate on NoSQL | Design a schema, write queries, use SQLAlchemy and migrations |
| Cloud (AWS/Azure/GCP), Docker, Kubernetes, config, secrets, scaling, health | JD-Required (one cloud) | Moderate–deep | Containerize, write Kubernetes manifests, explain AWS architecture |
| Git, CI/CD (Jenkins/GitHub Actions), deployments, rollback, verification | JD-Required | Moderate | Write a pipeline with test/build/deploy/verify stages |
| Microservices, distributed systems, timeouts, retries, idempotency, consistency | JD-Required | Deep on failure behavior | Implement resilient calls and idempotent endpoints |
| LLM APIs, structured output, tool calling, RAG, agents, harnesses, evaluation, guardrails | JD-Required | Deep and practical | Call model APIs, validate outputs, build RAG and a bounded agent |
| Machine learning, data engineering, MLOps | JD-Preferred (exposure) | Conceptual | Explain pipelines and model lifecycle |
| FDE engineering: discovery, stakeholders, requirements, delivery, Agile | JD-Required (core of the role) | Deep, scenario-based | Turn ambiguity into testable requirements and a working demo |

**Likely interview loop for this role** [External]:

- A recruiter screen.
- A technical deep-dive (Python, APIs, data).
- A coding exercise (often a small API or data task).
- A system-design discussion that includes an AI component.
- A customer-scenario or FDE round (requirements, communication, trade-offs).
- Behavioral and experience questions.

## Version Baseline (verified October 2026)

| Technology | Version used / referenced | Notes |
|---|---|---|
| Python | Code targets **3.12+**, tested on 3.13 | 3.14 is current stable. 3.15.0 was reported released in October 2026 (verify on python.org). The code uses PEP 695 generics (3.12+) and `asyncio.TaskGroup` / `asyncio.timeout` (3.11+). |
| FastAPI | 0.143.x | Still 0.x and releases often; pin a minor version. |
| Pydantic | 2.14.x | v1 APIs are **legacy**. |
| SQLAlchemy | 2.1.x | The 2.0-style API (`select()`, `Mapped[]`) is current; 1.x `Query` style is **legacy**. |
| Alembic / psycopg | 1.20 / 3.3 | psycopg 3 is current; psycopg2 is legacy but common. |
| pytest / HTTPX | 9.1 / 0.28 | |
| PostgreSQL | 18 current; examples are compatible with 14+ | Tested locally on 16. |
| Redis | 7+/8 (or Valkey) | |
| Node.js | 22/24 LTS | |
| TypeScript | 7.0 (native compiler) | 5.x code is compatible for our purposes. |
| React | 19.x; React Router 7/8; Vite 8 | Class components are **legacy**. |
| Angular | 22 | Standalone components are the default. Signals are current. Zoneless change detection is the default for new apps since v21. NgModule-first apps are **legacy but encountered**. |
| Docker Engine | 29 | |
| Kubernetes | 1.36 stable | ingress-nginx has been retired in favor of **Gateway API**. |
| Anthropic Python SDK | `anthropic` 1.13: Messages API, `messages.parse()`, tool use | Default model `claude-opus-5-5`. |
| OpenAI Python SDK | `openai` 3.31: **Responses API** (`responses.create` / `responses.parse`) | Chat Completions is **legacy but still supported**. Set the model ID with `OPENAI_MODEL` from OpenAI's models page. |
| AWS Bedrock | Converse API (provider-neutral); Anthropic models also via the Mantle client | |

Version-sensitive statements in the text are flagged **[Current]**, **[Legacy]**, **[Deprecated]**, **[Experimental]**, **[Provider-specific]** or **[Framework-specific]**.

## How to Answer When Your Experience Is Limited

Interviewers value honest, precise answers over inflated ones. Separate four kinds of evidence and say which one you are using:

| Evidence type | Example wording |
|---|---|
| **Professional experience** | "In production at `<<company>>`, I owned..." |
| **Project experience** | "In a project I built end to end, I implemented..." |
| **Training/lab experience** | "In hands-on labs, including the projects in this guide, I implemented X and tested Y..." |
| **Theoretical understanding** | "I haven't implemented this yet. My understanding of how it works is..." |

**Template for a gap:**

> "I have not used **X** extensively in production. My direct experience is with **Y**, which shares these underlying concepts: **<<list>>**. I have also implemented **X** in hands-on project work, where I **<<what you built and how you verified it>>**. If I had to deliver it here, I would approach it by **<<steps>>**, and I'd verify it with **<<evidence>>**."

Never claim production ownership of something you only built in a lab. The interview follow-ups ("What broke? What did the dashboards show? What did you change after the incident?") reveal the difference quickly.

## The Standard Answer Framework for Experience Questions

```text
Situation → Requirement → Architecture → Implementation
          → Verification → Result → Lesson
```

Keep each element to one or two sentences. End with evidence: a metric, a test, a demo, an incident that was resolved. Then the lesson: what you'd do differently.

## Useful Primary References

- Python documentation: <https://docs.python.org/3/> · PEP index: <https://peps.python.org/>
- FastAPI: <https://fastapi.tiangolo.com/> · Pydantic: <https://docs.pydantic.dev/latest/>
- SQLAlchemy 2.x: <https://docs.sqlalchemy.org/en/21/> · Alembic: <https://alembic.sqlalchemy.org/>
- PostgreSQL: <https://www.postgresql.org/docs/current/> · MongoDB: <https://www.mongodb.com/docs/> · Redis: <https://redis.io/docs/latest/>
- MDN JavaScript: <https://developer.mozilla.org/en-US/docs/Web/JavaScript> · TypeScript: <https://www.typescriptlang.org/docs/>
- React: <https://react.dev/> · Angular: <https://angular.dev/>
- Docker: <https://docs.docker.com/> · Kubernetes: <https://kubernetes.io/docs/home/>
- AWS: <https://docs.aws.amazon.com/> · AWS Well-Architected: <https://aws.amazon.com/architecture/well-architected/>
- Git: <https://git-scm.com/doc> · GitHub Actions: <https://docs.github.com/en/actions> · Jenkins: <https://www.jenkins.io/doc/>
- Anthropic API: <https://docs.claude.com/> · OpenAI API: <https://platform.openai.com/docs> · Amazon Bedrock: <https://docs.aws.amazon.com/bedrock/>
- OpenTelemetry: <https://opentelemetry.io/docs/> · OWASP Top 10 for LLM Applications: <https://genai.owasp.org/llm-top-10/>
- HTTP semantics (RFC 9110): <https://www.rfc-editor.org/rfc/rfc9110> · Problem Details (RFC 9457): <https://www.rfc-editor.org/rfc/rfc9457>


# Unit 1 — Production Python Engineering

## 1. What This Unit Teaches

Python is the language of the backend, the data layer and the AI orchestration in this role **[JD-Required]**. This unit covers the Python an FDE needs to write *production* code, not scripts:

- how Python executes code;
- how to structure modules, functions and classes;
- when to use composition instead of inheritance;
- how type annotations catch bugs before runtime;
- how exceptions and context managers make failure handling explicit;
- how generators process data lazily;
- how `async`/`await` and the event loop let one process handle many slow network calls;
- how to test with pytest and mocks;
- how to debug and profile;
- how to lay out a project so another engineer can run it on day one.

## 2. Mental Model

```text
 source (.py)
     │  compile (automatic, cached in __pycache__)
     ▼
 bytecode ──► CPython interpreter loop ──► objects on the heap
                        │                  (everything is an object;
                        │                   names are references)
                        ▼
  ┌──────────────── one OS process ─────────────────┐
  │  main thread                                    │
  │   └─ asyncio event loop (only when you use it)  │
  │        ├─ task A: await http call  ─┐ waiting   │
  │        ├─ task B: await db query   ─┤ on I/O    │
  │        └─ task C: running Python ◄──┘ (one at   │
  │                                     a time)     │
  │  thread pool (for blocking calls)               │
  └─────────────────────────────────────────────────┘
```

Read it as follows:

- Your code becomes bytecode that one interpreter loop executes.
- In standard CPython the **Global Interpreter Lock (GIL)** lets only one thread run Python bytecode at a time. So threads help with *waiting* (I/O), not with CPU-heavy work.
- The **event loop** is a scheduler inside one thread. Each `await` is a point where a task says "I'm waiting; run someone else." That is why async code scales to thousands of concurrent network calls, and why a single blocking call (`time.sleep`, a synchronous HTTP client, a CPU-heavy loop) freezes *every* task.

The same idea at the level of a production codebase:

```text
 entry point (CLI / FastAPI app / worker)
        │
        ▼
 application services  ── business rules, orchestration
        │ depend on
        ▼
 interfaces (Protocols) ◄── implemented by ── adapters
        │                                (HTTP clients, DB repos,
        ▼                                 LLM clients, fakes)
 domain models (dataclasses / Pydantic) ── validated, typed data
```

## 3. Brief Theory

### 3.1 Execution model, names and objects

**What it is.**

- CPython compiles each module to bytecode and executes it top to bottom on first import.
- `import` runs a module once and caches it in `sys.modules`.
- Variables are *names bound to objects*. Assignment never copies.

**Why it matters.** Many production bugs come from misunderstanding this:

- mutable default arguments (`def f(items=[])` shares one list across calls);
- aliasing (two names pointing at the same dict);
- import-time side effects (opening a database connection at import time breaks tests and CLIs).

**How it works.**

- Every object has an identity, a type and a value.
- Immutable types (`int`, `str`, `tuple`, frozen dataclasses) cannot change in place. Mutable ones (`list`, `dict`, `set`) can.
- `is` compares identity; `==` compares value.
- Memory is reclaimed by reference counting, plus a cycle collector.

**[Current]** Free-threaded ("no-GIL") CPython builds are officially supported starting with 3.14 (PEP 779) but are not the default. Assume the GIL in production unless your platform says otherwise.

### 3.2 Functions and modules

- **What.** Functions are first-class objects: you can pass them, return them and decorate them. Modules are files and packages are directories.
- **Why.** Small pure functions are easy to test. Modules create boundaries and namespaces.
- **How.**
  - Keyword-only parameters (`def f(*, timeout)`) make call sites self-documenting.
  - Decorators (`@retry_async(...)`) are functions that take a function and return a new one, which is how cross-cutting behavior such as retries, logging and auth is added without editing the wrapped function.
  - Use `functools.wraps` to preserve the wrapped function's name and docstring.

### 3.3 Classes and OOP; composition vs inheritance

- **What.** Classes bundle state and behavior. Inheritance says "is-a"; composition says "has-a" or "uses-a".
- **Why.** You need abstractions that let you swap implementations: a real supplier or a fake, PostgreSQL or SQLite, Anthropic or OpenAI.
- **How it works in Python.**
  - **`dataclass(frozen=True, slots=True)`** generates `__init__`, `__eq__` and `__repr__`, makes instances immutable, and saves memory.
  - **`typing.Protocol`** defines an interface *structurally*: any class with the right methods satisfies it, without inheriting from anything (PEP 544). This is "duck typing that the type checker understands."
  - **Composition** means building behavior by holding collaborators. For example, a `PriceCalculator` *has* a list of `PricingRule` objects. Adding a rule never requires subclassing the calculator. This avoids deep hierarchies where a change in a base class silently breaks subclasses.
  - **Use inheritance** for genuine type hierarchies with shared behavior, such as an exception hierarchy or framework base classes (`BaseModel`, `DeclarativeBase`).

### 3.4 Type annotations

- **What.** Annotations describe expected types (`def total(price: Decimal, qty: int) -> Decimal`). Python does not enforce them at runtime; tools do: mypy or pyright for static checking, and Pydantic for runtime validation at boundaries.
- **Why.** They turn whole classes of bugs (`None` where a value is required, wrong argument order, missing attributes) into editor errors, and they document intent.
- **How.**
  - Use built-in generics (`list[int]`, `dict[str, Quote]`, `X | None`).
  - Use `Protocol` for interfaces and `Callable[[float], Awaitable[None]]` for function types.
  - Use **PEP 695** type parameters for generic functions (`def chunked[T](items: Iterable[T]) -> ...`) **[Current, 3.12+]**.
  - Use `ParamSpec` to type decorators that keep the wrapped signature.
  - Run `mypy --strict` in CI.

### 3.5 Exceptions

- **What.** The mechanism for signaling that something could not be done.
- **Why.** Explicit error types let callers decide what to do: retry a transient error, report a permanent one, crash on a bug.
- **How.**
  - Define a package base exception (`QuoteError`), then *transient* versus *permanent* subclasses.
  - Catch the **narrowest** type you can handle.
  - Never use a bare `except:` (it also catches `KeyboardInterrupt`).
  - Chain with `raise NewError(...) from exc` so the original traceback is kept.
  - Python 3.11+ adds `ExceptionGroup` and `except*`, which `asyncio.TaskGroup` uses to report multiple concurrent failures.

### 3.6 Context managers

- **What.** Objects used with `with`. They run setup code, yield control, and *always* run teardown code (`__enter__`/`__exit__`, or `@contextmanager` with try/finally).
- **Why.** They guarantee that resources are released (files, locks, DB sessions, HTTP clients, spans) even when exceptions occur.
- **How.** `async with` works the same way for async resources: `httpx.AsyncClient`, `asyncio.timeout`, database sessions and semaphores.

### 3.7 Iterators and generators

- **What.** A generator is a function containing `yield`. It produces values lazily, one at a time.
- **Why.** It gives constant memory over large or infinite streams: reading a 10 GB file line by line, batching rows for bulk insert, streaming LLM tokens.
- **How.** Calling a generator function returns an iterator. Each `next()` resumes it until the next `yield`. `itertools.islice`, `chain` and `batched` (3.12+) compose iterators.

### 3.8 async/await, the event loop and concurrency

- **What.** `async def` defines a coroutine. `await` suspends it until the awaited operation completes, and the event loop runs other tasks in the meantime.
- **Why.** Backend and AI code spend most of their time waiting on databases, HTTP APIs and LLMs. Async gives high concurrency for I/O with one thread and low memory.
- **How it works.**
  - `asyncio.run(main())` starts the loop. `asyncio.create_task` and **`asyncio.TaskGroup`** run coroutines concurrently. TaskGroup is structured concurrency: if one task fails unexpectedly, the others are cancelled and the errors are raised together.
  - **`asyncio.timeout(seconds)`** cancels work that takes too long.
  - **`asyncio.Semaphore(n)`** bounds how many operations run at once. This is backpressure that protects downstream services and rate limits.
  - **Blocking calls inside `async def` block the entire loop.** Use async libraries (`httpx.AsyncClient`, `asyncpg`, async SQLAlchemy), or offload blocking work with `await asyncio.to_thread(func)`.

| Workload | Tool | Why |
|---|---|---|
| Many network/DB waits | `asyncio` | Thousands of tasks, one thread |
| Blocking library you can't replace | `asyncio.to_thread` / thread pool | Moves the wait off the loop |
| CPU-heavy work (parsing, ML inference on CPU) | `ProcessPoolExecutor`, a worker queue, or native libraries that release the GIL | Bypasses the GIL |

### 3.9 Testing with pytest and mocking

- **What.**
  - **pytest** discovers `test_*.py` files and runs plain `assert` statements.
  - **Fixtures** provide reusable setup through dependency injection.
  - **`parametrize`** runs one test over many inputs.
  - **`unittest.mock`** (`Mock`, `AsyncMock`, `patch`) replaces collaborators.
- **Why.** Tests are the evidence that code works. They let you refactor safely, and they are what you show a customer or interviewer.
- **How.**
  - Prefer **fakes** (small in-memory implementations of a Protocol) over deep mocking, because fakes test behavior and mocks test calls.
  - Inject time and sleep (`sleep=AsyncMock()`) so retry tests run instantly.
  - Use **pytest-asyncio** (`asyncio_mode = "auto"`) to run `async def` tests.

### 3.10 Debugging

- **What.** The systematic process of finding why actual behavior differs from expected behavior.
- **How.**
  - Reproduce first, ideally with a failing test.
  - Read the full traceback from the bottom up; the chained "The above exception was the direct cause" sections matter.
  - Use `breakpoint()` (pdb) or your IDE debugger. Use `logging` (not `print`) with levels and context.
  - For asyncio, set `PYTHONASYNCIODEBUG=1` (or `asyncio.run(main(), debug=True)`). It logs coroutines that were never awaited and callbacks that block the loop for longer than 100 ms.

### 3.11 Performance basics

1. **Measure first.**
   - `time.perf_counter` for elapsed time;
   - `cProfile` plus `pstats` (or `python -m cProfile -s cumtime app.py`) for deterministic profiling;
   - `py-spy` for sampling a running process without restarting it;
   - `tracemalloc` for memory.
2. **Choose the right data structure.**
   - `dict` and `set` lookups are O(1) on average;
   - `list.pop(0)` is O(n), so use `collections.deque`;
   - a membership test on a list is O(n).
3. **Remove waiting before optimizing CPU.** Concurrency (async or batching) usually wins over micro-optimizations in I/O-bound services.
4. **Push heavy loops into C-backed libraries** (`sum`, comprehensions, NumPy) or into the database (aggregate in SQL instead of in Python).

### 3.12 Production code practices

- **Project layout.** `pyproject.toml` (PEP 621 metadata plus tool config), a package directory, `tests/`, a README with run commands, and a lockfile or pinned requirements.
- **Tooling.** `ruff` (lint and format), `mypy` (types) and `pytest` (tests), all run in CI. A pre-commit hook gives fast feedback.
- **Configuration from the environment** (12-factor), never hard-coded secrets. You'll see `pydantic-settings` from Unit 2 onward.
- **Logging.** Use `logging` with module-level loggers (`logging.getLogger(__name__)`). Configure handlers once, at the entry point.
- **Small modules** with one responsibility, and explicit dependencies passed in (dependency injection) rather than globals.

## 4. Application in a Real System

| Concept | Where it appears in an FDE system | What happens without it | Alternatives / trade-offs |
|---|---|---|---|
| Protocols + composition | LLM client interface (Anthropic/OpenAI/fake), repository interface (Postgres/in-memory) | Code married to one vendor; tests need real services | ABCs (nominal, runtime-checked) vs Protocols (structural, static) |
| Type annotations | Every service boundary; Pydantic models at API edges | Runtime `AttributeError`s in production | Gradual typing: start strict in new code |
| Exceptions hierarchy | Retry decisions (transient vs permanent); HTTP error mapping (404 vs 503) | Retrying permanent errors; 500s for user mistakes | Result types (return values) for expected failures — used here for `SupplierFailure` |
| Context managers | DB sessions, HTTP clients, timeouts, tracing spans | Connection leaks, locks never released | `try/finally` (more verbose, easy to forget) |
| Generators | Batch ingestion of documents for RAG; streaming LLM output | Memory blow-ups on large inputs | Pandas/Polars for analytics; streaming libraries |
| asyncio | FastAPI endpoints calling DBs, other services and LLMs concurrently | Thread-per-request limits; slow sequential calls | Threads (simpler for blocking libs), multiprocessing (CPU), queues/workers (long jobs) |
| pytest + fakes | CI pipeline gate; customer demo evidence | Regressions found by customers | unittest (verbose), property-based testing (Hypothesis) for edge cases |

**Concrete example.** A customer wants a service that collects prices from five supplier APIs. Called sequentially at ~400 ms each, one request takes ~2 s. Called concurrently with `asyncio`, it takes ~400 ms. That drop only holds up in production if you also add:

- **timeouts**, so one slow supplier cannot hang the request;
- **bounded concurrency**, so you don't trip supplier rate limits;
- **retries only on transient errors**, so you don't hammer a supplier that says "unknown SKU";
- **partial results**, so one failure doesn't fail the whole response.

That is the Unit 1 project.

## 5. Implementation

### 5.1 Composition with a Protocol

```python
from decimal import Decimal
from typing import Protocol


class PricingRule(Protocol):
    def apply(self, subtotal: Decimal, quantity: int) -> Decimal: ...


class PriceCalculator:
    def __init__(self, rules: list[PricingRule]) -> None:
        self._rules = tuple(rules)          # immutable copy

    def total(self, unit_price: Decimal, quantity: int) -> Decimal:
        amount = unit_price * quantity
        for rule in self._rules:            # each rule is a collaborator
            amount = rule.apply(amount, quantity)
        return amount
```

Any object with an `apply` method of the right shape is a `PricingRule`. You add behavior by writing a new rule class and passing it in. The calculator never changes (the open/closed principle).

### 5.2 A typed decorator: retry on transient errors only

```python
def retry_async(*, attempts: int = 3, base_delay: float = 0.1,
                retry_on=(TransientSupplierError,),
                sleep=asyncio.sleep):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on:
                    if attempt == attempts:
                        raise                       # give up
                    cap = base_delay * 2 ** (attempt - 1)
                    await sleep(random.uniform(0, cap))  # full jitter
        return wrapper
    return decorator
```

Key lines:

- `except retry_on` retries *only* errors classified as transient.
- **Exponential backoff** (`2 ** attempt`) gives a struggling service time to recover.
- **Jitter** (`random.uniform`) stops thousands of clients from retrying in lockstep, which is known as the *thundering herd*.
- `sleep` is injected so tests do not actually wait.

The full typed version, with `ParamSpec` and a `max_delay` cap, is in the solution.

### 5.3 Concurrency with timeout and backpressure

```python
async def quote_once(self, supplier, sku: str) -> Quote:
    async with self._semaphore:                  # ≤ N calls in flight
        try:
            async with asyncio.timeout(self._timeout):
                return await supplier.get_quote(sku)
        except TimeoutError as exc:              # built-in since 3.11
            raise SupplierTimeoutError(sku) from exc


async def best_quotes(self, skus):
    async with asyncio.TaskGroup() as tg:        # structured concurrency
        tasks = [tg.create_task(self._quote(s, sku))
                 for sku in skus for s in self._suppliers]
    outcomes = [t.result() for t in tasks]       # all finished here
```

Expected failures are converted to `SupplierFailure` values inside `_quote`, so they never escape and cancel the group. Only genuine bugs propagate as exceptions.

### 5.4 A generator and a context manager

```python
def chunked[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch                               # lazy, O(size) memory


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    result: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:                                      # runs even on error
        result["seconds"] = time.perf_counter() - start
```

### 5.5 Testing async code with fakes and AsyncMock

```python
async def test_transient_failure_is_retried() -> None:
    flaky = FakeSupplier("flaky", {"A": Decimal("1")}, fail_times=1)
    result = await QuoteAggregator([flaky], retry_attempts=2) \
        .best_quotes(["A"])
    assert result.best["A"].supplier == "flaky"
    assert flaky.calls == 2
```

The fake supplier is real code that obeys the `SupplierClient` Protocol, so the test checks *behavior* (a quote eventually arrives), not implementation details.

### 5.6 Blocking vs non-blocking: the most common async bug

```python
import asyncio
import time


async def bad() -> None:
    time.sleep(1)                 # blocks the whole event loop


async def good() -> None:
    await asyncio.sleep(1)        # yields to other tasks


async def offload_blocking() -> bytes:
    # A library with no async API? Run it in a worker thread.
    return await asyncio.to_thread(read_large_file, "data.bin")
```

### 5.7 Profiling a hotspot

```bash
python -m cProfile -s cumtime -m quotes SKU-1 SKU-2 | head -20
py-spy top --pid <PID>          # sample a live process
```

## 6. How It Connects to the Rest of the System

```text
 Unit 1 Python skills
   │
   ├── typed models ───────────► Pydantic schemas (Unit 2), ORM (Unit 3)
   ├── Protocols/DI ───────────► FastAPI dependencies, repositories,
   │                             LLM client adapters (Units 2, 3, 9)
   ├── async + timeouts ───────► async endpoints, service-to-service
   │                             calls, LLM calls (Units 2, 8, 9)
   ├── retries + idempotency ──► distributed systems (Unit 8)
   ├── generators ─────────────► document ingestion / streaming (Unit 10)
   ├── exceptions ─────────────► HTTP error mapping (Unit 2),
   │                             failure handling (Units 8, 11)
   └── pytest + fakes ─────────► CI gates (Unit 7), evals (Unit 10)
```

Every later unit is "Unit 1 plus a framework." FastAPI routes are async functions with typed parameters. SQLAlchemy sessions are context managers. LLM clients are adapters behind a Protocol. Resilience is retries, timeouts and exception classification.

## Comprehension Questions

1. Why does a `time.sleep(2)` inside an `async def` FastAPI endpoint slow down *unrelated* requests?
2. What is the practical difference between a `Protocol` and inheriting from an abstract base class?
3. Why should a retry decorator only retry *transient* errors, and why add jitter to the backoff?
4. What does `asyncio.Semaphore` protect against in the aggregator, and what does `asyncio.timeout` protect against?
5. Why does `QuoteAggregator` convert supplier errors to `SupplierFailure` values instead of letting exceptions escape the `TaskGroup`?
6. When would threads or processes be better than asyncio?
7. Why are fakes often preferable to mocks in tests?
8. What does `raise X from exc` give you during debugging?

## Comprehension Answers

1. The event loop runs in one thread. A blocking call stops that thread, so no other coroutine can run until it returns. Use `await asyncio.sleep` or `asyncio.to_thread`.
2. A Protocol is structural: any class with matching methods satisfies it, checked statically, with no import or inheritance. An ABC is nominal: classes must subclass it, and instantiating an incomplete subclass fails at runtime. Protocols decouple adapters from the interface module.
3. Retrying permanent errors (an invalid SKU, an auth failure) wastes time and load and never succeeds. Jitter spreads retries out so many clients don't hit a recovering service at the same instant (the thundering herd).
4. The semaphore bounds concurrent in-flight calls, which protects suppliers' rate limits and your own resources. The timeout bounds how long any single call can hang, which protects the overall request latency.
5. Inside a `TaskGroup`, an unhandled exception cancels all sibling tasks. Supplier failures are *expected*, so they are modeled as values, which preserves partial results. Unexpected exceptions (bugs) still propagate.
6. Threads suit blocking libraries that have no async version. Processes (or native libraries that release the GIL) suit CPU-bound work. asyncio suits many concurrent I/O waits.
7. A fake implements real behavior behind the same interface, so tests verify outcomes and survive refactoring. Mocks assert call details and break when the implementation changes even though the behavior is the same.
8. Exception chaining: the traceback shows the original low-level cause (for example `TimeoutError`) beneath the domain error (`SupplierTimeoutError`).

## Interview Questions — Theory-Based

**Q1. Explain the GIL and its impact on a Python web service.**

- *Strong answer:* The GIL lets only one thread execute Python bytecode at a time in standard CPython. I/O releases it, so threads and asyncio work well for I/O-bound services such as APIs and LLM calls. CPU-bound work does not parallelize across threads. For that I'd use multiple processes (several Uvicorn workers, a process pool, or a separate worker service), or libraries that release the GIL. Free-threaded builds exist from 3.14 but aren't the default, and library support varies.
- *Testing:* runtime understanding beyond buzzwords.
- *Follow-up:* "How many Uvicorn workers would you run, and why?" (Roughly one per CPU core for CPU-bound work. For async I/O-bound work, fewer workers with high concurrency each. Measure under load.)

**Q2. How does `async`/`await` work under the hood?**

- *Strong answer:* `async def` returns a coroutine object. The event loop drives coroutines. At each `await` on something not yet ready (a socket read, a sleep), the coroutine suspends and the loop runs other ready tasks. When the I/O completes, the loop resumes the coroutine. It is cooperative multitasking, so a task that never awaits starves everyone else.
- *Testing:* the mental model of concurrency.
- *Follow-up:* "What's the difference between `await coro()` and `asyncio.create_task(coro())`?" (`await` runs it now, sequentially. `create_task` schedules it to run concurrently, and you await the task later.)

**Q3. Composition vs inheritance: when do you use each?**

- *Strong answer:* Default to composition: objects collaborate through interfaces, so behavior is swapped by passing a different collaborator. That is easy to test and avoids fragile hierarchies. Use inheritance for true "is-a" relationships with stable shared behavior (exception hierarchies, framework base classes). In Python, Protocols give interface-based design without inheritance.
- *Testing:* design judgment.
- *Follow-up:* "Give an example where inheritance hurt maintainability."

**Q4. What problems do type annotations solve if Python doesn't enforce them?**

- *Strong answer:* Static checkers (mypy, pyright) catch None-handling errors, wrong types and attribute typos before runtime. Annotations document contracts and make refactoring safe. Pydantic uses them for runtime validation at boundaries. I run `mypy --strict` in CI on new code.
- *Follow-up:* "How do you type a decorator that preserves the wrapped signature?" (`ParamSpec` plus `TypeVar`, or PEP 695 syntax.)

**Q5. How do you make retries safe?**

- *Strong answer:* Retry only transient failures (timeouts, 429, 503, connection resets). Use exponential backoff with jitter and a cap. Limit attempts, respect `Retry-After`, and set an overall deadline. Above all, make sure the operation is **idempotent** (or uses an idempotency key), so a retry after an ambiguous failure doesn't duplicate side effects.
- *Testing:* distributed-systems maturity (Unit 8 goes deeper).
- *Follow-up:* "What happens if every layer retries three times?" (Retry amplification: 3 × 3 × 3 = 27 calls downstream. Retry at one layer, using budgets.)

**Q6. Explain generators and give a production use case.**

- *Strong answer:* A generator yields values lazily and keeps its state between `next()` calls, so memory stays constant. Use cases: streaming rows from a large export in batches for bulk inserts, and streaming LLM tokens to a client.
- *Follow-up:* "What's `yield from` / an async generator?"

**Q7. How do you debug a slow Python service?**

- *Strong answer:* Reproduce and measure, then determine whether it is CPU or waiting. Use metrics and traces to find the slow span. Use `py-spy` on the live process for CPU hotspots and `cProfile` locally. Check for blocking calls in async code (asyncio debug mode), N+1 queries and missing timeouts. Fix, and verify with the same measurement.
- *Follow-up:* "How do you profile without restarting production?" (`py-spy`.)

**Q8. Fixtures vs mocks vs fakes in pytest.**

- *Strong answer:* Fixtures provide setup through dependency injection. Mocks replace collaborators and record calls, which is useful for asserting interactions or simulating errors. Fakes are working lightweight implementations (an in-memory repository) that give behavior-focused, refactor-resistant tests. I use fakes for core logic, mocks at awkward boundaries, and a few integration tests with real services.

## Interview Questions — Application / Experience-Based

> Placeholders marked `<<personalize: ...>>` must be replaced with your own experience. If you lack professional experience, use the "limited experience" wording from *How to Use This Guide* and describe project or lab work honestly.

**A1. Tell me about a Python service or library you built.**

- *A strong answer covers:* the problem, the users, the structure (modules, interfaces), typing and testing, how it ran in production, and one design trade-off.
- *Structure:* Situation → Requirement → Architecture → Implementation → Verification → Result → Lesson.
- *Example structure:* "`<<personalize: context>>`. The requirement was `<<...>>`. I structured it as `<<services/adapters/models>>` with Protocol-based interfaces so `<<external system>>` could be faked in tests. I verified it with `<<n>>` pytest tests and `<<CI/mypy>>`. The result was `<<metric>>`. Next time I'd `<<lesson>>`."
- *Likely follow-ups:* "How did you handle configuration and secrets?" "What would you change now?"

**A2. Describe a time you used asyncio (or concurrency) to improve performance.**

- *Cover:* the baseline measurement, why the work was I/O-bound, how you bounded concurrency and set timeouts, how you handled partial failure, and the measured improvement.
- *Lab-based honest version:* "In a hands-on project I aggregated quotes from several simulated suppliers. Sequential calls took about the sum of the latencies; with a TaskGroup, a semaphore and per-call timeouts the request took about the slowest call. I proved it with a test that asserts total time stays under one second even with a 5-second supplier."
- *Follow-ups:* "How did you avoid overloading the downstream?" "What happened when one call failed?"

**A3. Walk me through a difficult bug you debugged in Python.**

- *Cover:* symptom, evidence gathered, hypothesis, how you confirmed it, the fix, and the regression test.
- *Follow-ups:* "What tool told you the most?" "How did you prevent recurrence?"

**A4. How do you structure tests for code that talks to external services?**

- *Cover:* interfaces and fakes, mocks for error simulation, contract or integration tests, test data, and determinism (injected time and sleep).
- *Follow-ups:* "How do you test retries without slow tests?"

**A5. Tell me about a code review where you pushed back or were pushed back on.**

- *Cover:* the technical issue (typing, error handling, a blocking call), how you communicated it, and the outcome.

**A6. How do you keep a Python codebase maintainable as a team grows?**

- *Cover:* layout, ruff, mypy, pytest in CI, pre-commit, review guidelines, documentation and ADRs.

## Troubleshooting Scenarios

**T1. An async endpoint blocks other requests.**

```text
SYMPTOM     p95 latency for ALL endpoints spikes when /report is called
WHAT TO CHECK  is any sync I/O or CPU loop inside async def? asyncio
               debug logs ("Executing <Task ...> took 1.2 seconds")
LIKELY CAUSES  requests/psycopg2/time.sleep in async def; CPU-heavy
               JSON/PDF processing on the loop
HOW TO CONFIRM PYTHONASYNCIODEBUG=1; py-spy dump shows the loop thread
               inside a blocking call
FIX         use async client; or asyncio.to_thread(); or make the
            endpoint `def` (FastAPI runs it in a threadpool); move CPU
            work to a worker process
PREVENTION  lint rule (ruff ASYNC), code review checklist, load test
```

*Strong interview answer:* "The loop is single-threaded, so one blocking call freezes every task on it. I'd confirm with asyncio debug mode or py-spy, then switch to an async client, or offload the call to a thread or a worker."

**T2. A retry storm makes an outage worse.**

```text
SYMPTOM     downstream at 100% CPU, our error rate climbing, traffic 5x
WHAT TO CHECK  retry counts per request; retry config at each layer
LIKELY CAUSES  retries without backoff/jitter; retries at client,
               SDK and proxy layers; retrying non-transient errors
HOW TO CONFIRM logs/metrics show attempts per request; traces show
               repeated identical spans
FIX         exponential backoff + jitter, cap attempts, single retry
            layer, circuit breaker, respect Retry-After
PREVENTION  retry budgets, load tests with failure injection
```

**T3. Memory grows until the process is killed.**

```text
SYMPTOM     RSS climbs steadily; container OOMKilled
WHAT TO CHECK  unbounded caches/dicts, lists accumulating results,
               reading whole files/responses into memory
LIKELY CAUSES  module-level cache with no eviction; loading a full
               export instead of streaming
HOW TO CONFIRM tracemalloc snapshots diff; memory profiler; heap dump
FIX         generators/streaming; bounded caches (functools.lru_cache
            maxsize, cachetools TTL); batch processing
PREVENTION  memory limits + alerts, load test with realistic data
```

**T4. A test passes locally but fails in CI intermittently.**

```text
SYMPTOM     flaky test_aggregator in CI
WHAT TO CHECK  real sleeps/timeouts tight vs slow CI; shared state
               between tests; ordering assumptions; random seeds
LIKELY CAUSES  timing-based assertions; global mutable fixtures
HOW TO CONFIRM run with `pytest -p no:randomly --count=50` locally
               (pytest-repeat), compare CI logs
FIX         inject clock/sleep; generous bounds; isolate fixtures
PREVENTION  no wall-clock dependencies in unit tests
```

**T5. "Task was destroyed but it is pending" or "coroutine was never awaited".**

```text
SYMPTOM     warnings in logs; work silently not done
CAUSES      calling an async function without await; create_task
            without keeping a reference or awaiting it
CONFIRM     asyncio debug mode shows where the coroutine was created
FIX         await it, or use TaskGroup so tasks are always awaited
PREVENTION  mypy/ruff flag un-awaited coroutines; TaskGroup by default
```

## Unit Practice Project — Async Supplier Quote Aggregator

### Project Goal

Build a small, production-quality Python package that requests price quotes from several suppliers **concurrently**, with per-call **timeouts**, **bounded concurrency** and **retries on transient errors only**. It keeps the cheapest quote per SKU, reports failures without crashing, and prices an order with **composable pricing rules**. Completing it proves you can write typed, async, tested Python with sound failure handling, which every later unit depends on.

### Architecture

```text
 CLI (python -m quotes)
        │
        ▼
 QuoteAggregator ──uses──► retry_async (transient only)
        │  TaskGroup + Semaphore + asyncio.timeout
        ▼
 SupplierClient (Protocol) ◄── FakeSupplier (latency, failures)
        │
        ▼
 Quote / SupplierFailure (frozen dataclasses)
        │
        ▼
 PriceCalculator ──has──► [BulkDiscount, FlatShipping] (rules)
```

### Requirements

1. `Quote` and `SupplierFailure` are immutable. `Quote` rejects non-positive prices and negative availability.
2. `PriceCalculator.total(unit_price, quantity)` applies rules in order and rounds half-up to cents. Quantity must be positive.
3. `BulkDiscount(min_quantity, percent)` and `FlatShipping(fee, free_above)` implement `PricingRule`.
4. `retry_async` retries only exceptions in `retry_on` (default: transient errors). It uses exponential backoff with full jitter capped at `max_delay`, re-raises after the last attempt, and has an injectable `sleep`.
5. `QuoteAggregator.best_quotes(skus)`:
   - de-duplicates SKUs;
   - queries every supplier for every SKU concurrently;
   - bounds each call with a timeout and the total in-flight calls with a semaphore;
   - returns the cheapest quote per SKU, plus a list of failures.
6. `chunked(items, size)` is a lazy generator. `timed(label)` measures elapsed time even when the block raises.
7. `python -m quotes SKU-1 SKU-2` prints a JSON report.

### Technical Requirements

- Python 3.12+ and only the standard library at runtime.
- `pytest` and `pytest-asyncio` (auto mode) for tests; `mypy --strict`; `ruff`.
- No real network calls: suppliers are fakes behind a Protocol.

### Project Structure

```text
solution/
├── quotes/
│   ├── __init__.py
│   ├── __main__.py
│   ├── aggregator.py
│   ├── errors.py
│   ├── models.py
│   ├── pricing.py
│   ├── retry.py
│   ├── suppliers.py
│   └── utils.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_aggregator.py
│   ├── test_models.py
│   ├── test_pricing.py
│   ├── test_retry.py
│   └── test_utils.py
├── README.md
├── pyproject.toml
└── requirements-dev.txt
```


### Step-by-Step Implementation

1. **Create the environment and run the starter tests.**
   - *What:* a virtualenv, `pip install -r requirements-dev.txt`, then `pytest -q`.
   - *Why:* to see the specification. Most tests fail with `NotImplementedError`.
   - *Connects to:* everything below.
   - *Test:* `pytest -q` runs and reports failures, not import errors.
2. **Read `models.py`, `errors.py` and `suppliers.py`** (already implemented).
   - *Why:* they define the domain and the interface.
   - *Note:* transient and permanent errors are separate classes, and `FakeSupplier` can simulate latency and failures.
   - *Test:* `pytest tests/test_models.py` passes.
3. **Implement the pricing rules and the calculator** (`pricing.py`).
   - *Why:* practise composition over inheritance and Decimal money handling.
   - *Test:* `pytest tests/test_pricing.py`.
4. **Implement `chunked` and `timed`** (`utils.py`).
   - *Why:* practise generators and context managers with `try/finally`.
   - *Test:* `pytest tests/test_utils.py`.
5. **Implement `retry_async`** (`retry.py`).
   - *Why:* practise a decorator with an injectable `sleep`, transient-only retry, backoff, jitter and a cap.
   - *Test:* `pytest tests/test_retry.py`, then write the missing backoff-cap test.
6. **Implement `_quote_once`** (semaphore plus timeout plus error translation).
   - *Why:* this is the I/O boundary. Timeouts must become a domain error.
   - *Test:* `test_slow_supplier_times_out_without_blocking_others`.
7. **Implement `_quote`** (retry wrapper plus conversion of `QuoteError` to `SupplierFailure`).
   - *Test:* `test_unknown_sku_is_reported_not_raised`.
8. **Implement `best_quotes`** (dedupe, TaskGroup, cheapest selection).
   - *Test:* the whole `tests/test_aggregator.py`, plus the two TODO tests you write.
9. **Run the CLI**, then `ruff check .` and `mypy`.
   - *Why:* production code passes lint and strict typing.
   - *Test:* the CLI output matches the Expected Behavior section below.

### Starter Code

The starter contains the full structure with working models, errors and fake suppliers. These files contain the `TODO`s you must implement:

**File: `quotes/pricing.py`**

```python
"""Pricing rules composed into a calculator (composition > inheritance)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

CENT = Decimal("0.01")


class PricingRule(Protocol):
    def apply(self, subtotal: Decimal, quantity: int) -> Decimal: ...


@dataclass(frozen=True)
class BulkDiscount:
    """Percentage off when quantity reaches a threshold."""

    min_quantity: int
    percent: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        # TODO: implement - reduce subtotal by `percent` % when
        # quantity >= min_quantity, otherwise return subtotal unchanged.
        raise NotImplementedError


@dataclass(frozen=True)
class FlatShipping:
    """Adds a fixed shipping fee below a free-shipping threshold."""

    fee: Decimal
    free_above: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        # TODO: implement - add `fee` unless subtotal >= free_above.
        raise NotImplementedError


class PriceCalculator:
    """Applies rules in order. New behaviour = new rule, no subclassing."""

    def __init__(self, rules: Sequence[PricingRule] = ()) -> None:
        self._rules = tuple(rules)

    def total(self, unit_price: Decimal, quantity: int) -> Decimal:
        # TODO: implement
        # 1. reject quantity <= 0 with ValueError
        # 2. start from unit_price * quantity
        # 3. apply each rule in order
        # 4. round to cents with ROUND_HALF_UP (Decimal.quantize)
        raise NotImplementedError
```


**File: `quotes/retry.py`**

```python
"""Async retry with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from quotes.errors import TransientSupplierError

P = ParamSpec("P")
T = TypeVar("T")
log = logging.getLogger(__name__)


def retry_async(
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (TransientSupplierError,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry an async function on *transient* errors only.

    ``sleep`` is injectable so tests run instantly and deterministically.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # TODO: implement
            # - call `await func(*args, **kwargs)` up to `attempts` times
            # - only catch exceptions listed in `retry_on`
            # - re-raise on the last attempt
            # - between attempts await sleep(delay) where delay is a
            #   random value in [0, min(max_delay, base_delay * 2**(n-1))]
            raise NotImplementedError

        return wrapper

    return decorator
```


**File: `quotes/utils.py`**

```python
"""Small helpers: a batching generator and a timing context manager."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

log = logging.getLogger(__name__)


def chunked[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of at most ``size`` items, lazily (constant memory)."""
    # TODO: implement as a generator (use `yield`); reject size < 1.
    # Hint: itertools.islice takes the next N items from an iterator.
    raise NotImplementedError


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    """Measure elapsed wall time; the result is available after exit."""
    # TODO: implement with time.perf_counter(); store elapsed seconds in
    # result["seconds"] even when the with-block raises (try/finally).
    result: dict[str, float] = {}
    yield result
```


**File: `quotes/aggregator.py`**

```python
"""Concurrent quote aggregation with timeouts and bounded concurrency."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from quotes.models import Quote, SupplierFailure
from quotes.suppliers import SupplierClient

log = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    best: dict[str, Quote] = field(default_factory=dict)
    failures: list[SupplierFailure] = field(default_factory=list)


class QuoteAggregator:
    """Asks every supplier for every SKU and keeps the cheapest quote.

    * Each call is bounded by ``timeout`` seconds (asyncio.timeout).
    * At most ``max_concurrency`` calls are in flight (Semaphore).
    * Transient errors are retried; failures never abort other calls.
    """

    def __init__(
        self,
        suppliers: Sequence[SupplierClient],
        *,
        timeout: float = 1.0,
        max_concurrency: int = 10,
        retry_attempts: int = 3,
    ) -> None:
        if not suppliers:
            raise ValueError("at least one supplier is required")
        self._suppliers = list(suppliers)
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._retry_attempts = retry_attempts

    async def _quote_once(
        self, supplier: SupplierClient, sku: str
    ) -> Quote:
        # TODO: acquire the semaphore, wrap supplier.get_quote(sku) in
        # `async with asyncio.timeout(self._timeout)`, and convert the
        # built-in TimeoutError into SupplierTimeoutError (use `from`).
        raise NotImplementedError

    async def _quote(
        self, supplier: SupplierClient, sku: str
    ) -> Quote | SupplierFailure:
        # TODO: wrap _quote_once with retry_async(attempts=...) and turn
        # any QuoteError into a SupplierFailure value (do not raise).
        raise NotImplementedError

    async def best_quotes(self, skus: Iterable[str]) -> AggregationResult:
        # TODO:
        # 1. de-duplicate SKUs while keeping order
        # 2. start one task per (sku, supplier) inside asyncio.TaskGroup
        # 3. collect failures and keep the cheapest Quote per SKU
        raise NotImplementedError
```


### Practice Tasks

1. **Normal behavior.**
   - Cheapest quote per SKU across suppliers.
   - Rules applied in order.
   - Totals rounded to cents.
2. **Validation.**
   - `quantity <= 0` raises `ValueError`.
   - `chunked(size < 1)` raises `ValueError`.
   - `retry_async(attempts=0)` raises `ValueError`.
   - The aggregator requires at least one supplier.
3. **Errors.**
   - A timeout becomes `SupplierTimeoutError`; unknown SKUs become `InvalidSkuError`.
   - Both are reported as `SupplierFailure` values and never raised from `best_quotes`.
4. **Edge cases.**
   - Duplicate SKUs are requested once.
   - A SKU no supplier knows is absent from `best` and present in `failures`.
   - A slow supplier must not delay the result past the timeout.
   - Concurrency never exceeds `max_concurrency`.
5. **Tests to write.** `test_transient_failure_is_retried`, `test_duplicate_skus_are_requested_once` and `test_backoff_delays_are_capped`.

### Hints

1. *Pricing:* `subtotal * (1 - percent / 100)`. Round once at the end with `amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
2. *chunked:* `iterator = iter(items)`, then loop while `batch := list(islice(iterator, size))` is non-empty.
3. *timed:* put the `yield` inside `try:` and compute elapsed time in `finally:`.
4. *retry:* `for attempt in range(1, attempts + 1)`. Inside `except retry_on:`, re-raise if `attempt == attempts`.
5. *Timeouts:* `asyncio.timeout()` raises the built-in `TimeoutError`. Catch it and `raise SupplierTimeoutError(...) from exc`.
6. *TaskGroup:* create tasks inside `async with asyncio.TaskGroup() as tg:`. After the block, every task is done, so call `task.result()`.
7. *Dedupe preserving order:* `list(dict.fromkeys(skus))`.

### Expected Behavior

```text
$ python -m quotes SKU-1 SKU-2
{
  "best": {
    "SKU-1": {"supplier": "globex", "unit_price": "9.10",
              "total_for_12": "103.74"},
    "SKU-2": {"supplier": "globex", "unit_price": "4.00",
              "total_for_12": "52.60"}
  },
  "failures": [
    {"sku": "SKU-1", "supplier": "slowco",
     "reason": "slowco timed out for SKU-1"},
    {"sku": "SKU-2", "supplier": "acme",
     "reason": "acme has no SKU SKU-2"},
    {"sku": "SKU-2", "supplier": "slowco",
     "reason": "slowco timed out for SKU-2"}
  ],
  "seconds": 1.0
}
```

(Output is reformatted here for width.) Note what the output shows:

- `globex` fails once with a transient error and is retried successfully.
- `slowco` (5 s latency) times out. With `timeout=0.5` and two attempts, the whole run stays at about 1 second rather than 5–10 seconds.

Failure examples:

```python
PriceCalculator().total(Decimal("1"), 0)   # ValueError
QuoteAggregator([])                        # ValueError
list(chunked([1, 2], 0))                   # ValueError
```

### Testing Requirements

- **Unit tests:** models, pricing, retry, utils.
- **Async behavior tests:** cheapest selection, timeout isolation, retry of transient failures, no retry of permanent failures, dedupe, the concurrency bound.
- **Negative tests:** invalid inputs raise `ValueError`.
- **Edge cases:** an unknown SKU, all suppliers failing, duplicate SKUs.

```bash
pytest -q                 # all tests
pytest -q -k aggregator   # one area
mypy                      # strict typing (configured in pyproject)
ruff check .              # lint
```

### Final Runnable Solution

**File: `README.md`**

````markdown
# Unit 1 Project — Async Supplier Quote Aggregator

Asks several suppliers for prices concurrently, with per-call timeouts,
bounded concurrency and retries on transient errors, then keeps the
cheapest quote per SKU and prices an order with composable rules.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m quotes SKU-1 SKU-2     # demo with fake suppliers
pytest -q                        # tests
ruff check . && mypy             # lint + strict type check
```
````

**File: `pyproject.toml`**

```toml
[project]
name = "quotes"
version = "1.0.0"
description = "Unit 1 project: async supplier quote aggregator"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=1.0", "mypy>=1.10", "ruff>=0.6"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 76
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.mypy]
strict = true
packages = ["quotes"]
```

**File: `quotes/__init__.py`**

```python
"""Async supplier quote aggregator (Unit 1 project)."""

from quotes.aggregator import AggregationResult, QuoteAggregator
from quotes.models import Quote

__all__ = ["AggregationResult", "Quote", "QuoteAggregator"]
```

**File: `quotes/__main__.py`**

```python
"""Demo: python -m quotes SKU-1 SKU-2"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import asdict
from decimal import Decimal

from quotes.aggregator import QuoteAggregator
from quotes.pricing import BulkDiscount, FlatShipping, PriceCalculator
from quotes.suppliers import FakeSupplier
from quotes.utils import timed


async def main(skus: list[str]) -> int:
    suppliers = [
        FakeSupplier("acme", {"SKU-1": Decimal("9.50")}, latency=0.05),
        FakeSupplier(
            "globex",
            {"SKU-1": Decimal("9.10"), "SKU-2": Decimal("4.00")},
            latency=0.08,
            fail_times=1,
        ),
        FakeSupplier("slowco", {"SKU-2": Decimal("3.00")}, latency=5.0),
    ]
    aggregator = QuoteAggregator(suppliers, timeout=0.5, retry_attempts=2)
    calculator = PriceCalculator(
        [
            BulkDiscount(10, Decimal("5")),
            FlatShipping(Decimal("7"), Decimal("50")),
        ]
    )
    with timed("aggregation") as timing:
        result = await aggregator.best_quotes(skus)
    output = {
        "best": {
            sku: {
                "supplier": q.supplier,
                "unit_price": str(q.unit_price),
                "total_for_12": str(calculator.total(q.unit_price, 12)),
            }
            for sku, q in result.best.items()
        },
        "failures": [asdict(f) for f in result.failures],
        "seconds": round(timing["seconds"], 3),
    }
    print(json.dumps(output, indent=2))
    return 0 if result.best else 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(message)s"
    )
    raise SystemExit(asyncio.run(main(sys.argv[1:] or ["SKU-1", "SKU-2"])))
```

**File: `quotes/aggregator.py`**

```python
"""Concurrent quote aggregation with timeouts and bounded concurrency."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from quotes.errors import QuoteError, SupplierTimeoutError
from quotes.models import Quote, SupplierFailure
from quotes.retry import retry_async
from quotes.suppliers import SupplierClient

log = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    best: dict[str, Quote] = field(default_factory=dict)
    failures: list[SupplierFailure] = field(default_factory=list)


class QuoteAggregator:
    """Asks every supplier for every SKU and keeps the cheapest quote.

    * Each call is bounded by ``timeout`` seconds (asyncio.timeout).
    * At most ``max_concurrency`` calls are in flight (Semaphore).
    * Transient errors are retried; failures never abort other calls.
    """

    def __init__(
        self,
        suppliers: Sequence[SupplierClient],
        *,
        timeout: float = 1.0,
        max_concurrency: int = 10,
        retry_attempts: int = 3,
    ) -> None:
        if not suppliers:
            raise ValueError("at least one supplier is required")
        self._suppliers = list(suppliers)
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._retry_attempts = retry_attempts

    async def _quote_once(
        self, supplier: SupplierClient, sku: str
    ) -> Quote:
        async with self._semaphore:
            try:
                async with asyncio.timeout(self._timeout):
                    return await supplier.get_quote(sku)
            except TimeoutError as exc:
                raise SupplierTimeoutError(
                    f"{supplier.name} timed out for {sku}"
                ) from exc

    async def _quote(
        self, supplier: SupplierClient, sku: str
    ) -> Quote | SupplierFailure:
        call = retry_async(attempts=self._retry_attempts, base_delay=0.05)(
            self._quote_once
        )
        try:
            return await call(supplier, sku)
        except QuoteError as exc:
            log.info("no quote from %s for %s: %s", supplier.name, sku, exc)
            return SupplierFailure(sku, supplier.name, str(exc))

    async def best_quotes(self, skus: Iterable[str]) -> AggregationResult:
        unique = list(dict.fromkeys(skus))  # dedupe, keep order
        # TaskGroup: if *we* have a bug (unexpected exception) all tasks
        # are cancelled. Expected supplier errors are converted to
        # SupplierFailure values inside _quote, so they never escape.
        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(self._quote(supplier, sku))
                for sku in unique
                for supplier in self._suppliers
            ]
        result = AggregationResult()
        for task in tasks:
            outcome = task.result()
            if isinstance(outcome, SupplierFailure):
                result.failures.append(outcome)
                continue
            current = result.best.get(outcome.sku)
            if current is None or outcome.unit_price < current.unit_price:
                result.best[outcome.sku] = outcome
        return result
```

**File: `quotes/errors.py`**

```python
"""Exception hierarchy. Callers catch the narrowest type they handle."""


class QuoteError(Exception):
    """Base class for all errors raised by this package."""


class TransientSupplierError(QuoteError):
    """Temporary failure (network blip, 503). Safe to retry."""


class SupplierTimeoutError(TransientSupplierError):
    """The supplier did not answer within the allowed time."""


class PermanentSupplierError(QuoteError):
    """Failure that will not go away on retry (bad SKU, auth error)."""


class InvalidSkuError(PermanentSupplierError):
    """The supplier does not recognise the SKU."""
```

**File: `quotes/models.py`**

```python
"""Domain models. Frozen dataclasses are immutable and hashable."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Quote:
    """A supplier's price for one SKU."""

    sku: str
    supplier: str
    unit_price: Decimal
    available: int

    def __post_init__(self) -> None:
        # Invariants are enforced at construction time, so every Quote
        # that exists in the program is valid.
        if self.unit_price <= 0:
            raise ValueError("unit_price must be positive")
        if self.available < 0:
            raise ValueError("available must be >= 0")


@dataclass(frozen=True, slots=True)
class SupplierFailure:
    """Records why a supplier could not quote a SKU."""

    sku: str
    supplier: str
    reason: str
```

**File: `quotes/pricing.py`**

```python
"""Pricing rules composed into a calculator (composition > inheritance)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

CENT = Decimal("0.01")


class PricingRule(Protocol):
    def apply(self, subtotal: Decimal, quantity: int) -> Decimal: ...


@dataclass(frozen=True)
class BulkDiscount:
    """Percentage off when quantity reaches a threshold."""

    min_quantity: int
    percent: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        if quantity >= self.min_quantity:
            return subtotal * (1 - self.percent / 100)
        return subtotal


@dataclass(frozen=True)
class FlatShipping:
    """Adds a fixed shipping fee below a free-shipping threshold."""

    fee: Decimal
    free_above: Decimal

    def apply(self, subtotal: Decimal, quantity: int) -> Decimal:
        return (
            subtotal if subtotal >= self.free_above else subtotal + self.fee
        )


class PriceCalculator:
    """Applies rules in order. New behaviour = new rule, no subclassing."""

    def __init__(self, rules: Sequence[PricingRule] = ()) -> None:
        self._rules = tuple(rules)

    def total(self, unit_price: Decimal, quantity: int) -> Decimal:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        amount = unit_price * quantity
        for rule in self._rules:
            amount = rule.apply(amount, quantity)
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
```

**File: `quotes/retry.py`**

```python
"""Async retry with exponential backoff and full jitter."""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from quotes.errors import TransientSupplierError

P = ParamSpec("P")
T = TypeVar("T")
log = logging.getLogger(__name__)


def retry_async(
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    retry_on: tuple[type[BaseException], ...] = (TransientSupplierError,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry an async function on *transient* errors only.

    ``sleep`` is injectable so tests run instantly and deterministically.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:
                    if attempt == attempts:
                        raise
                    # Full jitter: random delay in [0, capped exponential].
                    cap = min(max_delay, base_delay * 2 ** (attempt - 1))
                    delay = random.uniform(0, cap)
                    log.warning(
                        "attempt %d/%d failed (%s); retrying in %.3fs",
                        attempt,
                        attempts,
                        exc,
                        delay,
                    )
                    await sleep(delay)
            raise AssertionError("unreachable")  # pragma: no cover

        return wrapper

    return decorator
```

**File: `quotes/suppliers.py`**

```python
"""Supplier clients. The Protocol describes behaviour, not ancestry."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from quotes.errors import InvalidSkuError, TransientSupplierError
from quotes.models import Quote


class SupplierClient(Protocol):
    """Anything with a ``name`` and an async ``get_quote`` qualifies."""

    name: str

    async def get_quote(self, sku: str) -> Quote: ...


class FakeSupplier:
    """In-memory supplier used for demos and tests.

    ``latency`` simulates network delay. ``fail_times`` makes the first N
    calls raise a transient error, which lets tests exercise retries.
    """

    def __init__(
        self,
        name: str,
        prices: Mapping[str, Decimal],
        *,
        latency: float = 0.0,
        fail_times: int = 0,
    ) -> None:
        self.name = name
        self._prices = dict(prices)
        self._latency = latency
        self._failures_left = fail_times
        self.calls = 0

    async def get_quote(self, sku: str) -> Quote:
        self.calls += 1
        # asyncio.sleep yields to the event loop; time.sleep would block it.
        await asyncio.sleep(self._latency)
        if self._failures_left > 0:
            self._failures_left -= 1
            raise TransientSupplierError(f"{self.name} temporarily down")
        if sku not in self._prices:
            raise InvalidSkuError(f"{self.name} has no SKU {sku}")
        return Quote(
            sku=sku,
            supplier=self.name,
            unit_price=self._prices[sku],
            available=100,
        )
```

**File: `quotes/utils.py`**

```python
"""Small helpers: a batching generator and a timing context manager."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from itertools import islice

log = logging.getLogger(__name__)


def chunked[T](items: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of at most ``size`` items, lazily (constant memory)."""
    if size < 1:
        raise ValueError("size must be >= 1")
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


@contextmanager
def timed(label: str) -> Iterator[dict[str, float]]:
    """Measure elapsed wall time; the result is available after exit."""
    result: dict[str, float] = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        # finally runs on success AND on exceptions, like a with-block
        # guarantee for cleanup.
        result["seconds"] = time.perf_counter() - start
        log.info("%s took %.3fs", label, result["seconds"])
```

**File: `requirements-dev.txt`**

```text
pytest>=8
pytest-asyncio>=1.0
mypy>=1.10
ruff>=0.6
```

**File: `tests/__init__.py`**

```python

```

**File: `tests/conftest.py`**

```python
from decimal import Decimal

import pytest

from quotes.suppliers import FakeSupplier


@pytest.fixture
def cheap() -> FakeSupplier:
    return FakeSupplier("cheap", {"A": Decimal("1.00"), "B": Decimal("5")})


@pytest.fixture
def pricey() -> FakeSupplier:
    return FakeSupplier("pricey", {"A": Decimal("2.00"), "B": Decimal("4")})
```

**File: `tests/test_aggregator.py`**

```python
import asyncio
from decimal import Decimal

import pytest

from quotes.aggregator import QuoteAggregator
from quotes.models import Quote
from quotes.suppliers import FakeSupplier


async def test_picks_cheapest_per_sku(
    cheap: FakeSupplier, pricey: FakeSupplier
) -> None:
    result = await QuoteAggregator([cheap, pricey]).best_quotes(["A", "B"])
    assert result.best["A"].supplier == "cheap"
    assert result.best["B"].supplier == "pricey"
    assert result.failures == []


async def test_unknown_sku_is_reported_not_raised(
    cheap: FakeSupplier,
) -> None:
    result = await QuoteAggregator([cheap]).best_quotes(["A", "ZZZ"])
    assert set(result.best) == {"A"}
    assert result.failures[0].sku == "ZZZ"


async def test_slow_supplier_times_out_without_blocking_others(
    cheap: FakeSupplier,
) -> None:
    slow = FakeSupplier("slow", {"A": Decimal("0.10")}, latency=5)
    aggregator = QuoteAggregator(
        [cheap, slow], timeout=0.05, retry_attempts=1
    )
    loop = asyncio.get_running_loop()
    start = loop.time()
    result = await aggregator.best_quotes(["A"])
    assert loop.time() - start < 1
    assert result.best["A"].supplier == "cheap"
    assert "timed out" in result.failures[0].reason


async def test_transient_failure_is_retried() -> None:
    flaky = FakeSupplier("flaky", {"A": Decimal("1")}, fail_times=1)
    result = await QuoteAggregator([flaky], retry_attempts=2).best_quotes(
        ["A"]
    )
    assert result.best["A"].supplier == "flaky"
    assert flaky.calls == 2


async def test_duplicate_skus_are_requested_once(
    cheap: FakeSupplier,
) -> None:
    await QuoteAggregator([cheap]).best_quotes(["A", "A", "A"])
    assert cheap.calls == 1


class CountingSupplier:
    """Records the maximum number of concurrent calls."""

    def __init__(self) -> None:
        self.name = "counting"
        self.active = 0
        self.peak = 0

    async def get_quote(self, sku: str) -> Quote:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return Quote(sku, self.name, Decimal("1"), 1)


async def test_concurrency_is_bounded() -> None:
    supplier = CountingSupplier()
    aggregator = QuoteAggregator([supplier], max_concurrency=3)
    await aggregator.best_quotes([f"SKU-{i}" for i in range(20)])
    assert supplier.peak == 3


def test_requires_a_supplier() -> None:
    with pytest.raises(ValueError):
        QuoteAggregator([])
```

**File: `tests/test_models.py`**

```python
from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from quotes.models import Quote


def test_quote_is_immutable() -> None:
    quote = Quote("A", "s", Decimal("1"), 1)
    with pytest.raises(FrozenInstanceError):
        quote.unit_price = Decimal("2")  # type: ignore[misc]


@pytest.mark.parametrize(
    ("price", "available"), [(Decimal("0"), 1), (Decimal("1"), -1)]
)
def test_quote_rejects_invalid_values(
    price: Decimal, available: int
) -> None:
    with pytest.raises(ValueError):
        Quote("A", "s", price, available)
```

**File: `tests/test_pricing.py`**

```python
from decimal import Decimal

import pytest

from quotes.pricing import BulkDiscount, FlatShipping, PriceCalculator


def test_no_rules_is_price_times_quantity() -> None:
    assert PriceCalculator().total(Decimal("2.50"), 4) == Decimal("10.00")


def test_rules_apply_in_order() -> None:
    calc = PriceCalculator(
        [
            BulkDiscount(10, Decimal("10")),
            FlatShipping(Decimal("5"), Decimal("100")),
        ]
    )
    # 10 * 9.00 = 90 -> 10% off = 81 -> below 100 so +5 shipping = 86
    assert calc.total(Decimal("9.00"), 10) == Decimal("86.00")


def test_bulk_discount_not_applied_below_threshold() -> None:
    rule = BulkDiscount(10, Decimal("10"))
    assert rule.apply(Decimal("50"), 9) == Decimal("50")


def test_rounds_half_up_to_cents() -> None:
    calc = PriceCalculator([BulkDiscount(1, Decimal("33.333"))])
    assert calc.total(Decimal("1.00"), 1) == Decimal("0.67")


@pytest.mark.parametrize("quantity", [0, -3])
def test_rejects_non_positive_quantity(quantity: int) -> None:
    with pytest.raises(ValueError):
        PriceCalculator().total(Decimal("1"), quantity)
```

**File: `tests/test_retry.py`**

```python
from unittest.mock import AsyncMock

import pytest

from quotes.errors import InvalidSkuError, TransientSupplierError
from quotes.retry import retry_async


async def test_returns_after_transient_failures() -> None:
    sleep = AsyncMock()
    func = AsyncMock(side_effect=[TransientSupplierError(), "ok"])
    wrapped = retry_async(attempts=3, sleep=sleep)(func)

    assert await wrapped() == "ok"
    assert func.await_count == 2
    sleep.assert_awaited_once()


async def test_raises_after_last_attempt() -> None:
    func = AsyncMock(side_effect=TransientSupplierError("down"))
    wrapped = retry_async(attempts=3, sleep=AsyncMock())(func)

    with pytest.raises(TransientSupplierError):
        await wrapped()
    assert func.await_count == 3


async def test_does_not_retry_permanent_errors() -> None:
    func = AsyncMock(side_effect=InvalidSkuError("nope"))
    wrapped = retry_async(attempts=5, sleep=AsyncMock())(func)

    with pytest.raises(InvalidSkuError):
        await wrapped()
    assert func.await_count == 1


async def test_backoff_delays_are_capped() -> None:
    sleep = AsyncMock()
    func = AsyncMock(side_effect=TransientSupplierError())
    wrapped = retry_async(
        attempts=6, base_delay=1.0, max_delay=2.0, sleep=sleep
    )(func)
    with pytest.raises(TransientSupplierError):
        await wrapped()
    delays = [call.args[0] for call in sleep.await_args_list]
    assert len(delays) == 5
    assert all(0 <= d <= 2.0 for d in delays)


def test_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        retry_async(attempts=0)
```

**File: `tests/test_utils.py`**

```python
import itertools

import pytest

from quotes.utils import chunked, timed


def test_chunked_splits_with_remainder() -> None:
    assert list(chunked(range(5), 2)) == [[0, 1], [2, 3], [4]]


def test_chunked_is_lazy() -> None:
    # An infinite iterator works because chunked never materialises it.
    first = next(chunked(itertools.count(), 3))
    assert first == [0, 1, 2]


def test_chunked_rejects_bad_size() -> None:
    with pytest.raises(ValueError):
        list(chunked([1], 0))


def test_timed_records_even_on_error() -> None:
    with pytest.raises(RuntimeError):
        with timed("boom") as result:
            raise RuntimeError
    assert result["seconds"] >= 0
```


### How to Run

```bash
cd projects/unit01-python/solution
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m quotes SKU-1 SKU-2
pytest -q
mypy && ruff check .
```

### Verify the Solution

1. `pytest -q` shows **25 passed**.
2. `python -m quotes SKU-1 SKU-2` finishes in about 1 second (not 5+), even though `slowco` has 5 s latency.
3. The INFO logs show the retry warning for `globex`, then success.
4. `mypy` reports *Success: no issues found*.
5. Change `max_concurrency` to 1 in the CLI and confirm the run gets slower. That is evidence the semaphore works.

### Project Interview Debrief

1. **Why did you model supplier failures as values instead of exceptions?**
   Failures are expected and partial results are valuable. Inside a TaskGroup, an escaping exception cancels the sibling tasks. Values keep the successful quotes and make failures reportable. Bugs still raise.
2. **What would break first at scale?**
   Supplier rate limits and connection limits. I'd add per-supplier semaphores, a shared `httpx.AsyncClient` with connection pooling, respect for `Retry-After`, a circuit breaker for failing suppliers, and caching of recent quotes.
3. **How would you make this production-ready?**
   Real HTTP adapters with timeouts and pooling, configuration from the environment, structured logging with correlation IDs, metrics (latency and failure rate per supplier), an overall deadline per request, and contract tests against supplier sandboxes.
4. **Why inject `sleep` into the retry decorator?**
   Determinism and speed. Tests assert the delays without waiting, and production uses the real `asyncio.sleep`.
5. **Why `Decimal` instead of `float` for money?**
   Binary floats can't represent most decimal fractions exactly (`0.1 + 0.2 != 0.3`). `Decimal` with explicit rounding gives correct, auditable totals.


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

```text
solution/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── routes_auth.py
│   │   └── routes_customers.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── errors.py
│   │   └── security.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── customer.py
│   │   └── user.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── customer_repo.py
│   │   └── user_repo.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── customer_service.py
│   ├── __init__.py
│   ├── config.py
│   └── main.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_customers.py
│   ├── test_service.py
│   └── test_validation.py
├── .env.example
├── README.md
├── pyproject.toml
├── requirements-dev.txt
└── requirements.txt
```


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

**File: `app/core/security.py`**

```python
"""Password hashing and JWT handling."""

from __future__ import annotations

import jwt  # noqa: F401  (you will need it)
from pwdlib import PasswordHash

from app.config import Settings
from app.models.user import Role, User  # noqa: F401

# Argon2id via pwdlib: the hashing approach the FastAPI docs now show.
password_hasher = PasswordHash.recommended()


class InvalidTokenError(Exception):
    """Token missing, expired, tampered with, or for another audience."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, settings: Settings) -> str:
    """Return a signed JWT for ``user``.

    TODO: implement with jwt.encode(...). Include the claims
    sub, role, iss, aud, iat and exp (now + access_token_minutes) and
    sign with settings.jwt_secret using settings.jwt_algorithm.
    """
    raise NotImplementedError


def decode_access_token(token: str, settings: Settings) -> User:
    """Validate ``token`` and return the User it represents.

    TODO: implement with jwt.decode(...):
      - pin algorithms=[settings.jwt_algorithm]
      - verify audience and issuer
      - require exp, sub, aud, iss
      - convert any jwt.PyJWTError / KeyError / ValueError into
        InvalidTokenError (use `raise ... from exc`)
    """
    raise NotImplementedError
```


**File: `app/api/deps.py`**

```python
"""Dependency providers: FastAPI calls these and injects the results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status  # noqa: F401
from fastapi.security import OAuth2PasswordBearer

from app.config import Settings, get_settings
from app.core.security import (  # noqa: F401
    InvalidTokenError,
    decode_access_token,
)
from app.models.user import Role, User
from app.repositories.customer_repo import CustomerRepository
from app.repositories.user_repo import InMemoryUserRepository
from app.services.customer_service import CustomerService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_customer_repo(request: Request) -> CustomerRepository:
    repo: CustomerRepository = request.app.state.customer_repo
    return repo


def get_user_repo(request: Request) -> InMemoryUserRepository:
    repo: InMemoryUserRepository = request.app.state.user_repo
    return repo


def get_customer_service(
    repo: Annotated[CustomerRepository, Depends(get_customer_repo)],
) -> CustomerService:
    return CustomerService(repo)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], settings: SettingsDep
) -> User:
    """Authentication: WHO is calling? Invalid token -> 401."""
    # TODO: decode the token with decode_access_token(). On
    # InvalidTokenError raise HTTPException(401) with the header
    # WWW-Authenticate: Bearer.
    raise NotImplementedError


ROLE_RANK = {Role.VIEWER: 1, Role.ADMIN: 2}


def require_role(minimum: Role) -> Callable[..., User]:
    """Authorization: MAY this caller do this? Insufficient -> 403."""

    def checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        # TODO: raise HTTPException(403) when the user's rank is below
        # ROLE_RANK[minimum]; otherwise return the user.
        raise NotImplementedError

    return checker


ServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
ViewerDep = Annotated[User, Depends(require_role(Role.VIEWER))]
AdminDep = Annotated[User, Depends(require_role(Role.ADMIN))]
```


**File: `app/services/customer_service.py`**

```python
"""Business rules live here, not in routes and not in the repository."""

from __future__ import annotations

from app.core.errors import ConflictError, NotFoundError  # noqa: F401
from app.models.customer import Customer, CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self._repo = repo

    def create(self, data: CustomerCreate) -> Customer:
        # TODO: lower-case the email, raise ConflictError if a customer
        # with that email exists, otherwise add it via the repository.
        raise NotImplementedError

    def get(self, customer_id: int) -> Customer:
        customer = self._repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        return customer

    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]:
        return self._repo.list(limit=limit, offset=offset, query=query)

    def update(self, customer_id: int, data: CustomerUpdate) -> Customer:
        # TODO:
        # 1. load the customer (self.get raises NotFoundError)
        # 2. changes = data.model_dump(exclude_unset=True)
        # 3. if email changes: lower-case it; ConflictError if another
        #    customer already uses it
        # 4. model_copy(update={**changes, "updated_at": now}) and save
        raise NotImplementedError

    def delete(self, customer_id: int) -> None:
        # TODO: delete via the repository; NotFoundError if nothing
        # was deleted.
        raise NotImplementedError
```


**File: `app/api/routes_customers.py`**

```python
"""Customer resource: thin HTTP layer that delegates to the service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminDep, ServiceDep, ViewerDep
from app.models.customer import (
    CustomerCreate,
    CustomerOut,
    CustomerPage,
    CustomerUpdate,  # noqa: F401
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def list_customers(
    service: ServiceDep,
    _: ViewerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> CustomerPage:
    items, total = service.list(limit=limit, offset=offset, query=q)
    return CustomerPage(
        items=[
            CustomerOut.model_validate(c, from_attributes=True)
            for c in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    service: ServiceDep,
    _: AdminDep,
    response: Response,
) -> CustomerOut:
    # TODO: create via the service, set the Location header to
    # /customers/{id}, return the CustomerOut.
    raise NotImplementedError


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int, service: ServiceDep, _: ViewerDep
) -> CustomerOut:
    return CustomerOut.model_validate(
        service.get(customer_id), from_attributes=True
    )


# TODO: PATCH /customers/{customer_id} (admin only) -> CustomerOut


# TODO: DELETE /customers/{customer_id} (admin only) -> 204 No Content
```


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

**File: `README.md`**

````markdown
# Unit 2 Project — Secured Customers API (FastAPI)

CRUD REST API with Pydantic v2 validation, dependency injection,
service/repository layers, JWT authentication, role-based
authorization and RFC 9457 problem-details errors.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                       # dev settings
uvicorn app.main:create_app --factory --reload
# open http://127.0.0.1:8000/docs
pytest -q
```

Demo users (dev only): `admin / admin-password` (admin) and
`viewer / viewer-password` (viewer).
````

**File: `.env.example`**

```bash
# Copy to .env for local development. Never commit real secrets.
APP_ENV=dev
APP_JWT_SECRET=change-me-to-a-long-random-string-of-32-plus-chars
APP_JWT_ISSUER=customers-api
APP_JWT_AUDIENCE=customers-api-clients
APP_ACCESS_TOKEN_MINUTES=30
# Demo users (dev only): username:password:role, comma separated
APP_DEMO_USERS=admin:admin-password:admin,viewer:viewer-password:viewer
```

**File: `app/__init__.py`**

```python

```

**File: `app/api/__init__.py`**

```python

```

**File: `app/api/deps.py`**

```python
"""Dependency providers: FastAPI calls these and injects the results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import Role, User
from app.repositories.customer_repo import CustomerRepository
from app.repositories.user_repo import InMemoryUserRepository
from app.services.customer_service import CustomerService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_customer_repo(request: Request) -> CustomerRepository:
    repo: CustomerRepository = request.app.state.customer_repo
    return repo


def get_user_repo(request: Request) -> InMemoryUserRepository:
    repo: InMemoryUserRepository = request.app.state.user_repo
    return repo


def get_customer_service(
    repo: Annotated[CustomerRepository, Depends(get_customer_repo)],
) -> CustomerService:
    return CustomerService(repo)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], settings: SettingsDep
) -> User:
    """Authentication: WHO is calling? Invalid token -> 401."""
    try:
        return decode_access_token(token, settings)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


ROLE_RANK = {Role.VIEWER: 1, Role.ADMIN: 2}


def require_role(minimum: Role) -> Callable[..., User]:
    """Authorization: MAY this caller do this? Insufficient -> 403."""

    def checker(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {minimum.value}",
            )
        return user

    return checker


ServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
ViewerDep = Annotated[User, Depends(require_role(Role.VIEWER))]
AdminDep = Annotated[User, Depends(require_role(Role.ADMIN))]
```

**File: `app/api/routes_auth.py`**

```python
"""Token endpoint (OAuth2 password flow, for the demo only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import SettingsDep, get_user_repo
from app.core.security import create_access_token, verify_password
from app.models.user import Token, User
from app.repositories.user_repo import InMemoryUserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    users: Annotated[InMemoryUserRepository, Depends(get_user_repo)],
    settings: SettingsDep,
) -> Token:
    # `def`, not `async def`: Argon2 is CPU-heavy, so FastAPI runs this
    # in its threadpool instead of blocking the event loop.
    user = users.get(form.username)
    if user is None or not verify_password(
        form.password, user.password_hash
    ):
        # Same message for unknown user and wrong password (no user
        # enumeration).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    public = User(username=user.username, role=user.role)
    return Token(
        access_token=create_access_token(public, settings),
        expires_in=settings.access_token_minutes * 60,
    )
```

**File: `app/api/routes_customers.py`**

```python
"""Customer resource: thin HTTP layer that delegates to the service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import AdminDep, ServiceDep, ViewerDep
from app.models.customer import (
    CustomerCreate,
    CustomerOut,
    CustomerPage,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def list_customers(
    service: ServiceDep,
    _: ViewerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> CustomerPage:
    items, total = service.list(limit=limit, offset=offset, query=q)
    return CustomerPage(
        items=[
            CustomerOut.model_validate(c, from_attributes=True)
            for c in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    service: ServiceDep,
    _: AdminDep,
    response: Response,
) -> CustomerOut:
    customer = service.create(body)
    response.headers["Location"] = f"/customers/{customer.id}"
    return CustomerOut.model_validate(customer, from_attributes=True)


@router.get("/{customer_id}")
async def get_customer(
    customer_id: int, service: ServiceDep, _: ViewerDep
) -> CustomerOut:
    return CustomerOut.model_validate(
        service.get(customer_id), from_attributes=True
    )


@router.patch("/{customer_id}")
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    service: ServiceDep,
    _: AdminDep,
) -> CustomerOut:
    return CustomerOut.model_validate(
        service.update(customer_id, body), from_attributes=True
    )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int, service: ServiceDep, _: AdminDep
) -> None:
    service.delete(customer_id)
```

**File: `app/config.py`**

```python
"""Settings loaded from environment variables (12-factor config)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    # SecretStr hides the value in repr/logs. No default: the app must
    # not start with a missing or weak signing key.
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "customers-api"
    jwt_audience: str = "customers-api-clients"
    access_token_minutes: int = Field(default=30, ge=1, le=24 * 60)
    demo_users: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is parsed once per process."""
    return Settings()
```

**File: `app/core/__init__.py`**

```python

```

**File: `app/core/errors.py`**

```python
"""Domain errors and their mapping to RFC 9457 problem details."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)
PROBLEM_JSON = "application/problem+json"


class DomainError(Exception):
    """Base for errors the service layer raises on purpose."""

    status_code = status.HTTP_400_BAD_REQUEST
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"


def problem(
    status_code: int, title: str, detail: str, **extra: object
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        **extra,
    }
    return JSONResponse(
        body, status_code=status_code, media_type=PROBLEM_JSON
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return problem(exc.status_code, exc.title, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        return problem(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Validation failed",
            "The request body or parameters are invalid.",
            errors=errors,
        )

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log full details server-side; never leak stack traces to clients.
        log.exception(
            "unhandled error on %s %s", request.method, request.url
        )
        return problem(500, "Internal server error", "Unexpected error.")
```

**File: `app/core/security.py`**

```python
"""Password hashing and JWT handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.config import Settings
from app.models.user import Role, User

# Argon2id via pwdlib: the hashing approach the FastAPI docs now show.
password_hasher = PasswordHash.recommended()


class InvalidTokenError(Exception):
    """Token missing, expired, tampered with, or for another audience."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": user.username,
        "role": user.role.value,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(
        claims,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> User:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            # Pin the algorithm list: never accept "none" or a different
            # algorithm chosen by whoever crafted the token.
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        return User(username=claims["sub"], role=Role(claims["role"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
```

**File: `app/main.py`**

```python
"""Application factory: wiring only, no business logic."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import routes_auth, routes_customers
from app.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.repositories.customer_repo import InMemoryCustomerRepository
from app.repositories.user_repo import InMemoryUserRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory --reload"""
    logging.basicConfig(level=logging.INFO)
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup: build long-lived resources once (DB pools, clients).
        app.state.customer_repo = InMemoryCustomerRepository()
        app.state.user_repo = InMemoryUserRepository.from_spec(
            settings.demo_users if settings.env != "prod" else ""
        )
        yield
        # Shutdown: close pools/clients here.

    app = FastAPI(
        title="Customers API",
        version="1.0.0",
        lifespan=lifespan,
        description="Unit 2 project: secured customer CRUD.",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    register_error_handlers(app)
    app.include_router(routes_auth.router)
    app.include_router(routes_customers.router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
```

**File: `app/models/__init__.py`**

```python

```

**File: `app/models/customer.py`**

```python
"""API schemas (DTOs). They are the contract, separate from storage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CustomerCreate(BaseModel):
    # extra="forbid": unknown fields are a client bug -> 422, not ignored
    model_config = ConfigDict(extra="forbid")

    name: Name
    email: EmailStr
    company: Annotated[str | None, Field(max_length=120)] = None


class CustomerUpdate(BaseModel):
    """PATCH body: every field optional; only sent fields change."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    email: EmailStr | None = None
    company: Annotated[str | None, Field(max_length=120)] = None
    status: CustomerStatus | None = None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> CustomerUpdate:
        # Omitting a field means "leave it"; sending null for a required
        # field is a client error, caught here at the boundary (422).
        for name in ("name", "email", "status"):
            if (
                name in self.model_fields_set
                and getattr(self, name) is None
            ):
                raise ValueError(f"{name} cannot be null")
        return self


class Customer(BaseModel):
    """Internal domain object returned by the repository."""

    id: int
    name: str
    email: str
    company: str | None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    company: str | None
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime


class CustomerPage(BaseModel):
    items: list[CustomerOut]
    total: int
    limit: int
    offset: int
```

**File: `app/models/user.py`**

```python
"""User and token schemas."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Role(StrEnum):
    VIEWER = "viewer"
    ADMIN = "admin"


class User(BaseModel):
    username: str
    role: Role


class UserInDB(User):
    password_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
```

**File: `app/repositories/__init__.py`**

```python

```

**File: `app/repositories/customer_repo.py`**

```python
"""Persistence boundary. Unit 3 swaps this for SQLAlchemy/PostgreSQL."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Protocol

from app.models.customer import Customer, CustomerStatus


class CustomerRepository(Protocol):
    def add(
        self, name: str, email: str, company: str | None
    ) -> Customer: ...
    def get(self, customer_id: int) -> Customer | None: ...
    def get_by_email(self, email: str) -> Customer | None: ...
    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]: ...
    def update(self, customer: Customer) -> Customer: ...
    def delete(self, customer_id: int) -> bool: ...


class InMemoryCustomerRepository:
    """Thread-safe dict store; good for tests and the first iteration."""

    def __init__(self) -> None:
        self._rows: dict[int, Customer] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def add(self, name: str, email: str, company: str | None) -> Customer:
        with self._lock:
            now = datetime.now(UTC)
            customer = Customer(
                id=self._next_id,
                name=name,
                email=email,
                company=company,
                status=CustomerStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            self._rows[customer.id] = customer
            self._next_id += 1
            return customer

    def get(self, customer_id: int) -> Customer | None:
        return self._rows.get(customer_id)

    def get_by_email(self, email: str) -> Customer | None:
        return next(
            (c for c in self._rows.values() if c.email == email), None
        )

    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]:
        rows = sorted(self._rows.values(), key=lambda c: c.id)
        if query:
            q = query.lower()
            rows = [
                c
                for c in rows
                if q in c.name.lower() or q in (c.company or "").lower()
            ]
        return rows[offset : offset + limit], len(rows)

    def update(self, customer: Customer) -> Customer:
        with self._lock:
            self._rows[customer.id] = customer
            return customer

    def delete(self, customer_id: int) -> bool:
        with self._lock:
            return self._rows.pop(customer_id, None) is not None
```

**File: `app/repositories/user_repo.py`**

```python
"""Demo user store. Production: an identity provider (Cognito, Entra
ID, Auth0, Okta) issues tokens and this service only validates them."""

from __future__ import annotations

from app.core.security import hash_password
from app.models.user import Role, UserInDB


class InMemoryUserRepository:
    def __init__(self, users: dict[str, UserInDB]) -> None:
        self._users = users

    @classmethod
    def from_spec(cls, spec: str) -> InMemoryUserRepository:
        """Parse 'name:password:role,name2:password2:role2'."""
        users: dict[str, UserInDB] = {}
        for item in filter(None, (s.strip() for s in spec.split(","))):
            username, password, role = item.split(":")
            users[username] = UserInDB(
                username=username,
                role=Role(role),
                password_hash=hash_password(password),
            )
        return cls(users)

    def get(self, username: str) -> UserInDB | None:
        return self._users.get(username)
```

**File: `app/services/__init__.py`**

```python

```

**File: `app/services/customer_service.py`**

```python
"""Business rules live here, not in routes and not in the repository."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import ConflictError, NotFoundError
from app.models.customer import Customer, CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import CustomerRepository


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self._repo = repo

    def create(self, data: CustomerCreate) -> Customer:
        email = data.email.lower()
        if self._repo.get_by_email(email):
            raise ConflictError(f"A customer with email {email} exists.")
        return self._repo.add(data.name, email, data.company)

    def get(self, customer_id: int) -> Customer:
        customer = self._repo.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        return customer

    def list(
        self, *, limit: int, offset: int, query: str | None
    ) -> tuple[list[Customer], int]:
        return self._repo.list(limit=limit, offset=offset, query=query)

    def update(self, customer_id: int, data: CustomerUpdate) -> Customer:
        customer = self.get(customer_id)
        # exclude_unset distinguishes "not sent" from "sent as null".
        changes = data.model_dump(exclude_unset=True)
        if "email" in changes:
            changes["email"] = changes["email"].lower()
            other = self._repo.get_by_email(changes["email"])
            if other and other.id != customer_id:
                raise ConflictError(
                    "Email already used by another customer."
                )
        updated = customer.model_copy(
            update={**changes, "updated_at": datetime.now(UTC)}
        )
        return self._repo.update(updated)

    def delete(self, customer_id: int) -> None:
        if not self._repo.delete(customer_id):
            raise NotFoundError(f"Customer {customer_id} not found.")
```

**File: `pyproject.toml`**

```toml
[project]
name = "customers-api"
version = "1.0.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 76
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
packages = ["app"]
```

**File: `requirements-dev.txt`**

```text
-r requirements.txt
pytest>=8
httpx>=0.27
mypy>=1.10
ruff>=0.6
```

**File: `requirements.txt`**

```text
fastapi>=0.135
uvicorn[standard]>=0.30
pydantic>=2.9
pydantic-settings>=2.6
pyjwt>=2.9
pwdlib[argon2]>=0.2
python-multipart>=0.0.12
email-validator>=2.2
```

**File: `tests/__init__.py`**

```python

```

**File: `tests/conftest.py`**

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        env="test",
        jwt_secret="test-secret-that-is-at-least-32-characters!",
        demo_users="admin:admin-pw:admin,viewer:viewer-pw:viewer",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    # The context manager runs the lifespan (startup/shutdown).
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client, 'admin', 'admin-pw')}"}


@pytest.fixture
def viewer_headers(client: TestClient) -> dict[str, str]:
    token = login(client, "viewer", "viewer-pw")
    return {"Authorization": f"Bearer {token}"}
```

**File: `tests/test_auth.py`**

```python
from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from app.config import Settings


def test_login_returns_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/auth/token", data={"username": "admin", "password": "admin-pw"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60


def test_wrong_password_and_unknown_user_look_identical(
    client: TestClient,
) -> None:
    wrong = client.post(
        "/auth/token", data={"username": "admin", "password": "nope"}
    )
    unknown = client.post(
        "/auth/token", data={"username": "ghost", "password": "nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get("/customers").status_code == 401


def test_tampered_token_is_401(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    headers = {"Authorization": admin_headers["Authorization"] + "x"}
    assert client.get("/customers", headers=headers).status_code == 401


def test_expired_token_is_401(
    client: TestClient, settings: Settings
) -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": past,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    response = client.get(
        "/customers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_token_for_other_audience_is_401(
    client: TestClient, settings: Settings
) -> None:
    token = jwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "iss": settings.jwt_issuer,
            "aud": "some-other-api",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    response = client.get(
        "/customers", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_viewer_cannot_create(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/customers",
        json={"name": "A", "email": "a@example.com"},
        headers=viewer_headers,
    )
    assert response.status_code == 403
```

**File: `tests/test_customers.py`**

```python
from fastapi.testclient import TestClient

Headers = dict[str, str]


def create(client: TestClient, headers: Headers, **overrides: str) -> dict:
    body = {"name": "Ada Lovelace", "email": "ada@example.com"} | overrides
    response = client.post("/customers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_returns_201_with_location(
    client: TestClient, admin_headers: Headers
) -> None:
    response = client.post(
        "/customers",
        json={"name": "  Ada  ", "email": "ADA@Example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/customers/{body['id']}"
    assert body["name"] == "Ada"  # whitespace stripped
    assert body["email"] == "ada@example.com"  # normalised
    assert body["status"] == "active"


def test_duplicate_email_is_409_problem_json(
    client: TestClient, admin_headers: Headers
) -> None:
    create(client, admin_headers)
    response = client.post(
        "/customers",
        json={"name": "Other", "email": "ada@example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Conflict"


def test_get_and_404(
    client: TestClient, admin_headers: Headers, viewer_headers: Headers
) -> None:
    created = create(client, admin_headers)
    ok = client.get(f"/customers/{created['id']}", headers=viewer_headers)
    assert ok.status_code == 200
    missing = client.get("/customers/999", headers=viewer_headers)
    assert missing.status_code == 404
    assert missing.json()["status"] == 404


def test_list_paginates_and_filters(
    client: TestClient, admin_headers: Headers
) -> None:
    for i in range(5):
        create(
            client,
            admin_headers,
            name=f"User {i}",
            email=f"u{i}@example.com",
            company="Globex" if i % 2 else "Acme",
        )
    page = client.get(
        "/customers?limit=2&offset=1", headers=admin_headers
    ).json()
    assert page["total"] == 5
    assert [c["name"] for c in page["items"]] == ["User 1", "User 2"]
    filtered = client.get("/customers?q=globex", headers=admin_headers)
    assert filtered.json()["total"] == 2


def test_patch_updates_only_sent_fields(
    client: TestClient, admin_headers: Headers
) -> None:
    created = create(client, admin_headers, company="Acme")
    response = client.patch(
        f"/customers/{created['id']}",
        json={"status": "inactive"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "inactive"
    assert body["company"] == "Acme"
    assert body["updated_at"] >= created["updated_at"]


def test_patch_cannot_steal_another_email(
    client: TestClient, admin_headers: Headers
) -> None:
    create(client, admin_headers)
    second = create(client, admin_headers, email="bob@example.com")
    response = client.patch(
        f"/customers/{second['id']}",
        json={"email": "ada@example.com"},
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_delete_then_404(
    client: TestClient, admin_headers: Headers
) -> None:
    created = create(client, admin_headers)
    path = f"/customers/{created['id']}"
    assert client.delete(path, headers=admin_headers).status_code == 204
    assert client.delete(path, headers=admin_headers).status_code == 404


def test_health_needs_no_auth(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_openapi_documents_the_contract(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    assert "/customers/{customer_id}" in spec["paths"]
    assert "CustomerCreate" in spec["components"]["schemas"]
```

**File: `tests/test_service.py`**

```python
"""Service tests need no HTTP at all: business rules in isolation."""

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, NotFoundError
from app.models.customer import CustomerCreate, CustomerUpdate
from app.repositories.customer_repo import InMemoryCustomerRepository
from app.services.customer_service import CustomerService


@pytest.fixture
def service() -> CustomerService:
    return CustomerService(InMemoryCustomerRepository())


def test_email_uniqueness_is_case_insensitive(
    service: CustomerService,
) -> None:
    service.create(CustomerCreate(name="A", email="a@example.com"))
    with pytest.raises(ConflictError):
        service.create(CustomerCreate(name="B", email="A@EXAMPLE.com"))


def test_patch_schema_rejects_explicit_null() -> None:
    with pytest.raises(ValidationError):
        CustomerUpdate(name=None)
    assert CustomerUpdate().model_fields_set == set()  # omitted is fine


def test_missing_customer(service: CustomerService) -> None:
    with pytest.raises(NotFoundError):
        service.get(42)
```

**File: `tests/test_validation.py`**

```python
import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "body",
    [
        {"email": "a@example.com"},  # missing name
        {"name": "", "email": "a@example.com"},  # empty name
        {"name": "A", "email": "not-an-email"},
        {"name": "A", "email": "a@example.com", "role": "admin"},  # extra
        {"name": "x" * 121, "email": "a@example.com"},
    ],
)
def test_invalid_bodies_are_422(
    client: TestClient, admin_headers: dict[str, str], body: dict
) -> None:
    response = client.post("/customers", json=body, headers=admin_headers)
    assert response.status_code == 422
    problem = response.json()
    assert problem["title"] == "Validation failed"
    assert problem["errors"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_invalid_query_params_are_422(
    client: TestClient, admin_headers: dict[str, str], query: str
) -> None:
    response = client.get(f"/customers?{query}", headers=admin_headers)
    assert response.status_code == 422


def test_non_integer_id_is_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get("/customers/abc", headers=admin_headers)
    assert response.status_code == 422


def test_patch_null_name_is_422(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    created = client.post(
        "/customers",
        json={"name": "A", "email": "a@example.com"},
        headers=admin_headers,
    ).json()
    response = client.patch(
        f"/customers/{created['id']}",
        json={"name": None},
        headers=admin_headers,
    )
    assert response.status_code == 422
```


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


# Unit 3 — Data Engineering for Application Developers

## 1. What This Unit Teaches

Every FDE system stores and retrieves data, and data mistakes are the most expensive to fix later **[JD-Required]**. This unit teaches:

- relational modeling and SQL on PostgreSQL;
- keys and constraints as executable business rules;
- joins, indexes and how to read a query plan;
- transactions and isolation levels, and the concurrency bugs they prevent;
- connection pooling;
- SQLAlchemy 2.x (Core and ORM, the session, N+1);
- migrations with Alembic;
- NoSQL options (document, key-value / Redis) and how to choose between SQL and NoSQL.

The emphasis is on what an application developer must get right, not database administration.

## 2. Mental Model

```text
 Application (FastAPI route → service)
     │  calls
     ▼
 Repository              builds SQL (via SQLAlchemy), returns objects
     │  borrows a connection
     ▼
 Connection Pool         reuses N open connections (TCP+TLS+auth
     │                   are expensive to create)
     ▼
 Database (PostgreSQL)
     │  planner chooses:  Index scan?  Seq scan?  Join strategy?
     ▼
 Index / Query           B-tree lookup vs reading the whole table
     │
     ▼
 Transaction             BEGIN … COMMIT | ROLLBACK
     │                   isolation decides what concurrent
     │                   transactions can see
     ▼
 Result                  rows → ORM objects → Pydantic → JSON
```

Read it as follows:

- The application never talks to the database directly. It goes through a repository, which borrows a pooled connection.
- The database decides *how* to execute each query (the plan). Indexes give the planner faster options.
- Transactions group statements so they succeed or fail together.
- Isolation decides what concurrent transactions can see of each other's work.

## 3. Brief Theory

### 3.1 Relational databases and SQL

**What it is.**

- A relational database stores data in **tables** (relations) of rows with typed columns. Relationships are expressed by **keys**.
- **SQL** is declarative: you describe *what* you want and the planner decides *how* to get it.
- **PostgreSQL** is the open-source default for application data. It has strong correctness (MVCC, real constraints, transactional DDL) and rich types (JSONB, arrays, ranges, full text). Extensions such as `pgvector` (Unit 10) add more.

**Why it matters.** Relational databases enforce integrity rules for *every* writer, answer ad-hoc questions with joins and aggregates, and give transactional guarantees that business data (orders, payments, inventory) requires.

**Essential SQL:**

```sql
-- Join + aggregate: revenue per customer in 2026
SELECT c.id, c.name, SUM(o.total) AS revenue, COUNT(*) AS orders
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.created_at >= '2026-01-01'
GROUP BY c.id, c.name
HAVING SUM(o.total) > 1000
ORDER BY revenue DESC
LIMIT 10;

-- LEFT JOIN keeps customers with no orders (orders = 0)
SELECT c.id, COUNT(o.id) AS orders
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id;

-- Window function: each customer's latest order
SELECT * FROM (
  SELECT o.*, ROW_NUMBER() OVER (PARTITION BY customer_id
                                 ORDER BY created_at DESC) AS rn
  FROM orders o) t
WHERE rn = 1;
```

| Join | Returns |
|---|---|
| INNER JOIN | Only rows that match in both tables |
| LEFT JOIN | All left rows; NULLs where the right side has no match |
| FULL OUTER JOIN | All rows from both sides |
| CROSS JOIN | Every combination (rarely intended) |

### 3.2 Schema design, primary and foreign keys, constraints

**What it is.** Choosing tables, columns, types and constraints so that the data is correct by construction.

**How to do it.**

- **Primary key (PK).** It uniquely identifies a row. Use surrogate keys (`bigint` identity or UUIDv7) for entities, and keep natural keys (email, SKU) as `UNIQUE` constraints.
- **Foreign key (FK).** It guarantees a referenced row exists (`orders.customer_id → customers.id`). Choose `ON DELETE` deliberately:
  - `RESTRICT` — you can't delete a customer who has orders;
  - `CASCADE` — deleting an order deletes its items;
  - `SET NULL`.
- **CHECK, NOT NULL and UNIQUE** turn business rules into guarantees (`stock >= 0`, `quantity > 0`). Application checks can race; constraints cannot.
- **Normalization.** Store each fact once (third normal form) to avoid update anomalies. **Denormalize** deliberately for read performance, and document who keeps the copies consistent.
- **Types.**
  - `numeric(12,2)` for money (never float);
  - `timestamptz` for instants (store UTC);
  - `text` or `varchar(n)` with validation;
  - `jsonb` for genuinely flexible attributes, not as a way to avoid design.

**Why it matters for an FDE.** Customers' data arrives messy. The schema is where you decide what is authoritative and what is guaranteed.

### 3.3 Indexes

**What it is.** An index is an auxiliary data structure — by default a **B-tree**, sorted and balanced — that lets the database find rows without scanning the whole table.

**How it works.**

- A B-tree lookup is O(log n) and can also return rows already *in index order*, which avoids a sort.
- **Composite indexes** follow the leftmost-prefix rule. `(customer_id, created_at)` serves `WHERE customer_id = ? ORDER BY created_at`, but not `WHERE created_at > ?` alone.
- **Covering indexes** (`INCLUDE (...)`) let index-only scans avoid reading the table.
- **Partial indexes** (`WHERE status = 'open'`) index only hot rows.
- **GIN indexes** serve JSONB, arrays and full-text search; pgvector adds ANN indexes for embeddings (Unit 10).

**Trade-offs.** Every index:

- costs storage;
- slows every `INSERT`, `UPDATE` and `DELETE`, because the index must be maintained;
- adds planner work.

Index for your real query patterns, measured with `EXPLAIN ANALYZE`. Unique constraints create indexes automatically.

### 3.4 Query behavior and query plans

`EXPLAIN` shows the plan. `EXPLAIN (ANALYZE, BUFFERS)` runs the query and shows actual times and pages touched. This is real output from the project's `scripts/explain_demo.py` on 500,000 orders:

```text
--- BEFORE index ---
Limit (actual time=10.259..13.248 rows=20 loops=1)
  ->  Gather Merge (actual time=10.257..13.244 rows=20 loops=1)
        Workers Planned: 2
        ->  Sort  Sort Key: created_at DESC
              ->  Parallel Seq Scan on demo_orders
                    Filter: (customer_id = 4242)
                    Rows Removed by Filter: 166649
Execution Time: 13.267 ms
--- AFTER index (customer_id, created_at DESC) ---
Limit (actual time=0.027..0.051 rows=20 loops=1)
  ->  Index Scan using ix_demo_customer_created on demo_orders
        Index Cond: (customer_id = 4242)
Execution Time: 0.065 ms
```

**How to read it:**

- **Before:** a sequential scan read every row (about 500,000 discarded by the filter), then sorted. That cost grows with table size.
- **After:** the index finds the customer's rows already sorted by date and stops after 20. That is roughly 200× faster, and it stays fast as the table grows.

**Red flags in plans:**

- `Seq Scan` on a large table for a selective filter;
- `Rows Removed by Filter` in the hundreds of thousands;
- an explicit `Sort` you could avoid;
- `Nested Loop` with huge row estimates;
- estimated rows far from actual rows, which means stale statistics (run `ANALYZE`).

**Common causes of slow queries:**

- a missing or unusable index (a function on the column, a type mismatch, a leading wildcard such as `LIKE '%x'`);
- N+1 queries from the ORM;
- `SELECT *` over wide rows;
- OFFSET pagination deep into a table.

### 3.5 Transactions (ACID)

**What it is.** A transaction groups statements into one unit:

| Property | Meaning |
|---|---|
| **Atomicity** | All statements apply or none do |
| **Consistency** | Constraints hold before and after |
| **Isolation** | Concurrent transactions don't see each other's partial work |
| **Durability** | Committed data survives crashes (write-ahead log) |

**Why it matters.** Placing an order touches several rows: decrement stock, insert the order, insert its items. A failure halfway must not leave stock decremented with no order.

**In SQLAlchemy:**

```python
with session.begin():          # BEGIN
    ...                        # any exception → ROLLBACK
                               # normal exit → COMMIT
```

### 3.6 Isolation levels and concurrency anomalies

| Level | Prevents | Still possible | PostgreSQL notes |
|---|---|---|---|
| Read Committed (**PG default**) | Dirty reads | Non-repeatable reads, phantoms, **lost updates** with read-modify-write | Each *statement* sees the latest committed data |
| Repeatable Read | + non-repeatable reads, phantoms (snapshot) | Write skew | The transaction sees one snapshot; conflicting writes raise a serialization error, so retry |
| Serializable (SSI) | All anomalies | — | May abort transactions; the application must retry |

**The classic bug — lost update (read-modify-write race):**

```text
T1: SELECT stock → 1         T2: SELECT stock → 1
T1: UPDATE stock = 0         T2: UPDATE stock = 0
→ two orders sold the last unit
```

**Three correct fixes:**

1. **Atomic conditional update.** Check and write in *one* statement. This is what the project does:

   ```sql
   UPDATE products SET stock = stock - :q
   WHERE sku = :sku AND stock >= :q
   RETURNING id, price;            -- no row ⇒ insufficient stock
   ```

2. **Pessimistic locking.** `SELECT ... FOR UPDATE` locks the row until commit, so other writers wait.
3. **Optimistic locking.** A `version` column: `UPDATE ... SET version = version + 1 WHERE id = ? AND version = ?`. Zero rows updated means someone else changed it, so return 409 or retry.

**Deadlocks** happen when two transactions lock rows in opposite orders. Lock in a **consistent order** (the project sorts SKUs), keep transactions short, and retry on deadlock errors.

### 3.7 Connection pooling

**What it is.** A set of reusable open database connections.

**Why it exists.** Opening a PostgreSQL connection costs a TCP handshake, TLS, authentication and a backend process (several milliseconds, plus memory on the server). Doing that per request is slow, and many clients can exhaust `max_connections`.

**How it works.**

- SQLAlchemy's `QueuePool` keeps `pool_size` connections and allows `max_overflow` extras. `pool_timeout` bounds the wait, and `pool_pre_ping` discards dead connections.
- **Capacity math:** total connections = replicas × workers × (pool_size + max_overflow). Ten pods × 2 workers × 15 = 300 connections, which may exceed the database limit.
- Use an external pooler (**PgBouncer**, **RDS Proxy**) for many clients or serverless workloads.

**Symptoms of exhaustion:**

- requests hang, then time out with `QueuePool limit ... reached`;
- sessions are not closed (always use a `yield` dependency or a context manager);
- long transactions hold connections.

### 3.8 SQLAlchemy 2.x

**What it is.** The standard Python database toolkit.

- **Core:** a SQL expression language (`select`, `update`), engines, connections.
- **ORM:** maps classes to tables, with a **Session** that implements the *unit of work* (tracks changes, flushes them in order) and an *identity map* (one object per row per session).

**[Current: 2.0-style API — `select()`, `Mapped[...]`, `mapped_column`. The 1.x `session.query()` style is legacy but still widely seen. 2.1 is current and keeps the 2.0 API.]**

**Key mechanics:**

- `session.add()` stages an object. `flush()` sends the SQL without committing, so an id becomes available. `commit()` makes it durable.
- **Lazy loading:** accessing `order.items` triggers a query. In a loop over N orders that is **N+1 queries**. Fix it with eager loading:
  - `selectinload` — one extra `IN` query per relationship;
  - `joinedload` — a JOIN, suited to many-to-one.
- `expire_on_commit=False` keeps objects readable after commit. That is convenient in APIs, but you must reload deliberately when you need fresh data.
- Sync sessions block. Use them from `def` FastAPI endpoints (which run in the threadpool), or use `AsyncSession` with `asyncpg` or `psycopg` async, with `async def` throughout.

### 3.9 Migrations

**What it is.** Versioned, ordered scripts that evolve the schema (Alembic for SQLAlchemy).

**Why it exists.** Every environment (developer laptops, CI, staging, production) must reach the same schema reproducibly, with a reviewed history and a downgrade path.

**How to use it:**

- `alembic revision --autogenerate -m "msg"` compares the models with the database and writes a draft. **Always review it**: autogenerate can't infer renames and may miss some constraints.
- `alembic upgrade head` runs as a **deploy step** (a CI/CD job or a Kubernetes init Job), not at application import time.
- **Zero-downtime changes** use *expand/contract*:
  1. add the new nullable column;
  2. deploy code that writes both columns;
  3. backfill;
  4. switch reads;
  5. drop the old column in a later release.
- Build large indexes with `CREATE INDEX CONCURRENTLY` to avoid locking writes.

### 3.10 NoSQL

**What it is.** A family of non-relational stores, each optimized for specific access patterns:

| Type | Examples | Model | Strengths | Weaknesses |
|---|---|---|---|---|
| Document | MongoDB, Amazon DocumentDB, Firestore, Cosmos DB | JSON documents, nested | Flexible schema, aggregate-oriented reads, horizontal scaling | Cross-document joins and transactions are limited or costly; duplication must be managed |
| Key-value | Redis/Valkey, DynamoDB (also wide-column-like) | Key → value | Very fast lookups at massive scale, TTLs | Queries limited to known keys or indexes; design around access patterns |
| Wide-column | Cassandra, ScyllaDB | Partitioned rows | Huge write throughput, multi-region | Query-first modeling, eventual consistency |
| Search | OpenSearch, Elasticsearch | Inverted index | Full-text, relevance, aggregations | Not a system of record |
| Graph | Neo4j, Neptune | Nodes and edges | Relationship traversal | Niche |
| Vector | pgvector, OpenSearch k-NN, Pinecone | Embeddings | Similarity search (RAG) | Approximate; needs metadata filtering |

**Document database example (MongoDB, pymongo):**

```python
from pymongo import MongoClient, ASCENDING

client = MongoClient("mongodb://localhost:27017",
                     serverSelectionTimeoutMS=2000)
orders = client.shop.orders
orders.create_index([("customer_id", ASCENDING), ("created_at", -1)])
orders.insert_one({
    "customer_id": 1,
    "status": "placed",
    "items": [{"sku": "KB-01", "qty": 2, "unit_price": "89.00"}],
    "shipping": {"city": "Austin", "zip": "78701"},  # embedded, not joined
})
recent = orders.find({"customer_id": 1}).sort("created_at", -1).limit(20)
```

The order *with its items* is one document because it is always read together. This is aggregate-oriented modeling. The cost is that product names copied into items can go stale, which is a deliberate denormalization.

**DynamoDB** **[Provider-specific, AWS]**. Design the partition key and sort key from the access patterns (`PK=CUSTOMER#1`, `SK=ORDER#2026-10-14#123`), and add Global Secondary Indexes for other patterns. Reads are eventually consistent by default.

### 3.11 Redis

**What it is.** An in-memory data-structure server: strings, hashes, lists, sets, sorted sets and streams, with TTLs.

**Uses in FDE systems:**

- **cache-aside** for hot reads;
- rate limiting (`INCR` plus `EXPIRE`);
- distributed locks (with care);
- session storage;
- idempotency-key storage (Unit 8);
- lightweight queues and streams.

**Cache-aside:**

```text
read:  value = cache.get(k) → hit? return
                            → miss? value = db.get(); cache.set(k, ttl)
write: db.update(); then cache.delete(k)   # after COMMIT
```

**Pitfalls and fixes:**

| Pitfall | What goes wrong | Fix |
|---|---|---|
| **Stale data** | Readers see old values | Invalidate after commit; short TTLs |
| **Stampede** | Many concurrent misses hit the database at once | Locks, request coalescing, or jittered TTLs |
| **Cache as a single point of failure** | A Redis outage breaks reads | Treat Redis errors as misses (the project does this) |
| **Unbounded memory** | Redis fills up | `maxmemory` plus an eviction policy |

### 3.12 SQL vs NoSQL: how to choose

| Question | Lean relational (PostgreSQL) | Lean NoSQL |
|---|---|---|
| Do you need multi-row/multi-entity transactions? | Yes (orders, payments, inventory) | Rarely |
| Are queries ad-hoc or evolving (reports, analytics, joins)? | Yes | No, the access patterns are known and fixed |
| Is the data shape stable with relationships? | Yes | Highly variable or nested aggregates |
| Scale | Vertical plus read replicas covers most apps | Massive write throughput or global distribution |
| Team skills and operations | SQL is ubiquitous | Managed services reduce operational work |

The **FDE default** is PostgreSQL as the system of record, Redis for cache and ephemeral state, and a search or vector index derived from the system of record. Add a document store when the access pattern clearly fits it.

## 4. Application in a Real System

```text
 FastAPI ──► Service ──► Repository ──► SQLAlchemy Session
                │                             │ pool
                │ cache-aside                 ▼
                └──► Redis (ElastiCache)   PostgreSQL (RDS/Aurora)
                                              │ logical replication / CDC
                                              ▼
                           Search/Vector index, data warehouse
                           (derived, rebuildable — not authoritative)
```

| Choice | Why | Without it | Alternatives |
|---|---|---|---|
| PostgreSQL (RDS / Aurora) | Integrity, transactions, rich SQL, managed backups and failover | Data corruption, hand-written consistency logic | MySQL (similar); DynamoDB (scale, access-pattern design) |
| SQLAlchemy ORM + Core | Productivity plus full SQL when needed | Hand-written SQL everywhere, or an ORM hiding SQL behind magic | Raw psycopg (more control), SQLModel (thin layer over SQLAlchemy + Pydantic) |
| Alembic | Reproducible schema history | "Works on my machine" schemas | Flyway / Liquibase (JVM ecosystem) |
| Redis cache | Cuts read latency and database load | Database overload on hot keys | In-process cache (per-replica, inconsistent), CDN for public data |
| Constraints in the database | Rules enforced for every writer | Race conditions, bad data from scripts | Application-only validation (insufficient) |

## 5. Implementation

### 5.1 Typed ORM models with constraints and an index

```python
class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_products_stock_nonneg"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"))
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan")
```

### 5.2 Engine, pool and a per-request session

```python
engine = create_engine(url, pool_size=5, max_overflow=10,
                       pool_pre_ping=True, pool_timeout=10)
factory = sessionmaker(engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    session = factory()
    try:
        yield session          # FastAPI injects this
    finally:
        session.close()        # connection returns to the pool
```

### 5.3 A transaction with an atomic, race-free stock decrement

```python
with session.begin():                       # COMMIT or ROLLBACK
    for sku in sorted(quantities):          # consistent lock order
        row = session.execute(
            update(Product)
            .where(Product.sku == sku, Product.stock >= quantities[sku])
            .values(stock=Product.stock - quantities[sku])
            .returning(Product.id, Product.price)
        ).one_or_none()
        if row is None:                     # raising → ROLLBACK
            raise InsufficientStockError(sku)
        ...
    session.add(order)
cache.delete(*keys)                         # after COMMIT
```

### 5.4 Avoiding N+1 with eager loading

```python
stmt = (select(Order)
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .limit(20)
        .options(selectinload(Order.items)
                 .selectinload(OrderItem.product)))
orders = session.scalars(stmt).all()        # 3 queries total
```

The project's test counts the SQL statements with an engine event listener and asserts exactly three. That turns a performance property into a regression test.

### 5.5 Letting the database enforce uniqueness

```python
try:
    with session.begin():
        session.add(Customer(name=..., email=email))
except IntegrityError as exc:               # UNIQUE violated
    raise ConflictError("Email already registered.") from exc
```

### 5.6 Cache-aside that survives a Redis outage

```python
def get(self, key: str) -> dict | None:
    try:
        raw = self._client.get(key)
    except redis.RedisError as exc:          # outage = cache miss
        log.warning("cache get failed: %s", exc)
        return None
    return json.loads(raw) if raw else None
```

### 5.7 Migrations

```bash
alembic revision --autogenerate -m "initial schema"   # draft
# review alembic/versions/0001_initial_schema.py
alembic upgrade head          # apply
alembic downgrade -1          # roll back one step
alembic history               # audit trail
```

## 6. How It Connects to the Rest of the System

```text
 Unit 2 API ─► service ─► repository (this unit) ─► pool ─► PostgreSQL
                 │                                      ▲
                 └─► Redis cache ◄────── invalidation ──┘
 Unit 6: RDS/Aurora + ElastiCache, secrets for DB credentials,
         readiness probe runs SELECT 1, migration Job before rollout
 Unit 7: CI runs migrations + tests against a real Postgres service
 Unit 8: idempotency keys and outbox tables live in this database
 Unit 10: pgvector stores embeddings next to authoritative records
 Unit 11: slow-query logs, pool metrics, DB spans in traces
```

## Cross-Unit System Map (Units 1–3)

```text
 Client (curl / Swagger UI / future SPA)
   │ HTTPS + JSON + Bearer JWT
   ▼
 FastAPI app (Unit 2)
   ├─ Pydantic validation at the boundary
   ├─ authN (JWT) → authZ (roles)
   ▼
 Service layer (Unit 2) — business rules, domain errors
   │  typed Python, Protocols, exceptions, tests (Unit 1)
   ▼
 Repository (Unit 3) — SQLAlchemy 2.x
   ├─ connection pool
   ├─ transactions (atomic stock decrement)
   ▼
 PostgreSQL (constraints, indexes)      Redis (cache-aside)
```

Everything in this map is **deterministic**: the same input produces the same output, and correctness is enforced by types, validation, constraints and transactions. Later units add network failures (Unit 8) and probabilistic model behavior (Units 9–10) *around* this deterministic core. They never replace it.

## FDE Scenario 2 — "The numbers in the dashboard don't match the ERP"

**Stakeholder:** "Your new order dashboard shows 4% more revenue than our ERP. Finance is upset. Fix it today."

- *Clarify first:*
  - Which numbers (gross or net, with or without tax, refunds, currency)?
  - Which period and time zone ("today" in UTC or in local time)?
  - Which system is **authoritative** for revenue? Usually the ERP or ledger, not your operational database.
- *Investigate with evidence:*
  - reconcile one day order by order (`FULL OUTER JOIN` of both extracts on order ID);
  - classify the differences: missing refunds, duplicated orders from retries, time-zone boundary, currency conversion.
- *Likely causes:*
  - retries created duplicate orders (no idempotency key, Unit 8);
  - cancelled orders counted;
  - `created_at` stored without a time zone.
- *What must be deterministic:* the revenue definition, written down as an acceptance criterion with a SQL query both sides agree on.
- *Deliver:* a reconciliation report, a fix (unique constraint plus idempotency keys; a status filter), a regression test using the reconciliation query, and a short note to finance explaining the definition.
- *Communicate:* "Here's the exact cause for each difference, the fix, and the check we'll run daily so this can't recur silently."

## Comprehension Questions

1. Why should "stock can't go negative" be a database CHECK constraint even if the service already checks it?
2. A composite index on `(customer_id, created_at)` exists. Which of these does it help, and why: (a) `WHERE customer_id=7 ORDER BY created_at DESC`, (b) `WHERE created_at > now() - '1 day'`?
3. Why might an index improve one query but hurt write performance?
4. Explain the lost-update race, and two ways to prevent it.
5. What is the N+1 problem and how does `selectinload` fix it?
6. Why use a connection pool, and how can it be exhausted?
7. Why must cache invalidation happen after the transaction commits?
8. When would you choose a document database over PostgreSQL?

## Comprehension Answers

1. Application checks can race between concurrent requests and are bypassed by other writers (scripts, other services). The constraint is enforced atomically for every write.
2. (a) Yes. The leftmost column matches the equality filter and the second column provides the sort order, so it is an index scan with no sort. (b) Not efficiently: `created_at` is not the leftmost column. It needs its own index.
3. Reads can use it to avoid scans. Every INSERT, UPDATE or DELETE must also update the index, which costs CPU, I/O, WAL and storage.
4. Two transactions read the same value, then both write a value derived from that stale read, and one update is lost. Prevent it with an atomic conditional `UPDATE ... WHERE stock >= q`, `SELECT ... FOR UPDATE`, or optimistic locking with a version column.
5. Loading N parents and then lazily loading each parent's children issues 1 + N queries. `selectinload` loads all the children in one `IN (...)` query per relationship.
6. Creating connections is slow and limited by the database's `max_connections`. A pool reuses them. It is exhausted when sessions leak, transactions are long, or replicas × pool size exceeds what the database or traffic allows.
7. If you invalidate before commit, a concurrent reader can repopulate the cache with the old committed value, which is then stale until the TTL expires.
8. When data is naturally read and written as self-contained aggregates with flexible or nested shape, the access patterns are known, and cross-entity transactions or joins are rare — and when horizontal scale or a managed serverless model matters.

## Interview Questions — Theory-Based

**Q1. Explain ACID and give an example where atomicity matters.**

- *Strong answer:* Atomicity means all statements apply or none do. Consistency means constraints hold. Isolation means concurrent transactions don't see partial work. Durability means committed data survives crashes, via the WAL. Example: placing an order decrements stock and inserts the order and its items. If the item insert fails, the stock decrement must roll back.
- *Testing:* the fundamentals beyond acronyms.
- *Follow-up:* "How do you make an operation atomic across two services?" (You can't with one database transaction. Use a saga or the outbox pattern; see Unit 8.)

**Q2. What isolation level does PostgreSQL use by default, and what anomalies can occur?**

- *Strong answer:* Read Committed. Each statement sees data committed before that statement started, so non-repeatable reads, phantoms and lost updates in read-modify-write code are possible. I prevent them with atomic updates or row locks, or use Repeatable Read or Serializable with retry logic when needed.
- *Follow-up:* "What does Serializable cost?" (Possible serialization failures that need retries, and some overhead.)

**Q3. How do you find and fix a slow query?**

- *Strong answer:*
  1. Identify it from slow-query logs, `pg_stat_statements` or APM traces.
  2. Run `EXPLAIN (ANALYZE, BUFFERS)` and look for sequential scans on selective filters, large "rows removed", sorts and bad estimates.
  3. Fix: add or adjust an index (column order matters), rewrite the query, avoid functions on indexed columns, fix N+1 in the ORM, update statistics, use keyset pagination.
  4. Verify with the same plan and with production-like data.
- *Follow-up:* "When would you not add an index?" (Write-heavy tables, low-selectivity columns, queries that touch most rows.)

**Q4. Explain connection pooling and how you'd size it.**

- *Strong answer:* A pool keeps reusable connections because creating one is expensive. Size it from concurrency needs and database limits: replicas × workers × (pool_size + overflow) must stay under `max_connections` with headroom. Add PgBouncer or RDS Proxy for many clients. Watch pool wait time, in-use connections and timeouts.

**Q5. ORM vs raw SQL: trade-offs?**

- *Strong answer:* An ORM gives productivity, type-safe models, the unit of work and portability. The risks are hidden queries (N+1) and inefficient SQL. Raw SQL gives full control and performance. SQLAlchemy lets me mix them: ORM for CRUD, Core or text for complex reports. Either way I read the generated SQL and the plans.

**Q6. How do you run schema migrations without downtime?**

- *Strong answer:* Use expand/contract. Make additive changes first (nullable columns, new tables), deploy code compatible with both schemas, backfill in batches, switch reads, then remove the old structures in a later release. Use `CREATE INDEX CONCURRENTLY`, avoid long locks, and run migrations as a separate deploy step with a rollback plan.

**Q7. SQL vs NoSQL for an order system?**

- *Strong answer:* Orders, payments and inventory need multi-entity transactions and constraints, so PostgreSQL is the system of record. Redis serves caching and rate limits. A document store or DynamoDB fits huge, simple key-based access such as session data or an event log by customer. Search and vector indexes are derived, not authoritative.

**Q8. What is cache-aside and what can go wrong?**

- *Strong answer:* Read from the cache; on a miss, load from the database and populate the cache with a TTL; on a write, update the database and then delete the key. What can go wrong: stale data (invalidation timing), stampedes on popular keys, cache outages taking down reads (treat errors as misses), unbounded memory, and caching per-user data under shared keys (a security leak).

## Interview Questions — Application / Experience-Based

**A1. Tell me about a schema you designed.**

- *Cover:* the entities and their relationships, keys and constraints, indexes chosen from the query patterns, how it evolved (migrations), and one trade-off (normalize vs denormalize, JSONB vs columns).
- *Structure:* Situation → Requirement → Architecture → Implementation → Verification → Result → Lesson.
- *Personalize:* "`<<personalize: domain>>`. Core tables were `<<...>>`, with FKs and a unique constraint on `<<natural key>>`. The hot query `<<...>>` got a composite index `<<...>>`, verified with EXPLAIN ANALYZE (`<<before → after>>`)."
- *Follow-ups:* "What would you change now?" "How did you handle a breaking change?"

**A2. Describe a performance problem caused by the database.**

- *Cover:* the symptom (latency or CPU), the evidence (plans, `pg_stat_statements`, traces), the root cause (missing index, N+1, lock contention), the fix and the measured result.

**A3. Have you dealt with concurrency or data-integrity bugs?**

- *Cover:* the race you found, how you reproduced it (a concurrency test), and the fix (atomic update, lock, constraint, idempotency).
- *Lab-honest version:* "In a project I wrote a test that fires eight concurrent purchases at the last unit; with an atomic conditional UPDATE exactly one succeeds."

**A4. How have you used Redis or another cache?**

- *Cover:* what you cached and why, TTL and invalidation, failure behavior, and measured impact.

**A5. Tell me about a data migration you ran.**

- *Cover:* the planning, batching, verification counts and checksums, rollback, and communication.

## Troubleshooting Scenarios

**T1. A database query suddenly becomes slow.**

```text
SYMPTOM     /customers/{id}/orders p95 from 30ms to 3s
WHAT TO CHECK  EXPLAIN ANALYZE now vs before; row count growth;
               recent deploy (new filter/sort?); stats freshness;
               lock waits (pg_stat_activity, pg_locks)
LIKELY CAUSES  index not used (type mismatch, function on column,
               changed ORDER BY), stale statistics, table bloat, N+1
               after a code change, lock contention from a migration
HOW TO CONFIRM plan shows Seq Scan + Sort; ANALYZE fixes estimates;
               query count per request in traces
FIX         add/adjust composite index; ANALYZE; eager loading;
            rewrite query; CREATE INDEX CONCURRENTLY in prod
PREVENTION  pg_stat_statements review, query-count tests, load tests
            with realistic data volumes
```

*Strong answer:* "I'd compare the current plan with the expected one. Most sudden slowdowns are a plan change (stats or data growth), an index the query can no longer use, or N+1 introduced by a code change. I'd verify the fix with EXPLAIN ANALYZE and protect it with a test."

**T2. Requests hang with "QueuePool limit reached".**

```text
CHECK       sessions closed? long transactions? replica × pool size
            vs max_connections? slow queries holding connections?
CAUSES      session leak (no close), awaiting an external API while
            holding a transaction, traffic spike
FIX         yield-dependency closes sessions; keep transactions short
            (no network calls inside); tune pool; add PgBouncer/RDS
            Proxy; set pool_timeout to fail fast
```

**T3. Duplicate rows appear after an outage.**

```text
CAUSE       client retried POST after timeout; no unique constraint /
            idempotency key → second insert succeeded
FIX         unique business key or Idempotency-Key table; dedupe data
PREVENT     every create endpoint idempotent (Unit 8)
```

**T4. Deadlock detected errors under load.**

```text
CAUSE       two transactions lock the same rows in opposite order
FIX         lock in a consistent order (sort keys), shorter
            transactions, retry on deadlock (SQLSTATE 40P01)
```

**T5. A migration locks a production table.**

```text
CAUSE       ALTER TABLE adding NOT NULL with default on old PG / index
            built without CONCURRENTLY / long-running transaction
FIX         expand/contract; CONCURRENTLY; lock_timeout; off-peak
```

## Unit Practice Project — Orders Data Layer

### Project Goal

Build the persistence layer of an order system on SQLAlchemy 2.x and PostgreSQL:

- a schema with real constraints and indexes;
- migrations;
- repositories;
- a transactional, race-free order placement;
- N+1-free reads;
- a Redis cache that degrades gracefully.

This proves you can make data correct under concurrency and fast under load, and prove both with tests.

### Architecture

```text
 FastAPI (sync def endpoints, threadpool)
   ├─ POST /customers ─► CustomerRepository ──┐
   ├─ GET  /products/{sku} ─► CatalogService ─┼─► Session ─► pool ─► DB
   │                           └─ cache-aside ─► Redis / in-memory
   ├─ POST /orders ─► OrderService (one transaction, atomic UPDATE)
   └─ GET  /customers/{id}/orders ─► OrderRepository (selectinload)
 Alembic migrations ──► schema    scripts/explain_demo.py ──► plans
```

### Requirements

1. Tables `customers`, `products`, `orders` and `order_items`, with:
   - PKs and FKs (`RESTRICT` on customer, `CASCADE` on items);
   - `UNIQUE(email)`, `UNIQUE(sku)`;
   - `CHECK(stock >= 0)`, `CHECK(price > 0)`, `CHECK(quantity > 0)`;
   - an index `(customer_id, created_at)`.
2. `POST /customers` returns 201. A duplicate email returns 409, enforced by the UNIQUE constraint.
3. `GET /products/{sku}` uses cache-aside and sets `X-Cache: HIT|MISS`. An unknown SKU returns 404.
4. `POST /orders` merges duplicate SKUs and performs everything in **one transaction**:
   - an unknown customer returns 404, and unknown SKUs return 422;
   - insufficient stock returns 409 and **nothing changes**;
   - stock is decremented atomically, and the total is computed from current prices;
   - product cache keys are invalidated after commit.
5. `GET /customers/{id}/orders` returns orders newest first, using exactly 3 SQL queries regardless of the number of orders.
6. A Redis outage never fails a request.
7. Alembic migration `0001` creates the schema. Upgrade and downgrade both work.
8. A concurrency test proves only one of eight concurrent buyers gets the last unit (PostgreSQL).

### Technical Requirements

- Python 3.12+, FastAPI, SQLAlchemy 2.x, Alembic, psycopg 3, redis-py and pydantic-settings.
- SQLite in-memory for fast tests. PostgreSQL 14+ (docker compose provides 18) for the realistic tests.
- pytest; a `TEST_DATABASE_URL` switch for PostgreSQL.

### Project Structure

```text
solution/
├── alembic/
│   ├── versions/
│   │   └── 0001_initial_schema.py
│   ├── env.py
│   └── script.py.mako
├── app/
│   ├── services/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   └── orders.py
│   ├── __init__.py
│   ├── cache.py
│   ├── config.py
│   ├── db.py
│   ├── errors.py
│   ├── main.py
│   ├── models.py
│   ├── repositories.py
│   ├── schemas.py
│   └── seed.py
├── scripts/
│   ├── __init__.py
│   └── explain_demo.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_cache.py
│   ├── test_concurrency.py
│   ├── test_constraints.py
│   └── test_repositories.py
├── .env.example
├── README.md
├── alembic.ini
├── docker-compose.yml
├── pyproject.toml
├── requirements-dev.txt
└── requirements.txt
```


### Step-by-Step Implementation

1. **Run the starter on SQLite.** `pip install -r requirements-dev.txt`, `python -m app.seed`, then `pytest -q`.
   - *Why:* to see which behaviors are missing (failing tests).
2. **Review `models.py`.** Identify every constraint and index and the business rule each encodes.
   - *Test:* `pytest tests/test_constraints.py` passes already.
3. **Generate and review the migration.**
   - Start PostgreSQL with `docker compose up -d`.
   - Run `alembic revision --autogenerate -m "initial schema"`.
   - Read the file, run `alembic upgrade head`, then `alembic downgrade base` and `upgrade` again.
   - *Why:* migrations, not `create_all`, are how real environments get schemas.
4. **Implement the customer insert with IntegrityError translation** (`main.py`).
   - *Test:* `test_create_customer_and_duplicate_email`.
5. **Implement `RedisProductCache` and `CatalogService.get_product`.**
   - *Test:* `test_product_read_is_cached` and `test_redis_outage_degrades_to_cache_miss`.
6. **Implement `OrderRepository.list_for_customer` with `selectinload`.**
   - *Test:* `test_list_orders_avoids_n_plus_one` (asserts exactly 3 queries).
7. **Implement `OrderService.place_order`** (Counter merge, `session.begin()`, sorted atomic UPDATEs, invalidation after commit).
   - *Test:* the order tests in `test_api.py`, especially `test_insufficient_stock_rolls_back_everything`.
8. **Implement the concurrency test** and run it against PostgreSQL with `TEST_DATABASE_URL=... pytest -q`.
9. **Run `python -m scripts.explain_demo`** against PostgreSQL and explain the before and after plans in your own words.

### Starter Code

**File: `app/services/orders.py`**

```python
"""Order placement: one transaction, atomic stock decrement."""

from __future__ import annotations

from collections import Counter  # noqa: F401
from decimal import Decimal  # noqa: F401

from sqlalchemy import update  # noqa: F401
from sqlalchemy.orm import Session

from app.cache import ProductCache
from app.errors import (
    NotFoundError,
)
from app.models import Customer, Order, OrderItem, Product  # noqa: F401
from app.repositories import (  # noqa: F401
    OrderRepository,
    ProductRepository,
)
from app.schemas import OrderIn, OrderLineOut, OrderOut
from app.services.catalog import cache_key  # noqa: F401


def to_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        lines=[
            OrderLineOut(
                sku=item.product.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
    )


class OrderService:
    def __init__(self, session: Session, cache: ProductCache) -> None:
        self._session = session
        self._cache = cache

    def place_order(self, data: OrderIn) -> OrderOut:
        # TODO: implement order placement as ONE transaction:
        # 1. merge duplicate SKUs (collections.Counter)
        # 2. `with self._session.begin():` so any exception rolls back
        # 3. NotFoundError if the customer does not exist
        # 4. UnknownSkuError (422) listing SKUs that do not exist
        # 5. for each SKU in sorted order run an atomic conditional
        #    UPDATE products SET stock = stock - :qty
        #    WHERE sku = :sku AND stock >= :qty RETURNING id, price
        #    -> no row returned means InsufficientStockError
        # 6. build Order + OrderItem rows, compute the total, add()
        # 7. after commit, delete the product cache keys
        raise NotImplementedError

    def list_for_customer(self, customer_id: int) -> list[OrderOut]:
        if self._session.get(Customer, customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        orders = OrderRepository(self._session).list_for_customer(
            customer_id
        )
        return [to_out(o) for o in orders]
```


**File: `app/repositories.py`**

```python
"""Repositories: the only code that builds SQL for these tables."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload  # noqa: F401

from app.models import Customer, Order, OrderItem, Product  # noqa: F401


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, email: str) -> Customer:
        customer = Customer(name=name, email=email)
        self.session.add(customer)
        self.session.flush()  # INSERT now so the id is available
        return customer

    def get(self, customer_id: int) -> Customer | None:
        return self.session.get(Customer, customer_id)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_sku(self, sku: str) -> Product | None:
        return self.session.scalar(
            select(Product).where(Product.sku == sku)
        )

    def get_by_skus(self, skus: Iterable[str]) -> dict[str, Product]:
        rows = self.session.scalars(
            select(Product).where(Product.sku.in_(list(skus)))
        )
        return {p.sku: p for p in rows}


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_customer(
        self, customer_id: int, *, limit: int = 20
    ) -> Sequence[Order]:
        # TODO: select the customer's orders, newest first
        # (created_at DESC, id DESC), limited to `limit`, and eager-load
        # Order.items and OrderItem.product with selectinload so listing
        # N orders costs 3 queries, not 1 + N + N (test_repositories).
        raise NotImplementedError
```


**File: `app/services/catalog.py`**

```python
from __future__ import annotations

from app.cache import ProductCache
from app.errors import NotFoundError  # noqa: F401
from app.repositories import ProductRepository
from app.schemas import ProductOut


def cache_key(sku: str) -> str:
    return f"product:{sku}"


class CatalogService:
    def __init__(self, products: ProductRepository, cache: ProductCache):
        self._products = products
        self._cache = cache

    def get_product(self, sku: str) -> tuple[ProductOut, bool]:
        """Cache-aside: try cache, else DB then populate cache.

        Returns (product, served_from_cache)."""
        # TODO:
        # 1. look up cache_key(sku) in self._cache -> HIT: return it, True
        # 2. MISS: load from self._products; NotFoundError if missing
        # 3. store out.model_dump(mode="json") in the cache, return False
        raise NotImplementedError
```


The starter's `app/cache.py` (`RedisProductCache` methods), the `create_customer` route in `app/main.py`, and `tests/test_concurrency.py` contain further TODOs. `alembic/versions/` is empty, because you generate the first migration.

### Practice Tasks

1. **Normal behavior:**
   - order creation decrements stock;
   - totals are correct (2 × 89.00 + 29.50 = 207.50);
   - listing is newest first;
   - cache HIT on the second read.
2. **Validation:** an empty `lines` list returns 422; `quantity < 1` returns 422; unknown fields return 422.
3. **Errors:** an unknown customer returns 404; an unknown SKU returns 422; insufficient stock returns 409; a duplicate email returns 409.
4. **Edge cases:**
   - duplicate SKUs in one order are merged;
   - a failure on the second SKU rolls back the first;
   - the cache is invalidated after an order;
   - a Redis outage is harmless.
5. **Tests:** the concurrency test on PostgreSQL. Optionally, a test for `ON DELETE RESTRICT` (deleting a customer with orders fails).

### Hints

1. `Counter[str]()` with `quantities[line.sku] += line.quantity` merges duplicates.
2. `with self._session.begin():` — raising any exception inside rolls back.
3. `update(Product).where(Product.sku == sku, Product.stock >= qty).values(stock=Product.stock - qty).returning(Product.id, Product.price)`, then `.one_or_none()`.
4. Build `OrderItem(product=products[sku], quantity=qty, unit_price=row.price)` and append it to `order.items`.
5. Eager loading: `.options(selectinload(Order.items).selectinload(OrderItem.product))`.
6. For the concurrency test, create **one session per thread**. Sessions are not thread-safe.

### Expected Behavior

```text
POST /orders {"customer_id":1,"lines":[{"sku":"KB-01","quantity":2},
                                       {"sku":"MS-01","quantity":1}]}
→ 201 {"id":1,"customer_id":1,"status":"placed","total":"207.50",
       "lines":[{"sku":"KB-01","quantity":2,"unit_price":"89.00"},
                {"sku":"MS-01","quantity":1,"unit_price":"29.50"}],...}

GET /products/KB-01 → 200  X-Cache: MISS   {"stock":23,...}
GET /products/KB-01 → 200  X-Cache: HIT

POST /orders ... {"sku":"MN-27","quantity":6} (stock 5)
→ 409 {"title":"Insufficient stock","detail":"Not enough stock for MN-27."}
  (and no stock changed for any other line)

POST /orders ... {"sku":"NOPE","quantity":1}
→ 422 {"title":"Unknown SKU","detail":"Unknown SKUs: NOPE"}
```

### Testing Requirements

- **Unit and integration tests** on SQLite (fast feedback) and PostgreSQL (real behavior).
- **Negative tests:** constraint violations, 404, 409, 422.
- **Transaction test:** a partial failure rolls everything back.
- **Performance regression test:** query count for the listing.
- **Concurrency test** (PostgreSQL): eight threads, one winner.

```bash
pytest -q                                   # SQLite
TEST_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders \
  pytest -q                                 # PostgreSQL (+ concurrency)
alembic upgrade head && alembic downgrade base && alembic upgrade head
```

### Final Runnable Solution

**File: `README.md`**

````markdown
# Unit 3 Project — Orders Data Layer (SQLAlchemy 2.x + PostgreSQL)

Schema with constraints and indexes, Alembic migrations, repositories,
transactional order placement with an atomic stock decrement,
N+1-free reads, and Redis cache-aside with graceful degradation.

## Run (SQLite, zero setup)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed
uvicorn app.main:create_app --factory --reload
pytest -q
```

## Run against PostgreSQL + Redis

```bash
docker compose up -d
cp .env.example .env
alembic upgrade head          # create schema via migrations
python -m app.seed
uvicorn app.main:create_app --factory --reload
TEST_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders \
  pytest -q                   # includes the concurrency test
python -m scripts.explain_demo   # index vs no index query plans
```
````

**File: `.env.example`**

```bash
# SQLite works out of the box; PostgreSQL via docker compose:
#   docker compose up -d
APP_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders
# Leave empty to use the in-process cache instead of Redis.
APP_REDIS_URL=redis://localhost:6379/0
APP_CACHE_TTL_SECONDS=60
APP_SQL_ECHO=false
```

**File: `alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
# The URL comes from APP_DATABASE_URL (see alembic/env.py).

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

**File: `alembic/env.py`**

```python
"""Alembic environment: uses the app's settings and metadata."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app import models  # noqa: F401  (registers tables on Base)
from app.config import get_settings
from app.db import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**File: `alembic/script.py.mako`**

```text
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

**File: `alembic/versions/0001_initial_schema.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Generated by `alembic revision --autogenerate`, then reviewed.
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "price", sa.Numeric(precision=10, scale=2), nullable=False
        ),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_products_price_pos"),
        sa.CheckConstraint("stock >= 0", name="ck_products_stock_nonneg"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "total", sa.Numeric(precision=12, scale=2), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_orders_customer_created",
        "orders",
        ["customer_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "unit_price", sa.Numeric(precision=10, scale=2), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="ck_items_qty_pos"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id", "product_id", name="uq_item_product"
        ),
    )
    op.create_index(
        op.f("ix_order_items_order_id"),
        "order_items",
        ["order_id"],
        unique=False,
    )


def downgrade() -> None:
    # Generated by `alembic revision --autogenerate`, then reviewed.
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")
    op.drop_index("ix_orders_customer_created", table_name="orders")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("customers")
```

**File: `app/__init__.py`**

```python

```

**File: `app/cache.py`**

```python
"""Cache-aside for product reads: Redis in production, dict in tests."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

import redis

log = logging.getLogger(__name__)


class ProductCache(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def set(self, key: str, value: dict[str, Any]) -> None: ...
    def delete(self, *keys: str) -> None: ...


class InMemoryProductCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        item = self._data.get(key)
        if item is None or item[0] < time.monotonic():
            self._data.pop(key, None)
            return None
        return item[1]

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)


class RedisProductCache:
    """A cache outage must degrade performance, never correctness, so
    every Redis error is logged and treated as a cache miss."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        self._client = redis.Redis.from_url(
            url, socket_timeout=0.2, socket_connect_timeout=0.2
        )
        self._ttl = ttl_seconds

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self._client.get(key)
        except redis.RedisError as exc:
            log.warning("cache get failed: %s", exc)
            return None
        return json.loads(raw) if raw else None

    def set(self, key: str, value: dict[str, Any]) -> None:
        try:
            self._client.set(key, json.dumps(value), ex=self._ttl)
        except redis.RedisError as exc:
            log.warning("cache set failed: %s", exc)

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._client.delete(*keys)
        except redis.RedisError as exc:
            log.warning("cache delete failed: %s", exc)
```

**File: `app/config.py`**

```python
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    database_url: str = "sqlite:///./orders.db"
    redis_url: str = ""
    cache_ttl_seconds: int = 60
    sql_echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**File: `app/db.py`**

```python
"""Engine, connection pool and per-request sessions."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings


class Base(DeclarativeBase):
    pass


def make_engine(settings: Settings) -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        kwargs: dict[str, object] = {
            "connect_args": {"check_same_thread": False}
        }
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # one shared in-memory DB
        engine = create_engine(url, echo=settings.sql_echo, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            # SQLite ignores foreign keys unless asked to enforce them.
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    # PostgreSQL: a bounded pool. pool_pre_ping discards dead
    # connections (e.g. after a DB failover) before handing them out.
    return create_engine(
        url,
        echo=settings.sql_echo,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        pool_timeout=10,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit, which
    # is convenient when converting them to response models.
    return sessionmaker(engine, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """One session per request; always closed (connection returned)."""
    session = factory()
    try:
        yield session
    finally:
        session.close()
```

**File: `app/errors.py`**

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    title = "Bad request"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    status_code = 404
    title = "Not found"


class ConflictError(DomainError):
    status_code = 409
    title = "Conflict"


class InsufficientStockError(ConflictError):
    title = "Insufficient stock"


class UnknownSkuError(DomainError):
    status_code = 422
    title = "Unknown SKU"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            {
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
            },
            status_code=exc.status_code,
            media_type="application/problem+json",
        )
```

**File: `app/main.py`**

```python
"""FastAPI app wiring the data layer. Run:
uvicorn app.main:create_app --factory --reload"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cache import InMemoryProductCache, ProductCache, RedisProductCache
from app.config import Settings, get_settings
from app.db import Base, make_engine, make_session_factory, session_scope
from app.errors import ConflictError, register_error_handlers
from app.repositories import CustomerRepository, ProductRepository
from app.schemas import (
    CustomerIn,
    CustomerOut,
    OrderIn,
    OrderOut,
    ProductOut,
)
from app.services.catalog import CatalogService
from app.services.orders import OrderService


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_cache(request: Request) -> ProductCache:
    cache: ProductCache = request.app.state.cache
    return cache


SessionDep = Annotated[Session, Depends(get_session)]
CacheDep = Annotated[ProductCache, Depends(get_cache)]


def create_app(
    settings: Settings | None = None, *, create_schema: bool = True
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings)
        if create_schema:
            # Dev convenience only. Real environments run
            # `alembic upgrade head` as a deploy step.
            Base.metadata.create_all(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        app.state.cache = (
            RedisProductCache(
                settings.redis_url, settings.cache_ttl_seconds
            )
            if settings.redis_url
            else InMemoryProductCache(settings.cache_ttl_seconds)
        )
        yield
        engine.dispose()  # close pooled connections

    app = FastAPI(title="Orders Data API", lifespan=lifespan)
    register_error_handlers(app)

    # Sync `def` endpoints: SQLAlchemy sync sessions block, so FastAPI
    # runs these in its threadpool instead of on the event loop.
    @app.get("/health")
    def health(session: SessionDep) -> dict[str, str]:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}

    @app.post("/customers", status_code=status.HTTP_201_CREATED)
    def create_customer(
        body: CustomerIn, session: SessionDep
    ) -> CustomerOut:
        try:
            with session.begin():
                customer = CustomerRepository(session).add(
                    body.name, body.email.lower()
                )
        except IntegrityError as exc:
            # The UNIQUE constraint is the source of truth; checking
            # first and inserting second would race.
            raise ConflictError("Email already registered.") from exc
        return CustomerOut.model_validate(customer)

    @app.get("/products/{sku}")
    def get_product(
        sku: str, session: SessionDep, cache: CacheDep, response: Response
    ) -> ProductOut:
        product, hit = CatalogService(
            ProductRepository(session), cache
        ).get_product(sku)
        response.headers["X-Cache"] = "HIT" if hit else "MISS"
        return product

    @app.post("/orders", status_code=status.HTTP_201_CREATED)
    def place_order(
        body: OrderIn, session: SessionDep, cache: CacheDep
    ) -> OrderOut:
        return OrderService(session, cache).place_order(body)

    @app.get("/customers/{customer_id}/orders")
    def list_orders(
        customer_id: int, session: SessionDep, cache: CacheDep
    ) -> list[OrderOut]:
        return OrderService(session, cache).list_for_customer(customer_id)

    return app
```

**File: `app/models.py`**

```python
"""ORM models (SQLAlchemy 2.0 typed declarative style)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    orders: Mapped[list[Order]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="ck_products_stock_nonneg"),
        CheckConstraint("price > 0", name="ck_products_price_pos"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    stock: Mapped[int] = mapped_column(default=0)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        # Supports "orders for customer X, newest first" without a sort.
        Index("ix_orders_customer_created", "customer_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(20), default="placed")
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_items_qty_pos"),
        UniqueConstraint("order_id", "product_id", name="uq_item_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
```

**File: `app/repositories.py`**

```python
"""Repositories: the only code that builds SQL for these tables."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Customer, Order, OrderItem, Product


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, name: str, email: str) -> Customer:
        customer = Customer(name=name, email=email)
        self.session.add(customer)
        self.session.flush()  # INSERT now so the id is available
        return customer

    def get(self, customer_id: int) -> Customer | None:
        return self.session.get(Customer, customer_id)


class ProductRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_sku(self, sku: str) -> Product | None:
        return self.session.scalar(
            select(Product).where(Product.sku == sku)
        )

    def get_by_skus(self, skus: Iterable[str]) -> dict[str, Product]:
        rows = self.session.scalars(
            select(Product).where(Product.sku.in_(list(skus)))
        )
        return {p.sku: p for p in rows}


class OrderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_customer(
        self, customer_id: int, *, limit: int = 20
    ) -> Sequence[Order]:
        stmt = (
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(limit)
            # Eager-load items and their products in 2 extra queries
            # total, instead of 1 query per order (the N+1 problem).
            .options(
                selectinload(Order.items).selectinload(OrderItem.product)
            )
        )
        return self.session.scalars(stmt).all()
```

**File: `app/schemas.py`**

```python
"""API schemas (separate from ORM models)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sku: str
    name: str
    price: Decimal
    stock: int


class OrderLineIn(BaseModel):
    sku: Annotated[str, Field(min_length=1, max_length=40)]
    quantity: Annotated[int, Field(ge=1, le=1000)]


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: int
    lines: Annotated[list[OrderLineIn], Field(min_length=1, max_length=50)]


class OrderLineOut(BaseModel):
    sku: str
    quantity: int
    unit_price: Decimal


class OrderOut(BaseModel):
    id: int
    customer_id: int
    status: str
    total: Decimal
    created_at: datetime
    lines: list[OrderLineOut]
```

**File: `app/seed.py`**

```python
"""Seed demo data: python -m app.seed"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, make_engine
from app.models import Customer, Product

PRODUCTS = [
    ("KB-01", "Mechanical keyboard", Decimal("89.00"), 25),
    ("MS-01", "Wireless mouse", Decimal("29.50"), 100),
    ("MN-27", "27-inch monitor", Decimal("249.99"), 5),
]


def seed(session: Session) -> None:
    if session.scalar(select(Product).limit(1)) is not None:
        return
    session.add_all(
        Product(sku=s, name=n, price=p, stock=q) for s, n, p, q in PRODUCTS
    )
    session.add(Customer(name="Jorge", email="jorge@example.com"))
    session.commit()


if __name__ == "__main__":
    engine = make_engine(get_settings())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
    print("seeded")
```

**File: `app/services/__init__.py`**

```python

```

**File: `app/services/catalog.py`**

```python
from __future__ import annotations

from app.cache import ProductCache
from app.errors import NotFoundError
from app.repositories import ProductRepository
from app.schemas import ProductOut


def cache_key(sku: str) -> str:
    return f"product:{sku}"


class CatalogService:
    def __init__(self, products: ProductRepository, cache: ProductCache):
        self._products = products
        self._cache = cache

    def get_product(self, sku: str) -> tuple[ProductOut, bool]:
        """Cache-aside: try cache, else DB then populate cache.

        Returns (product, served_from_cache)."""
        cached = self._cache.get(cache_key(sku))
        if cached is not None:
            return ProductOut.model_validate(cached), True
        product = self._products.get_by_sku(sku)
        if product is None:
            raise NotFoundError(f"Product {sku} not found.")
        out = ProductOut.model_validate(product)
        self._cache.set(cache_key(sku), out.model_dump(mode="json"))
        return out, False
```

**File: `app/services/orders.py`**

```python
"""Order placement: one transaction, atomic stock decrement."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.cache import ProductCache
from app.errors import (
    InsufficientStockError,
    NotFoundError,
    UnknownSkuError,
)
from app.models import Customer, Order, OrderItem, Product
from app.repositories import OrderRepository, ProductRepository
from app.schemas import OrderIn, OrderLineOut, OrderOut
from app.services.catalog import cache_key


def to_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        customer_id=order.customer_id,
        status=order.status,
        total=order.total,
        created_at=order.created_at,
        lines=[
            OrderLineOut(
                sku=item.product.sku,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item in order.items
        ],
    )


class OrderService:
    def __init__(self, session: Session, cache: ProductCache) -> None:
        self._session = session
        self._cache = cache

    def place_order(self, data: OrderIn) -> OrderOut:
        quantities = Counter[str]()
        for line in data.lines:
            quantities[line.sku] += line.quantity  # merge duplicate SKUs

        # session.begin(): COMMIT if the block finishes, ROLLBACK if it
        # raises. Either every row changes or none does (atomicity).
        with self._session.begin():
            if self._session.get(Customer, data.customer_id) is None:
                raise NotFoundError(
                    f"Customer {data.customer_id} not found."
                )
            products = ProductRepository(self._session).get_by_skus(
                quantities
            )
            missing = sorted(set(quantities) - set(products))
            if missing:
                raise UnknownSkuError(f"Unknown SKUs: {', '.join(missing)}")

            order = Order(customer_id=data.customer_id, total=Decimal("0"))
            total = Decimal("0")
            # Sorted order = every transaction locks rows in the same
            # order, which prevents deadlocks between concurrent orders.
            for sku in sorted(quantities):
                qty = quantities[sku]
                # Conditional UPDATE is atomic: check and decrement happen
                # in one statement, so two concurrent orders cannot both
                # take the last unit (no read-then-write race).
                row = self._session.execute(
                    update(Product)
                    .where(Product.sku == sku, Product.stock >= qty)
                    .values(stock=Product.stock - qty)
                    .returning(Product.id, Product.price)
                ).one_or_none()
                if row is None:
                    raise InsufficientStockError(
                        f"Not enough stock for {sku}."
                    )
                order.items.append(
                    OrderItem(
                        product=products[sku],
                        quantity=qty,
                        unit_price=row.price,
                    )
                )
                total += row.price * qty
            order.total = total
            self._session.add(order)
        # Invalidate AFTER commit so readers never re-cache stale stock.
        self._cache.delete(*(cache_key(s) for s in quantities))
        return to_out(order)

    def list_for_customer(self, customer_id: int) -> list[OrderOut]:
        if self._session.get(Customer, customer_id) is None:
            raise NotFoundError(f"Customer {customer_id} not found.")
        orders = OrderRepository(self._session).list_for_customer(
            customer_id
        )
        return [to_out(o) for o in orders]
```

**File: `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:18
    environment:
      POSTGRES_USER: orders
      POSTGRES_PASSWORD: orders
      POSTGRES_DB: orders
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U orders"]
      interval: 5s
      retries: 10
  redis:
    image: redis:8
    ports: ["6379:6379"]
volumes:
  pgdata:
```

**File: `pyproject.toml`**

```toml
[project]
name = "orders-data"
version = "1.0.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 76
target-version = "py312"
extend-exclude = ["alembic/versions"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
packages = ["app"]
```

**File: `requirements-dev.txt`**

```text
-r requirements.txt
pytest>=8
httpx>=0.27
mypy>=1.10
ruff>=0.6
```

**File: `requirements.txt`**

```text
fastapi>=0.135
uvicorn[standard]>=0.30
pydantic>=2.9
pydantic-settings>=2.6
sqlalchemy>=2.0
alembic>=1.13
psycopg[binary]>=3.2
redis>=5.0
```

**File: `scripts/__init__.py`**

```python

```

**File: `scripts/explain_demo.py`**

```python
"""Show how an index changes a query plan (PostgreSQL only).

APP_DATABASE_URL=postgresql+psycopg://... python -m scripts.explain_demo
"""

from __future__ import annotations

from sqlalchemy import text

from app.config import get_settings
from app.db import make_engine

QUERY = """
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total, created_at FROM demo_orders
WHERE customer_id = 4242
ORDER BY created_at DESC
LIMIT 20
"""


def main() -> None:
    engine = make_engine(get_settings())
    if engine.dialect.name != "postgresql":
        raise SystemExit("This demo needs PostgreSQL (APP_DATABASE_URL).")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_orders"))
        conn.execute(
            text(
                "CREATE TABLE demo_orders (id bigserial PRIMARY KEY,"
                " customer_id int NOT NULL, total numeric(12,2) NOT NULL,"
                " created_at timestamptz NOT NULL)"
            )
        )
        # 500k rows, 10k customers: realistic enough to see the effect.
        conn.execute(
            text(
                "INSERT INTO demo_orders (customer_id, total, created_at)"
                " SELECT (random()*10000)::int,"
                " (random()*500)::numeric(12,2),"
                " now() - (random() * interval '365 days')"
                " FROM generate_series(1, 500000)"
            )
        )
        conn.execute(text("ANALYZE demo_orders"))
        print("--- BEFORE index ---")
        for row in conn.execute(text(QUERY)):
            print(row[0])
        conn.execute(
            text(
                "CREATE INDEX ix_demo_customer_created"
                " ON demo_orders (customer_id, created_at DESC)"
            )
        )
        conn.execute(text("ANALYZE demo_orders"))
        print("--- AFTER index ---")
        for row in conn.execute(text(QUERY)):
            print(row[0])
        conn.execute(text("DROP TABLE demo_orders"))


if __name__ == "__main__":
    main()
```

**File: `tests/__init__.py`**

```python

```

**File: `tests/conftest.py`**

```python
"""Tests run on in-memory SQLite by default. Set TEST_DATABASE_URL to
a PostgreSQL URL to run the same suite (plus concurrency tests) there."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, make_engine
from app.main import create_app
from app.seed import seed

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")
IS_POSTGRES = TEST_DB_URL.startswith("postgresql")


@pytest.fixture
def settings() -> Settings:
    return Settings(database_url=TEST_DB_URL, redis_url="")


@pytest.fixture
def engine(settings: Settings) -> Iterator[Engine]:
    engine = make_engine(settings)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed(session)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    app = create_app(settings, create_schema=False)
    with TestClient(app) as test_client:
        # Share the test engine so the app sees the seeded data
        # (essential for in-memory SQLite).
        app.state.engine.dispose()
        from app.db import make_session_factory

        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        yield test_client
```

**File: `tests/test_api.py`**

```python
from fastapi.testclient import TestClient


def order(
    client: TestClient, *lines: tuple[str, int], customer_id: int = 1
):
    return client.post(
        "/orders",
        json={
            "customer_id": customer_id,
            "lines": [{"sku": s, "quantity": q} for s, q in lines],
        },
    )


def test_health_checks_database(client: TestClient) -> None:
    assert client.get("/health").json()["database"] == "up"


def test_create_customer_and_duplicate_email(client: TestClient) -> None:
    body = {"name": "Ada", "email": "Ada@Example.com"}
    first = client.post("/customers", json=body)
    assert first.status_code == 201
    assert first.json()["email"] == "ada@example.com"
    second = client.post("/customers", json=body)
    assert second.status_code == 409


def test_product_read_is_cached(client: TestClient) -> None:
    first = client.get("/products/KB-01")
    second = client.get("/products/KB-01")
    assert first.headers["x-cache"] == "MISS"
    assert second.headers["x-cache"] == "HIT"
    assert second.json()["stock"] == 25


def test_place_order_decrements_stock_and_totals(
    client: TestClient,
) -> None:
    response = order(client, ("KB-01", 2), ("MS-01", 1))
    assert response.status_code == 201
    body = response.json()
    assert body["total"] == "207.50"  # 2*89.00 + 29.50
    assert client.get("/products/KB-01").json()["stock"] == 23


def test_duplicate_skus_in_one_order_are_merged(client: TestClient) -> None:
    response = order(client, ("MS-01", 1), ("MS-01", 2))
    assert response.status_code == 201
    assert response.json()["lines"] == [
        {"sku": "MS-01", "quantity": 3, "unit_price": "29.50"}
    ]


def test_insufficient_stock_rolls_back_everything(
    client: TestClient,
) -> None:
    # KB-01 succeeds first (sorted order), then MN-27 fails: the KB-01
    # decrement must be rolled back too.
    response = order(client, ("MN-27", 6), ("KB-01", 1))
    assert response.status_code == 409
    assert response.json()["title"] == "Insufficient stock"
    assert client.get("/products/KB-01").json()["stock"] == 25
    assert client.get("/customers/1/orders").json() == []


def test_cache_is_invalidated_after_order(client: TestClient) -> None:
    assert client.get("/products/MN-27").json()["stock"] == 5
    assert order(client, ("MN-27", 2)).status_code == 201
    after = client.get("/products/MN-27")
    assert after.headers["x-cache"] == "MISS"
    assert after.json()["stock"] == 3


def test_unknown_sku_and_customer(client: TestClient) -> None:
    assert order(client, ("NOPE", 1)).status_code == 422
    assert order(client, ("KB-01", 1), customer_id=999).status_code == 404


def test_order_validation(client: TestClient) -> None:
    assert order(client).status_code == 422  # no lines
    assert order(client, ("KB-01", 0)).status_code == 422


def test_list_orders_newest_first(client: TestClient) -> None:
    order(client, ("KB-01", 1))
    order(client, ("MS-01", 1))
    orders = client.get("/customers/1/orders").json()
    assert [o["lines"][0]["sku"] for o in orders] == ["MS-01", "KB-01"]
    assert client.get("/customers/999/orders").status_code == 404
```

**File: `tests/test_cache.py`**

```python
import time

from app.cache import InMemoryProductCache, RedisProductCache


def test_in_memory_cache_expires() -> None:
    cache = InMemoryProductCache(ttl_seconds=0)
    cache.set("k", {"a": 1})
    time.sleep(0.01)
    assert cache.get("k") is None


def test_redis_outage_degrades_to_cache_miss() -> None:
    # Nothing listens on port 1: every call fails fast and is swallowed.
    cache = RedisProductCache("redis://127.0.0.1:1/0", ttl_seconds=60)
    cache.set("k", {"a": 1})
    assert cache.get("k") is None
    cache.delete("k")
```

**File: `tests/test_concurrency.py`**

```python
"""Two customers race for the last unit. Exactly one may win.

Runs only against PostgreSQL (real row locks); SQLite serialises
writes for the whole database, which hides the race."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.cache import InMemoryProductCache
from app.db import make_session_factory
from app.errors import InsufficientStockError
from app.models import Product
from app.schemas import OrderIn
from app.services.orders import OrderService
from tests.conftest import IS_POSTGRES

pytestmark = pytest.mark.skipif(
    not IS_POSTGRES, reason="needs TEST_DATABASE_URL=postgresql+psycopg://"
)


def test_last_unit_is_sold_once(engine: Engine) -> None:
    factory = make_session_factory(engine)
    with Session(engine) as session:
        session.query(Product).filter_by(sku="MN-27").update({"stock": 1})
        session.commit()

    def attempt(_: int) -> str:
        with factory() as session:
            service = OrderService(session, InMemoryProductCache(60))
            try:
                service.place_order(
                    OrderIn.model_validate(
                        {
                            "customer_id": 1,
                            "lines": [{"sku": "MN-27", "quantity": 1}],
                        }
                    )
                )
                return "ok"
            except InsufficientStockError:
                return "sold out"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))

    assert results.count("ok") == 1
    assert results.count("sold out") == 7
    with Session(engine) as session:
        stock = session.query(Product).filter_by(sku="MN-27").one().stock
        assert stock == 0
```

**File: `tests/test_constraints.py`**

```python
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Order, Product


def test_stock_cannot_go_negative(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            Product(sku="X", name="x", price=Decimal("1"), stock=-1)
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_order_requires_existing_customer(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(Order(customer_id=12345, total=Decimal("1")))
        with pytest.raises(IntegrityError):
            session.commit()
```

**File: `tests/test_repositories.py`**

```python
from decimal import Decimal

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product
from app.repositories import OrderRepository


def test_list_orders_avoids_n_plus_one(engine: Engine) -> None:
    with Session(engine) as session:
        product = session.query(Product).filter_by(sku="KB-01").one()
        for _ in range(5):
            session.add(
                Order(
                    customer_id=1,
                    total=Decimal("89.00"),
                    items=[
                        OrderItem(
                            product=product,
                            quantity=1,
                            unit_price=Decimal("89.00"),
                        )
                    ],
                )
            )
        session.commit()

    statements: list[str] = []

    def count(*args: object) -> None:
        statements.append(str(args[2]))  # (conn, cursor, statement, ...)

    event.listen(engine, "before_cursor_execute", count)
    try:
        with Session(engine) as session:
            orders = OrderRepository(session).list_for_customer(1)
            skus = [i.product.sku for o in orders for i in o.items]
    finally:
        event.remove(engine, "before_cursor_execute", count)

    assert len(skus) == 5
    # orders + items + products = 3 queries, regardless of order count.
    assert len(statements) == 3
```


### How to Run

```bash
cd projects/unit03-data/solution
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed && uvicorn app.main:create_app --factory --reload
pytest -q
# PostgreSQL + Redis:
docker compose up -d && cp .env.example .env
alembic upgrade head && python -m app.seed
uvicorn app.main:create_app --factory --reload
```

### Verify the Solution

1. `pytest -q` on SQLite gives **15 passed, 1 skipped** (the concurrency test).
2. Against PostgreSQL: **16 passed**, including `test_last_unit_is_sold_once`.
3. `curl -i localhost:8000/products/KB-01` twice gives `X-Cache: MISS`, then `HIT`.
4. Place the order shown above and check that `stock` dropped by 2.
5. Order 6 × MN-27: **409**. `GET /customers/1/orders` shows no new order (rollback).
6. Stop Redis (`docker compose stop redis`). Product reads still work, and the logs show "cache get failed".
7. `python -m scripts.explain_demo` shows a seq scan before and an index scan after.

### Project Interview Debrief

1. **Why an atomic `UPDATE ... WHERE stock >= q` instead of reading the stock first?**
   Reading and then writing is a race under Read Committed: two requests can both read stock 1. One conditional UPDATE checks and writes atomically under a row lock. The concurrency test proves it.
2. **What would break first at scale?**
   Hot rows (a popular SKU) serialize writers, and the connection count grows with replicas. Mitigations: keep transactions short, add PgBouncer or RDS Proxy, possibly use a reservation pattern or queue for flash sales, read replicas for listings, and keyset pagination.
3. **Why invalidate the cache instead of updating it?**
   Deleting after commit is simpler and avoids writing a value computed from a transaction that might not commit. The next read repopulates from the source of truth.
4. **What would you change for production?**
   Run migrations as a deploy step, use DB credentials from a secret manager, add pool metrics and slow-query logging, add idempotency keys on `POST /orders` (Unit 8), monitor with `pg_stat_statements`, run backups and restore drills.
5. **Why SQLite in tests if production is PostgreSQL?**
   Fast feedback for logic. But concurrency, locking and some SQL behavior differ, so CI also runs the suite against a real PostgreSQL service (Unit 7) — never SQLite alone.
