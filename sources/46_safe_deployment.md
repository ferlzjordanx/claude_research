## Unit 46 — Safe Deployment, Drift and Resilience for AI

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Design** versioning for every behaviour-affecting artifact — model, prompt, retrieval index, embedding model, chunker, tool schemas, policies — bundled into an immutable release manifest.
2. **Distinguish** regression (caused by your change) from drift (caused by changes in inputs, data or dependencies over time) and **choose** detection methods for each.
3. **Implement** drift monitors for output distributions and retrieval quality (PSI, distribution tests, canary query sets, online evals).
4. **Plan** an embedding-model migration (re-embedding, dual indexes, shadow reads, cutover, rollback).
5. **Design** staged rollouts (shadow, canary, progressive) with eval-based gates and **define** measurable stop criteria.
6. **Implement** timeouts, retries with backoff and jitter, circuit breakers, bulkheads and a fallback ladder that ends in a safe non-AI path or refusal.
7. **Simulate** a model/provider outage and **verify** graceful degradation.
8. **Defend** release-gate, rollout and fallback decisions in an interview.

### 2. Prerequisite Knowledge

* Unit 44: eval datasets, baselines, gates; Unit 45: provenance attributes, metrics, traces.
* Deployment basics: blue/green, canary, feature flags, rollback.
* Distributed-systems resilience: timeouts, retries, idempotency, backpressure.
* RAG internals: embeddings, vector indexes (HNSW/IVF), metadata filters.

### 3. Mental Model

An AI feature is **code + configuration + data + someone else's model**. Any of the four can change behaviour:

```
            ┌───────────────── RELEASE MANIFEST (immutable, versioned) ─────────────────┐
            │ code: git SHA          prompt: support_system@v14 (sha256…)                │
            │ model: provider/model-2026-08-15 (pinned snapshot, not "latest")           │
            │ retrieval: index kb-acme@2026-10-05 · embed model text-embed-v3 · chunker v4│
            │ tools: schema v7 · policy 2026-10-01 · decision schema 2026-09              │
            └───────────────────────────────────────────────────────────────────────────┘
                 │ change any line = new candidate release
                 v
  OFFLINE EVAL GATE ──> SHADOW (no user impact) ──> CANARY 1%→5%→25% ──> 100%
     (Unit 44)            compare outputs           stop criteria           keep previous
                                                    auto-rollback           manifest warm
                 ^
  meanwhile, in production:  DRIFT MONITORS (inputs, outputs, retrieval, online evals)
                             RESILIENCE (timeouts, breakers, fallbacks) for dependency failures
```

Two different questions:

* **"Did *our change* make things worse?"** → regression → offline eval gates and canary comparisons against control.
* **"Is *the world* making things worse?"** → drift → continuous monitoring with no deploy involved.

And a third, about failure:

* **"What happens when the model is down or slow?"** → resilience → bounded waits, fast failure, safe degradation.

### 4. Comprehensive Theory

#### 4.1 Model, Prompt and Index Versioning

**Definition.** Versioning assigns immutable identifiers to every artifact that influences AI behaviour, so that any output can be attributed (provenance, Unit 45) and any release can be reproduced and rolled back.

**What to version and how:**

| Artifact | Practice | Pitfall |
|---|---|---|
| **Model** | Pin dated snapshot IDs; track provider deprecation/retirement schedules; record `response.model` | Aliases ("latest") silently change behaviour |
| **Prompt** | Prompt templates in git or a prompt registry; immutable versions + content hash; reviewed like code | Editing prompts in a dashboard with no history |
| **Decoding config** | temperature, max tokens, structured-output settings in the manifest | "Small" parameter tweaks without evals |
| **Retrieval index** | Build ID = (source snapshot, chunker version, embedding model, index params); immutable; alias for "current" | Rebuilding in place — no rollback |
| **Embedding model** | Part of the index identity; queries must use the same model | Mixing vectors from two models |
| **Tools / schemas / policies** | Versioned with code; decision schema version in persisted data | Schema change without migration (Unit 42) |
| **Eval dataset + judge** | Versioned; results keyed by dataset/judge version | Comparing scores across dataset versions |

**Release manifest.** A single versioned document referencing all of the above. Deploy = point traffic at a manifest; rollback = point back. Store it in config (with change review), not in the container image alone, so prompt/model changes go through the same pipeline as code.

```yaml
# releases/supportops/2026-10-07.1.yaml
release: 2026-10-07.1
code_sha: 9f1c2ab
model: {provider: example_provider, id: model-large-2026-08-15, temperature: 0.2, max_tokens: 1024}
fallback_model: {provider: other_provider, id: model-mid-2026-06-01}   # must pass the same evals
prompt: {id: support_system, version: v14, sha256: 6b0e…}
retrieval: {index_alias: kb-acme-current, index_build: kb-acme@2026-10-05, embedding_model: text-embed-v3,
            chunker: v4, top_k: 8, reranker: rerank-v2}
schemas: {decision: "2026-09", tools: v7}
policy_version: 2026-10-01
eval_report: s3://evals/supportops/2026-10-07.1/report.json
```

#### 4.2 Drift: Output Distribution and Retrieval Quality

**Definitions.**

* **Input (data) drift** — the distribution of requests changes (new product launch, new language, seasonal issues).
* **Output-distribution drift** — the distribution of the system's outputs changes: decision kinds, refusal rate, tool usage, answer length, citation rate, approval-rejection rate.
* **Retrieval-quality drift** — retrieval gets worse over time: KB content goes stale, new documents are not indexed, top-similarity scores fall, empty-result rate rises, recall on a fixed canary query set drops.
* **Model drift** — the provider changes the model behind an identifier or you're forced to migrate (deprecation).
* **Concept drift** — the correct answer changes (policy updated) while inputs look the same.

**Drift vs regression:**

| | Regression | Drift |
|---|---|---|
| Cause | A change you deployed | Change in world, data, users or dependencies |
| Timing | Correlates with a release | Gradual or sudden, no deploy |
| Detection | Offline eval vs baseline; canary vs control | Monitoring distributions; online evals; canary query sets |
| Fix | Roll back / fix the change | Update data/index/prompt/model; add eval cases |

**Detection methods:**

