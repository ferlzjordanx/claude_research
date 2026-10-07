# Part XVIII — Interview Preparation

**What this part teaches.** Part XVIII converts knowledge into interview performance across four tracks: Python language depth (Unit 49), FastAPI/backend engineering (Unit 50), algorithms and data structures (Unit 51), and AI/Forward-Deployed-Engineer scenarios (Unit 52). Each unit is organized for drilling: three-level explanations, code reading and debugging, timed builds, and scenario practice.

**Why it matters.** Interviews compress years of judgment into 45–60 minutes. Candidates fail not because they don't know things but because they can't retrieve and communicate them under time pressure: they ramble on easy questions, freeze on debugging, or skip clarification on design questions. Deliberate practice — answering out loud, timed, with feedback — fixes that.

**Where it appears.** Phone screens (quick questions), technical rounds (coding and code reading), system design rounds, take-home/timed builds, and customer-facing scenario rounds for FDE roles.

**Connections.** Every earlier unit of the curriculum feeds this part; Units 47–48 supply design content, and the Unit 53 capstone becomes the project you discuss in behavioral and scenario rounds.

**How to practice every unit in this part.**

1. Answer aloud and record yourself. Review for filler, missing structure, and inaccuracies.
2. Use the **three-tier format**: 30 seconds (definition + one key insight), 2 minutes (mechanism + example + trade-off), deep (internals, edge cases, production story).
3. For code questions: **predict output before running**; then verify; then explain why.
4. Track weak topics in a spreadsheet; revisit with spaced repetition (1, 3, 7, 14 days).

## Unit 49 — Python Interview Track

### 1. Learning Objectives

1. **Explain** the Python object model — identity, type, value; names vs objects; mutability; `is` vs `==` — in 30 seconds, 2 minutes and in depth.
2. **Predict** the output of code involving aliasing, mutable defaults, late-binding closures, scope rules (LEGB, `nonlocal`, `global`), and generator laziness.
3. **Implement** decorators (with and without arguments, preserving metadata via `functools.wraps`, sync and async), context managers, generators, and descriptors.
4. **Explain** the data model (`__eq__`/`__hash__` contract, `__repr__`, `__iter__`, `__getattr__` vs `__getattribute__`, `__slots__`) and MRO via C3 linearization with `super()`.
5. **Compare** built-in collections and their complexities; choose among `list`, `deque`, `dict`, `set`, `heapq`, `Counter`, `defaultdict`, `OrderedDict`, dataclasses and named tuples.
6. **Explain** typing in modern Python: generics (PEP 695 syntax in 3.12), `Protocol`, `TypedDict`, `Literal`, `Self`, `TypeGuard`/`TypeIs`, variance, and the runtime/static boundary.
7. **Explain** memory management in CPython — reference counting, cyclic GC, generational thresholds, interning/small-int caching — and the GIL, including the free-threaded build status.
8. **Compare** threads, processes and asyncio for I/O- and CPU-bound workloads and **debug** concurrency bugs (race conditions, blocking the loop, unawaited coroutines, cancellation).
9. **Test** Python code with pytest fixtures, parametrization, mocking, Hypothesis property tests and async test support.
10. **Optimize** Python code with profiling (cProfile, py-spy, Scalene), algorithmic changes, and appropriate built-ins, and articulate when not to optimize.

### 2. Prerequisite Knowledge

Comfortable Python programming; basic familiarity with CPython being the reference implementation written in C; awareness of bytecode (`dis` module). Supported versions as of October 2026: **3.10 (security-only until Oct 2026 EOL), 3.11, 3.12, 3.13 and 3.14**; 3.15 is in development. Interview answers should use modern syntax (3.10+ `match`, `X | Y` unions, 3.12 generic syntax) but mention version differences when relevant.

### 3. Mental Model

```
Source (.py)
  ↓ tokenizer → parser (PEG, 3.9+) → AST
  ↓ compiler (symbol table decides local/global/free/cell for each name)
Code objects (bytecode + constants + names)          ← cached in __pycache__/*.pyc
  ↓ CPython evaluation loop (specializing adaptive interpreter, 3.11+)
Frames (locals, value stack) executing on a thread holding the GIL (default build)
  ↓ operating on
Objects on the heap: every object = header (refcount, type pointer) + data
  ↓ lifetime managed by
Reference counting (immediate) + cyclic garbage collector (periodic)
```

**Names are labels attached to objects.** Assignment never copies; it binds a name to an object. Mutation changes an object; rebinding changes which object a name refers to. Almost every Python "gotcha" reduces to confusing these two.

### 4. Comprehensive Theory

#### 4.1 Object Model: Identity, Equality, Mutability

- Every object has an **identity** (`id()`; in CPython the memory address), a **type** (fixed at creation, mostly), and a **value**.
- `is` compares identity; `==` calls `__eq__` (value equality, customizable).
- Use `is` only for singletons: `None`, `True`/`False` (rarely needed), sentinels (`_MISSING = object()`), `Ellipsis`/`NotImplemented`.
- **CPython caching details (implementation-specific, never rely on them):** small ints −5..256 are cached; some strings are interned (identifier-like literals, `sys.intern`); constants within one code object may be shared. Hence `a = 256; b = 256; a is b` is `True` but `1000 is 1000`-style comparisons vary by context (and emit `SyntaxWarning: "is" with a literal` since 3.8).

**Mutability.** Mutable: list, dict, set, bytearray, most user objects. Immutable: int, float, str, bytes, tuple, frozenset, `None`. A tuple is immutable *shallowly*: `t = ([1], 2); t[0].append(3)` works. Hashability requires an immutable *hash-relevant* state: `hash(([1],))` raises `TypeError`.

**Aliasing and copying.** `b = a` aliases; `a[:]`, `list(a)`, `copy.copy(a)` shallow-copy; `copy.deepcopy(a)` copies recursively (handles cycles via memo). Classic bug: `grid = [[0] * 3] * 3` creates three references to the same inner list.

**Interview perspective.** "Explain `is` vs `==`" tests whether you understand identity vs value and avoid relying on CPython caching. Strong answer includes `None` checks and the warning for literal comparisons.

