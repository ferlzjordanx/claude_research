# Part XV — Production Agentic Engineering

**What this part teaches.** Earlier parts taught you to build agents: a model that chooses tools, observes results and loops until a stopping condition. This part teaches you to make such an agent *safe to connect to real systems*. It covers three tightly coupled disciplines:

1. **Guardrails and agent security (Unit 41)** — how agents are attacked (direct and indirect prompt injection, tool misuse, excessive agency, data leakage) and how to build defenses that do not depend on the model behaving.
2. **Structured output and deterministic boundaries (Unit 42)** — how to turn free-form model output into typed, validated *proposals* and how to keep business invariants in ordinary, testable code.
3. **Human-in-the-loop approval workflows (Unit 43)** — how to pause an agent before a risky side effect, persist the proposal, collect an accountable human decision, and resume or abandon safely.

**Why it matters.** An LLM is a probabilistic component that reads attacker-controllable text. The moment it can call a tool that moves money, sends email or deletes data, every classic security property — authentication, authorization, input validation, audit, least privilege — must be enforced *around* the model. Most real-world agent incidents (data exfiltration through markdown images, email agents forwarding inboxes, coding agents running hostile commands) are not "the model was dumb"; they are systems that let model output become an authorized action without a deterministic check.

**Where it appears in real systems.** Customer-support agents issuing refunds; IT/helpdesk agents resetting passwords; coding agents with shell access; sales agents sending outbound email; internal copilots over document stores; Forward Deployed Engineers (FDEs) integrating an agent into a customer's CRM, ERP or ticketing system where the customer's security team must sign off.

**How it connects.**

```
Earlier parts                         This part (XV)                       Next part (XVI)
─────────────                         ─────────────                        ───────────────
FastAPI, Pydantic, SQLAlchemy  ──>   Unit 41: threat model + authz   ──>  Unit 44: evaluate safety and
Auth (OAuth2/JWT, RBAC)        ──>   Unit 42: typed decisions        ──>           task success
RAG, tool calling, agent loops ──>   Unit 43: approvals + audit      ──>  Unit 45: trace every decision
Async, retries, idempotency    ──>                                    ──>  Unit 46: ship changes safely
```

The single idea that runs through the whole part:

> **The model proposes. Deterministic code disposes.**
> The LLM may *suggest* an action; authentication, authorization, validation, business rules, approval and execution are performed by ordinary code that the model cannot talk its way past.