* **Population Stability Index (PSI)** over categorical or bucketed signals: PSI = Σ (aᵢ − eᵢ)·ln(aᵢ/eᵢ). Common rule of thumb: < 0.1 stable, 0.1–0.25 moderate, > 0.25 significant — heuristics, tune for your traffic. Sensitive to empty bins (use smoothing).
* **Statistical tests**: chi-square for categorical, Kolmogorov–Smirnov for continuous signals; with large traffic, *everything* is "significant" — combine with effect size (PSI, absolute deltas).
* **Embedding-based input drift**: cluster query embeddings; watch cluster share changes and new clusters (emerging topics).
* **Canary query set**: a fixed set of questions with gold documents run daily against production retrieval — recall@k over time is a direct retrieval-quality signal independent of traffic mix.
* **Online evals**: sampled production traces scored by calibrated judges (Unit 44), trended by version.
* **Business signals**: escalation rate, thumbs-down, re-contact rate, approval rejections.

**Response to drift.** Investigate before acting; drift is a symptom. Typical responses: re-index stale content, add new documents, adjust prompts for new topics, add eval cases for the new distribution, migrate models.

#### 4.3 Embedding Model Migration

**Why it's special.** Embeddings from different models live in different vector spaces (often with different dimensions). A query embedded with model B cannot be meaningfully compared with documents embedded with model A. Migration therefore means **re-embedding the whole corpus** and switching queries and documents **together**.

**Procedure:**

```
1. Offline evaluation: build index B on a snapshot; run retrieval evals (recall@k, nDCG, MRR)
   on the canary query set + eval dataset; compare with A, per slice (languages, doc types).
2. Capacity & cost plan: re-embedding cost, index build time, storage (dimension change!),
   ANN parameters (HNSW M/ef) re-tuned.
3. Dual-write: new/updated documents are embedded with both A and B going forward.
4. Backfill: re-embed all existing documents into B (idempotent, resumable batches, rate-limited).
5. Verify completeness: document counts and checksums per tenant match between A and B.
6. Shadow reads: for a sample of live queries, query both A and B; log overlap@k and score
   distributions; run online evals on B's results (no user impact).
7. Canary: route x% of queries (sticky per conversation) to B end-to-end; compare task success.
8. Cutover: switch the index alias (and query embedding model) atomically in the release manifest.
9. Rollback window: keep A and dual-writes running until confidence; then decommission.
```

**Pitfalls.** Forgetting that the *query* embedder must switch at the same moment as the index; partial backfills causing tenant-specific recall drops; metadata filters not migrated; gold labels at chunk level breaking when chunking changes (label at document level).

With PostgreSQL + pgvector, a dimension change means a new column or table (`vector(1024)` vs `vector(1536)`) and a new ANN index; build the index after backfill (`CREATE INDEX CONCURRENTLY` to avoid blocking writes).

#### 4.4 Staged Rollout and Canary Concepts

**Stages:**

| Stage | What happens | What you learn | Risk |
|---|---|---|---|
| **Offline gate** | Eval suite vs baseline (Unit 44) | Known-case quality, safety, cost | None |
| **Shadow (dark launch)** | Candidate runs on real traffic; outputs discarded or compared; **no side effects** (tools disabled/stubbed) | Real-distribution quality, latency, cost, output drift vs control | Cost; must not execute actions |
| **Canary** | Small % of real users get candidate | Real outcomes and business metrics | Limited user impact |
| **Progressive rollout** | 1% → 5% → 25% → 50% → 100% with analysis at each step | Confidence with scale | Bounded by stop criteria |
| **A/B experiment** | Randomized split to measure effect on business metrics | Causal impact | Needs sample size |

**AI-specific considerations:**

* **Sticky assignment** per conversation/session — switching models mid-conversation confuses users and metrics.
* **Assignment unit** — per tenant for enterprise customers who must approve changes; per request for consumer traffic.
* **Quality signals are slow and noisy** — canary needs online evals (sampled judging), not only error rates; plan sample sizes.
* **Shadow mode must never execute side effects** — run with tools in dry-run mode.
* **Record the arm** (control/canary, manifest ID) on spans (Unit 45) so every metric can be split.

#### 4.5 Eval-Based Deployment Gates and Stop Criteria

**Gates by stage:**

```
PR / config change ──> offline smoke eval (fast) ──> full offline eval + trials (pre-release)
     ──> shadow: output diff + online eval sample ──> canary: stop criteria checked every interval
     ──> promote / hold / rollback (automated) ──> post-release monitoring (drift)
```

**Stop criteria must be:**

* **Measurable** — a metric with a definition and data source.
* **Comparative** — candidate vs control in the same period (seasonality cancels out).
* **Bounded** — explicit allowed degradation (absolute or relative).
* **Powered** — a minimum sample count before "promote".
* **Prioritized** — *hard limits* (instant rollback, e.g., any forbidden behaviour, error rate > 2%, p95 > SLO) vs *soft limits* (rollback if worse by more than X after N samples).

**Example stop criteria for a prompt/model change:**

| Metric | Source | Rule |
|---|---|---|
| Forbidden-behaviour events | Online checks + policy denials of model-initiated actions | Any increase over control → rollback |
| Error rate (5xx + agent failures) | Metrics | > 2% absolute → rollback |
| p95 latency | Metrics | > control + 500 ms → rollback |
| Schema-compliance rate | Validation metrics | < 99% → rollback |
| Task success (online judge) | Sampled evals | < control − 2 pts after ≥ 500 judged samples → rollback |
| Escalation / thumbs-down rate | Product events | > control + 1.5 pts → hold & investigate |
| Cost per successful task | Metrics + evals | > control + 20% → hold (product decision) |

Tools such as **Argo Rollouts** (AnalysisTemplates) and **Flagger** automate progressive delivery with metric analysis on Kubernetes; for prompt/model changes that don't redeploy code, a feature-flag service with percentage rollouts plus your own analysis job serves the same purpose.

#### 4.6 Circuit Breakers and Graceful Degradation for AI Dependencies

AI dependencies (model APIs, embedding APIs, vector stores, rerankers) are remote, rate-limited, sometimes slow and occasionally down. Design for it.

**Resilience toolkit:**

| Mechanism | Purpose | AI-specific notes |
|---|---|---|
| **Timeouts** | Bound waiting | Separate connect/read; total budget per request; streaming: time-to-first-token and inter-token timeouts |
| **Retries with exponential backoff + full jitter** | Recover from transient errors | Retry only retryable errors (429, 5xx/overloaded, timeouts); honour `Retry-After`; cap attempts; **retry budget** to avoid amplifying outages; never retry non-idempotent tool actions without idempotency keys |
| **Circuit breaker** | Stop calling a failing dependency; fail fast; probe recovery | Per provider/model/region; states CLOSED → OPEN → HALF_OPEN |
| **Bulkhead** | Isolate resources (concurrency limits) | Prevent slow model calls from exhausting the event loop/workers |
| **Load shedding / rate limiting** | Protect under overload | Prioritize interactive over batch; per-tenant quotas |
| **Fallback ladder** | Keep serving something safe | See below |
| **Caching** | Serve repeated questions | Only for non-personalized, non-action answers; respect tenancy |

