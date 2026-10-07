## Unit 42 — Structured Agent Output and Deterministic Boundaries

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Design** Pydantic v2 models that represent an agent's *decision* (not just its answer), including discriminated unions of action types.
2. **Explain** how provider-side structured output (JSON-schema-constrained decoding, strict tool schemas) differs from client-side validation and why you need both.
3. **Implement** a parse → validate → authorize → execute pipeline that rejects malformed, unknown or unauthorized actions *before* any side effect.
4. **Implement** bounded validation-retry, repair and refusal strategies and **choose** among them based on failure type.
5. **Separate** probabilistic model judgment (intent, extraction, drafting) from deterministic business invariants (eligibility, amounts, state transitions, limits).
6. **Compare** in-process policy code, OPA/Rego and Cedar as deterministic policy engines and **implement** one.
7. **Test** for schema drift and unexpected model output using contract tests, schema snapshots, golden outputs, fuzzing and Hypothesis.
8. **Defend** in an interview which responsibilities belong to the model and which belong to code.

### 2. Prerequisite Knowledge

* **Pydantic v2 core API:** `BaseModel`, `Field`, `ConfigDict`, `model_validate`, `model_validate_json`, `model_dump(mode="json")`, `model_json_schema()`, `TypeAdapter`, `field_validator`, `model_validator`. Pydantic v2's validation runs in `pydantic-core` (Rust). **Pydantic v1 patterns** (`class Config`, `parse_obj`, `.dict()`, `@validator`) are **legacy** — don't use them in new code.
* **Python typing:** `Literal`, `Annotated`, unions with `|`, `Enum`/`StrEnum`.
* **JSON Schema basics:** `type`, `properties`, `required`, `enum`, `const`, `oneOf`/`anyOf`, `additionalProperties`, `$defs`/`$ref`.
* **Tool calling** (Unit 41): the model returns `{name, arguments}`; your code executes.
* **State machines:** states, transitions, guards.

### 3. Mental Model

The model is a **form-filling clerk**; your application is the **back office**.

```
   Natural-language world                      Typed world (your code)
 ┌────────────────────────┐    contract    ┌──────────────────────────────────────────┐
 │ user goal, documents,  │ ─────────────> │ AgentDecision (discriminated union)      │
 │ conversation           │   JSON Schema  │   ├─ Answer                              │
 │                        │                │   ├─ AskClarification                    │
 │      LLM (judgment)    │                │   ├─ ProposeRefund(order_id, reason)     │
 │                        │                │   ├─ ProposeAddressChange(...)           │
 └────────────────────────┘                │   └─ Escalate / Refuse                   │
                                           └──────────────┬───────────────────────────┘
                                                          v
                    parse ─> validate (shape) ─> resolve (load real records)
                         ─> check invariants (business rules, state machine)
                         ─> authorize (policy engine)  ─> approve? ─> execute
```

Three ideas to hold on to:

