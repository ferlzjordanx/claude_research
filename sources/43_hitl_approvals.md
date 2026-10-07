## Unit 43 — Human-in-the-Loop and Approval Workflows

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Classify** agent actions by risk (impact, reversibility, blast radius, external exposure, data sensitivity, confidence/provenance) and **design** an approval policy that maps risk to controls.
2. **Explain** the difference between confirmation, single approval, multi-party approval and post-hoc review, and **choose** among them.
3. **Design** interrupt/resume workflows that survive process restarts, using a persisted state machine (and **compare** with LangGraph interrupts and durable-execution engines such as Temporal).
4. **Implement** approval gates for email sending, data modification, refund-like financial actions and deletion with FastAPI, Pydantic v2 and SQLAlchemy 2.x.
5. **Implement** payload binding, atomic decisions, segregation of duties, expiry and exactly-once execution.
6. **Persist** proposal, approver, decision, execution result and audit events, and **reconstruct** what happened from them.
7. **Design** reviewer context and UX that support good decisions and resist approval fatigue and manipulation.
8. **Test** concurrency, expiry, rejection, tampering and resume behaviour.

### 2. Prerequisite Knowledge

* Units 41–42: risk classes, `REQUIRE_APPROVAL` outcome, typed proposals, invariants, policy decisions.
* **Database transactions and isolation**: atomic `UPDATE … WHERE` (compare-and-set), unique constraints, row locks (`SELECT … FOR UPDATE`), optimistic concurrency with a `version` column.
* **Idempotency**: an operation that can be safely repeated with the same effect; idempotency keys at downstream APIs.
* **Async background work**: workers, schedulers, outbox pattern (write an event in the same transaction as the state change; a relay publishes it).
* **FastAPI lifespan, dependencies, `TestClient`/`httpx`.**

### 3. Mental Model

Treat an approval like a **cheque that needs a second signature**:

* The cheque (proposal) is written out *in full* — payee, amount, memo — before anyone signs.
* The signer sees exactly that cheque, not a summary of it.
* The signature applies to that cheque only; altering the amount voids it.
* Unsigned cheques expire.
* The bank cashes a cheque once, even if it is presented twice.
* Every step is in the ledger.

In system terms:

```
 Agent loop                  Approval service (durable)                    Humans
 ──────────                  ──────────────────────────                    ──────
 decision: ProposeRefund ─>  validate → resolve → policy = REQUIRE_APPROVAL
                             persist Proposal(status=pending, payload, hash,
                                              reviewer_context, expires_at)
 agent pauses  <──────────── returns proposal_id ("waiting for approval")
 (state checkpointed)                         │ notify ─────────────────────> reviewer queue / Slack
                                              │                              reviewer opens proposal
                                              │ <── decision(approve|reject, comment, payload_hash)
                             atomic CAS pending→approved|rejected (if not expired)
                             approved → executor re-validates → execute once
                             persist Execution + AuditEvents
 agent resumes <──────────── event: proposal decided/executed/expired
 tells user the real outcome
```

The agent is **not** the thing waiting. A process holding an `await` for four hours is not a workflow; a database row in state `pending` is.

### 4. Comprehensive Theory

#### 4.1 Where Humans Belong

**Definition.** Human-in-the-loop (HITL) places a human decision *inside* the execution path (the action can't happen without it). Human-*on*-the-loop means humans monitor and can intervene, but actions proceed automatically. Human-*out*-of-the-loop means full automation with after-the-fact review.

**Why it exists.** Some actions are high-impact, irreversible or legally accountable; some decisions need context the system doesn't have; regulation sometimes requires it (e.g., the EU AI Act's human-oversight obligations for high-risk systems; GDPR Article 22 limits on solely automated decisions with legal or similarly significant effects). Approval also cuts the "excessive autonomy" root cause of excessive agency (Unit 41).

**Where humans add value — and where they don't.**