**Fallback ladder (SupportOps):**

```
1. Primary model (pinned)                                    normal
2. Secondary model/provider (pre-evaluated, same safety gates)   degraded-quality
3. Cached/approved answer for FAQ-type questions             degraded-coverage
4. Non-AI deterministic path: KB search links, forms, ticket creation   degraded-experience
5. Honest refusal / "saved, a human will follow up"          safe
```

**Rules:**

* **Fallbacks for actions fail closed.** If the model can't decide, the action doesn't happen. Never fall back to a less safe path ("skip policy check when the policy service is down").
* **A fallback model is a different configuration** — it must pass the same offline evals and safety tests; otherwise your outage path is your least-tested path.
* **Tell users the truth** about degraded mode; mark responses `degraded=true` in telemetry.
* **Test outages** regularly (game days, fault injection in staging).

### 5. Internal Mechanics

#### 5.1 Circuit breaker state machine

```
          failure rate ≥ threshold over ≥ min_calls
 CLOSED ───────────────────────────────────────────> OPEN
   ^                                                  │ cool-down elapsed
   │ k consecutive successful trial calls             v
   └──────────────────────────────────────────── HALF_OPEN ── any failure ──> OPEN
                                                 (≤ k concurrent trial calls)
```

While OPEN, calls fail immediately (no network wait) → the caller goes straight to the next fallback, keeping latency bounded during outages and giving the provider room to recover.

#### 5.2 Why jitter

If 1,000 clients retry after exactly 1 s, 2 s, 4 s, they hit the recovering service in synchronized waves. Full jitter (`sleep(random(0, min(cap, base·2^n)))`) spreads retries out and reduces peak load.

#### 5.3 Canary analysis loop

```
every interval (e.g. 10 min):
    control_metrics ← query metrics where arm=control, window
    canary_metrics  ← query metrics where arm=canary,  window
    if any hard limit breached → rollback (set flag to 0%), page on-call
    elif any soft criterion worse than bound → rollback
    elif samples < minimum → hold
    else → promote to next step (1% → 5% → 25% → …)
```

### 6. Implementation Examples

#### Example 1 — Minimal: timeout + single fallback (Runnable)

```python
import asyncio

async def flaky_model(q: str) -> str:
    await asyncio.sleep(5)              # simulates a hung provider
    return "never"

async def answer(q: str) -> str:
    try:
        return await asyncio.wait_for(flaky_model(q), timeout=1.0)
    except TimeoutError:
        return "Our assistant is busy. Here is our refunds help page: /help/refunds"

print(asyncio.run(answer("refund status?")))
```

#### Example 2 — Realistic and production-oriented: breaker, fallback ladder, drift PSI and canary stop criteria (Runnable)

**Architecture.** `CircuitBreaker` (sliding-window failure rate, cool-down, half-open trials, injectable clock); `ResilientAnswerer` (bulkhead semaphore → primary with retry/backoff/jitter through its breaker → secondary → non-AI KB links → refusal; actions fail closed); `psi` and `bucketize` for drift; `canary_decision` for promote/hold/rollback with hard limits and comparative criteria.