#### 4.2 Functions: Scope, Defaults, Closures

**Default arguments are evaluated once, at function definition time.**

```python
def append_to(item, bucket=[]):     # one list shared across calls
    bucket.append(item)
    return bucket

append_to(1); append_to(2)          # → [1, 2]

def append_to_fixed(item, bucket: list | None = None) -> list:
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket
```

Why: `def` is an executable statement; defaults are stored in `func.__defaults__`. Same applies to dataclass fields (hence `field(default_factory=list)`, and dataclasses raise `ValueError` for mutable defaults like `list`).

**Scope (LEGB).** Local → Enclosing → Global → Builtins. The compiler decides at compile time whether a name is local: any assignment in a function makes it local throughout the function, hence `UnboundLocalError`:

```python
count = 0
def inc():
    count += 1        # UnboundLocalError: count is local because it's assigned
```

Fix with `global count` (module state — usually a design smell) or `nonlocal` for enclosing function scopes.

**Closures.** An inner function capturing variables from an enclosing scope keeps them alive via **cell objects** (`func.__closure__`). Closures capture *variables*, not values — **late binding**:

```python
fns = [lambda: i for i in range(3)]
[f() for f in fns]                  # [2, 2, 2]
fns = [lambda i=i: i for i in range(3)]     # bind current value as default → [0, 1, 2]
```

**First-class functions, `*args/**kwargs`, keyword-only (`*`) and positional-only (`/`) parameters**, `functools.partial`, and `functools.cache/lru_cache` (memoization; arguments must be hashable; unbounded cache can leak memory; on methods it holds references to `self`).

#### 4.3 Decorators

**Definition.** A decorator is a callable that takes a callable (or class) and returns a replacement. `@d` above `def f` is sugar for `f = d(f)`, evaluated at definition time.

```python
import functools
import time
from collections.abc import Callable, Awaitable
from typing import ParamSpec, TypeVar
import inspect

P = ParamSpec("P")
R = TypeVar("R")


def timed(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)                         # copies __name__, __doc__, __wrapped__, etc.
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            print(f"{fn.__qualname__} took {time.perf_counter() - start:.4f}s")
    return wrapper


def retry(times: int = 3, exceptions: tuple[type[BaseException], ...] = (Exception,)):
    """Decorator factory: works for sync and async functions."""
    def decorator(fn):
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrapper(*args, **kwargs):
                for attempt in range(1, times + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except exceptions:
                        if attempt == times:
                            raise
            return awrapper

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise
        return wrapper
    return decorator
```

Key points: decorator *with arguments* is a factory returning a decorator (three levels of nesting); `functools.wraps` preserves metadata and sets `__wrapped__` (used by `inspect.signature`, which FastAPI relies on — a decorator without `wraps` on a FastAPI endpoint breaks parameter detection); decorating an `async def` with a sync wrapper returns a coroutine without awaiting it — handle both; class decorators and `__call__`-based decorators for stateful decoration; stacking order is bottom-up application (`@a @b def f` → `a(b(f))`).

#### 4.4 Iterators and Generators

- **Iterable**: has `__iter__` returning an iterator. **Iterator**: has `__next__` (raises `StopIteration` when exhausted) and `__iter__` returning itself. Iterators are single-pass.
- **Generator function**: contains `yield`; calling it returns a generator object without running the body. Each `next()` resumes until the next `yield`. The frame is suspended and kept alive between steps — this is how generators use O(1) memory for streams.
- **Generator expressions** `(x*x for x in data)` are lazy; list comprehensions are eager.
- `yield from sub` delegates to a sub-iterator (and forwards `send`/`throw`); the value of `return x` in a generator becomes `StopIteration.value`.
- `send()`, `throw()`, `close()` (raises `GeneratorExit` at the paused `yield`; `finally` blocks run).
- Since PEP 479 (3.7), a `StopIteration` raised inside a generator becomes `RuntimeError`.
- **Context managers via generators**: `contextlib.contextmanager` (and `asynccontextmanager`); FastAPI's `yield` dependencies build on this idea.

```python
from collections.abc import Iterator, Iterable


def batched_lines(path: str, size: int) -> Iterator[list[str]]:
    batch: list[str] = []
    with open(path, encoding="utf-8") as fh:     # file closed even if consumer stops early (on close/GC)
        for line in fh:
            batch.append(line.rstrip("\n"))
            if len(batch) == size:
                yield batch
                batch = []
    if batch:
        yield batch

# Python 3.12+: itertools.batched(iterable, n) yields tuples
```

**Gotcha:** a generator can be consumed only once — `sum(gen)` then `max(gen)` → `max()` raises `ValueError` on empty. Another: generator laziness means exceptions occur at iteration time, not at call time.

#### 4.5 Data Model and OOP

**Special methods** let user classes integrate with syntax: `__repr__` (unambiguous; dev-facing) vs `__str__` (user-facing); `__eq__` and `__hash__` (objects that compare equal must have equal hashes; defining `__eq__` sets `__hash__ = None` unless you define it); `__lt__` etc. (`functools.total_ordering`); `__len__`, `__getitem__`, `__contains__`, `__iter__`; `__enter__/__exit__`; `__call__`; `__bool__`.

**Attribute lookup** (`obj.attr`) via `type(obj).__getattribute__`:
1. Look up `attr` on the type's MRO. If it's a **data descriptor** (defines `__set__` or `__delete__`), call its `__get__`.
2. Else check `obj.__dict__`.
3. Else if found on type as a **non-data descriptor** (only `__get__`, e.g. functions), call `__get__` (this is how methods bind `self`).
4. Else return the class attribute.
5. Else call `__getattr__` if defined (only on failure).

**Descriptors** power `property`, methods, `classmethod`, `staticmethod`, `__slots__`, and ORMs/validators (SQLAlchemy `Mapped` attributes, Django fields).