1. **Typed decisions turn "what did the model mean?" into "which branch of the union is this?"** — a question code can answer exactly.
2. **Structure ≠ correctness.** A perfectly valid `ProposeRefund` can still name the wrong order, be ineligible, or be unauthorized. Validation is necessary, not sufficient.
3. **The model judges; the code decides.** Let the model do what is fuzzy (understand intent, extract fields from messy text, draft language). Keep what must be *always true* (refund ≤ paid amount, can't refund a cancelled order twice, only supervisors approve >$500) in deterministic code.

### 4. Comprehensive Theory

#### 4.1 Pydantic Models for Model Decisions

**Definition.** A *decision schema* is a typed model describing everything the agent may decide to do next — including "answer", "ask a question", "propose action X", "escalate" and "refuse" — so that every model turn is parsed into exactly one well-defined object.

**Why it exists.** Free text is ambiguous ("I've gone ahead and processed that for you" — did it? which order? how much?). Tool calling helps, but an agent often needs to choose between *answering*, *clarifying* and *acting*. A decision schema makes that choice explicit, logged and testable.

**How it works.** You define models; Pydantic generates JSON Schema (`model_json_schema()`), which you pass to the provider (as a response format or as tool input schemas). The model's output is validated back into Python objects with `model_validate_json`. Validation errors are structured (`loc`, `type`, `msg`) and can be fed back for a retry.

**Syntax.**

```python
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

OrderId = Annotated[str, StringConstraints(pattern=r"^ord_[a-z0-9]{12}$")]

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rationale: str = Field(max_length=600, description="Short reason, shown to reviewers.")

class Answer(Decision):
    kind: Literal["answer"] = "answer"
    text: str = Field(max_length=4000)
    cited_article_ids: list[str] = Field(default_factory=list, max_length=10)

class AskClarification(Decision):
    kind: Literal["ask_clarification"] = "ask_clarification"
    question: str = Field(max_length=500)
```

**Design considerations.**

* **Include a short `rationale`** for reviewers and evaluation — but never *trust* it as evidence (models can produce plausible but unfaithful rationales).
* **Use `extra="forbid"`** so unexpected fields are errors, not silently dropped.
* **Use `frozen=True`** for decisions: they are facts about what the model proposed; mutating them later obscures the audit trail.
* **Keep descriptions precise**: Field descriptions become part of the JSON Schema the model sees. They are prompt text.
* **Prefer identifiers over values**: `order_id` rather than `customer_email`; `reason_code` enum rather than free text — the back office looks up the rest.

**Trade-offs.** Rich schemas improve control but increase prompt tokens and can reduce model quality if overly nested or ambiguous. Very large unions (dozens of actions) are harder for the model — split by sub-agent or stage.

**Common mistakes.** Using `dict[str, Any]` "for flexibility" (you just moved parsing into ad-hoc code); optional-everything models where `None` means five different things; numbers as `float` for money.

#### 4.2 Discriminated Unions for Action Types

**Definition.** A *discriminated (tagged) union* is a union of models that share a literal field (the *discriminator*, e.g. `kind`) whose value identifies which model applies.

**Why it exists.** With a plain union, Pydantic's default *smart mode* tries members to find the best match; ambiguity produces confusing errors and, in edge cases, the wrong branch. With a discriminator, validation reads the tag and validates only against that branch: faster, deterministic and with precise error messages. The generated JSON Schema includes a `discriminator` mapping and `oneOf`, which helps both providers and humans.

**Syntax.**

```python
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter

class RefundReason(StrEnum):
    DAMAGED = "damaged"
    NOT_RECEIVED = "not_received"
    WRONG_ITEM = "wrong_item"

class ProposeRefund(Decision):
    kind: Literal["propose_refund"] = "propose_refund"
    order_id: OrderId
    reason: RefundReason
    line_item_ids: list[str] = Field(min_length=1, max_length=50)  # amount computed by code

class Escalate(Decision):
    kind: Literal["escalate"] = "escalate"
    queue: Literal["billing", "fraud", "tier2"]

class Refuse(Decision):
    kind: Literal["refuse"] = "refuse"
    user_message: str = Field(max_length=500)

AgentDecision = Annotated[
    Union[Answer, AskClarification, ProposeRefund, Escalate, Refuse],
    Field(discriminator="kind"),
]
decision_adapter: TypeAdapter[AgentDecision] = TypeAdapter(AgentDecision)
```

`decision_adapter.validate_json(raw)` returns the correct subclass; `match` handles it:

```python
match decision_adapter.validate_json(raw):
    case Answer(text=text):
        ...
    case ProposeRefund() as proposal:
        ...
    case AskClarification(question=q):
        ...
    case Escalate() | Refuse():
        ...
```

Notice `ProposeRefund` has **no amount field**. The model identifies *which items* and *why*; the refund amount is computed deterministically from the order's line items and payments. This is the single most effective design move in this unit: *remove from the model's output any value that code can compute.*

**Nested/callable discriminators.** Pydantic v2 also supports `Discriminator(callable)` with `Tag(...)` for cases where the tag is derived (e.g., legacy payloads without a `kind` field) — useful during schema migrations.

**Common mistakes.** Forgetting the default on the `Literal` field (then every instance must pass `kind`); putting the discriminator in a nested object; using `str` instead of `Literal` (no discrimination happens).

**Interview perspective.** "Why a discriminated union instead of a `type: str` field and if/else?" — exhaustive handling, precise validation, schema-level documentation, and static type narrowing with `match`.

#### 4.3 Provider-Side Structured Output vs Client-Side Validation

There are three ways to get structured output from a model, with very different guarantees:

| Approach | Mechanism | Guarantee | Status |
|---|---|---|---|
| **Prompting for JSON** ("respond in JSON like …") | Instructions only | None; frequent syntax/shape errors | **Legacy** for production |
| **JSON mode** | Decoder constrained to *valid JSON* | Syntactically valid JSON, any shape | Superseded by schema-constrained modes |
| **Schema-constrained output / strict tools** | Decoder constrained by a grammar compiled from your JSON Schema | Output matches the (supported subset of) schema | **Current** — e.g. OpenAI Structured Outputs (`strict: true`), Anthropic structured outputs (`output_config.format` for JSON outputs; `strict: true` on tool definitions), Gemini `response_schema` |

**How constrained decoding works.** At each generation step the model produces logits over the vocabulary. The serving stack compiles your schema into a grammar/automaton and *masks* tokens that would make the output invalid, so only schema-consistent continuations can be sampled. The result is syntactically and structurally valid — but the model can still choose the wrong branch, a wrong ID, or a semantically poor value.

**Why you still validate client-side.**

1. Providers support only a **subset** of JSON Schema (e.g. some keywords such as certain numeric bounds, string formats or complex patterns may be unsupported or ignored; some require `additionalProperties: false` and all fields required). SDK helpers may strip unsupported constraints from the schema they send and then validate locally. Check the provider's documentation for the supported subset — this is **version-dependent**.
2. **Truncation**: if the response hits `max_tokens`, output may be cut off mid-object.
3. **Refusals**: safety refusals arrive in a provider-specific shape (e.g. a refusal stop reason or field) rather than your schema.
4. **Semantic constraints** (cross-field rules, existence of IDs) can't be expressed in JSON Schema at all.
5. **Defense in depth**: provider bugs, model changes, gateway proxies or fallback models without constrained decoding.

So the rule is: **use constrained decoding to reduce failures; use Pydantic to enforce the contract; use business code to enforce truth.**

**Schema design for providers.** Keep schemas flat-ish, use enums for closed sets, avoid deeply recursive types, keep descriptions short and unambiguous, and generate them from the same Pydantic models you validate with (single source of truth).

#### 4.4 Validation, Retry and Refusal Strategies

Not all failures deserve the same treatment. Classify first:

| Failure class | Example | Strategy |
|---|---|---|
| **Syntax** | Truncated JSON, trailing text | Retry once (increase `max_tokens` if stop reason was length); with constrained decoding, mostly disappears |
| **Schema** | Missing field, wrong enum, extra field | Retry with structured error feedback (bounded: 1–2 attempts) |
| **Semantic / referential** | Unknown `order_id`, line items not in order | Return a *tool-style error* to the model so it can ask the user or look up; do **not** "fix" silently |
| **Business invariant** | Refund on already-refunded item | Deterministic rejection with a reason; model may explain to user |
| **Authorization** | Role can't do this | Deny or route to approval; never retry in a loop hoping for a different result |
| **Model refusal** | Safety refusal | Respect; map to `Refuse` decision; log as refusal, not as error |
| **Repeated failure** | 3 schema errors in a row | Fallback: escalate to human / safe default answer |

**Retry with feedback (bounded).** Send back the validation errors *without* echoing raw input, and ask for a corrected object. Keep a hard cap; every retry costs latency and tokens, and repeated failure indicates a prompt/schema problem, not bad luck.

**Repair vs reject.** Deterministic *repair* is acceptable for harmless formatting (strip code fences around JSON, normalize whitespace). It is **not** acceptable for meaning (guessing a missing order ID, clamping an amount to the limit, mapping an unknown enum to the "closest" value). Silent semantic repair hides bugs and can turn an attack into an action.

**Refusal handling.** Treat "the model refused" as a first-class outcome: `Refuse` in your union for *policy* refusals the agent chooses, and a provider-refusal adapter that maps provider-level refusals into it. Measure refusal rate (too high = over-blocking; sudden change = drift — Unit 46).

#### 4.5 Separating Model Judgment from Business Invariants

**Definition.** A *business invariant* is a condition that must always hold regardless of who or what initiated the action — e.g., "total refunds on an order never exceed captured payments", "an account with an open chargeback can't be deleted", "addresses must pass the carrier's validation".

**Allocation of responsibility:**

| Probabilistic (model) | Deterministic (code) |
|---|---|
| Understand the user's intent | Whether the action is permitted for this principal |
| Extract order ID / item references from messy text | Whether the order exists and belongs to the tenant |
| Classify reason (damaged vs not received) | Eligibility windows, return policies, limits |
| Draft a polite reply | Refund amount computation, tax, currency rounding |
| Decide to ask a clarifying question | State transitions (`shipped → refunded` allowed? `refunded → refunded`?) |
| Summarize a case for the reviewer | Idempotency, concurrency control, audit |

**How to implement.** Put invariants in the **domain layer** (entities/services), not in the agent. The agent calls the same domain service a human-operated UI would. That way:

* the invariant holds for every caller (API, batch job, agent, admin UI);
* it is unit-testable without any model;
* changing the model cannot weaken it.

**State machines for actions.** Model each proposal's lifecycle explicitly (Unit 43 reuses this):

```
proposed ──validate──> validated ──authorize──> approved/auto_approved ──execute──> executed
    │                       │                         │                              │
    └──> rejected_invalid   └──> rejected_policy      └──> expired/rejected          └──> failed
```

Transitions are functions that check guards and raise on illegal moves.

**Common mistakes.** Letting the model compute amounts ("refund 2 × $19.99 + tax"); trusting the model's statement that a check passed ("I verified the customer's identity"); encoding eligibility rules in the prompt and in code with subtle differences.

#### 4.6 Deterministic Policy Engines and Application Checks

**Definition.** A policy engine evaluates authorization/business policies against a structured request (principal, action, resource, context) and returns a decision. Options:

| Option | Model | Strengths | Weaknesses |
|---|---|---|---|
| **In-process Python** (functions, `match`) | Code | Simple, fast, typed, easy to test | Policy changes require deploys; harder for non-engineers to audit |
| **OPA / Rego** (CNCF graduated) | Datalog-like rules over JSON input | Policy-as-code, decoupled from services, decision logs, mature ecosystem | Another language; sidecar/network hop unless embedded; untyped inputs |
| **Cedar** (AWS, open source; Amazon Verified Permissions) | Principal–action–resource–context, permit/forbid | Readable, analyzable (formal verification tooling), schema-typed | Narrower scope (authorization), fewer integrations than OPA |
| **Casbin / Oso-style libraries** | RBAC/ABAC models | Embeddable | Varying expressiveness |

**Cedar example** (illustrative):

```cedar
permit (
  principal in Role::"support_agent",
  action == Action::"issue_refund",
  resource
)
when {
  resource.tenant == principal.tenant &&
  context.amount <= 50 &&
  !context.untrusted_content_seen
};

forbid (principal, action == Action::"delete_account", resource)
unless { context.approved_by_supervisor };
```

**Rego example** (OPA v1 syntax, illustrative):

```rego
package supportops.authz

default decision := "deny"

decision := "allow" if {
    input.action == "issue_refund"
    input.resource.tenant == input.principal.tenant
    input.context.amount <= limits[input.principal.role]
    not input.context.untrusted_content_seen
}

decision := "require_approval" if {
    input.action == "issue_refund"
    input.resource.tenant == input.principal.tenant
    input.context.amount > limits[input.principal.role]
}

limits := {"support_agent": 50, "supervisor": 500}
```

OPA 1.0 (released December 2024) made the `if`/`contains` keywords mandatory; older Rego without them is **legacy** syntax.

**Design considerations.** Whatever engine you use: inputs are **resolved facts** (loaded from your DB), not model claims; the engine returns a decision *and a reason*; decisions are logged with the policy version; the default is deny.

**Interview perspective.** The interviewer wants to see that you put *facts* into the policy engine (resolved by code) and not *model assertions*, and that you can articulate when a separate engine is worth its operational cost.

#### 4.7 Schema Drift and Unexpected Model Output

**Definition.** *Schema drift* is a mismatch between what your code expects and what arrives — caused by model upgrades, prompt edits, schema changes not propagated to all consumers, provider SDK changes, or fallback to a model without constrained decoding.

**Defenses.**

* **Version the contract**: `schema_version: Literal["2026-09"]` in persisted decisions; migrations for stored proposals.
* **Snapshot the JSON Schema** in a test (`model_json_schema()` compared with a committed file) so schema changes are reviewed deliberately.
* **Golden outputs**: store representative real model outputs (redacted) and re-validate them in CI against the current models.
* **Tolerant reader only where safe**: for *read-only display* you may ignore unknown fields; for *actions*, forbid them.
* **Fuzz the parser**: Hypothesis generates random JSON and near-miss payloads; assert they either validate into a legal decision or raise `ValidationError` — never crash, never execute.
* **Monitor**: validation-failure rate per model/prompt version (Unit 45/46).

### 5. Internal Mechanics

#### 5.1 What Pydantic does on `validate_json`

```
raw bytes ──> pydantic-core JSON parser (Rust, jiter) ──> Python-independent values
          ──> discriminator lookup: read "kind" ──> select branch schema (O(1) dict lookup)
          ──> validate fields in branch: type checks, constraints, nested models
          ──> collect *all* errors for the branch (not just the first)
          ──> construct model instance (frozen → hash/eq semantics; no __setattr__)
```

* Validating **JSON directly** (`validate_json`) is faster than `json.loads` + `validate_python` and applies JSON-mode coercion rules (e.g., strings accepted for `Decimal`).
* In **lax mode** (default), Pydantic coerces some types (`"5"` → `5` for `int`). For model outputs that drive actions, consider `strict=True` on sensitive fields (`Field(strict=True)`) — note that strict JSON mode still accepts JSON strings for types like `Decimal`/`datetime` where JSON has no native type.
* Errors carry `loc` (path), `type` (machine code like `literal_error`, `missing`, `extra_forbidden`), `msg`, and `input`. Strip `input` when feeding errors back to a model or logs.

#### 5.2 What happens with a discriminated union's JSON Schema

`TypeAdapter(AgentDecision).json_schema()` emits `$defs` for each member and a `oneOf` with a `discriminator: {propertyName: "kind", mapping: {...}}`. Some providers ignore `discriminator` but honour `const`/`enum` on `kind` within each branch; the `Literal` default produces `const`. Verify the schema your provider accepts — some require all properties to be listed in `required` even if they have defaults.

#### 5.3 The decision pipeline end to end

```
model output (JSON)
  │ 1 parse+validate (Pydantic)            → ValidationError → retry-with-feedback (≤ N) → escalate
  v
typed decision (e.g. ProposeRefund)
  │ 2 resolve references (DB lookups)      → NotFound → tool error to model / ask clarification
  v
resolved command (Order, LineItems, computed amount)
  │ 3 invariants (domain service)          → InvariantViolation → explain to user, no retry
  v
valid command
  │ 4 policy engine (facts only)           → deny | require_approval | allow
  v
authorized command
  │ 5 execute (idempotent, transactional)  → audit + outcome
```

Each stage has a distinct error type and handling policy. Collapsing them (e.g., one `try/except Exception: retry`) makes the system both less safe and harder to debug.

### 6. Implementation Examples

#### Example 1 — Minimal: validate a decision union (Runnable)

```python
# ex42_1.py   pip install "pydantic>=2.7"
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class Answer(_Base):
    kind: Literal["answer"] = "answer"
    text: str

class LookupOrder(_Base):
    kind: Literal["lookup_order"] = "lookup_order"
    order_id: str = Field(pattern=r"^ord_[a-z0-9]{12}$")

Decision = Annotated[Union[Answer, LookupOrder], Field(discriminator="kind")]
adapter = TypeAdapter(Decision)

samples = [
    '{"kind": "answer", "text": "Your order shipped."}',
    '{"kind": "lookup_order", "order_id": "ord_abc123def456"}',
    '{"kind": "lookup_order", "order_id": "12345"}',
    '{"kind": "delete_everything"}',
    '{"kind": "answer", "text": "hi", "admin": true}',
]
for raw in samples:
    try:
        print("OK ", repr(adapter.validate_json(raw)))
    except ValidationError as e:
        print("ERR", [(err["type"], err["loc"]) for err in e.errors()])
```

```
OK  Answer(kind='answer', text='Your order shipped.')
OK  LookupOrder(kind='lookup_order', order_id='ord_abc123def456')
ERR [('string_pattern_mismatch', ('lookup_order', 'order_id'))]
ERR [('union_tag_invalid', ())]
ERR [('extra_forbidden', ('answer', 'admin'))]
```

Note how the error location includes the selected branch tag — this is what makes discriminated unions debuggable.

#### Example 2 — Realistic: decision → resolve → invariant → policy (Runnable, in-memory)

**Architecture.** The agent proposes a refund of *line items*; the domain service computes the amount and enforces invariants; the policy decides allow / approval / deny on facts.

```python
# ex42_2.py
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

# ---------- contract (what the model may say) ----------
class _Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rationale: str = Field(max_length=600)

class RefundReason(StrEnum):
    DAMAGED = "damaged"
    NOT_RECEIVED = "not_received"
    WRONG_ITEM = "wrong_item"

class Answer(_Decision):
    kind: Literal["answer"] = "answer"
    text: str = Field(max_length=4000)

class AskClarification(_Decision):
    kind: Literal["ask_clarification"] = "ask_clarification"
    question: str = Field(max_length=500)

class ProposeRefund(_Decision):
    kind: Literal["propose_refund"] = "propose_refund"
    order_id: str = Field(pattern=r"^ord_[a-z0-9]{12}$")
    line_item_ids: list[str] = Field(min_length=1, max_length=50)
    reason: RefundReason

AgentDecision = Annotated[Union[Answer, AskClarification, ProposeRefund],
                          Field(discriminator="kind")]
DECISION = TypeAdapter(AgentDecision)

# ---------- domain (truth) ----------
@dataclass
class LineItem:
    id: str
    price: Decimal
    refunded: bool = False

@dataclass
class Order:
    id: str
    tenant_id: str
    status: str
    items: dict[str, LineItem] = field(default_factory=dict)

class DomainError(Exception):
    """Business invariant violated — deterministic, not retryable by the model."""

class NotFound(DomainError):
    pass

ORDERS: dict[str, Order] = {
    "ord_aaaaaaaaaaaa": Order("ord_aaaaaaaaaaaa", "acme", "delivered", {
        "li_1": LineItem("li_1", Decimal("19.99")),
        "li_2": LineItem("li_2", Decimal("45.00"), refunded=True),
    }),
}

@dataclass(frozen=True)
class RefundCommand:
    order_id: str
    item_ids: tuple[str, ...]
    amount: Decimal
    reason: RefundReason

def resolve_refund(tenant_id: str, p: ProposeRefund) -> RefundCommand:
    order = ORDERS.get(p.order_id)
    if order is None or order.tenant_id != tenant_id:
        raise NotFound("order not found")
    if order.status not in {"delivered", "shipped"}:
        raise DomainError(f"cannot refund an order in status {order.status}")
    if len(set(p.line_item_ids)) != len(p.line_item_ids):
        raise DomainError("duplicate line items")
    items = []
    for item_id in p.line_item_ids:
        item = order.items.get(item_id)
        if item is None:
            raise NotFound(f"line item {item_id} not on order")
        if item.refunded:
            raise DomainError(f"line item {item_id} already refunded")
        items.append(item)
    amount = sum((i.price for i in items), Decimal("0"))       # code computes money
    return RefundCommand(order.id, tuple(p.line_item_ids), amount, p.reason)

# ---------- policy (facts in, decision out) ----------
class Outcome(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"

LIMITS = {"support_agent": Decimal("50"), "supervisor": Decimal("500")}

def decide(role: str, cmd: RefundCommand) -> tuple[Outcome, str]:
    limit = LIMITS.get(role)
    if limit is None:
        return Outcome.DENY, "role cannot refund"
    if cmd.amount <= limit:
        return Outcome.ALLOW, f"{cmd.amount} within {role} limit {limit}"
    return Outcome.REQUIRE_APPROVAL, f"{cmd.amount} exceeds {role} limit {limit}"

# ---------- orchestration ----------
def handle(raw_model_output: str, tenant_id: str, role: str) -> str:
    try:
        decision = DECISION.validate_json(raw_model_output)
    except ValidationError as e:
        return f"INVALID_OUTPUT {[(x['type'], x['loc']) for x in e.errors()]}"
    match decision:
        case Answer(text=text):
            return f"ANSWER {text}"
        case AskClarification(question=q):
            return f"ASK {q}"
        case ProposeRefund() as proposal:
            try:
                cmd = resolve_refund(tenant_id, proposal)
            except NotFound as e:
                return f"NOT_FOUND {e}"              # tell the model; it may ask the user
            except DomainError as e:
                return f"REJECTED {e}"               # invariant; do not retry
            outcome, reason = decide(role, cmd)
            return f"{outcome.upper()} amount={cmd.amount} ({reason})"
    return "UNREACHABLE"

if __name__ == "__main__":
    cases = [
        '{"kind":"propose_refund","rationale":"box crushed","order_id":"ord_aaaaaaaaaaaa",'
        '"line_item_ids":["li_1"],"reason":"damaged"}',
        '{"kind":"propose_refund","rationale":"x","order_id":"ord_aaaaaaaaaaaa",'
        '"line_item_ids":["li_2"],"reason":"damaged"}',
        '{"kind":"propose_refund","rationale":"x","order_id":"ord_aaaaaaaaaaaa",'
        '"line_item_ids":["li_1"],"reason":"damaged","amount":"999"}',
        '{"kind":"ask_clarification","rationale":"which order?","question":"Which order?"}',
    ]
    for c in cases:
        print(handle(c, tenant_id="acme", role="support_agent"))
```

```
ALLOW amount=19.99 (19.99 within support_agent limit 50)
REJECTED line item li_2 already refunded
INVALID_OUTPUT [('extra_forbidden', ('propose_refund', 'amount'))]
ASK Which order?
```

The third case is instructive: an injected or hallucinated `amount` is not "ignored" — it is *rejected*, which shows up in metrics.

#### Example 3 — Production-oriented: structured output service with bounded retry, refusal mapping and telemetry

**Architecture.**

```
app/agent/structured.py
  StructuredDecider
    ├─ builds schema once from TypeAdapter (single source of truth)
    ├─ calls ModelClient.generate_json(schema=..., messages=...)
    ├─ classifies result: ok | truncated | refused | schema_error
    ├─ bounded retry with sanitized error feedback
    └─ returns DecisionResult(decision | fallback, attempts, failure_reasons)
```

```python
# app/agent/structured.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import TypeAdapter, ValidationError

from app.agent.decisions import AgentDecision, Escalate, Refuse

log = logging.getLogger("supportops.structured")

class StopReason(StrEnum):
    END = "end"
    MAX_TOKENS = "max_tokens"
    REFUSAL = "refusal"

@dataclass(frozen=True)
class RawGeneration:
    text: str
    stop_reason: StopReason
    model: str
    input_tokens: int
    output_tokens: int

class JsonModelClient(Protocol):
    async def generate_json(self, *, messages: list[dict[str, Any]], schema: dict[str, Any],
                            max_tokens: int) -> RawGeneration: ...

@dataclass
class DecisionResult:
    decision: Any                     # an AgentDecision member
    attempts: int
    failures: list[str] = field(default_factory=list)
    used_fallback: bool = False

class StructuredDecider:
    def __init__(self, client: JsonModelClient, *, max_attempts: int = 2, max_tokens: int = 1024):
        self._client = client
        self._adapter: TypeAdapter = TypeAdapter(AgentDecision)
        self._schema = self._adapter.json_schema()
        self._max_attempts = max_attempts
        self._max_tokens = max_tokens

    async def decide(self, messages: list[dict[str, Any]]) -> DecisionResult:
        failures: list[str] = []
        convo = list(messages)
        max_tokens = self._max_tokens
        for attempt in range(1, self._max_attempts + 1):
            gen = await self._client.generate_json(messages=convo, schema=self._schema,
                                                   max_tokens=max_tokens)
            if gen.stop_reason is StopReason.REFUSAL:
                log.info("model_refusal model=%s", gen.model)
                return DecisionResult(Refuse(rationale="provider refusal",
                                             user_message="I can't help with that request."),
                                      attempt, failures)
            if gen.stop_reason is StopReason.MAX_TOKENS:
                failures.append("truncated")
                max_tokens = min(max_tokens * 2, 4096)     # syntax failure: give room, retry
                continue
            try:
                decision = self._adapter.validate_json(_strip_fences(gen.text))
                return DecisionResult(decision, attempt, failures)
            except ValidationError as exc:
                errs = exc.errors(include_input=False, include_url=False, include_context=False)
                failures.append("schema:" + ",".join(e["type"] for e in errs))
                log.info("decision_invalid attempt=%d model=%s errors=%s",
                         attempt, gen.model, [e["type"] for e in errs])
                convo = convo + [
                    {"role": "assistant", "content": gen.text[:2000]},
                    {"role": "user", "content":
                        "Your previous output did not match the required schema. "
                        f"Errors: {json.dumps(errs)}. Return one corrected JSON object only."},
                ]
        log.warning("decision_fallback failures=%s", failures)
        return DecisionResult(Escalate(rationale="structured output failed", queue="tier2"),
                              self._max_attempts, failures, used_fallback=True)

def _strip_fences(text: str) -> str:
    """Harmless syntactic repair only: remove ```json fences. Never repair meaning."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()
```

**Design decisions explained.**

* The schema is generated **once** from the same `TypeAdapter` used to validate — no hand-written schema that can drift.
* Truncation is a *syntax* failure: retry with more tokens. Schema errors: retry with sanitized feedback. Refusal: map to `Refuse` immediately (don't retry to "get around" a refusal).
* Fallback is **escalation to a human queue**, not "pick the most likely action".
* `failures` are returned so the caller can record them as span attributes/metrics (Unit 45): validation-failure rate by model version is a key drift signal (Unit 46).

**Provider adapter sketch (Illustrative).** The adapter is where provider specifics live: passing the JSON Schema as a structured-output format or as a single strict tool, mapping the provider's stop/refusal signals to `StopReason`, and recording usage. Keep this in one module so that a provider or SDK upgrade touches one file and its contract tests.

**FastAPI integration.**

```python
@router.post("/v1/agent/decide")
async def decide(req: ChatRequest, principal: CurrentPrincipal,
                 decider: Annotated[StructuredDecider, Depends(get_decider)]):
    result = await decider.decide(build_messages(principal, req))
    match result.decision:
        case ProposeRefund() as p:
            outcome = await refund_service.propose(principal, p)   # resolve → invariants → policy
            return {"type": "proposal", "status": outcome.status, "proposal_id": outcome.id}
        case Answer(text=t):
            return {"type": "answer", "text": sanitize_markdown(t)}
        case AskClarification(question=q):
            return {"type": "question", "text": q}
        case Escalate(queue=q):
            return {"type": "escalated", "queue": q}
        case Refuse(user_message=m):
            return {"type": "refused", "text": m}
```

### 7. Comparative Analysis

| Comparison | Key difference | When to use | Interview trap |
|---|---|---|---|
| **Free text vs JSON mode vs schema-constrained** | No guarantee / valid JSON / schema-valid | Constrained for any machine-consumed output | "Constrained decoding means we don't need validation" |
| **Tool calling vs decision schema (response format)** | Model selects among functions vs model fills one union object | Tool calling for multi-step loops with many tools; decision schema when each turn must be exactly one of a small set of outcomes (incl. answer/clarify) | They are complementary; tool inputs are also schemas |
| **Plain union vs discriminated union** | Smart-mode trial vs tag dispatch | Discriminated for any action union | Using `str` instead of `Literal` for the tag |
| **dataclass vs Pydantic model vs TypedDict** | No validation / validation+serialization / static typing only | Pydantic at trust boundaries; dataclasses for internal resolved commands; TypedDict for typing JSON you don't validate | "Type hints validate at runtime" |
| **Validation error vs domain error vs authorization error vs HTTP error** | Shape vs truth vs permission vs transport | Distinct handling and metrics for each | One `except Exception` for all |
| **Retry vs repair vs reject vs escalate** | Ask again / fix syntax / refuse / hand to human | Retry: schema errors (bounded). Repair: harmless syntax only. Reject: invariants. Escalate: repeated failure | Retrying authorization denials |
| **In-process policy vs OPA vs Cedar** | Code vs general policy language vs authz-specific language | In-process for small teams; OPA for org-wide policy; Cedar for typed, analyzable authz | Putting model claims into policy input |
| **Model judgment vs business invariant** | Fuzzy and context-dependent vs always-true rules | Model for intent/extraction/drafting; code for money, state, eligibility | Letting the model compute amounts |

### 8. Failure Modes and Debugging

**F1 — Validation failures spike after a model upgrade.**
SYMPTOM: `decision_invalid` rate jumps from 0.3% to 9%.
↓ CAUSE: New model formats differently (e.g., wraps JSON in prose) or the provider adapter no longer enables constrained output for the new model ID.
↓ INVESTIGATE: Group failures by `error.type` and `gen_ai.response.model`; replay golden prompts against old/new model; inspect the request payload the adapter sends.
↓ FIX: Enable schema-constrained output for the new model; adjust prompt; pin model version.
↓ PREVENT: Contract tests per model; eval gate on schema-compliance rate (Unit 44/46).

**F2 — Silent wrong branch.**
SYMPTOM: Some refund requests come back as `Answer` saying "I've refunded you" with no refund.
↓ CAUSE: The model chose `Answer` and *claimed* an action. The UI showed it.
↓ FIX: Product rule: only `ProposeRefund` results can produce "refunded" messaging — generated from the actual outcome, not model text. Add an output check that `Answer` text doesn't claim completed actions.
↓ PREVENT: Eval cases for "claims action without performing it" as forbidden behaviour.

**F3 — `union_tag_invalid` for valid-looking output.**
SYMPTOM: Model emits `{"type": "propose_refund", ...}`.
↓ CAUSE: Prompt or provider schema used `type` while code uses `kind` (drift between hand-written schema and models).
↓ FIX: Generate the schema from the TypeAdapter; snapshot test.

**F4 — Extra field silently dropped.**
SYMPTOM: Auditors find the model *tried* to set `amount` but the system ignored it — no record.
↓ CAUSE: Default `extra="ignore"`.
↓ FIX: `extra="forbid"` and record rejections; investigate why the model tried (possible injection).

**F5 — Infinite retry and cost spike.**
SYMPTOM: One request consumed 60k tokens.
↓ CAUSE: Retry loop on *authorization* or *domain* errors.
↓ FIX: Only schema/syntax failures are retried, with a cap. Domain/authz errors are terminal for that proposal.

**F6 — Money rounding discrepancies.**
SYMPTOM: Refund totals off by a cent.
↓ CAUSE: `float` in schema or model-computed totals.
↓ FIX: `Decimal` everywhere; code computes totals with explicit `quantize(Decimal("0.01"), ROUND_HALF_EVEN)` per currency rules.

**Debugging tools.** `ValidationError.errors()` grouped by `type`/`loc`; JSON Schema diff (`model_json_schema()` snapshot vs current); replaying stored raw outputs through the adapter; traces with `error.type` on validation spans; Hypothesis shrinking to minimal failing payloads.

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Who owns it?* For 15 responsibilities (e.g., "compute tax", "detect sarcasm", "choose refund reason", "check return window", "decide if user is a supervisor"), assign *model* or *code* and justify. Hints: Could two correct implementations disagree? Is it ever acceptable to be wrong 2% of the time?

*1.2 Read the errors.* Given five `ValidationError.errors()` outputs, explain what the model did wrong and the appropriate strategy (retry/reject/escalate). Hints: `literal_error` vs `missing` vs `extra_forbidden` vs `union_tag_invalid`.

**Level 2 — Implementation**

*2.1 Decision union.* Implement `AgentDecision` with `Answer`, `AskClarification`, `ProposeRefund`, `ProposeAddressChange`, `ProposeAccountDeletion`, `Escalate`, `Refuse`. Requirements: discriminator `kind`, `extra="forbid"`, `frozen=True`, no money fields. Tests: parameterized valid/invalid payloads; schema snapshot. Hints: Use `Annotated[Union[...], Field(discriminator="kind")]`; for addresses use a nested model with country `Literal` set.

*2.2 Resolver and invariants.* Implement `resolve_address_change` (carrier validation stub, order not yet shipped) and `resolve_account_deletion` (no open orders, no chargebacks). Expected: domain errors with stable codes. Hints: Define `DomainError(code: str)`; test each code.

*2.3 Retry policy.* Implement `StructuredDecider` with a fake client that returns scripted generations (valid, truncated, schema error, refusal). Tests assert attempt counts and fallbacks. Hints: Make the fake client record the messages it received to assert that error feedback excludes raw input.

**Level 3 — Integration**

*3.1 Policy engine swap.* Implement the refund policy in Python and in either Rego (run with `opa eval`) or Cedar (via `cedarpy`), and run the same 30 decision test cases against both. Hints: Normalize inputs to a JSON fact document first; the test table is the contract.

*3.2 End-to-end endpoint.* `POST /v1/agent/decide` returns proposals with status `auto_approved | pending_approval | rejected`. Use dependency overrides for the decider. Hints: Return proposal IDs, not model text, for actions.

**Level 4 — Debugging / Production Scenario**

*4.1 Diagnose this handler.*

```python
def handle(output: str):
    data = json.loads(output.replace("```json", "").replace("```", ""))
    if data.get("type") == "refund":
        amount = float(data.get("amount", 0))
        if amount < 100:
            payments.refund(data["order"], amount)
            return f"Refunded ${amount}"
    return data.get("text", "Done!")
```

Find at least seven problems (hint: money type, model-supplied amount, no tenant check, no schema, fail-open default message, no idempotency, no audit, claims success without verifying).

*4.2 Drift drill.* A teammate renamed `line_item_ids` to `items` in the Pydantic model but persisted proposals from yesterday use the old name. Design the migration and the compatibility strategy. Hints: `validation_alias=AliasChoices(...)` for reading; `schema_version`; never accept both names for *new* model outputs.

### 10. Independent Implementation Project — "Typed Decisions for SupportOps"

**Goal.** Replace free-form agent actions with a typed decision contract and a deterministic pipeline so that every action is validated, resolved, checked against invariants and authorized before execution.

**Functional requirements.**

1. Decision union: answer, clarify, propose refund (line items), propose address change, propose account deletion, escalate, refuse.
2. Resolver per proposal that loads facts from PostgreSQL and computes derived values (amounts, affected records).
3. Domain invariants with stable error codes.
4. Policy engine (Python plus one of OPA/Cedar) returning `allow | require_approval | deny` with reason and policy version.
5. Bounded retry/refusal strategy; escalation fallback.
6. Proposal records persisted with status and the raw (redacted) model output for audit.

**Technical requirements.** Pydantic v2 discriminated unions; SQLAlchemy 2.x async; FastAPI; pytest, Hypothesis; optional `opa` binary or `cedarpy`.

**Suggested structure.**

```
app/
├── agent/{decisions.py, structured.py, provider_adapter.py}
├── domain/{orders.py, refunds.py, accounts.py, errors.py}
├── policy/{python_policy.py, rego/refunds.rego, cedar/policies.cedar, facts.py}
├── services/proposals.py           orchestration: decision → resolve → invariant → policy → persist
├── repositories/{orders.py, proposals.py}
└── api/agent_routes.py
tests/
├── unit/{test_decisions.py, test_invariants.py, test_policy_table.py, test_structured_retry.py}
├── contract/{test_schema_snapshot.py, golden_outputs/*.json, test_golden_outputs.py}
├── property/test_parser_fuzz.py
└── integration/test_proposals_endpoint.py
```

**Milestones.** (1) contract + snapshot; (2) resolvers + invariants; (3) policy table tests; (4) structured decider with fake client; (5) endpoint + persistence; (6) golden outputs from a real model (redacted) + fuzzing.

**Testing requirements.** ≥40 parameterized decision payloads; policy table shared between engines; Hypothesis fuzz asserting "no exception other than ValidationError, no execution"; schema snapshot; golden output replay.

**Definition of Done.**

* [ ] No code path executes an action from anything but a validated, resolved, authorized command.
* [ ] Amounts and affected records are computed by code; the schema has no money fields.
* [ ] Unknown branches, extra fields and malformed JSON are rejected and counted.
* [ ] Policy decisions identical across Python and OPA/Cedar for the full table.
* [ ] Retry is bounded and only for syntax/schema failures; refusals are respected.

**Optional extensions.** Add `schema_version` and a migration for stored proposals; implement a callable discriminator for a legacy format; add a constrained-decoding provider adapter and compare schema-compliance rates with and without it.

### 11. Testing Strategy

* **Unit tests** on each decision model (valid/invalid matrices) and on each invariant.
* **Table-driven policy tests**: one YAML/CSV of `(principal, action, facts) → expected decision` run against every policy implementation.
* **Schema snapshot tests** to make contract changes explicit.
* **Golden output tests**: real (redacted) model outputs re-validated in CI.
* **Property-based fuzzing** of the parser and the pipeline.
* **Negative tests** for every rejection reason.
* **Retry behaviour tests** with a scripted fake client.
* **Eval metrics** (Unit 44): schema-compliance rate, correct-branch rate, invariant-violation rate per model/prompt version.

```python
# tests/contract/test_schema_snapshot.py
import json, pathlib
from pydantic import TypeAdapter
from app.agent.decisions import AgentDecision

SNAPSHOT = pathlib.Path(__file__).with_name("agent_decision.schema.json")

def test_decision_schema_unchanged():
    current = TypeAdapter(AgentDecision).json_schema()
    assert current == json.loads(SNAPSHOT.read_text()), (
        "AgentDecision schema changed. If intentional, regenerate the snapshot, bump "
        "schema_version, and update prompts/provider adapters + golden outputs."
    )
```

```python
# tests/property/test_parser_fuzz.py
import json
from hypothesis import given, strategies as st
from pydantic import ValidationError
from app.agent.decisions import DECISION

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(),
    lambda children: st.lists(children) | st.dictionaries(st.text(), children),
    max_leaves=20,
)

@given(st.dictionaries(st.sampled_from(["kind", "order_id", "line_item_ids", "reason",
                                        "text", "rationale", "amount"]), json_values))
def test_parser_never_crashes(payload):
    try:
        DECISION.validate_json(json.dumps(payload))
    except ValidationError:
        pass   # the only acceptable failure
```

### 12. Engineering Scenarios

**Scenario 1 — "Let the model compute the refund, it's good at math now."**
*Investigate:* rounding, tax, partial shipments, promotions, currency.
*Reasoning:* Even if accurate 99.9% of the time, money must be exact and explainable. Model chooses items/reason; code computes. The model can *explain* the computed amount to the customer.

**Scenario 2 — New provider lacks schema-constrained output.**
*Options:* tool-calling with a single tool whose schema is the union; JSON mode + validation + retry; keep the old provider for action-producing turns.
*Reasoning:* Measure schema-compliance and correct-branch rates on the eval set (Unit 44). Validation guarantees safety either way; the difference is cost/latency from retries.

**Scenario 3 — OPA vs in-process.**
A platform team wants every service to use OPA. Your agent makes ~20 decisions per request.
*Reasoning:* Use OPA embedded (Go SDK / WASM) or bundle-evaluated locally to avoid network hops; or keep Python policies with the *same test table* exported for audit. Key criteria: who changes policies, audit needs, latency, consistency across services.

**Scenario 4 (FDE) — "Make the bot handle returns."**
A retail customer asks for returns automation. Before designing the schema, clarify:
* Which return types (refund, exchange, store credit)? Which channels?
* What is the authoritative return policy (document vs ERP rules)? Are there regional differences?
* Which values can the model infer (intent, item, reason) and which must be looked up (eligibility, amount)?
* What does "done" mean (label generated? refund issued? ticket closed?) and what evidence will the customer accept?
*Expected reasoning:* The ambiguity is in the *business rules*, not the model. Encode them as invariants with the customer's ERP as source of truth; build the decision schema around the minimal model-provided fields; demo with a table of real past tickets showing typed decisions and deterministic outcomes.

### 13. Interview Preparation

#### Quick Questions

**Q: Why use structured output for agents?**
A: Turns model behaviour into typed, validated, testable objects; enables exhaustive handling, policy checks and audit; reduces parsing failures.
Trap: "So the output is correct" — structure ≠ correctness.

**Q: What is a discriminated union and why use it?**
A: A union tagged by a literal field; validation dispatches on the tag — deterministic, faster, clearer errors, and `match`-friendly.

**Q: Does constrained decoding remove the need for Pydantic validation?**
A: No — subset support, truncation, refusals, semantic rules, fallback models, defense in depth.

**Q: What's the difference between a validation error and a business-rule violation?**
A: Validation = the shape is wrong; business-rule violation = the shape is right but the action is not allowed by domain truth. Different handling, different metrics.

#### Intermediate Questions

**Q: How do you handle invalid model output?**
Strong answer: Classify (syntax, schema, semantic, invariant, authz, refusal). Retry syntax/schema with sanitized feedback up to a small cap; return semantic errors as tool errors; reject invariant violations; route authz to deny/approval; respect refusals; fall back to escalation. Log and measure each class.
Weak answer: "Retry until it works."

**Q: Which responsibilities belong to the model vs deterministic code?**
Strong answer: Model: intent, extraction, classification, drafting, choosing to clarify. Code: identity, permissions, money, eligibility, state transitions, idempotency, audit. The test: if being wrong 1% of the time is unacceptable or rules must be explainable/auditable, it's code.

**Q: How do you detect schema drift?**
A: Schema snapshot tests, golden outputs, contract tests per model, validation-failure metrics by model/prompt version, `schema_version` in persisted data.

#### Advanced Questions

**Q: How does constrained decoding work and what are its limits?**
A: Schema compiled to a grammar; at each step invalid tokens are masked from the logits. Limits: supported schema subset, can't express cross-field semantics, can distort model quality when schemas are awkward (the model is forced down unlikely paths), first-request schema compilation latency in some implementations, and no guarantee of correct *values*.

**Q: Design a policy layer for an agent that operates across 200 enterprise customers with different rules.**
A: Facts resolver → policy engine with per-tenant policy bundles (OPA bundles / Cedar policy stores), versioned and tested with tenant-specific tables; decision logs with policy version; defaults deny; tenant admins change thresholds via config validated against schema; changes go through CI policy tests.

#### Coding Questions

1. Write a discriminated union for three actions and a `match` that handles all branches exhaustively (bonus: `typing.assert_never`).
2. Write a bounded retry that only retries `ValidationError` and stops on refusal.
3. Given a `ProposeRefund`, write `resolve_refund` that computes the amount and enforces "not already refunded".

#### Scenario Questions

* "The model says 'I've cancelled your subscription' but nothing happened. Why, and how do you prevent it?"
* "Security asks you to prove the model can never set the refund amount. What do you show?" (Schema has no amount field + `extra="forbid"` test + resolver computes + audit samples.)

### 14. Explain-It-at-Three-Levels

**Structured output**

* *30 s:* We make the model fill a typed form — a discriminated union of possible decisions — and validate it with Pydantic before doing anything. That makes behaviour predictable and checkable.
* *2 min:* Add constrained decoding vs validation, refusal/truncation handling, bounded retry, and why the schema omits values code can compute.
* *Deep:* Token masking mechanics, provider schema subsets, pydantic-core validation path, error taxonomies and metrics, schema versioning and drift testing, interplay with tool calling.

**Deterministic boundaries**

* *30 s:* The model proposes; code decides. Invariants, permissions, money and state live in deterministic code.
* *2 min:* Pipeline: validate → resolve → invariants → policy → execute; distinct errors; same domain services as human UIs.
* *Deep:* Policy engines (Python/OPA/Cedar) with fact resolution, decision logs, versioned policies, multi-tenant bundles, state machines, idempotent execution, and evaluating the probabilistic parts separately.

### 15. Knowledge Check

**Conceptual**

1. Name four reasons to validate client-side even with schema-constrained decoding.
2. Why does `ProposeRefund` deliberately omit an amount?
3. What does `extra="forbid"` change, and why does it matter for security monitoring?
4. When is deterministic "repair" of model output acceptable?
5. What must be true of the inputs to a policy engine?

**Code reading**

6. What does this produce for `{"kind":"answer"}` and why?
   ```python
   class Answer(BaseModel):
       kind: Literal["answer"] = "answer"
       text: str
   ```
7. Why is `kind: str = "answer"` in each union member a problem?
8. In `StructuredDecider`, why is a refusal not retried?

**Debugging**

9. Validation failures are 0% but customers report "refunds promised but not issued". Diagnose.
10. After a schema change, all persisted proposals fail to load. What went wrong and how do you fix it?

**Design**

11. When would you choose Cedar over in-process Python policy?
12. Your decision union has 35 action types and the model often chooses wrong. What do you do?

#### Knowledge Check Answers

1. Provider schema-subset limits; truncation; refusals; semantic/cross-field rules; fallback models/gateways without constraints; defense in depth.
2. Money is computed by code from authoritative records; removing it eliminates hallucinated or injected amounts and makes the invariant enforceable.
3. Unknown fields raise errors instead of being silently dropped; attempted extra fields (e.g. `amount`, `approved: true`) become visible signals of injection or drift.
4. Only for meaning-preserving syntax fixes (code fences, whitespace). Never to guess or clamp values.
5. They must be resolved facts from authoritative sources (DB, IdP), not model assertions, and be complete enough for a default-deny evaluation.
6. `ValidationError` — `text` is missing (`missing` at `('text',)`); the defaulted `kind` doesn't make `text` optional.
7. Without `Literal`, Pydantic cannot use the field as a discriminator; plain unions fall back to smart mode with ambiguous matching.
8. A refusal is a deliberate safety outcome; retrying is an attempt to bypass it, wastes tokens and risks policy violations.
9. The model used `Answer` to *claim* actions. Fix by generating action confirmations only from executed outcomes; add forbidden-behaviour evals and an output check for completion claims.
10. Breaking schema change without versioning/migration. Add `schema_version`, read old payloads with aliases or a migration, keep strict validation for new model outputs.
11. When you need human-readable, analyzable authorization policies, typed schemas, policy stores managed outside code, or formal analysis — especially across many tenants/services.
12. Split into stages or sub-agents (route first: category → specific action), narrow by context (only show actions relevant to the current state), improve descriptions, and measure branch accuracy per action in evals.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "Structured output means the answer is right." | It means the *shape* is right. Truth and permission are separate checks. |
| "Constrained decoding = no validation needed." | Validation remains the contract; constrained decoding just lowers failure rates. |
| "Just retry until valid." | Bounded retries for syntax/schema only; others are terminal or escalate. |
| "Let the model calculate totals and check eligibility." | Money and eligibility are invariants → code. |
| "The model's rationale proves it checked the rule." | Rationales are not evidence; enforce rules in code. |
| "`extra='ignore'` is more robust." | For actions it hides attacks and drift; use `forbid`. |
| "Policy engine input can include the model's claims like `user_is_manager: true`." | Only resolved facts from authoritative sources. |

### 17. Cheat Sheet

```python
model_config = ConfigDict(extra="forbid", frozen=True)
kind: Literal["propose_refund"] = "propose_refund"
AgentDecision = Annotated[Union[A, B, C], Field(discriminator="kind")]
adapter = TypeAdapter(AgentDecision); adapter.validate_json(raw); adapter.json_schema()
exc.errors(include_input=False, include_url=False, include_context=False)
Field(strict=True)        # per-field strictness
AliasChoices("new", "old")  # reading legacy payloads only
```

* **Pipeline:** parse/validate → resolve facts → invariants → policy → approval → execute → audit.
* **Errors:** syntax (retry, more tokens) · schema (retry w/ feedback ≤2) · semantic (tool error) · invariant (reject) · authz (deny/approval) · refusal (respect) · repeated (escalate).
* **Model owns:** intent, extraction, classification, drafting, clarifying. **Code owns:** identity, permissions, money, eligibility, state, idempotency, audit.
* **Structured output modes:** prompt-only (legacy) < JSON mode < schema-constrained/strict tools (current). Always validate anyway.
* **Policy engines:** Python (simple), OPA/Rego v1 syntax (`if`, `contains`), Cedar (permit/forbid, typed). Inputs = facts. Default deny. Log policy version.
* **Drift defenses:** schema snapshot, golden outputs, `schema_version`, contract tests per model, failure-rate metrics.

### 18. Completion Checklist

* [ ] I can design a discriminated-union decision schema with `extra="forbid"` and no computable values.
* [ ] I can explain constrained decoding and list why client-side validation is still required.
* [ ] I can implement a bounded retry/refusal/fallback strategy and justify each branch.
* [ ] I can separate model judgment from invariants and implement invariants in the domain layer.
* [ ] I can implement a policy in Python and in OPA or Cedar with a shared test table.
* [ ] I can write schema snapshot, golden-output and fuzz tests.
* [ ] I can debug drift from validation-error telemetry.
* [ ] I can identify when an action should not be model-initiated at all.

### 19. Further Research

**Essential**

* Pydantic — Unions & discriminated unions: <https://docs.pydantic.dev/latest/concepts/unions/> — tag dispatch, callable discriminators, error shapes.
* Pydantic — Strict mode and conversion table: <https://docs.pydantic.dev/latest/concepts/strict_mode/> and <https://docs.pydantic.dev/latest/concepts/conversion_table/> — exactly what coerces in JSON vs Python mode.
* Pydantic — JSON Schema: <https://docs.pydantic.dev/latest/concepts/json_schema/> — how your models become the schema the model sees.
* Anthropic — Structured outputs: <https://platform.claude.com/docs/en/build-with-claude/structured-outputs> — JSON outputs and strict tool use, supported schema features, model availability.
* OpenAI — Structured Outputs: <https://platform.openai.com/docs/guides/structured-outputs> — `strict` mode, supported JSON Schema subset, refusals.

**Deeper Study**

* Open Policy Agent docs and Rego v1: <https://www.openpolicyagent.org/docs/> — policy-as-code, decision logs, bundles.
* Cedar policy language: <https://docs.cedarpolicy.com/> — permit/forbid semantics, schemas, validation and analysis.
* Willard & Louf, "Efficient Guided Generation for Large Language Models" (2023): <https://arxiv.org/abs/2307.09702> — the finite-state approach behind constrained decoding (Outlines).
* JSON Schema 2020-12 specification: <https://json-schema.org/specification> — `oneOf`, `const`, `$defs`.

**Practice**

* Instructor library: <https://python.useinstructor.com/> — study its retry/validation patterns, then compare with your own bounded design.
* Hypothesis documentation: <https://hypothesis.readthedocs.io/> — property-based testing of parsers.
* OPA Playground: <https://play.openpolicyagent.org/> — write and test the refund policy interactively.

### Unit Completion Standard

Before moving on, you must be able to: **explain** why structure is necessary but not sufficient and how constrained decoding works; **implement** a discriminated-union decision contract whose actions flow through validate → resolve → invariants → policy → execute, with money and eligibility computed in code; **test** it with parameterized, snapshot, golden-output and property-based tests that prove malformed, unknown and unauthorized actions never execute; **debug** drift and wrong-branch failures from validation telemetry; and **defend** in an interview a clear allocation of probabilistic versus deterministic responsibilities.