```python
# ai_resilience.py — circuit breaker, fallback chain, drift (PSI) and canary stop criteria.
from __future__ import annotations

import asyncio
import math
import random
import time
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum


# ----------------------------------------------------------------------------- circuit breaker
class BreakerState(StrEnum):
    CLOSED = "closed"          # calls flow; failures counted
    OPEN = "open"              # calls short-circuit to fallback until cool-down ends
    HALF_OPEN = "half_open"    # limited trial calls decide whether to close again


class CircuitOpen(Exception):
    pass


@dataclass
class CircuitBreaker:
    name: str
    failure_rate_threshold: float = 0.5     # open when ≥50% of recent calls failed…
    min_calls: int = 10                     # …over at least this many calls
    window: int = 20                        # sliding window of outcomes
    open_seconds: float = 30.0              # cool-down before half-open
    half_open_max_calls: int = 3
    clock: Callable[[], float] = time.monotonic
    state: BreakerState = BreakerState.CLOSED
    _outcomes: deque[bool] = field(default_factory=deque)
    _opened_at: float = 0.0
    _half_open_inflight: int = 0
    _half_open_successes: int = 0

    def _transition(self, to: BreakerState) -> None:
        self.state = to
        if to is BreakerState.OPEN:
            self._opened_at = self.clock()
        if to is BreakerState.HALF_OPEN:
            self._half_open_inflight = self._half_open_successes = 0
        if to is BreakerState.CLOSED:
            self._outcomes.clear()

    def before_call(self) -> None:
        if self.state is BreakerState.OPEN:
            if self.clock() - self._opened_at < self.open_seconds:
                raise CircuitOpen(self.name)
            self._transition(BreakerState.HALF_OPEN)
        if self.state is BreakerState.HALF_OPEN:
            if self._half_open_inflight >= self.half_open_max_calls:
                raise CircuitOpen(self.name)
            self._half_open_inflight += 1

    def record(self, success: bool) -> None:
        if self.state is BreakerState.HALF_OPEN:
            if not success:
                self._transition(BreakerState.OPEN)
                return
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_max_calls:
                self._transition(BreakerState.CLOSED)
            return
        self._outcomes.append(success)
        if len(self._outcomes) > self.window:
            self._outcomes.popleft()
        failures = self._outcomes.count(False)
        if len(self._outcomes) >= self.min_calls and failures / len(self._outcomes) >= self.failure_rate_threshold:
            self._transition(BreakerState.OPEN)

    async def call(self, fn: Callable[[], Awaitable[str]], timeout_s: float) -> str:
        self.before_call()
        try:
            result = await asyncio.wait_for(fn(), timeout=timeout_s)
        except Exception:
            self.record(False)
            raise
        self.record(True)
        return result


# ----------------------------------------------------------------------------- fallback chain
class ProviderError(Exception):
    pass


@dataclass
class Answer:
    text: str
    source: str            # "primary" | "secondary" | "non_ai_fallback" | "refusal"
    degraded: bool


async def retry_with_backoff(fn: Callable[[], Awaitable[str]], attempts: int = 2,
                             base_s: float = 0.05, cap_s: float = 0.5) -> str:
    for attempt in range(attempts):
        try:
            return await fn()
        except CircuitOpen:
            raise                                  # never retry into an open breaker
        except Exception:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(random.uniform(0, min(cap_s, base_s * 2 ** attempt)))  # full jitter
    raise AssertionError("unreachable")


@dataclass
class ResilientAnswerer:
    primary: Callable[[str], Awaitable[str]]
    secondary: Callable[[str], Awaitable[str]] | None
    kb_search: Callable[[str], Awaitable[list[str]]]      # deterministic, non-AI
    primary_breaker: CircuitBreaker
    secondary_breaker: CircuitBreaker
    bulkhead: asyncio.Semaphore = field(default_factory=lambda: asyncio.Semaphore(50))
    timeout_s: float = 8.0

    async def answer(self, question: str, *, action_requested: bool = False) -> Answer:
        async with self.bulkhead:                   # cap concurrent AI calls; protect the process
            for name, fn, breaker in (("primary", self.primary, self.primary_breaker),
                                      ("secondary", self.secondary, self.secondary_breaker)):
                if fn is None:
                    continue
                try:
                    text = await retry_with_backoff(
                        lambda fn=fn, breaker=breaker: breaker.call(lambda: fn(question), self.timeout_s))
                    return Answer(text, name, degraded=(name != "primary"))
                except Exception:
                    continue
        # Every AI path failed. Never guess an action; offer a safe, deterministic alternative.
        if action_requested:
            return Answer("I can't process changes right now. Your request has been saved and "
                          "an agent will follow up.", "refusal", degraded=True)
        links = await self.kb_search(question)
        if links:
            return Answer("I can't generate an answer right now. These articles may help: "
                          + ", ".join(links), "non_ai_fallback", degraded=True)
        return Answer("Our assistant is temporarily unavailable. Please try again shortly.",
                      "refusal", degraded=True)


# ----------------------------------------------------------------------------- drift: PSI
def psi(expected: Sequence[str], actual: Sequence[str], eps: float = 1e-4) -> float:
    """Population Stability Index over categorical outcomes (e.g. decision kind, refusal)."""
    cats = set(expected) | set(actual)
    e, a = Counter(expected), Counter(actual)
    total = 0.0
    for c in cats:
        pe = max(e[c] / len(expected), eps)
        pa = max(a[c] / len(actual), eps)
        total += (pa - pe) * math.log(pa / pe)
    return total


def bucketize(values: Sequence[float], edges: Sequence[float]) -> list[str]:
    """Turn a numeric signal (e.g. retrieval top score, answer length) into buckets for PSI."""
    out = []
    for v in values:
        i = sum(v >= e for e in edges)
        out.append(f"b{i}")
    return out


# ----------------------------------------------------------------------------- canary stop criteria
@dataclass(frozen=True)
class StopCriterion:
    metric: str
    max_degradation: float      # candidate may be worse than control by at most this (absolute)
    higher_is_better: bool = True


@dataclass(frozen=True)
class CanaryVerdict:
    action: str                 # "promote" | "hold" | "rollback"
    reasons: tuple[str, ...]


def canary_decision(control: dict[str, float], canary: dict[str, float], n_canary: int,
                    criteria: Sequence[StopCriterion], min_samples: int = 500,
                    hard_limits: dict[str, float] | None = None) -> CanaryVerdict:
    reasons = []
    for metric, limit in (hard_limits or {}).items():          # absolute guardrails: instant rollback
        if canary.get(metric, 0.0) > limit:
            reasons.append(f"{metric}={canary[metric]:.4f} exceeds hard limit {limit}")
    if reasons:
        return CanaryVerdict("rollback", tuple(reasons))
    for c in criteria:
        delta = canary[c.metric] - control[c.metric]
        worse_by = -delta if c.higher_is_better else delta
        if worse_by > c.max_degradation:
            reasons.append(f"{c.metric} worse by {worse_by:.4f} (> {c.max_degradation})")
    if reasons:
        return CanaryVerdict("rollback", tuple(reasons))
    if n_canary < min_samples:
        return CanaryVerdict("hold", (f"only {n_canary}/{min_samples} samples",))
    return CanaryVerdict("promote", ("all criteria within bounds",))
```

Simulating a provider outage, recovery, drift and three canary decisions:

```python
# demo_resilience.py — run: python demo_resilience.py
import asyncio
from ai_resilience import (CanaryVerdict, CircuitBreaker, ProviderError, ResilientAnswerer,
                           StopCriterion, bucketize, canary_decision, psi)

class FakeClock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

async def main():
    clock = FakeClock()
    primary_up = {"ok": False}

    async def primary(q):
        if not primary_up["ok"]:
            raise ProviderError("529 overloaded")
        return f"[primary] answer to {q!r}"

    async def secondary(q):
        raise ProviderError("secondary also down")

    async def kb_search(q):
        return ["kb/refund-timing", "kb/returns-policy"]

    pb = CircuitBreaker("primary", min_calls=4, window=10, open_seconds=30, clock=clock)
    sb = CircuitBreaker("secondary", min_calls=4, window=10, open_seconds=30, clock=clock)
    svc = ResilientAnswerer(primary, secondary, kb_search, pb, sb, timeout_s=1.0)

    for i in range(3):
        a = await svc.answer("How long do refunds take?")
        print(f"call {i}: source={a.source:<16} breaker={pb.state}")
    a = await svc.answer("Refund order ord_x", action_requested=True)
    print("action during outage:", a.source, "-", a.text[:45], "...")

    primary_up["ok"] = True
    clock.t += 31                                    # cool-down elapses → half-open trials
    for i in range(3):
        a = await svc.answer("How long do refunds take?")
        print(f"recovery {i}: source={a.source:<9} breaker={pb.state}")

    baseline = ["answer"] * 80 + ["ask_clarification"] * 12 + ["refuse"] * 3 + ["propose_action"] * 5
    this_week = ["answer"] * 62 + ["ask_clarification"] * 10 + ["refuse"] * 21 + ["propose_action"] * 7
    print(f"PSI decision kinds: {psi(baseline, this_week):.3f}  (>0.25 is commonly treated as major shift)")
    edges = [0.5, 0.7, 0.85]
    print(f"PSI retrieval top score: {psi(bucketize([0.9]*60+[0.8]*30+[0.6]*10, edges),
                                                 bucketize([0.9]*35+[0.8]*30+[0.6]*35, edges)):.3f}")

    criteria = [StopCriterion("task_success", 0.02), StopCriterion("p95_latency_s", 0.5, higher_is_better=False)]
    hard = {"forbidden_behavior_rate": 0.0, "error_rate": 0.02}
    control = {"task_success": 0.91, "p95_latency_s": 2.8}
    print(canary_decision(control, {"task_success": 0.90, "p95_latency_s": 2.9, "forbidden_behavior_rate": 0.0,
                                    "error_rate": 0.004}, n_canary=180, criteria=criteria, hard_limits=hard))
    print(canary_decision(control, {"task_success": 0.86, "p95_latency_s": 2.9, "forbidden_behavior_rate": 0.0,
                                    "error_rate": 0.004}, n_canary=800, criteria=criteria, hard_limits=hard))
    print(canary_decision(control, {"task_success": 0.92, "p95_latency_s": 2.7, "forbidden_behavior_rate": 0.001,
                                    "error_rate": 0.004}, n_canary=800, criteria=criteria, hard_limits=hard))

asyncio.run(main())
```