```python
class Positive:
    def __set_name__(self, owner, name):        # 3.6+: learns its attribute name
        self.private = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self                          # accessed on class
        return getattr(obj, self.private)

    def __set__(self, obj, value):
        if value <= 0:
            raise ValueError(f"{self.private[1:]} must be positive")
        setattr(obj, self.private, value)


class Order:
    quantity = Positive()
    def __init__(self, quantity: int) -> None:
        self.quantity = quantity                 # goes through Positive.__set__
```

**MRO and C3 linearization.** For `class D(B, C)` with `B(A)`, `C(A)`: `D.__mro__ == (D, B, C, A, object)`. C3 guarantees: children before parents, left-to-right order of bases preserved, and consistency (or `TypeError: Cannot create a consistent method resolution order`). `super()` means "next in the MRO of the instance's type," not "my parent" — enabling cooperative multiple inheritance where every class calls `super().__init__(**kwargs)`.

```python
class A:
    def hello(self): return "A"
class B(A):
    def hello(self): return "B>" + super().hello()
class C(A):
    def hello(self): return "C>" + super().hello()
class D(B, C):
    def hello(self): return "D>" + super().hello()

D().hello()       # 'D>B>C>A' — B's super() is C for a D instance
```

**Other OOP essentials.** `@classmethod` (alternative constructors), `@staticmethod`, `@property`, `abc.ABC` and `@abstractmethod`, `__slots__` (no per-instance `__dict__`; memory savings; no new attributes; affects weakrefs and multiple inheritance), `dataclasses` (`frozen=True`, `slots=True` (3.10+), `kw_only=True`, `field(default_factory=...)`), `__init_subclass__` (simpler than metaclasses for registration), metaclasses (rarely needed; class creation customization), composition over inheritance.

#### 4.6 Collections and Complexity

| Type | Access | Insert/Delete | Membership | Notes |
|---|---|---|---|---|
| `list` | O(1) index | O(1) amortized append; O(n) insert/pop(0) | O(n) | Dynamic array; over-allocates |
| `collections.deque` | O(1) ends; O(n) middle | O(1) both ends | O(n) | Queues, sliding windows; `maxlen` |
| `dict` | O(1) avg | O(1) avg | O(1) avg | Insertion-ordered (guaranteed 3.7+); compact layout |
| `set`/`frozenset` | — | O(1) avg | O(1) avg | Hash table |
| `heapq` on list | O(1) min | O(log n) push/pop | O(n) | Min-heap; negate for max-heap; tuples for priority |
| `bisect` on sorted list | O(log n) search | O(n) insert | O(log n) | Use for sorted sequences |
| `Counter` | dict | dict | dict | `most_common(k)` uses heap, O(n log k) |
| `defaultdict` | dict | dict | dict | Missing key calls factory — beware accidental insertion on read |
| `str` | O(1) index | immutable; concatenation in loop O(n²) worst — use `"".join` | O(n·m) substring | |

Hash table worst cases are O(n) (adversarial collisions; Python randomizes `str`/`bytes` hashes per process via `PYTHONHASHSEED` to mitigate).

#### 4.7 Typing

