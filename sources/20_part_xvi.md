# Part XVI — AI Evaluation and Operations

**What this part teaches.** Part XV made the agent *safe to connect*. Part XVI makes it *safe to operate and change*. Three disciplines:

1. **Evaluation (Unit 44)** — measuring whether AI behaviour is *good*: task success, tool selection, retrieval quality, groundedness, schema compliance, forbidden behaviour — and turning those measurements into release gates.
2. **Observability and tracing (Unit 45)** — knowing *what happened*: one trace across API, agent, retriever, model and tools; attribution of latency, errors, tokens and cost; provenance; privacy-safe telemetry; incident reconstruction.
3. **Safe deployment, drift and resilience (Unit 46)** — versioning models, prompts and indexes; detecting drift; migrating embeddings; staged rollouts with eval-based gates; circuit breakers and graceful degradation when AI dependencies fail.

**Why it matters.** LLM systems change even when your code doesn't: providers update models, documents change, users shift behaviour. Traditional tests check deterministic functions; AI systems need *statistical* quality evidence and *runtime* evidence. Without evaluation you can't tell if a change helped; without observability you can't tell why something failed; without safe deployment you learn about regressions from customers.

**Where it appears.** Every production AI team runs some version of: an offline eval suite in CI, online monitoring dashboards, trace-based debugging, canary releases of prompt/model changes, and fallbacks when a provider has an outage. For Forward Deployed Engineers, evaluation evidence is how you prove to a customer that the system works on *their* data.

**How it connects.**

```
Unit 41–43 (security, typed decisions, approvals)
     │   produce: forbidden behaviours, decision schemas, approval/rejection records
     v
Unit 44  Evaluation  ─────── "Was the behaviour good?"  (offline + online)
     │   produces: metrics, baselines, thresholds
     v
Unit 45  Observability ───── "What happened?"  (traces, metrics, logs, provenance)
     │   produces: telemetry joined to eval outcomes
     v
Unit 46  Safe deployment ─── "Can we change it safely, and survive failures?"
         uses: eval gates + telemetry for rollout decisions, drift detection, fallbacks
```

The single idea that runs through this part:

> **Observability tells you what happened. Evaluation tells you whether it was good. Deployment discipline uses both to decide what ships.**