```
call 0: source=non_ai_fallback  breaker=closed
call 1: source=non_ai_fallback  breaker=open
call 2: source=non_ai_fallback  breaker=open
action during outage: refusal - I can't process changes right now. Your reque ...
recovery 0: source=primary   breaker=half_open
recovery 1: source=primary   breaker=half_open
recovery 2: source=primary   breaker=closed
PSI decision kinds: 0.407  (>0.25 is commonly treated as major shift)
PSI retrieval top score: 0.448
CanaryVerdict(action='hold', reasons=('only 180/500 samples',))
CanaryVerdict(action='rollback', reasons=('task_success worse by 0.0500 (> 0.02)',))
CanaryVerdict(action='rollback', reasons=('forbidden_behavior_rate=0.0010 exceeds hard limit 0.0',))
```

**Reading the output.**

* Calls 0–2: both providers fail; the user gets KB links (non-AI fallback). After four recorded failures the primary breaker opens, so later calls fail fast instead of waiting on timeouts.
* The *action* request during the outage gets an honest refusal — actions never fall back to guessing.
* After the cool-down, half-open trial calls succeed and the breaker closes.
* PSI 0.41 on decision kinds: refusals jumped from 3% to 21% — investigate (model update? new topic? prompt change?).
* Canary verdicts: *hold* (not enough samples), *rollback* (task success −5 points), *rollback* (any forbidden behaviour breaches the hard limit even though task success improved).

**Tests to accompany it** (sketch):

```python
import asyncio, pytest
from ai_resilience import BreakerState, CircuitBreaker, CircuitOpen, psi

class Clock:
    def __init__(self): self.t = 0.0
    def __call__(self): return self.t

def test_breaker_opens_and_recovers():
    clock = Clock()
    b = CircuitBreaker("p", min_calls=4, window=4, open_seconds=10, half_open_max_calls=2, clock=clock)
    for _ in range(4):
        b.before_call(); b.record(False)
    assert b.state is BreakerState.OPEN
    with pytest.raises(CircuitOpen):
        b.before_call()
    clock.t = 11
    b.before_call(); b.record(True)
    b.before_call(); b.record(True)
    assert b.state is BreakerState.CLOSED

def test_half_open_failure_reopens():
    clock = Clock()
    b = CircuitBreaker("p", min_calls=2, window=2, open_seconds=1, clock=clock)
    for _ in range(2):
        b.before_call(); b.record(False)
    clock.t = 2
    b.before_call(); b.record(False)
    assert b.state is BreakerState.OPEN

def test_psi_zero_for_identical_distributions():
    xs = ["a"] * 50 + ["b"] * 50
    assert psi(xs, xs) == pytest.approx(0.0)
```

#### Example 3 — Embedding migration shadow comparison (Illustrative)

```python
async def shadow_compare(query: str, tenant: str, k: int = 8) -> dict:
    """Serve from index A; query B in the background for comparison only."""
    a_hits = await index_a.search(embed_a(query), tenant=tenant, k=k)
    async def compare():
        b_hits = await index_b.search(embed_b(query), tenant=tenant, k=k)   # matching query embedder!
        overlap = len({h.doc_id for h in a_hits} & {h.doc_id for h in b_hits}) / k
        metrics.histogram("app.migration.overlap_at_k").record(overlap, {"tenant_tier": tier(tenant)})
        if sample_for_eval():
            await online_eval_queue.put({"query_id": hash_q(query), "a": ids(a_hits), "b": ids(b_hits)})
    background.spawn(compare())          # bounded task group; never delays the user path
    return {"hits": a_hits}
```

Low overlap is not automatically bad (B may be *better*); it tells you where to look. Decide with retrieval evals and online judging, per slice.

### 7. Comparative Analysis

| Comparison | Key difference | When | Trap |
|---|---|---|---|
| **Drift vs regression** | World changed vs we changed something | Monitoring vs release gates | Rolling back code to fix KB staleness |
| **Shadow vs canary** | No user impact vs real users | Shadow first for risky changes (no side effects); canary for real outcomes | Shadow mode executing tools |
| **Canary vs A/B test** | Safety check vs causal measurement | Canary to catch harm; A/B to measure benefit | Treating a 1% canary as proof of improvement |
| **Pinned model vs alias** | Reproducible vs auto-updating | Pin in production; test aliases in staging | "latest" in production |
| **Retry vs circuit breaker** | Try again vs stop trying | Retry transient single failures; break on sustained failure | Retries amplifying an outage |
| **Fallback model vs non-AI fallback** | Degraded AI vs deterministic | Secondary model if evaluated; non-AI when all AI paths fail or for actions | Unevaluated fallback model |
| **Fail open vs fail closed** | Continue vs stop | Fail closed for actions and safety checks; degrade gracefully for informational answers | Skipping policy checks during outages |
| **Re-embed vs reuse old vectors** | Consistent space vs mixed spaces | Always re-embed corpus when changing embedding model | Mixing models in one index |

### 8. Failure Modes and Debugging

**F1 — Quality dropped with no deploy.** CAUSE: provider updated an aliased model; KB changed; traffic mix shifted. INVESTIGATE: `gen_ai.response.model` over time; index version; input clusters; online eval by version. FIX: pin model; re-index; add eval cases. PREVENT: pinning, drift monitors, canary query set.

**F2 — Outage cascades into total failure.** SYMPTOM: provider slow → all workers blocked → health checks fail → pods restarted. CAUSE: no timeouts/bulkheads; retries multiplied load. FIX: timeouts, bulkhead semaphores, breaker, retry budget, load shedding. PREVENT: game days.