- Annotations are **not enforced at runtime** by the interpreter; static checkers (mypy, pyright) and libraries (Pydantic, FastAPI) read them. **[Version-dependent]** Python 3.14 implements PEP 649/749 lazily evaluated annotations (accessed via `annotationlib`); `from __future__ import annotations` (stringified annotations) remains available.
- Modern syntax: `list[int]`, `dict[str, int]` (3.9+), `int | None` (3.10+), `type Alias = ...` and `def first[T](xs: list[T]) -> T` (PEP 695, 3.12+), `Self` (3.11), `@override` (3.12), `TypeIs` (3.13), `ReadOnly` TypedDict items (3.13), type parameter defaults (3.13).
- `Protocol` = structural typing (duck typing checked statically); `ABC` = nominal, runtime-enforced abstract methods. `@runtime_checkable` Protocols check only method presence at runtime.
- `TypedDict` for dict shapes (JSON); `dataclass` for internal records; Pydantic for validated boundaries.
- `Any` disables checking; `object` accepts anything but requires narrowing. `cast()` is a lie you tell the checker. Prefer `TypeGuard`/`TypeIs` for custom narrowing.
- **Variance:** `list[Cat]` is not a `list[Animal]` (lists are invariant because they're mutable); `Sequence[Cat]` is a `Sequence[Animal]` (covariant, read-only).
- `Callable[P, R]` with `ParamSpec` preserves signatures through decorators.

#### 4.8 Memory, GC and the GIL

**Reference counting.** Each object stores a refcount; incremented when a reference is created, decremented when one is dropped; at zero the object is deallocated immediately (deterministic destruction; `__del__` runs). `sys.getrefcount(x)` (one higher than you expect, due to the argument). **[Version-dependent]** 3.12 introduced **immortal objects** (PEP 683) — e.g. `None`, small ints — whose refcounts don't change.

**Cyclic GC.** Reference counting can't free cycles (`a.self = a`). The `gc` module periodically finds unreachable cycles among container objects. Historically three generations with thresholds (`gc.get_threshold()`); **[Version-dependent]** 3.13/3.14 changed the collector (3.14 introduced an incremental collector design with fewer generations to reduce pause times — check `gc` docs for your version). `gc.collect()`, `gc.freeze()` (useful before forking workers to reduce copy-on-write), `weakref` to avoid cycles in caches/observers.

**Memory tools.** `tracemalloc` (allocation snapshots and diffs), `sys.getsizeof` (shallow!), `pympler`, `memray` (Bloomberg's memory profiler, native-aware).

**The GIL.** In the default CPython build, the Global Interpreter Lock allows only one thread to execute Python bytecode at a time per interpreter. Threads switch on a time interval (`sys.getswitchinterval()`, default 5 ms) or when blocking I/O releases the GIL. Implications:

- I/O-bound threading works well (the GIL is released during blocking syscalls).
- CPU-bound pure-Python threading doesn't scale across cores; use `multiprocessing`/`ProcessPoolExecutor`, or C extensions that release the GIL (NumPy, many compression/crypto libs).
- **The GIL does not make your code thread-safe.** It protects interpreter internals, not your invariants. `counter += 1` is multiple bytecodes (load, add, store) and can race. Use `threading.Lock`, queues, or immutable data.
- **[Version-dependent]** Free-threaded CPython (`python3.13t`/`python3.14t`, PEP 703) removes the GIL; PEP 779 made it officially supported (but non-default) in 3.14 with roughly 5–10% single-thread overhead. C extensions must declare support; many popular packages now ship free-threaded wheels. Subinterpreters with per-interpreter GILs (PEP 684) and the `concurrent.interpreters` module (3.14, PEP 734) are another parallelism path.

#### 4.9 Concurrency: Threads, Processes, AsyncIO

| Model | Parallelism (default build) | Best for | Costs |
|---|---|---|---|
| Threads (`threading`, `ThreadPoolExecutor`) | No for Python bytecode; yes during I/O/C code | Blocking I/O libraries, moderate concurrency | Races, locks, ~MBs per thread stack |
| Processes (`multiprocessing`, `ProcessPoolExecutor`) | Yes | CPU-bound | Pickling overhead, memory, startup (spawn vs fork) |
| AsyncIO | No (single thread) | Massive I/O concurrency with async libraries | Function coloring, blocking calls stall everything |

**AsyncIO essentials.**
- `async def` returns a coroutine object; nothing runs until it's awaited or scheduled as a task.
- The event loop runs ready callbacks/tasks; an `await` on an incomplete future yields control.
- `asyncio.create_task` schedules concurrently — **keep a reference** (the loop holds only weak refs; unreferenced tasks may be GC'd) or use `TaskGroup` (3.11+), which also gives structured error handling (`ExceptionGroup`, `except*`).
- `asyncio.gather` vs `TaskGroup`: gather by default doesn't cancel siblings on failure; TaskGroup does.
- Timeouts: `async with asyncio.timeout(5):` (3.11+), `asyncio.wait_for`.
- Cancellation: raises `CancelledError` at the `await` point; always clean up in `finally`; don't swallow `CancelledError` (it's a `BaseException` since 3.8).
- Bridge to blocking code: `await asyncio.to_thread(fn, ...)`; CPU work: `loop.run_in_executor(process_pool, fn)`.
- Synchronization: `asyncio.Lock/Semaphore/Event/Queue` (not thread-safe; for coroutines on one loop).
- Debugging: `asyncio.run(main(), debug=True)` or `PYTHONASYNCIODEBUG=1` reports never-awaited coroutines and slow callbacks.

#### 4.10 Testing and Performance

**Testing.** pytest fixtures (scopes: function/module/session; `yield` fixtures for teardown), `parametrize`, `monkeypatch`, `tmp_path`, `unittest.mock` (`patch` where the name is *looked up*, not where it's defined; `autospec=True` to catch signature drift; `AsyncMock`), Hypothesis for properties (e.g. `decode(encode(x)) == x`), `pytest-asyncio` or AnyIO's pytest plugin for async tests, coverage (`pytest --cov`), and mutation testing (mutmut) for test-suite quality.

**Performance.** Measure first: `timeit` for micro-benchmarks, `cProfile` + `snakeviz`/`pstats` for deterministic profiling, `py-spy` (sampling, attach to production processes, flame graphs), Scalene (CPU/memory/GPU line-level). Typical wins in order: better algorithm/data structure → avoid repeated work (caching, hoisting) → built-ins and comprehension (C-implemented loops) → vectorization (NumPy) → concurrency → compiled extensions (Cython, Rust via PyO3, mypyc). **[Version-dependent]** 3.11+ is substantially faster thanks to the specializing adaptive interpreter; 3.13+ includes an experimental JIT (off by default).

### 5. Internal Mechanics

**Bytecode for `x += 1` (3.12+):**

```python
import dis
def f():
    global x
    x += 1
dis.dis(f)
#   LOAD_GLOBAL  x
#   LOAD_CONST   1
#   BINARY_OP    13 (+=)
#   STORE_GLOBAL x
```

A thread switch can occur between `LOAD_GLOBAL` and `STORE_GLOBAL` → lost updates. This is the concrete proof that the GIL doesn't make compound operations atomic.

**Method binding.** `obj.method` finds a function on the class; functions are non-data descriptors whose `__get__` returns a bound method object holding `__self__` and `__func__`. `obj.method is obj.method` is `False` (new bound method each time).

**Closure cells.** `f.__code__.co_freevars` lists captured names; `f.__closure__[i].cell_contents` holds current values — late binding is visible here.

**Generators.** A generator object holds a suspended frame (`gi_frame`), its instruction pointer, and local variables. `gi_suspended`/`inspect.getgeneratorstate` show state.

**Dict internals.** Compact dict: an index table (sparse, small ints) + dense entries array (hash, key, value) in insertion order — why dicts are ordered and memory-efficient. Key-sharing dicts for instances of the same class reduce memory.

### 6. Implementation Examples

#### Example 1 — Minimal: Demonstrate identity, aliasing and copying

```python
import copy

a = [[1, 2], [3, 4]]
b = a                 # alias
c = a[:]              # shallow copy
d = copy.deepcopy(a)  # deep copy

a[0].append(99)
print(b[0], c[0], d[0])      # [1, 2, 99] [1, 2, 99] [1, 2]
print(a is b, a is c, a == c) # True False True
```

#### Example 2 — Realistic: LRU cache with TTL as a decorator, typed, sync-only

```python
import functools
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")


def ttl_lru_cache(maxsize: int = 128, ttl_s: float = 60.0,
                  clock: Callable[[], float] = time.monotonic):
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        store: OrderedDict[Hashable, tuple[float, R]] = OrderedDict()

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            key = (args, tuple(sorted(kwargs.items())))
            now = clock()
            if key in store:
                expires, value = store[key]
                if expires > now:
                    store.move_to_end(key)
                    return value
                del store[key]
            value = fn(*args, **kwargs)
            store[key] = (now + ttl_s, value)
            if len(store) > maxsize:
                store.popitem(last=False)          # evict least recently used
            return value

        wrapper.cache_clear = store.clear          # type: ignore[attr-defined]
        return wrapper
    return decorator
```

Discussion points: keys must be hashable; not thread-safe (add a `threading.Lock` for threaded use — the GIL won't protect the check-then-act sequence); injectable clock for testing; for async functions you'd cache futures/tasks to coalesce concurrent misses.

#### Example 3 — Production-oriented: Thread-safe vs async-safe counters, with tests

```python
# counters.py
import asyncio
import threading


class ThreadSafeCounter:
    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def increment(self) -> None:
        with self._lock:
            self._value += 1

    @property
    def value(self) -> int:
        return self._value


class AsyncCounter:
    """Safe among coroutines on one event loop *only if* there's no await between read and write."""

    def __init__(self) -> None:
        self._value = 0
        self._lock = asyncio.Lock()

    async def increment_with_io(self, io: "Callable[[], Awaitable[None]]") -> None:
        async with self._lock:               # needed because we await between read and write
            current = self._value
            await io()
            self._value = current + 1
```

```python
# test_counters.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from counters import AsyncCounter, ThreadSafeCounter


def test_thread_safe_counter():
    c = ThreadSafeCounter()
    with ThreadPoolExecutor(max_workers=16) as pool:
        for _ in range(10_000):
            pool.submit(c.increment)
    assert c.value == 10_000


@pytest.mark.anyio
async def test_async_counter_with_await_inside_critical_section():
    c = AsyncCounter()
    await asyncio.gather(*(c.increment_with_io(lambda: asyncio.sleep(0)) for _ in range(100)))
    assert c._value == 100
```

Key insight for interviews: in asyncio, races occur only at `await` points; in threads, races occur between any bytecodes (and truly in parallel on free-threaded builds).

### 7. Comparative Analysis

| Comparison | Key difference | Trap |
|---|---|---|
| `is` vs `==` | Identity vs value equality | `x is 1000`; using `is` for strings |
| list vs tuple | Mutable vs immutable (shallow) | "Tuples make contents immutable" |
| shallow vs deep copy | Copies container vs recursively | Nested lists after `list(a)` |
| `__str__` vs `__repr__` | User vs developer | Missing `__repr__` makes debugging painful |
| `__getattr__` vs `__getattribute__` | Fallback on miss vs every access | Infinite recursion in `__getattribute__` |
| generator vs list comprehension | Lazy, single-pass vs eager, reusable | Iterating a generator twice |
| dataclass vs Pydantic vs plain class | Boilerplate reduction vs validation/serialization vs full control | Using Pydantic for internal hot-path objects unnecessarily |
| Protocol vs ABC | Structural (static) vs nominal (runtime) | Thinking Protocol enforces at runtime |
| threading vs multiprocessing vs asyncio | I/O with blocking libs vs CPU vs massive async I/O | "GIL means threads are useless" |
| `gather` vs `TaskGroup` | No automatic sibling cancel vs structured | Orphaned tasks after failure |
| `lru_cache` vs manual dict | Bounded, thread-safe internals vs control (TTL) | Caching methods leaks `self` |
| `@staticmethod` vs `@classmethod` | No implicit arg vs receives class | Alternative constructors should be classmethods |

### 8. Failure Modes and Debugging

**P1 — Shared state across requests.** SYMPTOM: one user's data appears in another's response. CAUSE: mutable default argument or module-level list in a FastAPI dependency. INVESTIGATE: look for `def f(x=[])`, module globals mutated per request. FIX: `None` sentinel, per-request objects. PREVENT: ruff rule `B006` (mutable default), code review.

**P2 — `UnboundLocalError`.** CAUSE: assignment makes a name local. FIX: rename, pass as parameter, `nonlocal`. PREVENT: avoid shadowing globals.

**P3 — Coroutine never awaited.** SYMPTOM: `RuntimeWarning: coroutine 'x' was never awaited`; side effect didn't happen. FIX: `await`, or schedule with TaskGroup. PREVENT: ruff/pyright checks; asyncio debug mode in tests.

**P4 — Memory leak in long-running worker.** SYMPTOM: RSS grows steadily. CAUSE: unbounded caches (`lru_cache(maxsize=None)` on methods), global lists, reference cycles with `__del__`, accumulating tasks. INVESTIGATE: `tracemalloc` snapshots diff, `memray`, `gc.get_objects()` counts by type, `objgraph`. FIX: bound caches, weakrefs. PREVENT: memory soak tests.

**P5 — Decorated FastAPI endpoint loses parameters.** CAUSE: decorator without `functools.wraps` hides the signature. FIX: `wraps`; for async endpoints, async wrapper.

**P6 — Race condition in threaded code.** INVESTIGATE: stress tests with many threads; `sys.setswitchinterval(1e-6)` to increase interleavings; reason about compound operations. FIX: locks, `queue.Queue`, atomic designs.

**P7 — Hash-related bugs.** SYMPTOM: objects "disappear" from sets/dicts. CAUSE: mutating fields used in `__hash__` after insertion; defining `__eq__` without `__hash__`. FIX: hash only immutable fields; `@dataclass(frozen=True)`.

**Tools.** `pdb`/`breakpoint()`, `python -X dev` (dev mode warnings), `faulthandler`, `traceback`, `dis`, `inspect`, `tracemalloc`, `py-spy dump` for hung processes.

### 9. Guided Practice

#### Level 1 — Concept Reinforcement
**1.1 Prediction drills.** Write 20 snippets covering aliasing, defaults, closures, scope, generators, MRO and predict outputs before running. Hints: (1) draw names→objects diagrams; (2) for closures, ask "when is the variable read?"
**1.2 Three-tier answers.** Prepare 30-s/2-min/deep explanations for: `is` vs `==`, mutable defaults, closures, decorators, generators, GIL, async, typing, MRO, descriptors. Record and time yourself. Hints: (1) 30 s = definition + one insight + one example; (2) deep = include CPython mechanism.

#### Level 2 — Implementation
**2.1 Decorators.** Implement `@retry(times, backoff, exceptions)` supporting sync and async, preserving signature; test with fake sleep. Hints: `inspect.iscoroutinefunction`, `functools.wraps`, inject a sleep function.
**2.2 Descriptor-based validation.** Implement `Typed`, `Bounded(min, max)` descriptors and a class using them; tests for errors and class-level access. Hints: `__set_name__`; return `self` when `obj is None`.
**2.3 Generator pipeline.** Build `read → parse → filter → batch` over a 1 GB synthetic file with constant memory; measure memory with `tracemalloc`. Hints: chain generators; `itertools.islice`.

#### Level 3 — Integration
**3.1 Concurrency comparison.** Download 200 URLs (local test server) and compute SHA-256 of large payloads, using threads, processes and asyncio (+ `to_thread` for hashing). Report timings and explain. Hints: separate I/O-bound and CPU-bound phases; try the free-threaded build if available.

#### Level 4 — Debugging
**4.1 Debug this.**

```python
class Registry:
    handlers = []                               # (1)
    def register(self, fn):
        self.handlers.append(fn); return fn

def make_multipliers():
    return [lambda x: x * i for i in range(4)]  # (2)

async def fetch_all(urls):
    for u in urls:
        asyncio.create_task(fetch(u))           # (3)

def process(items, seen=set()):                 # (4)
    for i in items:
        if i in seen: continue
        seen.add(i); yield i
```
Identify each bug, its symptom and the fix. Hints: class attribute shared by all instances; late binding; task references and no awaiting; mutable default persisting across calls.

### 10. Independent Implementation Project — "Python Interview Kit"

**Goal.** Build a personal repository that serves as your Python interview drill kit.

**Requirements.** (1) `topics/` with one Markdown file per interview topic (is/==, mutable defaults, closures, decorators, generators, GIL, async, typing, MRO, descriptors, data model, collections, memory, testing, performance), each with 30-s/2-min/deep answers. (2) `snippets/` with 50+ "predict the output" files and a pytest runner that checks your predictions recorded in comments. (3) `implementations/` with tested implementations: LRU+TTL cache, retry decorator (sync/async), descriptors, context managers (class and generator-based), a thread-safe bounded queue built on `Condition`, an async rate limiter, a generator pipeline. (4) `debugging/` with 15 broken programs and fixed versions plus explanations. (5) `bench/` with profiling exercises (cProfile, py-spy) and a write-up.

**Technical requirements.** Python 3.12+ (test on 3.14 too), `uv` for environment/dependency management, pytest, Hypothesis, pytest-asyncio or AnyIO plugin, mypy or pyright in strict mode, ruff.

**Structure.**
```
python-interview-kit/
├── pyproject.toml
├── topics/  snippets/  implementations/  debugging/  bench/
└── tests/ (test_snippets.py, test_implementations/, test_debugging/)
```

**Milestones.** Topics → snippets runner → implementations with tests → debugging set → profiling write-up → mock interview recordings.

**Testing.** 95%+ coverage on implementations; Hypothesis properties for cache and queue; concurrency stress tests; strict type checks pass.

**Definition of done.** You can draw a random topic and give all three tiers fluently; all snippets predicted correctly twice on separate days; CI green.

**Optional extensions.** Add free-threaded build CI job; write a tiny bytecode disassembler explainer; implement a metaclass-based plugin registry and compare with `__init_subclass__`.

### 11. Testing Strategy

- **Parametrize** language-behavior tests (e.g. MRO for several class graphs).
- **Property tests** for data structures (cache never exceeds `maxsize`; queue preserves FIFO order).
- **Concurrency tests** with many threads and reduced switch interval; async tests with `gather` and cancellation.
- **Mocking discipline**: patch where looked up; use `autospec`.
- **Type tests**: run mypy/pyright in CI; `typing.assert_type` in tests.

```python
from hypothesis import given, strategies as st
from implementations.cache import ttl_lru_cache


@given(st.lists(st.integers(min_value=0, max_value=50), max_size=500))
def test_cache_bounded_and_correct(keys):
    calls = []

    @ttl_lru_cache(maxsize=10, ttl_s=1e9)
    def square(x: int) -> int:
        calls.append(x)
        return x * x

    for k in keys:
        assert square(k) == k * k
    assert len(calls) <= len(keys)
```

### 12. Engineering Scenarios

1. **"Our CPU-heavy FastAPI endpoint doesn't scale with threads."** Reason: GIL; move to process pool or separate worker; consider free-threaded build only after verifying extension support and measuring.
2. **"Memory grows in Celery workers."** Use `tracemalloc` diffs; check unbounded caches; set `worker_max_tasks_per_child` as mitigation while fixing root cause.
3. **"Do we adopt strict typing?"** Trade-offs: catches bugs and improves refactoring vs annotation overhead; adopt gradually per module with CI gates.
4. **"Should we use dataclasses or Pydantic for domain objects?"** Pydantic at boundaries (validation/serialization), dataclasses (or attrs) internally for speed and simplicity — avoid validating the same data repeatedly.

### 13. Interview Preparation

#### Quick Questions

**Q: `is` vs `==`?**
Strong: `is` checks identity (same object), `==` checks value equality via `__eq__`. Use `is` for `None` and sentinels. Small-int and string caching are CPython details; never rely on them.
Trap: "`is` is faster so use it for ints."

**Q: Why are mutable default arguments dangerous?**
Strong: Defaults are evaluated once at definition time and stored on the function, so mutations persist across calls. Use `None` and create inside.

**Q: What is a closure?**
Strong: A function that retains access to variables from its enclosing scope after that scope has finished, via cell objects; variables are looked up when the inner function runs (late binding).

**Q: What does the GIL do?**
Strong: In default CPython, it ensures only one thread executes Python bytecode at a time, simplifying memory management (refcounts). It's released during blocking I/O and by some C extensions. It doesn't make your code thread-safe. Python 3.14 officially supports an optional free-threaded build.

**Q: What's a generator?**
Strong: A function with `yield` that returns a lazy iterator; its frame is suspended between values, giving O(1) memory streaming; single-pass.

#### Intermediate Questions

**Q: Write a decorator that accepts arguments. Explain each layer.**
Strong: Outer factory receives configuration → returns decorator receiving function → returns wrapper receiving call args; use `functools.wraps`; handle async separately. (See §4.3.)

**Q: Explain MRO with a diamond.**
Strong: C3 linearization yields D, B, C, A, object; `super()` follows the instance's MRO, enabling cooperative calls; inconsistent hierarchies raise `TypeError`.

**Q: What's a descriptor? Give a real-world use.**
Strong: An object defining `__get__`/`__set__`/`__delete__` that customizes attribute access when stored on a class. Properties, methods (binding), `classmethod`, ORMs (SQLAlchemy instrumented attributes) and validation fields use them. Data descriptors take precedence over instance `__dict__`; non-data do not.

**Q: When do you use asyncio vs threads vs processes?**
Strong: asyncio for many concurrent I/O operations with async libraries; threads for blocking libraries or modest concurrency; processes for CPU-bound parallelism (or free-threaded builds/subinterpreters when appropriate). Mention measuring and function coloring.

**Q: How does typing work at runtime?**
Strong: Annotations are metadata; not enforced by the interpreter; static checkers analyze them; frameworks like Pydantic/FastAPI introspect them at runtime to generate validation. 3.14 evaluates annotations lazily.

#### Advanced Questions

**Q: Why can `counter += 1` race even with the GIL? Show the bytecode.**
Strong: Load/add/store are separate bytecodes; a switch between load and store loses an update. Use a lock. On free-threaded builds, true parallelism makes races more frequent.

**Q: How does CPython free memory? What about cycles?**
Strong: Refcounting frees immediately at zero; cyclic GC detects unreachable cycles among containers; objects with finalizers in cycles are collectable since PEP 442 (3.4); weakrefs break cycles; `gc.freeze()` before fork reduces copy-on-write.

**Q: Explain cancellation in asyncio and how to write cancellation-safe code.**
Strong: `task.cancel()` raises `CancelledError` at the next await inside the task; use `try/finally` or async context managers to release resources; don't swallow `CancelledError` (re-raise); shield critical sections sparingly with `asyncio.shield`; TaskGroup cancels siblings on error; timeouts are implemented via cancellation.

**Q: How do `__eq__` and `__hash__` interact?**
Strong: Equal objects must have equal hashes; defining `__eq__` without `__hash__` makes instances unhashable; mutable objects shouldn't be hashable by mutable state.

#### Coding Questions

1. Implement `flatten(nested)` as a generator handling arbitrary depth (iterative with an explicit stack to avoid recursion limits); don't flatten strings.
2. Implement a context manager `timer()` both as a class and with `@contextmanager`.
3. Implement `@singledispatch`-based serializer for several types.
4. Implement a `Vector` class with `__add__`, `__mul__`, `__eq__`, `__hash__`, `__repr__`, `__iter__`, `__abs__`.
5. Implement an async `bounded_map(fn, items, limit)` preserving order.

#### Code Reading / Debugging Practice

Predict output:
```python
def gen():
    try:
        yield 1
        yield 2
    finally:
        print("cleanup")

g = gen()
print(next(g))
del g        # → prints 1, then "cleanup" (CPython: refcount drop → close() → GeneratorExit)
```

```python
x = 10
def outer():
    x = 20
    def inner():
        nonlocal x
        x += 1
        return x
    return inner
f = outer(); print(f(), f(), x)   # 21 22 10
```

### 14. Explain-It-at-Three-Levels

**Decorators.** *30 s:* A decorator wraps a function to add behavior; `@d` means `f = d(f)` at definition time. *2 min:* Explain closures holding the original function, `wraps`, decorators with arguments as factories, stacking order, and use cases (logging, retry, caching, auth in frameworks). *Deep:* Signature preservation via `__wrapped__` and `inspect.signature` (critical for FastAPI), `ParamSpec` typing, async-aware decorators, class decorators, descriptor interplay when decorating methods (a decorator returning a non-descriptor callable breaks method binding).

**GIL.** *30 s:* One thread runs Python bytecode at a time in default CPython; great for I/O concurrency, not CPU parallelism; not a thread-safety guarantee. *2 min:* Why it exists (refcount safety, simple C-API), switching interval, release during I/O and in C extensions, multiprocessing alternative. *Deep:* PEP 703 free-threading (biased refcounting, per-object locks, mimalloc), PEP 779 status in 3.14, single-thread overhead, extension compatibility, subinterpreters (PEP 684/734).

**Async.** *30 s:* asyncio runs many coroutines on one thread, switching at `await` points; ideal for I/O-heavy concurrency. *2 min:* Event loop, tasks, futures, `TaskGroup`, timeouts, cancellation, `to_thread`. *Deep:* Selector/proactor loops, how `await` desugars to generator-based suspension, structured concurrency, cancellation semantics, AnyIO's model in Starlette/FastAPI, and debugging blocked loops.

### 15. Knowledge Check

**Conceptual**
1. Why does `[[0]*3]*3` cause surprising behavior?
2. Why does defining `__eq__` make instances unhashable?
3. Difference between data and non-data descriptors in lookup precedence?
4. Why might `asyncio.create_task(x())` silently not complete?
5. When is a `Protocol` preferable to an ABC?

**Code reading**
6. Output?
```python
def f(a, L=[]):
    L.append(a); return L
print(f(1), f(2), f(3, []))
```
7. Output?
```python
class A: x = []
a, b = A(), A()
a.x.append(1); b.x = [2]
print(A.x, a.x, b.x)
```
8. Output?
```python
gen = (i * i for i in range(3))
print(list(gen), list(gen))
```

**Debugging**
9. An async endpoint takes 5 s for all users when one user uploads a large file. Cause?
10. Multithreaded counter shows 9,874 instead of 10,000. Why and fix?

**Design**
11. You need 10k concurrent outbound HTTP calls and SHA-256 on each 50 MB response. Design the concurrency.
12. Dataclass, Pydantic model or TypedDict for: (a) API request body, (b) internal event in a hot loop, (c) JSON config passed to a typed function?

#### Knowledge Check Answers

1. List multiplication copies references: three references to the same inner list; mutating one row changes all.
2. Python sets `__hash__ = None` when `__eq__` is defined without `__hash__` to preserve the invariant that equal objects have equal hashes.
3. Data descriptors (with `__set__`/`__delete__`) take precedence over the instance `__dict__`; non-data descriptors (only `__get__`) are overridden by instance attributes.
4. Unreferenced tasks may be garbage-collected (loop holds weak refs), exceptions are unobserved, and the program may exit before completion; keep references or use TaskGroup.
5. When you want structural compatibility without inheritance (third-party classes, duck typing), statically checked.
6. `[1, 2] [1, 2] [3]` — note both first two prints show the same list object after both calls since arguments are evaluated before print.
7. `[1] [1] [2]` — `a.x.append` mutates the class attribute; `b.x = [2]` creates an instance attribute on b.
8. `[0, 1, 4] []` — generators are single-pass.
9. Blocking/CPU work on the event loop (e.g. synchronous file processing or hashing in `async def`); offload to thread/process pool or worker, or use async streaming.
10. `+=` is non-atomic (load/add/store); use a `threading.Lock` or per-thread counts then sum.
11. asyncio + httpx with bounded concurrency (semaphore) for I/O; hashing streamed chunks (hashlib releases the GIL for large buffers, so `to_thread` can help) or a process pool for heavy CPU; bound memory by streaming rather than holding 50 MB × 10k.
12. (a) Pydantic (validation at boundary); (b) dataclass with `slots=True` (or tuple) for speed; (c) TypedDict for typed dict shape without runtime cost (validate once at load if untrusted).

### 16. Common Interview Traps

| Trap | Correct model |
|---|---|
| "A tuple makes every nested value immutable." | Tuples are shallowly immutable. |
| "The GIL makes Python code thread-safe." | It protects interpreter internals, not your compound operations. |
| "`async def` makes code faster." | It enables concurrency during I/O waits; it adds overhead and doesn't help CPU work. |
| "Type hints are enforced at runtime." | Only by libraries that choose to (Pydantic); the interpreter ignores them. |
| "`super()` calls the parent class." | It calls the next class in the instance's MRO. |
| "`del x` deletes the object." | It deletes the name; the object is freed when its refcount reaches zero. |
| "Generators are faster than lists." | They save memory; per-item overhead can be higher. |
| "Python is pass-by-reference/value." | Call by object reference ("pass by assignment"): the callee gets a reference to the same object; rebinding inside doesn't affect the caller, mutation does. |

### 17. Cheat Sheet

- `is` → identity (None/sentinels); `==` → `__eq__`.
- Defaults evaluated once → use `None`.
- LEGB; assignment makes local; `nonlocal`/`global`.
- Closures late-bind → default-arg trick or `functools.partial`.
- Decorator: `f = d(f)`; factory for args; always `functools.wraps`; async-aware.
- Generator: lazy, single-pass, `yield from`, `close()` runs `finally`.
- Attribute lookup: data descriptor > instance dict > non-data descriptor > class attr > `__getattr__`.
- MRO: C3; `super()` = next in MRO.
- Hash contract: `a == b ⇒ hash(a) == hash(b)`.
- Complexity: list append O(1)*, insert(0) O(n); deque ends O(1); dict/set O(1) avg; heap push/pop O(log n).
- GIL: one bytecode thread; I/O releases; not thread-safety; 3.14 free-threaded build supported/optional.
- asyncio: TaskGroup, `asyncio.timeout`, `to_thread`, keep task refs, never swallow CancelledError.
- Tools: `dis`, `tracemalloc`, `cProfile`, `py-spy`, `python -X dev`, `PYTHONASYNCIODEBUG=1`.

### 18. Completion Checklist

- [ ] I can give 30-s/2-min/deep answers for all ten interview topics.
- [ ] I can predict outputs of aliasing, default, closure, scope, generator and MRO snippets.
- [ ] I can implement sync/async decorators with arguments and preserved signatures.
- [ ] I can implement descriptors and explain lookup precedence.
- [ ] I can explain refcounting, cyclic GC and the GIL, including free-threading status.
- [ ] I can choose and justify threads/processes/asyncio for a workload.
- [ ] I can debug races, unawaited coroutines, blocking loops and memory leaks.
- [ ] I can test with fixtures, parametrization, mocks, Hypothesis and async tests.

### 19. Further Research

**Essential**
- Python Language Reference — "Data model" (special methods, descriptors, MRO). <https://docs.python.org/3/reference/datamodel.html>
- Descriptor HowTo Guide (Raymond Hettinger). <https://docs.python.org/3/howto/descriptor.html>
- `asyncio` documentation, especially "Developing with asyncio" and task groups. <https://docs.python.org/3/library/asyncio.html>
- `typing` docs and the typing specification. <https://typing.python.org/>
- "What's New in Python 3.14" — lazy annotations, free-threaded support, `concurrent.interpreters`. <https://docs.python.org/3/whatsnew/3.14.html>
- Python free-threading HOWTO. <https://docs.python.org/3/howto/free-threading-python.html>

**Deeper Study**
- Luciano Ramalho, *Fluent Python* (2nd ed.) — data model, descriptors, generators, concurrency.
- PEP 703 (free-threading), PEP 779, PEP 683 (immortal objects), PEP 649/749 (annotations), PEP 695 (generics syntax).
- "The Python 2.3 Method Resolution Order" (Michele Simionato) — the C3 explanation. <https://docs.python.org/3/howto/mro.html>
- CPython Internals (Anthony Shaw) and the CPython devguide internals docs.

**Practice**
- Exercism Python track; "Python Morsels" exercises; write and run your own prediction snippets.
- Hypothesis documentation's "What you can generate and how."

### Unit Completion Standard

Before moving on you must be able to **explain** Python's object model, scope, closures, decorators, generators, data model, MRO, descriptors, typing, memory management, GIL and asyncio at three depths; **implement** decorators, descriptors, generators, context managers and concurrency-safe structures with types; **test** them with pytest, Hypothesis and async tests; **debug** aliasing, default-argument, closure, race, unawaited-coroutine, blocking-loop and memory-leak bugs by reading code; and **defend** concurrency and data-structure choices with complexity and CPython-internals reasoning in an interview.