| Humans add value | Humans add little (automate or block instead) |
|---|---|
| Irreversible or high-value actions | High-volume, low-risk, reversible actions (approval fatigue) |
| Judgment calls with incomplete data (goodwill credits, exceptions) | Rules that can be checked deterministically (do it in code) |
| External communication with legal/reputational impact | Actions that are always wrong (deny in policy, don't ask) |
| Novel situations / low model confidence / untrusted context | Time-critical actions where delay causes more harm |

A human is not a substitute for a deterministic check. If the reviewer would apply a rule mechanically, encode the rule.

#### 4.2 Risk Classification and Approval Policies

**Risk dimensions:**

| Dimension | Question | Example scoring |
|---|---|---|
| Impact | How bad if wrong? | $ amount, # records, legal exposure |
| Reversibility | Can it be undone, and at what cost? | address change (easy) vs deletion (impossible) vs sent email (impossible) |
| Blast radius | How many entities affected? | one customer vs bulk |
| Exposure | Does it leave the trust boundary? | internal note vs customer email vs public post |
| Sensitivity | Does it touch PII/financial/health data? | |
| Provenance | Did untrusted content influence the proposal? | taint flag from Unit 41 |
| Principal | Does it exceed the requester's own authority? | role limits |

**Policy mapping (SupportOps):**

| Action | Condition | Risk | Control | Approver | TTL |
|---|---|---|---|---|---|
| `send_email` | to order's customer, template-based, no untrusted influence | Low | Auto, log | — | — |
| `send_email` | free-form body, or after untrusted content | Medium | Single approval | supervisor | 24 h |
| `update_record` | shipping address before shipment | Low/Medium | Requester confirmation | requester | 15 min |
| `update_record` | email/phone change (account takeover vector) | High | Single approval + verification | supervisor | 4 h |
| `issue_refund` | ≤ role limit, clean context | Low | Auto, log | — | — |
| `issue_refund` | > role limit or tainted | High | Single approval | supervisor | 4 h |
| `issue_refund` | > $1,000 | Critical | Two-person approval | 2 × manager | 1 h |
| `delete_account` | any | Critical | Two-person + delayed execution (cool-off) | manager + privacy officer | 1 h to approve; execute after 24 h unless cancelled |

**Approval types:**

* **Confirmation** — the requester confirms an action they asked for ("Send this email?"). Guards against model misunderstanding, *not* against a malicious or compromised requester.
* **Single approval** — an independent, qualified person approves. Enforce **segregation of duties**: requester ≠ approver.
* **Multi-party (four-eyes / N-of-M)** — two or more distinct approvers; often with role requirements.
* **Delayed execution / cool-off** — approved irreversible actions wait before executing and can be cancelled.
* **Post-hoc review** — sample-based audit for auto-approved actions; feeds evals (Unit 44).

**Design considerations.** Express the policy as data (table/config) evaluated by code, version it, and record the policy version on each proposal. Thresholds should come from the business (FDE: ask who owns them).

#### 4.3 Interrupt/Resume Workflow Design

**Definition.** An *interrupt* suspends an agent or workflow at a well-defined point, persists everything needed to continue, and releases compute. *Resume* continues from that point with new input (the human decision).

**Why it exists.** Approvals take minutes to days; processes restart, deploy and scale. Holding an in-memory coroutine is fragile and wasteful.

**Three implementation styles:**

| Style | How | Pros | Cons |
|---|---|---|---|
| **Persisted state machine (DB rows + events)** | Proposal rows with status; agent session state stored; decision endpoint triggers execution and emits an event; agent resumes by loading session state | Simple, transparent, works with any stack; easy to audit | You write the state handling and retries yourself |
| **Agent framework interrupts** (e.g. LangGraph) | `interrupt(payload)` inside a node pauses the graph; a checkpointer persists state per `thread_id`; resume with `Command(resume=value)` which becomes the return value of `interrupt()` | Native to the agent graph; supports editing state | **The interrupted node re-runs from its start on resume**, so side effects before `interrupt()` repeat; requires a durable checkpointer (not in-memory) in production; approval semantics (who may resume) are *your* job |
| **Durable execution engine** (Temporal, AWS Step Functions, Azure Durable Functions) | Workflow code waits for a *signal* / task token; engine persists history and replays | Robust timers, retries, timeouts, long waits; great for multi-step side effects | Operational dependency; determinism constraints on workflow code; learning curve |

**Critical properties regardless of style:**

1. **Idempotent resume** — resuming twice must not execute twice.
2. **Authorization on resume** — the resume endpoint authenticates the approver and checks role, tenant and segregation of duties. A framework's `Command(resume=...)` does not know who is allowed to send it.
3. **Re-validation at execution time** — state may have changed since the proposal (order already refunded by someone else, customer closed account). Re-check invariants and policy immediately before executing (*time-of-check vs time-of-use*).
4. **Bound resumes to the exact proposal** — hash of canonical payload displayed to the approver and submitted with the decision.
5. **Resume the conversation honestly** — the agent tells the user the *actual* outcome (approved and executed / rejected with reason / expired), generated from records rather than model imagination.

**LangGraph sketch (Illustrative; check current docs for API changes):**

```python
from langgraph.types import interrupt, Command

def request_refund_approval(state):
    # Anything above this line runs again on resume — keep it side-effect free.
    decision = interrupt({"proposal_id": state["proposal_id"], "summary": state["summary"]})
    return {"approval": decision}

# graph compiled with a durable checkpointer (e.g. PostgreSQL), invoked with
# config={"configurable": {"thread_id": session_id}}
# Later, from your *authorized* decision endpoint:
# graph.invoke(Command(resume={"approved": True, "approver": "sam"}), config=...)
```

Even when using a framework, keep the **proposal/approval/execution records in your own tables**: they are the system of record for audit, not the framework's checkpoint blobs.

#### 4.4 Persisting Proposal, Approver, Decision and Execution Result

**Data model:**

```
proposals             one row per proposed side effect
  id, tenant_id, requested_by, agent_session_id, action_type,
  payload_json (canonical), payload_sha256, risk, policy_reason, policy_version,
  reviewer_context_json (snapshot), status, version, created_at, expires_at

approval_decisions    one row per human decision (N rows for multi-party)
  id, proposal_id, approver_id, decision, comment, payload_sha256 (what they saw), decided_at

executions            at most one row per proposal (UNIQUE(proposal_id))
  id, proposal_id, status, result_json, idempotency_key, executed_at

audit_events          append-only timeline
  id, proposal_id, event, actor, at, details_json, trace_id
```

**Status state machine:**

```
                 ┌─────────── reject ───────────> rejected (terminal)
 pending ────────┼─────────── approve ──────────> approved ──execute──> executed (terminal)
   │             │                                   │
   │             └── (N-of-M: approve until quorum)  └──execute fails──> failed (terminal; may create new proposal)
   └── expires_at passes ──────────────────────────> expired (terminal)
 pending ── requester cancels ─────────────────────> cancelled (terminal)
```

**Concurrency control.** Two reviewers clicking "Approve" simultaneously, or "Approve" racing with expiry, must result in exactly one outcome. Use an atomic conditional update:

```sql
UPDATE proposals
   SET status = 'approved', version = version + 1
 WHERE id = :id AND status = 'pending' AND version = :seen_version AND expires_at > now();
-- rowcount = 1 → you won; 0 → someone else decided or it expired
```

and a `UNIQUE(proposal_id)` constraint on `executions` so that a duplicated executor run cannot create a second effect. Downstream APIs (payments, email) also receive an **idempotency key** derived from the proposal ID.

**Indexes.** `(tenant_id, status, expires_at)` for the reviewer queue; `(status, expires_at)` for the expiry sweeper; `(proposal_id)` on decisions/events.

**Audit-log integrity.** Append-only via database grants (application role has `INSERT` but not `UPDATE/DELETE` on `audit_events`); optional hash chaining (`prev_hash`) or export to WORM storage for regulated contexts; include `trace_id` to link to telemetry (Unit 45).

#### 4.5 Audit Trails and Reviewer Context

**What the reviewer must see:**

| Element | Why |
|---|---|
| **Exact action and parameters** (rendered from the payload, not from model prose) | Prevents "approve the summary, execute something else" |
| **Diff** for modifications (before → after) | Makes the change concrete |
| **Computed values** (amount from code, affected record count) | The reviewer checks business sense |
| **Evidence** (order, previous refunds, customer history, source documents with links) | Grounds the decision |
| **Why approval is required** (policy reason) | Focuses attention |
| **Provenance warnings** ("this proposal followed untrusted content from ticket #4471") | Highlights injection risk |
| **Model rationale — labelled as AI-generated** | Helpful context, not evidence |
| **Expiry time** | Urgency |

**What the reviewer must not see** (or see masked): secrets, unnecessary PII, raw untrusted HTML (render as escaped text — the approval UI itself is an injection target; ASI09 *Human-Agent Trust Exploitation* covers agents manipulating humans into approving).

**Audit questions you must be able to answer from records:** Who asked? What did the agent propose and why (policy reason)? What did the reviewer see (payload hash, context snapshot)? Who decided, when, and why (comment)? What executed, with what result? Under which policy version and model/prompt version (Unit 45 provenance)?

#### 4.6 Timeout, Expiration and Rejected Actions

* **Expiration is fail-closed:** an expired proposal is never executed. Approvals have a TTL proportional to risk and to how fast the underlying facts go stale.
* **Enforce expiry in the decision transaction** (`expires_at > now()` in the CAS), *and* sweep periodically to mark rows expired and notify. Don't rely on the sweeper alone (race).
* **SLA escalation:** if no decision by 50% of TTL, notify a backup approver; if a queue routinely expires, the policy or staffing is wrong.
* **Rejected actions:** require a reason; return it to the agent so it can tell the user truthfully and avoid re-proposing the same action in a loop (rate-limit re-proposals of an identical payload hash). Rejections are labelled data for evals.
* **Timeouts inside execution:** if the payment API times out *after* approval, the outcome is *unknown* — don't blindly retry without an idempotency key; reconcile by querying the downstream system.
* **User experience:** the requester sees "Waiting for approval (expires 15:30)", can cancel, and is notified of the outcome. The agent conversation should not block the UI.

#### 4.7 UX Considerations and Approval Fatigue

* **Volume is the enemy.** If reviewers see hundreds of approvals a day with a 99% approval rate, they will rubber-stamp. Push low-risk actions to auto + sampling; raise thresholds based on data.
* **No "approve all"** for high-risk items; batch approvals only for homogeneous, low-risk items with a shown aggregate (total $).
* **Make rejection as easy as approval**, with reason codes.
* **Show changes since proposal** (stale data warnings).
* **Measure**: time-to-decision, approval rate by reviewer, override reversals, expired rate, post-approval incident rate. A reviewer approving in 2 seconds on average is a signal.

### 5. Internal Mechanics

#### 5.1 End-to-end sequence for a high-risk refund

```
1  POST /v1/agent/chat ─> agent decides ProposeRefund (Unit 42)
2  resolve → amount = 120.00 (code) → policy: REQUIRE_APPROVAL ("> limit 50")
3  BEGIN; INSERT proposals(status=pending, payload_sha256=H, expires_at=now+4h);
         INSERT audit_events('proposed'); INSERT outbox('proposal.created'); COMMIT
4  agent session state saved {awaiting: proposal_id}; user told "awaiting approval"
5  outbox relay → notification service → reviewer queue
6  reviewer GET /approvals → sees payload rendered from payload_json + context snapshot + H
7  POST /approvals/{id}/decision {approve, comment, H}
      authN reviewer → tenant check → role check → requester≠approver → H matches
      BEGIN; UPDATE … WHERE status='pending' AND version=v AND expires_at>now → 1 row
             INSERT approval_decisions; INSERT audit_events('approved'); COMMIT
8  executor: reload proposal, verify hash, re-check invariants (not already refunded),
      call payments with Idempotency-Key = proposal_id
      BEGIN; INSERT executions (UNIQUE proposal_id); UPDATE status=executed;
             INSERT audit_events('executed'); INSERT outbox('proposal.executed'); COMMIT
9  outbox → agent resume: session loads outcome from DB → tells user "Refund of $120.00 issued (rf_…)"
```

#### 5.2 Why the hash matters

Without binding, this race exists: reviewer opens proposal (amount 120); the agent (or an attacker with API access) updates the proposal to 1,200; reviewer clicks approve; the system approves "proposal 42" — now 1,200. Binding the decision to `sha256(canonical_payload)` makes the approval apply only to what was displayed. Canonicalization (sorted keys, fixed separators, normalized number strings) ensures the same logical payload always hashes identically.

#### 5.3 Exactly-once is "at-least-once + idempotency"

Networks and processes fail between "execute" and "record". True exactly-once delivery is not achievable end to end; you achieve *effectively-once* effects by combining at-least-once attempts with idempotency keys at the downstream system and uniqueness constraints in your own DB, plus reconciliation for unknown outcomes.

### 6. Implementation Examples

#### Example 1 — Minimal: an approval state machine (Runnable)

```python
# ex43_1.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import StrEnum

class Status(StrEnum):
    PENDING = "pending"; APPROVED = "approved"; REJECTED = "rejected"
    EXPIRED = "expired"; EXECUTED = "executed"

ALLOWED = {
    Status.PENDING: {Status.APPROVED, Status.REJECTED, Status.EXPIRED},
    Status.APPROVED: {Status.EXECUTED},
}

class IllegalTransition(Exception):
    pass

@dataclass
class Proposal:
    action: str
    requested_by: str
    expires_at: datetime
    status: Status = Status.PENDING
    history: list[tuple[Status, str]] = field(default_factory=list)

    def transition(self, to: Status, actor: str, now: datetime) -> None:
        if self.status is Status.PENDING and now >= self.expires_at and to is not Status.EXPIRED:
            self._move(Status.EXPIRED, "system")
            raise IllegalTransition("expired")
        if to not in ALLOWED.get(self.status, set()):
            raise IllegalTransition(f"{self.status} → {to}")
        if to is Status.APPROVED and actor == self.requested_by:
            raise IllegalTransition("requester cannot approve")
        self._move(to, actor)

    def _move(self, to: Status, actor: str) -> None:
        self.history.append((to, actor))
        self.status = to

now = datetime.now(UTC)
p = Proposal("delete_account:cus_42", requested_by="alice", expires_at=now + timedelta(hours=1))
for to, actor in [(Status.APPROVED, "alice"), (Status.APPROVED, "sam"),
                  (Status.APPROVED, "sam"), (Status.EXECUTED, "system")]:
    try:
        p.transition(to, actor, now)
        print("ok  ", to, "by", actor)
    except IllegalTransition as e:
        print("deny", to, "by", actor, "-", e)
print(p.history)
```

```
deny approved by alice - requester cannot approve
ok   approved by sam
deny approved by sam - approved → approved
ok   executed by system
[(<Status.APPROVED: 'approved'>, 'sam'), (<Status.EXECUTED: 'executed'>, 'system')]
```

#### Example 2 — Realistic: classifying risk and routing actions

```python
# app/approvals/policy.py  (Illustrative; plugs into the Unit 41/42 policy layer)
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

class Risk(StrEnum):
    LOW = "low"; MEDIUM = "medium"; HIGH = "high"; CRITICAL = "critical"

@dataclass(frozen=True)
class Requirement:
    risk: Risk
    approvals_required: int        # 0 = auto
    approver_roles: frozenset[str]
    ttl_minutes: int
    cool_off_minutes: int = 0
    policy_version: str = "2026-10-01"

def classify(action: str, *, amount: Decimal | None = None, role_limit: Decimal | None = None,
             tainted: bool = False, free_form: bool = False, field: str | None = None) -> Requirement:
    match action:
        case "send_email" if not (tainted or free_form):
            return Requirement(Risk.LOW, 0, frozenset(), 0)
        case "send_email":
            return Requirement(Risk.MEDIUM, 1, frozenset({"supervisor"}), 24 * 60)
        case "update_record" if field in {"email", "phone"}:
            return Requirement(Risk.HIGH, 1, frozenset({"supervisor"}), 4 * 60)
        case "update_record":
            return Requirement(Risk.LOW, 0, frozenset(), 0)
        case "issue_refund" if amount is not None and amount > Decimal("1000"):
            return Requirement(Risk.CRITICAL, 2, frozenset({"manager"}), 60)
        case "issue_refund" if amount is not None and role_limit is not None \
                and amount <= role_limit and not tainted:
            return Requirement(Risk.LOW, 0, frozenset(), 0)
        case "issue_refund":
            return Requirement(Risk.HIGH, 1, frozenset({"supervisor", "manager"}), 4 * 60)
        case "delete_account":
            return Requirement(Risk.CRITICAL, 2, frozenset({"manager", "privacy_officer"}),
                               60, cool_off_minutes=24 * 60)
        case _:
            # Unknown action: the strictest requirement, never auto.
            return Requirement(Risk.CRITICAL, 2, frozenset({"manager"}), 60)
```

The default branch is the strictest requirement — the approval-policy equivalent of fail-closed.

#### Example 3 — Production-oriented: persisted approvals service (Runnable)

**Architecture.** One FastAPI module with SQLAlchemy 2.x async models for proposals, decisions, executions and audit events; endpoints to create proposals (called by the agent orchestrator), list a reviewer queue, and decide; an executor registry that runs approved actions exactly once; and an expiry sweeper. It uses SQLite via `aiosqlite` so you can run it anywhere; the comments note the PostgreSQL differences.

Install and run the tests:

```bash
pip install "fastapi>=0.115" "sqlalchemy[asyncio]>=2.0" aiosqlite httpx pytest
pytest -q test_approvals.py
```

Note: SQLAlchemy's asyncio extension requires the `greenlet` package; install the `sqlalchemy[asyncio]` extra rather than plain `sqlalchemy` (recent releases no longer pull `greenlet` in on all platforms).

```python
# approvals_app.py — persisted proposals, approvals, expiry, execution and audit.
# Demo uses SQLite (aiosqlite). On PostgreSQL use TIMESTAMPTZ and timezone-aware datetimes.
from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)   # naive UTC for the SQLite demo only


# ----------------------------------------------------------------------------- persistence
class Base(DeclarativeBase):
    pass


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class Proposal(Base):
    __tablename__ = "proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str] = mapped_column(String(64))        # human on whose behalf
    agent_session_id: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[str] = mapped_column(Text)
    payload_sha256: Mapped[str] = mapped_column(String(64))
    risk: Mapped[str] = mapped_column(String(16))
    policy_reason: Mapped[str] = mapped_column(String(200))
    reviewer_context_json: Mapped[str] = mapped_column(Text)     # snapshot shown to reviewer
    status: Mapped[str] = mapped_column(String(16), index=True, default=ProposalStatus.PENDING)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)


class ApprovalDecisionRow(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"), index=True)
    approver_id: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(String(1000))
    payload_sha256: Mapped[str] = mapped_column(String(64))       # what the approver saw
    decided_at: Mapped[datetime]


class Execution(Base):
    __tablename__ = "executions"
    __table_args__ = (UniqueConstraint("proposal_id"),)            # at most one execution
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("proposals.id"))
    status: Mapped[str] = mapped_column(String(16))
    result_json: Mapped[str] = mapped_column(Text)
    executed_at: Mapped[datetime]


class AuditEvent(Base):
    __tablename__ = "audit_events"                                # append-only by convention + grants
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    proposal_id: Mapped[str] = mapped_column(String(36), index=True)
    event: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64))
    at: Mapped[datetime]
    details_json: Mapped[str] = mapped_column(Text)


# ----------------------------------------------------------------------------- domain
class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


APPROVAL_TTL = {Risk.MEDIUM: timedelta(hours=24), Risk.HIGH: timedelta(hours=4),
                Risk.CRITICAL: timedelta(hours=1)}
APPROVER_ROLES = {Risk.MEDIUM: {"supervisor", "manager"}, Risk.HIGH: {"supervisor", "manager"},
                  Risk.CRITICAL: {"manager"}}


def canonical_sha256(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str


# Executors re-validate against *current* state at execution time (TOCTOU defense).
Executor = Callable[[Principal, dict[str, Any]], Awaitable[dict[str, Any]]]
EXECUTORS: dict[str, Executor] = {}


def executor(action_type: str):
    def register(fn: Executor) -> Executor:
        EXECUTORS[action_type] = fn
        return fn
    return register


SENT_EMAILS: list[dict[str, Any]] = []      # fake side-effect sinks for the demo
REFUNDS: list[dict[str, Any]] = []


@executor("send_email")
async def exec_send_email(p: Principal, payload: dict[str, Any]) -> dict[str, Any]:
    SENT_EMAILS.append(payload)
    return {"message_id": f"msg_{len(SENT_EMAILS)}"}


@executor("issue_refund")
async def exec_refund(p: Principal, payload: dict[str, Any]) -> dict[str, Any]:
    REFUNDS.append(payload)
    return {"refund_id": f"rf_{len(REFUNDS)}"}


# ----------------------------------------------------------------------------- API schemas
class CreateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_session_id: str
    action_type: Literal["send_email", "update_record", "issue_refund", "delete_account"]
    payload: dict[str, Any]
    risk: Risk
    policy_reason: str = Field(max_length=200)
    reviewer_context: dict[str, Any]       # evidence, diff, model rationale (labelled as such)


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    comment: str = Field(min_length=1, max_length=1000)
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")   # binds decision to what was shown


class ProposalOut(BaseModel):
    id: str
    action_type: str
    status: str
    risk: str
    payload: dict[str, Any]
    payload_sha256: str
    policy_reason: str
    reviewer_context: dict[str, Any]
    requested_by: str
    expires_at: datetime


def to_out(p: Proposal) -> ProposalOut:
    return ProposalOut(id=p.id, action_type=p.action_type, status=p.status, risk=p.risk,
                       payload=json.loads(p.payload_json), payload_sha256=p.payload_sha256,
                       policy_reason=p.policy_reason,
                       reviewer_context=json.loads(p.reviewer_context_json),
                       requested_by=p.requested_by, expires_at=p.expires_at)


# ----------------------------------------------------------------------------- wiring
# StaticPool: one shared connection so the in-memory SQLite DB is visible to every session.
engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="SupportOps approvals", lifespan=lifespan)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_principal(x_user: Annotated[str, Header()], x_tenant: Annotated[str, Header()],
                        x_role: Annotated[str, Header()]) -> Principal:
    # Demo only. In production: validated JWT → Principal (Unit 41).
    return Principal(x_user, x_tenant, x_role)


DB = Annotated[AsyncSession, Depends(get_session)]
Me = Annotated[Principal, Depends(get_principal)]


async def audit(s: AsyncSession, proposal_id: str, event: str, actor: str, **details: Any) -> None:
    s.add(AuditEvent(proposal_id=proposal_id, event=event, actor=actor, at=utcnow(),
                     details_json=json.dumps(details, default=str)))


# ----------------------------------------------------------------------------- routes
@app.post("/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposal(body: CreateProposal, me: Me, s: DB) -> ProposalOut:
    if body.risk is Risk.LOW:
        raise HTTPException(422, "low-risk actions do not need approval")
    now = utcnow()
    p = Proposal(id=str(uuid4()), tenant_id=me.tenant_id, requested_by=me.user_id,
                 agent_session_id=body.agent_session_id, action_type=body.action_type,
                 payload_json=json.dumps(body.payload, sort_keys=True),
                 payload_sha256=canonical_sha256(body.payload), risk=body.risk,
                 policy_reason=body.policy_reason,
                 reviewer_context_json=json.dumps(body.reviewer_context),
                 status=ProposalStatus.PENDING, version=1, created_at=now,
                 expires_at=now + APPROVAL_TTL[body.risk])
    s.add(p)
    await audit(s, p.id, "proposed", me.user_id, risk=body.risk, reason=body.policy_reason)
    await s.commit()
    return to_out(p)


@app.get("/approvals")
async def list_pending(me: Me, s: DB) -> list[ProposalOut]:
    rows = await s.scalars(
        select(Proposal)
        .where(Proposal.tenant_id == me.tenant_id, Proposal.status == ProposalStatus.PENDING,
               Proposal.expires_at > utcnow())
        .order_by(Proposal.expires_at))
    return [to_out(p) for p in rows if me.role in APPROVER_ROLES[Risk(p.risk)]]


@app.post("/approvals/{proposal_id}/decision")
async def decide(proposal_id: str, body: DecisionIn, me: Me, s: DB) -> dict[str, Any]:
    p = await s.get(Proposal, proposal_id)
    if p is None or p.tenant_id != me.tenant_id:
        raise HTTPException(404, "not found")
    if me.role not in APPROVER_ROLES[Risk(p.risk)]:
        raise HTTPException(403, "role cannot approve this risk level")
    if me.user_id == p.requested_by:
        raise HTTPException(403, "requester cannot approve their own action")
    if body.payload_sha256 != p.payload_sha256:
        raise HTTPException(409, "proposal changed since it was displayed")

    now = utcnow()
    new_status = ProposalStatus.APPROVED if body.decision == "approve" else ProposalStatus.REJECTED
    # Atomic compare-and-set: only one decision can win, and only before expiry.
    result = await s.execute(
        update(Proposal)
        .where(Proposal.id == p.id, Proposal.status == ProposalStatus.PENDING,
               Proposal.version == p.version, Proposal.expires_at > now)
        .values(status=new_status, version=Proposal.version + 1))
    if result.rowcount != 1:
        await s.rollback()
        raise HTTPException(409, "proposal is no longer pending (decided or expired)")
    s.add(ApprovalDecisionRow(id=str(uuid4()), proposal_id=p.id, approver_id=me.user_id,
                              decision=body.decision, comment=body.comment,
                              payload_sha256=body.payload_sha256, decided_at=now))
    await audit(s, p.id, f"{body.decision}d", me.user_id, comment=body.comment)
    await s.commit()

    if new_status is ProposalStatus.REJECTED:
        return {"status": "rejected"}
    return await execute_approved(s, p.id, me)


async def execute_approved(s: AsyncSession, proposal_id: str, approver: Principal) -> dict[str, Any]:
    p = await s.get(Proposal, proposal_id, populate_existing=True)
    assert p is not None and p.status == ProposalStatus.APPROVED
    requester = Principal(p.requested_by, p.tenant_id, role="agent_delegate")
    payload = json.loads(p.payload_json)
    if canonical_sha256(payload) != p.payload_sha256:           # tamper check
        raise HTTPException(500, "payload integrity check failed")
    try:
        output = await EXECUTORS[p.action_type](requester, payload)
        outcome = ProposalStatus.EXECUTED
    except Exception as exc:                                       # executor re-validation failed
        output, outcome = {"error": type(exc).__name__}, ProposalStatus.FAILED
    s.add(Execution(id=str(uuid4()), proposal_id=p.id, status=outcome,
                    result_json=json.dumps(output), executed_at=utcnow()))
    p.status = outcome
    p.version += 1
    await audit(s, p.id, outcome, approver.user_id, result=output)
    await s.commit()                 # UNIQUE(proposal_id) prevents a second execution row
    return {"status": outcome, "result": output}


async def expire_stale(s: AsyncSession) -> int:
    """Run periodically (cron/worker). Expired proposals are never executed."""
    now = utcnow()
    ids = list(await s.scalars(select(Proposal.id).where(
        Proposal.status == ProposalStatus.PENDING, Proposal.expires_at <= now)))
    if ids:
        await s.execute(update(Proposal)
                        .where(Proposal.id.in_(ids), Proposal.status == ProposalStatus.PENDING)
                        .values(status=ProposalStatus.EXPIRED, version=Proposal.version + 1))
        for pid in ids:
            await audit(s, pid, "expired", "system")
        await s.commit()
    return len(ids)
```

**Important lines and decisions.**

* `payload_sha256` is computed from a canonical JSON serialization and must be echoed back by the approver: the decision is bound to what was displayed.
* The decision is an **atomic compare-and-set** (`UPDATE … WHERE status='pending' AND version=… AND expires_at>now`). Two concurrent approvals or an approval racing expiry produce exactly one winner; the loser gets `409`.
* `requested_by != approver` enforces segregation of duties; role sets are per risk level.
* `UNIQUE(proposal_id)` on `executions` is the last line of defense against double execution; downstream calls should also carry an idempotency key.
* Executors receive the *requester's* delegated principal, not the approver's — approval authorizes the requester's action; it doesn't transfer the approver's broader rights to the agent.
* Executor failures are recorded as `failed`, not retried blindly; a new proposal (or reconciliation) is required.
* `expire_stale` marks expired rows and audits them; the decision endpoint enforces expiry independently.

For multi-party approval, replace the single CAS with: insert a decision row (unique on `(proposal_id, approver_id)`), count distinct approvals inside the same transaction with the proposal row locked (`SELECT … FOR UPDATE` on PostgreSQL), and transition to `approved` when the quorum is reached; any rejection transitions to `rejected`.

**Tests (all passing against the module above):**

```python
# test_approvals.py — run: pytest -q test_approvals.py
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import approvals_app as m

AGENT = {"X-User": "alice", "X-Tenant": "acme", "X-Role": "support_agent"}
SUPERVISOR = {"X-User": "sam", "X-Tenant": "acme", "X-Role": "supervisor"}
OTHER_TENANT_SUP = {"X-User": "eve", "X-Tenant": "globex", "X-Role": "supervisor"}

PROPOSAL = {
    "agent_session_id": "sess_1",
    "action_type": "issue_refund",
    "payload": {"order_id": "ord_aaaaaaaaaaaa", "amount": "120.00", "currency": "USD"},
    "risk": "high",
    "policy_reason": "amount exceeds support_agent limit 50",
    "reviewer_context": {"order_total": "120.00", "model_rationale": "item arrived broken"},
}


@pytest.fixture
def client():
    m.SENT_EMAILS.clear(); m.REFUNDS.clear()
    with TestClient(m.app) as c:          # runs lifespan → creates tables
        yield c


def propose(client) -> dict:
    r = client.post("/proposals", json=PROPOSAL, headers=AGENT)
    assert r.status_code == 201, r.text
    return r.json()


def test_approve_executes_exactly_once(client):
    p = propose(client)
    body = {"decision": "approve", "comment": "photo confirms damage", "payload_sha256": p["payload_sha256"]}
    r = client.post(f"/approvals/{p['id']}/decision", json=body, headers=SUPERVISOR)
    assert r.json()["status"] == "executed"
    again = client.post(f"/approvals/{p['id']}/decision", json=body, headers=SUPERVISOR)
    assert again.status_code == 409
    assert len(m.REFUNDS) == 1


def test_requester_cannot_self_approve(client):
    p = propose(client)
    body = {"decision": "approve", "comment": "ok", "payload_sha256": p["payload_sha256"]}
    r = client.post(f"/approvals/{p['id']}/decision", json=body,
                    headers={**AGENT, "X-Role": "supervisor"})
    assert r.status_code == 403
    assert m.REFUNDS == []


def test_other_tenant_cannot_see_or_decide(client):
    p = propose(client)
    assert client.get("/approvals", headers=OTHER_TENANT_SUP).json() == []
    body = {"decision": "approve", "comment": "x", "payload_sha256": p["payload_sha256"]}
    assert client.post(f"/approvals/{p['id']}/decision", json=body,
                       headers=OTHER_TENANT_SUP).status_code == 404


def test_stale_payload_hash_rejected(client):
    p = propose(client)
    body = {"decision": "approve", "comment": "x", "payload_sha256": "0" * 64}
    assert client.post(f"/approvals/{p['id']}/decision", json=body,
                       headers=SUPERVISOR).status_code == 409


def test_rejection_persists_and_never_executes(client):
    p = propose(client)
    body = {"decision": "reject", "comment": "no evidence", "payload_sha256": p["payload_sha256"]}
    assert client.post(f"/approvals/{p['id']}/decision", json=body,
                       headers=SUPERVISOR).json() == {"status": "rejected"}
    assert m.REFUNDS == []


def test_expired_proposal_cannot_be_approved(client):
    p = propose(client)

    async def age_and_expire():
        async with m.SessionLocal() as s:
            row = await s.get(m.Proposal, p["id"])
            row.expires_at = m.utcnow() - timedelta(seconds=1)
            await s.commit()
            assert await m.expire_stale(s) == 1
            events = list(await s.scalars(select(m.AuditEvent.event)
                                          .where(m.AuditEvent.proposal_id == p["id"])))
            assert events == ["proposed", "expired"]

    client.portal.call(age_and_expire)
    body = {"decision": "approve", "comment": "late", "payload_sha256": p["payload_sha256"]}
    assert client.post(f"/approvals/{p['id']}/decision", json=body,
                       headers=SUPERVISOR).status_code == 409
    assert m.REFUNDS == []
```

**Resuming the agent.** When a proposal reaches a terminal state, publish an event (outbox → queue/webhook). The orchestrator loads the agent session by `agent_session_id`, appends a *system-generated* tool result such as `{"proposal_id": …, "status": "executed", "refund_id": "rf_1"}`, and lets the agent compose the user-facing message from that fact. If the user is offline, send a notification rendered from the record, not from the model.

### 7. Comparative Analysis

| Comparison | Key difference | When to use | Trap |
|---|---|---|---|
| **Confirmation vs approval** | Requester re-confirms vs independent reviewer | Confirmation for intended, reversible user actions; approval for policy-exceeding or high-impact actions | Treating requester confirmation as segregation of duties |
| **HITL vs human-on-the-loop vs post-hoc review** | Blocking vs monitoring vs sampling | HITL for irreversible/high-value; on-the-loop for reversible with fast undo; post-hoc for low-risk auto actions | HITL for everything → fatigue |
| **In-memory await vs persisted state machine vs durable engine** | Process-bound vs DB-backed vs engine-managed | Persisted state for most apps; durable engine for long multi-step workflows | `await asyncio.sleep(3600)` waiting for approval |
| **Framework interrupt vs your own approval tables** | Execution checkpoint vs system of record | Use both: interrupt to pause the graph, tables for audit/authorization | Treating checkpoint blobs as the audit trail |
| **Optimistic (version CAS) vs pessimistic (row lock)** | Detect conflicts vs prevent them | CAS for single decisions; locks for quorum counting | Read-then-write without either |
| **Expire vs auto-approve on timeout** | Fail closed vs fail open | Always expire for risky actions | "No response in 24h = approved" |

### 8. Failure Modes and Debugging

**F1 — Double execution.** SYMPTOM: customer refunded twice. CAUSE: two workers executed the same approved proposal; no uniqueness or idempotency key. INVESTIGATE: executions table, payment provider logs by idempotency key, trace spans for both executions. FIX: `UNIQUE(proposal_id)`; idempotency key to payments; CAS on status. PREVENT: concurrency test firing two executions in parallel.

**F2 — Approved amount differs from executed amount.** CAUSE: decision bound to proposal ID only; payload edited after display. INVESTIGATE: compare `approval_decisions.payload_sha256` with executed payload hash. FIX: payload binding; immutable payloads (edits create a new proposal). PREVENT: tamper test.

**F3 — Expired proposal executed.** CAUSE: expiry only enforced by a sweeper running every 10 minutes. FIX: expiry check inside the decision CAS. PREVENT: test with clock manipulation.

**F4 — Agent loops re-proposing a rejected action.** CAUSE: rejection not fed back; agent "tries again". FIX: return rejection reason as tool result; block identical payload hash re-proposal within a window; count rejections in session budget.

**F5 — Approval queue flooded, 98% approval rate, 3-second decisions.** CAUSE: thresholds too low; rubber-stamping. INVESTIGATE: metrics per action type/reviewer. FIX: raise auto thresholds with evidence, add sampling audit, improve context. PREVENT: dashboards and alerting on decision time and approval rate.

**F6 — Resume after deploy repeats a side effect (framework interrupt).** CAUSE: side effect placed *before* `interrupt()` in a node; node re-executes on resume. FIX: move side effects to a separate node after the approval node; make them idempotent.

**F7 — Reviewer approved a malicious email.** CAUSE: UI rendered the email body as HTML with hidden text; reviewer saw only a benign preview. FIX: render as plain text, show full content and recipients, highlight links and untrusted provenance.

**Debugging tools.** SQL over `proposals`/`approval_decisions`/`executions`/`audit_events` joined by `proposal_id`; traces via `trace_id` in audit details; provider idempotency-key logs; time-travel by replaying audit events.

### 9. Guided Practice

**Level 1 — Concept Reinforcement**

*1.1 Risk-rate 12 actions.* Use the dimensions in §4.2 to score and assign controls. Hints: reversibility and exposure usually dominate; a sent email is irreversible.

*1.2 Where's the human?* For five workflows (password reset, invoice dispute, marketing email blast, code deploy by a coding agent, contract clause redline), decide HITL / on-the-loop / post-hoc and justify.

**Level 2 — Implementation**

*2.1 Gates for four action types.* Add `send_email`, `update_record`, `issue_refund`, `delete_account` executors to Example 3 with re-validation (e.g., refund: not already refunded; delete: no open orders). Tests: each executor's failure path records `failed`. Hints: raise a `DomainError` and let the executor wrapper record it.

*2.2 Two-person rule.* Implement quorum approval for `CRITICAL` risk. Requirements: distinct approvers, neither is the requester, any reject terminates. Tests: concurrent approvals reach quorum exactly once. Hints: unique `(proposal_id, approver_id)`; transactional count.

*2.3 Cool-off.* For `delete_account`, approved proposals move to `scheduled` with `execute_after`; a worker executes later unless cancelled. Hints: a separate status and index on `execute_after`.

**Level 3 — Integration**

*3.1 Agent resume.* Connect the approvals service to the Unit 41 agent loop: on `REQUIRE_APPROVAL`, create a proposal and stop the loop with `stopped_because="awaiting_approval"`; on decision, resume the session with a system-generated tool result. Tests: user receives the real outcome; rejected → agent explains reason; expired → agent offers to re-submit.

*3.2 Reviewer UI contract.* Design `GET /approvals/{id}` returning everything a reviewer needs (diff, evidence links, provenance warnings, labelled model rationale) and nothing sensitive. Write a contract test asserting no raw secrets/PII fields are present.

**Level 4 — Debugging / Production Scenario**

*4.1 Find the flaws:*

```python
@app.post("/approve/{pid}")
async def approve(pid: str, user=Depends(get_user)):
    p = await repo.get(pid)
    if p.status == "pending":
        p.status = "approved"
        await repo.save(p)
        await EXECUTORS[p.action](p.payload)
    return {"ok": True}
```

Hints: tenant? role? self-approval? race between read and write? expiry? payload binding? idempotency? audit? error handling?

*4.2 Timeout ambiguity.* The payment API timed out after an approved refund. Design the reconciliation flow. Hints: idempotency key lookup; `unknown` status; never re-issue blindly.

### 10. Independent Implementation Project — "Approval Gates for SupportOps"

**Goal.** Add durable, auditable human approval to the SupportOps agent for email, data modification, refund-like actions and deletion.

**Functional requirements.**

1. Risk classification table (versioned) driving auto / confirm / single / two-person / cool-off.
2. Persist proposal, reviewer context snapshot, approver(s), decision(s), execution result and audit events.
3. Reviewer queue per tenant and role; decision endpoint with payload binding and segregation of duties.
4. Expiry enforced in-transaction and by a sweeper; SLA escalation notification.
5. Executors that re-validate and use idempotency keys; failed executions recorded.
6. Agent interrupt/resume: the agent pauses on approval and later reports the real outcome.

**Technical requirements.** FastAPI, Pydantic v2, SQLAlchemy 2.x async + PostgreSQL (testcontainers in tests), Alembic, an outbox table + relay worker, OpenTelemetry trace IDs in audit (Unit 45).

**Suggested structure.**

```
app/
├── approvals/{policy.py, models.py, service.py, executors.py, sweeper.py, schemas.py}
├── agent/{loop.py, resume.py}
├── api/{approval_routes.py, agent_routes.py}
├── infra/{db.py, outbox.py, notifications.py}
└── domain/{refunds.py, accounts.py, email.py}
migrations/
tests/
├── unit/{test_policy_table.py, test_state_machine.py}
├── integration/{test_decision_concurrency.py, test_expiry.py, test_quorum.py, test_resume.py}
└── contract/test_reviewer_view.py
```

**Milestones.** (1) policy table + state machine; (2) persistence + migrations + indexes; (3) decision endpoint with CAS, binding, SoD; (4) executors + idempotency + reconciliation stub; (5) expiry + escalation; (6) agent pause/resume; (7) quorum + cool-off.

**Testing requirements.** Concurrency tests (parallel approvals, approval vs expiry), tamper test, self-approval test, tenant isolation, expiry, rejection feedback, executor failure, resume idempotency.

**Definition of Done.**

* [ ] No side effect classified above LOW can execute without a persisted, unexpired, bound approval meeting policy.
* [ ] Every executed action has a complete audit chain from proposal to result.
* [ ] Parallel decision attempts produce exactly one outcome and one execution.
* [ ] Expired and rejected proposals never execute and the user is told the truth.
* [ ] A process restart between approval and execution does not lose or duplicate work.

**Optional extensions.** Slack/Teams approval buttons with signed callbacks; Temporal implementation of the same workflow; hash-chained audit log; reviewer analytics dashboard.

### 11. Testing Strategy

* **State-machine unit tests**: every legal and illegal transition.
* **Policy table tests**: action × context → requirement.
* **Concurrency tests**: `asyncio.gather` two approvals; approval racing sweeper; executor invoked twice. On PostgreSQL, run with real transactions (testcontainers) — SQLite's locking differs.
* **Time tests**: inject a clock or manipulate `expires_at`; never `sleep`.
* **Security tests**: self-approval, cross-tenant, wrong role, stale hash, missing comment.
* **Resume tests**: duplicate resume events, resume after restart.
* **Contract tests**: reviewer view excludes secrets/PII.
* **Eval feed**: rejected proposals become eval cases (Unit 44).

```python
# Concurrency sketch for PostgreSQL integration tests
import asyncio, pytest

@pytest.mark.anyio
async def test_parallel_approvals_single_winner(api_client, pending_proposal, sup1, sup2):
    body = {"decision": "approve", "comment": "ok", "payload_sha256": pending_proposal["payload_sha256"]}
    r1, r2 = await asyncio.gather(
        api_client.post(f"/approvals/{pending_proposal['id']}/decision", json=body, headers=sup1),
        api_client.post(f"/approvals/{pending_proposal['id']}/decision", json=body, headers=sup2),
    )
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
```

### 12. Engineering Scenarios

**Scenario 1 — "Approvals are slowing us down."** Support leads complain that 40% of refunds wait for approval. *Investigate:* approval rate, decision time, post-approval incident rate, amount distribution. *Options:* raise thresholds; auto-approve with post-hoc sampling for repeat-customer low-value refunds; better context to speed decisions. *Reasoning:* Use data: if 99.5% of $50–$100 refunds are approved and none later reversed, auto-approve them with sampling; keep human review where rejections actually happen.

**Scenario 2 — Deleting accounts on request.** Legal requires erasure within 30 days; fraud wants a hold for accounts with chargebacks. *Reasoning:* Deletion = critical; two-person approval with privacy officer; cool-off; invariants check chargebacks (hold, not reject); execution is a multi-step workflow (durable engine candidate) with per-system confirmations; audit retains *that* deletion happened without retaining the data.

**Scenario 3 — Approvals in Slack.** *Investigate:* how is the approver authenticated (Slack user ↔ IdP mapping)? Are callbacks signed and verified? Can the message be forwarded? *Reasoning:* Slack is a UI, not an authority: the callback hits your decision endpoint with full checks; render exact payload; expiry and binding still apply.

**Scenario 4 (FDE) — "We need a human to check everything the AI does."** A customer's compliance team asks for this at kickoff. *Clarify:* What risk are they worried about (wrong answers? unauthorized actions? regulatory)? Which actions exist and their volume? Who are the reviewers and their capacity? What evidence do auditors need? *Expected reasoning:* Propose risk tiers with data: review all external/irreversible actions, sample low-risk ones, and show a pilot dashboard of approval rate, time-to-decision and caught errors. "Everything" usually becomes "everything irreversible plus a sample".

### 13. Interview Preparation

#### Quick Questions

**Q: Where should humans be in an agent workflow?** Before irreversible, high-impact, external or policy-exceeding actions, and where judgment with missing context is needed — not for things code can check or for high-volume low-risk actions.

**Q: Why persist approval state instead of awaiting in memory?** Approvals take long; processes restart; you need audit, concurrency control and recovery.

**Q: What should happen when an approval expires?** Nothing executes (fail closed); the requester and agent are told; it may be re-proposed with fresh data.

**Q: Confirmation vs approval?** Confirmation is the requester re-affirming intent; approval is an independent, authorized decision with segregation of duties.

#### Intermediate Questions

**Q: How do you ensure the approver approved exactly what executes?**
Strong answer: Immutable proposal payloads, canonical hash displayed and submitted with the decision, compare on decision and before execution; edits create new proposals.

**Q: How do you prevent double execution?**
Strong answer: CAS on status, unique execution per proposal, idempotency keys downstream, reconciliation for unknown outcomes.

**Q: What context should a reviewer see?**
Strong answer: Exact action rendered from data, diffs, computed values, evidence, policy reason, provenance warnings, labelled AI rationale, expiry; minimal PII; untrusted content escaped.

#### Advanced Questions

**Q: Compare LangGraph interrupts with a durable execution engine for approvals.**
Strong answer: LangGraph interrupts pause a graph and persist state via a checkpointer; resume with `Command(resume=…)`; the interrupted node re-executes from its start on resume, so side effects must sit after the interrupt or be idempotent; authorization of the resumer is yours. Durable engines (Temporal) persist workflow history, provide timers/signals/retries and long waits, at the cost of operational complexity and deterministic workflow code. Either way, your own proposal/approval tables are the audit system of record.

**Q: Approval fatigue — how do you detect and fix it?**
Strong answer: Metrics (approval rate, decision latency, reviewer variance, post-approval incidents); move low-risk to auto + sampling; improve context; rotate reviewers; require reasons; red-team approvals with seeded bad proposals and measure catch rate.

#### Coding Questions

1. Write the SQL/SQLAlchemy for an atomic approve that fails if expired or already decided.
2. Implement quorum approval with distinct approvers.
3. Write a sweeper that expires proposals and is safe to run concurrently on two nodes.

#### Scenario Questions

* "An approved refund's payment call timed out. What now?"
* "The agent proposed deleting an account after reading a support email that said 'please delete my account'. Is approval enough?" (Verify identity of the requester through an authenticated channel; untrusted email provenance; approval plus verification.)

### 14. Explain-It-at-Three-Levels

**Approval workflows**

* *30 s:* Risky agent actions become persisted proposals that a qualified person approves or rejects; approvals are bound to the exact payload, expire, and execute exactly once with a full audit trail.
* *2 min:* Add risk classification, segregation of duties, CAS concurrency, expiry fail-closed, re-validation at execution, reviewer context, and how the agent pauses and resumes truthfully.
* *Deep:* State machine design, DB constraints and isolation, idempotency and reconciliation, outbox/resume events, framework interrupts vs durable engines, approval UX metrics and fatigue, regulatory drivers, and testing concurrency and time.

### 15. Knowledge Check

**Conceptual**

1. What is the difference between human-in-the-loop and human-on-the-loop?
2. Why must expiry be enforced in the decision transaction and not only by a sweeper?
3. Why does an approval need to be bound to a payload hash?
4. What is segregation of duties and how is it enforced here?
5. Why are executors re-validating state that was already validated at proposal time?

**Code reading**

6. In Example 3, what happens if two supervisors approve at the same moment?
7. Why does `execute_approved` construct a principal from `requested_by` rather than using the approver?
8. In a LangGraph node, what's wrong with calling `payments.refund()` before `interrupt()`?

**Debugging**

9. A refund executed twice. Which three mechanisms should have prevented it?
10. Reviewers approve 99% of email proposals in under 3 seconds. What do you do?

**Design**

11. Design the control for "change customer email address".
12. When would you choose a durable execution engine over DB state + outbox?

#### Knowledge Check Answers

1. HITL blocks execution until a human decides; on-the-loop lets actions proceed while humans monitor and can intervene.
2. Sweeper runs periodically; between runs a stale proposal could be approved. The CAS includes `expires_at > now`, closing the race.
3. To ensure the decision applies to the exact action displayed; prevents edit-after-display and summary/action mismatches.
4. The person requesting an action can't approve it; enforced by `requested_by != approver_id` (plus distinct approvers for quorum).
5. State changes between proposal and execution (TOCTOU) — e.g., already refunded, account closed; executing on stale facts violates invariants.
6. Both read `pending`; only one conditional `UPDATE` matches (`rowcount==1`); the other gets 409. One decision row, one execution.
7. Approval authorizes the requester's action; using the approver's broader privileges would escalate the agent beyond the requester (confused deputy).
8. On resume the node re-runs from its start, so the refund would execute again (and it executed before approval!). Place side effects after the approval node and make them idempotent.
9. Status CAS, `UNIQUE(proposal_id)` on executions, idempotency key at the payment provider.
10. Treat as fatigue: analyze risk of those emails; auto-approve templated low-risk ones with sampling; improve context; keep approvals for free-form/tainted emails; seed test proposals to measure catch rate.
11. High risk (account takeover): verify via existing channel (send confirmation to old email), supervisor approval if agent-initiated, short TTL, notify old address after change, audit.
12. Multi-step, long-running workflows with timers, retries and compensations across several systems (e.g., account deletion across 8 services) where hand-rolled state machines become error-prone.

### 16. Common Interview Traps

| Trap | Correct mental model |
|---|---|
| "Add a human and it's safe." | Only with exact payload binding, qualified independent reviewers, good context and fatigue management. |
| "Approval = the user clicked confirm." | Confirmation ≠ independent approval. |
| "Timeout → auto-approve to keep things moving." | Fail closed: expire. |
| "The framework's checkpoint is our audit log." | Keep your own proposal/decision/execution records. |
| "Approved means execute whenever." | Re-validate at execution; expiry; cool-off. |
| "Exactly-once execution is guaranteed by the queue." | Effectively-once requires idempotency + uniqueness + reconciliation. |
| "Show reviewers the model's summary." | Show data-rendered exact action; label model text as AI-generated. |

### 17. Cheat Sheet

* **Risk dimensions:** impact, reversibility, blast radius, exposure, sensitivity, provenance, principal authority.
* **Controls:** auto+log · confirm · single approval (SoD) · N-of-M · cool-off · post-hoc sampling.
* **Tables:** `proposals` · `approval_decisions` · `executions (UNIQUE proposal_id)` · `audit_events (append-only)` · `outbox`.
* **CAS:** `UPDATE proposals SET status='approved', version=version+1 WHERE id=:id AND status='pending' AND version=:v AND expires_at>now()` → rowcount 1.
* **Binding:** `sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")))`, echoed by approver.
* **Execution:** reload → verify hash → re-validate → idempotency key → record result → event.
* **Expiry:** in-transaction + sweeper; never auto-approve.
* **Resume:** event → load session → system-generated tool result → agent reports truth.
* **LangGraph:** `interrupt(value)` / `Command(resume=…)` with durable checkpointer and `thread_id`; node re-runs on resume.
* **Metrics:** queue depth, time-to-decision, approval rate by action/reviewer, expiry rate, post-approval incidents.

### 18. Completion Checklist

* [ ] I can classify actions by risk and map them to controls.
* [ ] I can implement persisted proposals with payload binding, SoD, CAS decisions and expiry.
* [ ] I can guarantee effectively-once execution with constraints and idempotency keys.
* [ ] I can implement interrupt/resume so the agent reports real outcomes.
* [ ] I can design reviewer context and measure approval fatigue.
* [ ] I can test concurrency, expiry, tampering and resume.
* [ ] I can explain when *not* to add a human (and automate or deny instead).

### 19. Further Research

**Essential**

* LangGraph — Interrupts / human-in-the-loop: <https://docs.langchain.com/oss/python/langgraph/interrupts> — `interrupt()`, `Command(resume=…)`, checkpointers, re-execution semantics.
* Temporal — Workflow message passing (signals/updates) and timers: <https://docs.temporal.io/> — durable waiting for human decisions.
* PostgreSQL — Explicit locking and `SELECT … FOR UPDATE`: <https://www.postgresql.org/docs/current/explicit-locking.html>; transaction isolation: <https://www.postgresql.org/docs/current/transaction-iso.html>.
* SQLAlchemy 2.x asyncio: <https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html> — `AsyncSession`, `async_sessionmaker`, greenlet requirement.

**Deeper Study**

* OWASP Top 10 for Agentic Applications — ASI09 Human-Agent Trust Exploitation: <https://genai.owasp.org/> — how agents can manipulate reviewers.
* Stripe — Idempotent requests: <https://docs.stripe.com/api/idempotent_requests> — a reference design for idempotency keys.
* Microservices.io — Transactional outbox: <https://microservices.io/patterns/data/transactional-outbox.html>.
* EU AI Act, Article 14 (Human oversight): <https://artificialintelligenceact.eu/article/14/> — regulatory framing of human oversight.

**Practice**

* Build the same approval flow in LangGraph and Temporal; compare failure handling when you kill the worker mid-approval.
* testcontainers-python: <https://testcontainers-python.readthedocs.io/> — run PostgreSQL concurrency tests realistically.

### Unit Completion Standard

Before moving on, you must be able to: **explain** where humans belong in agent workflows and why approval is a control only when bound, independent, time-limited and audited; **implement** persisted approval gates for email, data modification, refunds and deletion with risk classification, payload binding, segregation of duties, atomic decisions, expiry and effectively-once execution; **test** concurrency, expiry, tampering, rejection and resume behaviour; **debug** double-execution, stale-approval and fatigue problems from the audit tables; and **defend** in an interview your approval-state design, UX choices and timeout policy.