**F3 — Fallback model produced unsafe actions.** CAUSE: fallback never evaluated; weaker instruction following. FIX: run full eval + adversarial suite on fallback; restrict fallback to read-only/answer mode; actions fail closed when on fallback.

**F4 — Retrieval recall collapsed after embedding migration for one tenant.** CAUSE: backfill incomplete for that tenant / metadata filter not migrated. INVESTIGATE: per-tenant document counts A vs B; overlap@k by tenant. FIX: complete backfill; verification step gating cutover.

**F5 — Canary "passed" but production degraded.** CAUSE: canary too small/short; no online quality metric; assignment not sticky; canary traffic unrepresentative (e.g., one region). FIX: minimum samples, online evals, sticky assignment, representative selection.

**F6 — Retry storm after provider recovery.** CAUSE: synchronized retries without jitter. FIX: full jitter, `Retry-After`, breaker half-open limits.

**Debugging tools.** Provenance-split dashboards; breaker state metrics and logs; PSI/drift reports; canary analysis logs; traces showing fallback source (`degraded=true`); fault injection (Toxiproxy, provider sandbox errors).

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Drift or regression?* Classify 10 incident descriptions. Hints: Was there a deploy? Did the manifest change? Did inputs change?

*1.2 Manifest audit.* List every behaviour-affecting artifact in SupportOps and how it's versioned today. Hints: decoding params, reranker, chunker, policy, judge.

**Level 2 — Implementation**

*2.1 Baseline/candidate comparison.* Using Unit 44's `evalkit`, write `compare.py` that runs two manifests on the same dataset (with trials), prints per-metric deltas with bootstrap CIs and slice tables, and exits non-zero on gate failure. Hints: paired comparison per case.

*2.2 Breaker + fallback.* Extend `ResilientAnswerer` with `Retry-After` support and a retry budget (max 10% of calls may be retries per minute). Tests with a fake clock.

*2.3 Drift monitor.* Compute daily PSI for decision kinds, refusal rate, retrieval top-score buckets and answer-length buckets vs a 28-day baseline; alert above thresholds. Tests with synthetic shifts.

**Level 3 — Integration**

*3.1 Outage simulation.* In docker-compose, put Toxiproxy between the app and a fake model server; inject latency and 529s; verify breaker state transitions, p95 latency bounded, non-AI fallback served, actions refused, telemetry marked degraded. Hints: assert on traces from Unit 45.

*3.2 Canary controller.* Implement a job that reads control/canary metrics (from Prometheus or a fake), applies `canary_decision`, and updates a feature flag percentage. Tests: scripted metric sequences produce expected promote/hold/rollback paths.

**Level 4 — Debugging / Production Scenario**

*4.1 Review this resilience code.*

```python
async def ask(q):
    for _ in range(10):
        try:
            return await client.complete(model="latest", prompt=q)       # no timeout
        except Exception:
            await asyncio.sleep(1)
    return await backup_client.complete(model="cheap", prompt=q, tools=ALL_TOOLS)
```

Hints: unpinned model; no timeout; retries everything 10× without jitter or budget; fallback not evaluated and has all tools; no breaker; no degraded flag.

*4.2 Migration post-mortem.* Write a post-mortem for "new embedding model shipped; Spanish queries' recall dropped 30%". Hints: per-slice offline eval, shadow overlap by language, canary by locale.

### 10. Independent Implementation Project — "Ship Changes Safely"

**Goal.** Make SupportOps safe to change and resilient to AI dependency failures.

**Functional requirements.**

1. Release manifest covering model, prompt, retrieval index, embedding model, chunker, schemas, policy; provenance on spans (Unit 45).
2. Baseline/candidate eval comparison with CIs and slice gates (Unit 44 harness).
3. Shadow mode (no side effects) and canary with sticky assignment and recorded arm.
4. Measurable stop criteria and an automated promote/hold/rollback controller.
5. Drift monitors: output distribution (decision kinds, refusals, length, tool usage) and retrieval quality (canary query set recall@k, top-score PSI, empty-result rate).
6. Resilience: timeouts, retries with jitter and budget, per-provider circuit breakers, bulkhead, fallback ladder ending in a non-AI path or refusal; actions fail closed.
7. Outage simulation and game-day runbook.
8. Embedding migration plan executed on a small corpus (index A → B with shadow comparison and cutover via alias).

**Technical requirements.** Python 3.12+, FastAPI, Pydantic v2, OpenTelemetry, Prometheus (or fake metrics), a feature-flag mechanism (config table or OpenFeature-compatible provider), Toxiproxy, pgvector or another vector store, pytest.

**Suggested structure.**

```
app/
├── release/{manifest.py, loader.py, flags.py}
├── resilience/{breaker.py, retry.py, fallback.py, bulkhead.py}
├── drift/{psi.py, monitors.py, canary_queries.yaml}
├── rollout/{controller.py, criteria.yaml}
├── retrieval/{index_registry.py, migration.py, shadow.py}
└── … (agent, approvals, telemetry from earlier units)
releases/supportops/*.yaml
deploy/{docker-compose.yaml, toxiproxy.json}
docs/{runbooks/model_outage.md, migration_plan_embeddings.md, rollout_policy.md}
tests/{resilience/, drift/, rollout/, migration/}
```

**Milestones.** (1) manifest + provenance; (2) baseline/candidate comparison; (3) resilience layer + unit tests with fake clocks; (4) outage simulation; (5) drift monitors; (6) shadow + canary controller; (7) embedding migration.

**Testing requirements.** Breaker/retry unit tests (fake clock); fallback ladder tests per failure combination; "actions fail closed" test; PSI tests; controller scenario tests; migration verification (counts per tenant, overlap metrics); outage integration test asserting bounded latency.

**Definition of Done.**

* [ ] Any production output can be traced to a manifest ID; rollback is a config change completing in minutes.
* [ ] A candidate that regresses task success by >2 points or introduces any forbidden behaviour is blocked offline or rolled back automatically in canary.
* [ ] Simulated provider outage: p95 latency stays within the degraded SLO, users get non-AI help or honest refusal, no actions execute, telemetry marks degraded mode.
* [ ] Drift alerts fire on synthetic shifts and are documented in runbooks.
* [ ] Embedding migration completes with verified completeness and no recall regression on any slice.

**Optional extensions.** Multi-region provider failover; cost-aware routing (cheap model first, escalate on low confidence) with evals; Argo Rollouts AnalysisTemplate using your metrics.

### 11. Testing Strategy

