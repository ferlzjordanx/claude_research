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

{{tree projects/unit01-python/solution}}

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

{{file projects/unit01-python/starter/quotes/pricing.py}}

{{file projects/unit01-python/starter/quotes/retry.py}}

{{file projects/unit01-python/starter/quotes/utils.py}}

{{file projects/unit01-python/starter/quotes/aggregator.py}}

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

{{files projects/unit01-python/solution}}

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