* **Unit tests with fake clocks** for breakers, retries, budgets and expiries — never `sleep` in tests.
* **Fault-injection integration tests** (Toxiproxy/fake servers): latency, errors, partial responses, hung streams.
* **Fallback matrix tests**: each combination of primary/secondary/KB availability × action/informational request.
* **Eval gates** for every manifest change, including fallback models.
* **Drift tests** on synthetic distributions (known PSI values).
* **Rollout controller tests** with scripted metric sequences.
* **Migration tests**: completeness checks, query-embedder/index consistency check (assert embedding dimension and model ID match index metadata at startup — fail fast on mismatch).
* **Load tests** to validate bulkhead sizing and shedding behaviour.

### 12. Engineering Scenarios

**Scenario 1 — Provider deprecates your model in 60 days.** *Investigate:* candidate replacements; eval on full suite and adversarial set; cost/latency. *Reasoning:* Treat as a release: offline gate, shadow, canary per tenant, rollback plan. Start early — deprecations are scheduled drift.

**Scenario 2 — Refusal rate doubled overnight.** *Investigate:* deploys/manifests (none?), `response.model` changes, input clusters (new topic?), prompt/policy changes. *Reasoning:* If inputs shifted (e.g., a recall notice brought safety questions), refusals may be correct; if the model changed behind an alias, pin and evaluate.

**Scenario 3 — Primary provider has a 2-hour outage.** *Reasoning:* Breaker opens; secondary (pre-evaluated) serves informational answers; actions queue for humans; status banner; telemetry shows degraded share; post-incident: review fallback quality and capacity (secondary rate limits!).

**Scenario 4 (FDE) — Enterprise customer insists on approving every model change.** *Clarify:* what counts as a "change" (prompt tweaks? KB updates? provider patch versions?); their review SLA; evidence they need. *Reasoning:* Per-tenant manifests and tenant-scoped canaries; deliver an eval report (their dataset slices, safety results, cost/latency deltas) per release; KB content updates handled separately from behaviour changes with lighter review; agree an emergency path for security fixes.

**Scenario 5 — Embedding upgrade promises +8% recall.** *Reasoning:* Verify on *your* eval and canary query set per slice; budget re-embedding; dual-write + backfill + shadow + canary; keep A for rollback; check that metadata filters/tenancy work identically.

### 13. Interview Preparation

#### Quick Questions

**Q: Drift vs regression?** Regression is caused by your change (detect with offline evals/canary vs control); drift is a change in inputs, data or dependencies over time (detect with monitoring and online evals).

**Q: Why pin model versions?** Reproducibility and attribution; aliases can change behaviour without your release process.

**Q: What's a canary release?** Routing a small share of real traffic to a candidate and comparing to control with stop criteria before expanding.

**Q: What should happen to actions when the model is unavailable?** They don't execute — fail closed — and users are told; requests may be queued for humans.

#### Intermediate Questions

**Q: How do you design release gates for a prompt change?**
Strong answer: Offline eval vs baseline with trials and slices; absolute safety gates (zero forbidden behaviour, schema ≥ 99%); then shadow/canary with measurable stop criteria (task success via online judge with minimum samples, error rate, latency, escalation), automated rollback.

**Q: How do you migrate embedding models?**
Strong answer: Re-embed everything; evaluate offline; dual-write + backfill; verify completeness; shadow-compare; canary; switch index and query embedder together via alias; keep old index for rollback.

**Q: Describe a circuit breaker.**
Strong answer: CLOSED counts failures; past a threshold it OPENs and fails fast; after a cool-down HALF_OPEN lets limited trial calls through; successes close it, failures reopen. Combine with timeouts, jittered retries and fallbacks.

#### Advanced Questions

**Q: How do you get statistically meaningful canary results for AI quality?**
Strong answer: Online evals on sampled canary and control traffic with calibrated judges; minimum sample sizes based on detectable effect; paired/sticky assignment; longer windows for rare slices; hard limits for safety signals that don't need statistics (any forbidden event).

**Q: Your fallback model is cheaper and weaker. What guardrails apply?**
Strong answer: Same eval/adversarial suite; restricted capabilities (no actions, read-only tools); disclosure to users; telemetry flag; capacity planning (rate limits); automatic return to primary via half-open probes.

#### Coding Questions

1. Implement a circuit breaker with an injectable clock and tests.
2. Implement PSI with smoothing for categorical distributions.
3. Implement `canary_decision(control, canary, criteria)` with hard and soft limits.

#### Scenario Questions

* "Quality dropped 6 points last week; no deploys. Walk me through it."
* "Design the rollout for switching from provider A to provider B for 300 enterprise tenants."

### 14. Explain-It-at-Three-Levels

**Safe AI deployment**

* *30 s:* Version everything that changes behaviour, gate releases on evals against a baseline, roll out progressively with measurable stop criteria, and keep the previous version ready to roll back.
* *2 min:* Manifest, offline gates, shadow (no side effects), canary with sticky assignment and online evals, hard vs soft stop criteria, automated rollback.
* *Deep:* Statistical power, slice gates, tenant-scoped rollouts, provenance-based analysis, embedding migrations, and deprecation planning.

**Drift**

* *30 s:* Drift is the world changing under a fixed system; detect it by monitoring input/output distributions, retrieval quality and online evals.
* *2 min:* Types of drift, PSI and tests, canary query sets, responding by updating data/prompts/evals.
* *Deep:* Effect size vs significance at scale, embedding-cluster monitoring, concept drift from policy changes, alias-induced model drift.

**Resilience**

* *30 s:* Timeouts, jittered retries, circuit breakers and bulkheads keep AI outages from cascading; a fallback ladder ends in a safe non-AI path, and actions fail closed.
* *2 min:* Breaker states, retry budgets, fallback evaluation, honest degraded UX.
* *Deep:* Retry storms, half-open probing, provider rate-limit interplay, streaming timeouts, game days, and SLOs for degraded modes.

### 15. Knowledge Check

**Conceptual**

1. Name five artifacts that belong in an AI release manifest.
2. Why can't you mix vectors from two embedding models in one index?
3. What makes a stop criterion "measurable"?
4. Why must shadow mode disable side effects?
5. Why is an unevaluated fallback model dangerous?

**Code reading**

6. In `ResilientAnswerer.answer`, what happens to an action request when both models fail?
7. Why does `retry_with_backoff` re-raise `CircuitOpen` immediately?
8. In `canary_decision`, why are hard limits checked before sample-size sufficiency?

**Debugging**

9. Quality drops gradually over a month; the manifest hasn't changed. Three hypotheses?
10. During an outage, latency went to 60 s and workers died. What was missing?

**Design**

11. Propose stop criteria for switching the primary model.
12. How would you detect retrieval-quality drift independent of traffic mix?

#### Knowledge Check Answers

1. Model ID (pinned), prompt version/hash, decoding params, index build, embedding model, chunker, reranker, tool/decision schema versions, policy version, code SHA.
2. Each model defines its own vector space (and often dimension); similarities across spaces are meaningless.
3. A defined metric with a data source, comparison (vs control), threshold, and minimum sample size.
4. Shadow traffic duplicates real requests; executing tools would duplicate real actions (double refunds/emails).
5. The outage path becomes the least-tested path; it may violate safety or quality constraints exactly when monitoring is noisiest.
6. It returns an honest refusal ("saved, a human will follow up"); no action executes.
7. Retrying into an open breaker wastes time and defeats fail-fast; the caller should move to the next fallback.
8. Safety violations require immediate rollback regardless of how much data has accumulated.
9. Input drift (new topics), KB staleness/indexing gaps (retrieval drift), model behind an alias changed, concept drift (policy changes).
10. Timeouts, bulkheads/concurrency limits, circuit breaker, retry budget/jitter, load shedding.
11. Zero increase in forbidden events (hard); error rate < 2% (hard); schema compliance ≥ 99%; p95 ≤ control + 500 ms; task success ≥ control − 2 pts after ≥ 500 judged samples; escalation rate ≤ control + 1.5 pts; cost per success within budget.
12. A fixed canary query set with gold documents run on schedule against production retrieval (recall@k trend), plus empty-result rate and top-score distribution per index version.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "We didn't deploy, so nothing changed." | Models, data and users change; monitor drift. |
| "Use the latest model alias to get improvements automatically." | Pin; evaluate upgrades like any release. |
| "Retries make us resilient." | Unbounded retries amplify outages; use budgets, jitter and breakers. |
| "Fallback to a cheaper model is always safe." | Only if it passed the same evals and has restricted capabilities. |
| "A 1% canary with no errors means it's better." | Canaries detect harm; quality needs online evals and samples. |
| "New embeddings are drop-in." | Re-embed everything; switch query and index together. |
| "During outages, skip checks to stay available." | Safety and authorization fail closed. |

### 17. Cheat Sheet

* **Manifest:** code SHA · model (pinned) · decoding · prompt version/hash · index build · embedding model · chunker · reranker · schemas · policy · fallback model · eval report.
* **Regression** = our change → offline gate + canary vs control. **Drift** = world change → monitors + online evals.
* **PSI** = Σ(a−e)·ln(a/e); < 0.1 stable · 0.1–0.25 moderate · > 0.25 major (heuristic; smooth empty bins).
* **Retrieval drift:** canary query set recall@k · top-score distribution · empty-result rate · index freshness.
* **Embedding migration:** offline eval → dual-write → backfill → verify → shadow → canary → alias cutover → rollback window.
* **Rollout:** offline → shadow (no side effects) → 1% → 5% → 25% → 50% → 100%; sticky; arm on spans.
* **Stop criteria:** hard (forbidden events, error rate, SLO) → rollback; soft (quality/escalation/cost deltas after N samples) → rollback/hold.
* **Resilience:** timeouts · retries (retryable only, exp backoff + full jitter, Retry-After, budget) · breaker (CLOSED/OPEN/HALF_OPEN) · bulkhead · shedding · fallback ladder.
* **Fallback ladder:** primary → evaluated secondary → cached → non-AI path → honest refusal; actions fail closed.

### 18. Completion Checklist

* [ ] I can define a release manifest and roll back by switching it.
* [ ] I can explain and detect drift vs regression with appropriate methods.
* [ ] I can run a baseline/candidate eval comparison with CIs and slice gates.
* [ ] I can plan and verify an embedding model migration.
* [ ] I can define measurable rollout stop criteria and implement a controller.
* [ ] I can implement timeouts, jittered retries, breakers, bulkheads and a fallback ladder.
* [ ] I can simulate a provider outage and prove graceful, safe degradation.
* [ ] I can identify when *not* to fall back (actions, safety checks).

### 19. Further Research

**Essential**

* Google SRE Workbook — "Canarying Releases": <https://sre.google/workbook/canarying-releases/> — canary design, metric selection and evaluation.
* Google SRE Book — "Addressing Cascading Failures": <https://sre.google/sre-book/addressing-cascading-failures/> — timeouts, retries, load shedding.
* AWS Builders' Library — "Timeouts, retries, and backoff with jitter": <https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/> — retry budgets and jitter.
* Martin Fowler — "CircuitBreaker": <https://martinfowler.com/bliki/CircuitBreaker.html> — the pattern and its states.
* Your model providers' model deprecation/versioning pages (e.g. Anthropic models overview: <https://platform.claude.com/docs/en/about-claude/models/overview>; OpenAI deprecations: <https://platform.openai.com/docs/deprecations>) — pinning and retirement schedules.

**Deeper Study**

* Sculley et al., "Hidden Technical Debt in Machine Learning Systems" (NeurIPS 2015): <https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems> — entanglement, data dependencies, feedback loops.
* Argo Rollouts — Analysis & progressive delivery: <https://argo-rollouts.readthedocs.io/> ; Flagger: <https://docs.flagger.app/>.
* pgvector — indexing (HNSW/IVFFlat) and dimensions: <https://github.com/pgvector/pgvector>.
* OpenFeature — vendor-neutral feature flagging: <https://openfeature.dev/>.

**Practice**

* Toxiproxy: <https://github.com/Shopify/toxiproxy> — chaos-test model and vector-store dependencies.
* Evidently AI: <https://github.com/evidentlyai/evidently> — drift reports for tabular, text and embedding data.
* Run a game day: kill the primary provider in staging and verify the runbook end to end.

### Unit Completion Standard

Before moving on, you must be able to: **explain** drift vs regression, why everything behaviour-affecting must be versioned, and how staged rollouts and stop criteria work for AI; **implement** a release manifest, a baseline/candidate eval comparison, drift monitors for output distributions and retrieval quality, and a resilience layer (timeouts, jittered retries, circuit breakers, bulkheads, fallback ladder ending in a non-AI path or honest refusal, actions failing closed); **test** these with fake clocks, fault injection and scripted canary metrics; **debug** an outage cascade, a silent model change or an embedding-migration recall drop; and **defend** in an interview your release gates, rollout plan, fallback design and model/index versioning strategy.
