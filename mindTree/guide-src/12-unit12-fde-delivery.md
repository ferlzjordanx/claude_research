# Unit 12 — Forward Deployed Engineering: Customer-Facing Delivery

## 1. What This Unit Teaches

Units 1–11 taught you to build and run software. This unit teaches the part of the job that makes the title different: building it **with and for a specific customer**, inside their constraints, while the requirements are still moving **[JD-Required: working directly with customers, translating business needs into technical solutions, communication, ownership, rapid prototyping, delivering in ambiguous environments]**.

You will learn to:

- explain what an FDE does and how it differs from a software engineer, a solutions engineer and a consultant;
- run discovery: stakeholders, jobs to be done, the current process, success metrics and constraints;
- write requirements when the facts are incomplete: assumptions, open questions, a RAID log, MoSCoW and Given/When/Then acceptance criteria;
- scope with thin vertical slices, timeboxes and spikes, and move from prototype to pilot to production;
- communicate: demos, BLUF status updates with RAG status, saying no with trade-offs, change requests, customer incidents;
- handle security reviews, work inside the customer's environment, and handle their data ethically;
- deliver AI features honestly: probabilistic behavior, human-in-the-loop and eval-based acceptance;
- answer interview questions about all of this even when your direct customer experience is limited.

The project is a complete simulated engagement: discovery notes, requirements, an ADR, a status update and a handover for a fictional customer, plus a working intake-automation service whose acceptance tests are the requirements.

## 2. Mental Model

```text
  AMBIGUOUS ASK            "We drown in intake emails. Can AI fix it?"
       │
       ▼
  DISCOVERY      stakeholders · job to be done · current process
       │         success metric · constraints (security, data, people)
       ▼
  REQUIREMENTS   scope in/out · MoSCoW · assumptions · open questions
       │         acceptance criteria (Given/When/Then)  ◄── agreed
       ▼
  DECIDE         ADR: options, decision, consequences
       │
       ▼
  BUILD IN SLICES  thin end-to-end slice ─► demo ─► feedback ─► next
       │           acceptance tests = requirements, executable
       ▼
  PILOT          real users, guarded (human review), measured
       │         weekly status: BLUF + RAG + asks
       ▼
  PRODUCTION     security review · runbook · SLOs · handover
       │
       ▼
  FEEDBACK       to the customer (value/ROI) and to your product team
```

Three ideas carry the whole unit:

1. **The customer's problem is the spec, not their first request.** "Use AI" is a solution guess. "Front-desk staff spend 4 minutes retyping each email" is a problem you can measure and solve.
2. **Write it down, then make it executable.** Assumptions, decisions and acceptance criteria live in documents the customer signs off. The acceptance criteria then become tests, so "done" is not a matter of opinion.
3. **Trust is the deliverable.** Customers keep working with an FDE who tells them bad news early, says what they do not know, and never surprises them in a demo or in production.

## 3. Brief Theory

### 3.1 What an FDE is (and is not)

**What it is.** A Forward Deployed Engineer is a software engineer embedded with a customer to turn the company's product or platform into a working solution for that customer's problem. The term was popularized by Palantir; AI companies (including model providers and AI platform vendors) now hire FDEs to get customers from "interesting demo" to "running in production".

**Why it exists.** Powerful general platforms (data platforms, LLM APIs) do not solve a specific business problem out of the box. Someone has to understand the problem, integrate with messy systems, and own the outcome.

**Why it matters.** Interviewers test whether you understand that the role is both engineering *and* customer delivery. Pure coders and pure presenters both struggle.

| Role | Main output | Writes production code? | Owns outcome? |
|---|---|---|---|
| Software engineer (product) | Features for many customers | Yes, in the product | Product quality |
| **Forward deployed engineer** | Working solution for one customer, feedback to product | Yes, at the customer, often fast | Customer outcome, end to end |
| Solutions engineer / sales engineer | Demos, proofs of concept, technical win before the sale | Prototypes, rarely production | The technical win |
| Consultant | Advice, plans, sometimes delivery | Sometimes | The engagement scope |
| Customer success / support | Adoption, renewals, tickets | No | Retention |

**How it works.** A typical FDE week mixes customer calls, building (often in the customer's environment), demos, writing documents, and feeding product gaps back to the core engineering team. The FDE is often the only person who sees both the customer's reality and the product's internals.

### 3.2 Discovery

**What it is.** Structured learning before building: who cares, what job they are trying to get done, how it is done today, how success is measured, and what limits the solution.

**Why it exists.** The first request is usually a solution guess ("we need a chatbot"). Building the guess wastes weeks.

**Why it matters.** Most failed engagements fail in discovery: wrong problem, wrong sponsor, or a constraint (security, data residency) found in week five.

**How it works.**

- **Stakeholder map.** List people by influence and interest: sponsor (pays, decides scope), users, IT (operates it), security/privacy (can veto), and the people whose job changes. Name the decision maker and the person with a veto.
- **Jobs to be done (JTBD).** "When *situation*, I want to *motivation*, so I can *outcome*." It keeps you on the outcome, not the feature.
- **Current process map.** Shadow the work. Count steps, time per step, error rates, handoffs. Your baseline metrics come from here.
- **Success metrics.** One business metric the sponsor cares about (hours saved, error rate, time to answer), plus guardrail metrics (accuracy on critical fields, no PHI leaks).
- **Constraints.** Security (network, identity, approved vendors), compliance (healthcare, finance, GDPR), data residency (which region data may be in), integration (API, CSV, nothing), change management (who fears the change, who must be trained).

The discovery question bank (§3.18) is a ready checklist. In the project, `docs/discovery_notes.md` shows the output of a three-day discovery.

### 3.3 Requirements under ambiguity

**What it is.** A written, versioned description of what will be built, that is honest about what is still unknown.

**Why it exists.** You will never have complete information before you must start. Writing down assumptions turns hidden risks into tracked items.

**Why it matters.** When a stakeholder later says "that's not what we asked for", the requirements document and its change log are your shared memory, not a weapon.

**How it works.**

| Tool | What it is | Example |
|---|---|---|
| Assumptions log | Things you treat as true until confirmed, with owner and due date | "A-4: slash dates are month-first (US only)" |
| Open questions | Things you must learn, with owner and due date | "Q-1: which LLM vendor is approved?" |
| RAID log | Risks, Assumptions, Issues, Dependencies in one table | "Risk: vendor approval slips → fake extractor" |
| MoSCoW | Must / Should / Could / Won't (this time) | "FR-10 per-staff metrics: Won't" |
| Acceptance criteria | Testable statements of done, often Given/When/Then | see below |

Given/When/Then comes from behavior-driven development (BDD; see the [Gherkin reference](https://cucumber.io/docs/gherkin/reference/) **[External]**):

```text
AC-2  Given an intake with no date of birth
      When it is submitted
      Then it is placed in the review queue with the reason
        "date_of_birth: required field missing"
```

Good criteria name concrete values (which field, which message, which number) so a test can check them. "The system handles missing data gracefully" is not an acceptance criterion.

### 3.4 Scoping and estimation

**What it is.** Choosing what to build first and how long to allow, when you do not yet know enough to estimate precisely.

**Why it exists.** Customers need dates; engineers cannot know the unknowns. Scoping techniques reduce the unknowns quickly.

**How it works.**

- **Thin vertical slice.** One narrow path through every layer (input → extraction → validation → storage → UI/API → metric) before broadening any layer. It exposes integration risk in week one.
- **Timebox.** Fix the time, flex the scope: "two weeks for the pilot slice; whatever is not done becomes a Should."
- **Spike.** A short, throwaway investigation to answer one question ("can we reach their booking system's database from the VPN?"). The output is an answer and a decision, not production code.
- **Estimate in ranges with assumptions.** "3–5 days, assuming the CSV import accepts UTF-8 and we get VPN access by Monday." Re-estimate when an assumption breaks, and say so.

### 3.5 Prototype → pilot → production

| Stage | Purpose | Data | Users | Bar |
|---|---|---|---|---|
| Prototype | Prove feasibility, align on the idea | Synthetic or samples | The team, the sponsor | Works in a demo |
| Pilot | Prove value under real conditions, guarded | Real or anonymized, limited | A few real users | Acceptance criteria + guardrails + metrics |
| Production | Run the business on it | All | Everyone in scope | Security review, SLOs, runbook, support, handover |

The jump from pilot to production is where most AI projects stall: load (Unit 8), observability (Unit 11), security review (§3.11), on-call ownership and change management. Plan it from the start: FDE Scenario 13 covers this jump.

### 3.6 Demo craft

**What it is.** Showing working software in a way that builds confidence and gets a decision.

**How it works.**

- Start with the outcome ("today front desk retypes everything; here is what changes"), then show it.
- Demo the real system, not slides. Use fixed data and a frozen clock so it behaves the same every time (`scripts/demo.py`).
- Show a messy case on purpose and what happens to it. Hiding failure modes destroys trust when users find them.
- Let a customer user drive if possible.
- End with the metric and the ask: "33% auto-accepted on the demo set; we need the vendor decision by Friday."
- Have a fallback (recording or local run) if the network or VPN fails.

### 3.7 Communicating with executives and engineers

**BLUF (Bottom Line Up Front).** The first two sentences say where things stand and what you need. Details follow for those who want them.

**RAG status.** Green: on track. Amber: at risk, mitigation in place, may need help. Red: will miss without a decision or resources. Amber is not a failure; a status that jumps from Green to Red overnight is.

| Audience | Wants | Format |
|---|---|---|
| Executive sponsor | Outcome, risk, decisions needed, money and dates | BLUF, RAG, one metric, asks with deadlines |
| Customer engineers | How it works, what it needs from them, failure modes | Diagrams, ADRs, API docs, runbooks |
| End users | What changes in their day, how to get help | Short demo, one-page guide |
| Your product team | Patterns across customers, gaps, bugs | Written feedback with evidence and frequency |

### 3.8 Saying no and framing trade-offs

**What it is.** Declining or reshaping a request without damaging the relationship.

**How it works.** Never a bare "no". Offer options with costs: "We can add scanned PDFs, but it adds an OCR dependency and about two weeks. Options: (a) move the pilot date, (b) drop the CSV export to Should, (c) do PDFs in phase 2. Which matters more for the board meeting?" The customer decides priorities; you make the cost visible. Scenario 11 practices this when stakeholders disagree.

### 3.9 Scope creep and change requests

Small requests accumulate ("can it also..."). Handle each the same way:

1. Write it down (change log, issue).
2. Assess impact on dates, risk and the success metric.
3. Propose: accept and trade something, defer to a later phase, or decline with a reason.
4. Get the decision from the person who owns scope (the sponsor), not from whoever asked.
5. Update requirements and acceptance criteria in the same change.

### 3.10 Incidents with customers

The technical response is in Units 6–11. The customer-facing part:

- acknowledge fast, even before you know the cause;
- agree a cadence ("updates every hour until resolved");
- separate facts from hypotheses in every message;
- contain first (switch to human review, roll back), then find root cause;
- write a blameless post-incident summary: impact, timeline, cause, fix, prevention.

The incident comms template is in §3.18.

### 3.11 Security reviews and questionnaires

**What it is.** The customer's security and privacy teams assess your solution before it touches real data: questionnaires (data flow, encryption, access, retention, subprocessors, incident response), architecture review, sometimes penetration tests.

**Why it matters.** It is the most common reason a successful pilot cannot go to production on time. Start it in week one.

**How it works.** Prepare a data-flow diagram (what data, where it goes, who can access it), a list of subprocessors (for example, the LLM vendor), encryption in transit and at rest, identity and access, logging (no sensitive data), retention and deletion, and how you handle incidents. Point to recognized frameworks where relevant, such as the [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/) **[External]** and the [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) **[External]**. Scenario 12 covers a blocked review.

### 3.12 Documentation that survives you

- **Requirements** with a change log (`docs/requirements.md`).
- **Architecture Decision Records (ADRs):** one short file per significant decision: context, options, decision, consequences ([adr.github.io](https://adr.github.io/) **[External]**). They answer "why is it like this?" a year later.
- **Runbook:** how to start, check, and fix common problems, written for the person on call at 2 a.m.
- **Handover:** ownership table, configuration, known limitations, open items, access removal.

### 3.13 The feedback loop to product

An FDE sees what customers actually need. Write it down for your product team: the gap, the evidence (how many customers, how often), the workaround you built, and the cost of the workaround. The project's `handover.md` ends with "Product feedback sent". Good FDE teams turn repeated workarounds into product features.

### 3.14 Measuring value and ROI

Tie the solution to the metric agreed in discovery. A simple ROI line:

```text
messages/day 180 × minutes saved 2.5 × staff cost $0.60/min
  = $270/day ≈ $5,900/month, before error-reduction benefits
```

Report the measurement method and its limits ("estimate from 2 hours of shadowing"). In the project, `GET /metrics/summary` gives the auto-accept rate and per-field correction rates: the pilot's evidence.

### 3.15 Working in the customer's environment

Expect VPN access that takes days, no admin rights, their CI system (GitLab, Jenkins, Azure DevOps), their cloud account with restrictive IAM, egress blocked to the internet, and change boards (Unit 7). Practical habits:

- request access in week zero; list every account, role and network rule you need;
- keep a local, fake-backed version of the system (like this project's `FakeExtractor`) so you can keep working while access is pending;
- follow their conventions (branching, tickets, deploy windows), even if yours are better;
- never copy customer data to your laptop or personal tools.

### 3.16 Ethics and data handling

Use the minimum data needed. Use synthetic or anonymized data until real data is approved. Keep sensitive values out of logs, metrics and screenshots (acceptance criterion AC-8 in the project). Know who may see what, and keep an audit log of changes. Do not build features that monitor individuals without their knowledge (the project's "per-staff productivity: Won't"). If you are asked to do something you believe is unsafe or unlawful, raise it in writing with your manager.

### 3.17 Delivering AI features

**What is different.** LLM outputs are probabilistic: the same input can give different outputs, and a fluent answer can be wrong (Units 9–10).

**How to deliver it honestly.**

- **Set expectations early:** "It will be right most of the time, not all the time; here is how we catch the rest."
- **Deterministic where possible:** rules and parsers for formatted fields; the model for language (ADR-0001 in the project).
- **Human-in-the-loop:** route low-confidence or conflicting results to a person; measure corrections.
- **Eval-based acceptance criteria:** "On 200 labeled messages, zero auto-accepted wrong DOBs and ≥ 40% auto-accepted," instead of "it works on my examples". Model self-reported confidence is not calibrated; tune thresholds on labeled data.
- **Vendor and data approval** before real data reaches any model API. See provider guidance such as Anthropic's [documentation](https://docs.claude.com/) **[Provider-specific]** and OpenAI's [platform docs](https://platform.openai.com/docs) **[Provider-specific]**.

### 3.18 Templates

**Discovery question bank (by category).**

```text
BUSINESS   What problem costs you the most today? How do you know?
           What happens if we do nothing? Who pays for this?
           What would make this a success in 3 months? In 1 year?
USERS      Who does this work today? Can I watch them do it?
           What do they hate about it? What must not change?
PROCESS    Walk me through one real case, start to finish.
           How many per day? How long each? How often wrong?
           Where are the handoffs and the workarounds?
DATA       Where does the data live? Who owns it? How messy is it?
           Can we get 50 real (anonymized) examples this week?
SYSTEMS    What must we integrate with? API, files, database?
           Who can grant access? How long does that take?
SECURITY   Which data is sensitive (PII, PHI, PCI)? Which vendors
           are approved? Data residency? Retention? Audit needs?
DECISIONS  Who decides scope? Who can veto? Who signs off "done"?
CHANGE     Who is worried about this? Who must be trained?
           How will we roll it out and roll it back?
```

**Requirements document skeleton.**

```text
1. Problem (one paragraph, with a number)
2. Users and stakeholders
3. Scope: in / out (out is as important as in)
4. Functional requirements (ID, text, MoSCoW)
5. Non-functional: accuracy, privacy, latency, availability
6. Assumptions and open questions (ID, owner, due date)
7. Risks (RAID summary)
8. Acceptance criteria (Given/When/Then, IDs map to tests)
9. Change log (version, date, change, agreed by)
```

**ADR template.**

```text
# ADR-NNNN: <decision in a few words>
- Status: Proposed | Accepted | Superseded by ADR-MMMM
- Deciders: <names/roles>   Date: <yyyy-mm-dd>
## Context      forces, constraints, what we know and don't
## Options      2-4 options, each with pros and cons
## Decision     the choice and the main reason, tied to context
## Consequences positive, negative, follow-ups with triggers
```

**Status update template.**

```text
Subject: <Project> status, week N: <GREEN|AMBER|RED>
BOTTOM LINE  <2-3 sentences: where we are, the decision needed,
              by when>
DONE         <3-5 bullets, outcomes not activities>
NEXT         <3-5 bullets>
RISKS / ASKS <item | RAG | owner | needed by>
METRIC       <the agreed success metric, with its caveats>
```

**Incident comms template.**

```text
Subject: [INCIDENT] <service> <impact>, status: <investigating|
         mitigated|resolved>   Update #N, <time, timezone>
IMPACT     who/what is affected, since when (facts only)
STATUS     what we have done; current mitigation
NEXT       what we are doing now; next update at <time>
KNOWN      confirmed facts
UNKNOWN    hypotheses being tested (labeled as such)
ASK        anything we need from you (access, a decision)
```

**Handover checklist.**

```text
[ ] Code in the customer's repository; CI green
[ ] README: run, test, configure
[ ] Runbook: start, health, top 5 failure modes and fixes
[ ] ADRs for significant decisions
[ ] Ownership table: who operates, who changes config, escalation
[ ] Dashboards and alerts handed over (Unit 11)
[ ] Known limitations and open items listed
[ ] Two customer engineers have run and deployed it themselves
[ ] Secrets rotated; FDE access removed on an agreed date
[ ] Product feedback filed with your own team
```

### 3.19 Experience-Gap Playbook

Many candidates for FDE roles have strong engineering backgrounds but little direct customer-facing delivery. The general rules are in the front matter section "How to Answer When Your Experience Is Limited": name the evidence type you are using and never present lab work as production ownership. For FDE questions specifically:

- **Find transferable evidence.** Customer-facing work is broader than the job title. Internal customers count (another team that depended on your API), so do support rotations, gathering requirements from a product manager, explaining an outage to non-engineers, onboarding a new teammate, or freelance and volunteer projects. Say which it was.
- **Use the lab honestly.** This unit's project is a full simulated engagement. You can say: "In a simulated engagement I wrote discovery notes, requirements with Given/When/Then criteria, an ADR and a handover, and turned the criteria into executable tests." That is training evidence, and it is still evidence.
- **Show the method, not a fake story.** For "tell me about a difficult stakeholder", if you have no direct example, describe what you would do using the structure in §3.7–3.9, and say clearly that it is your approach, not a past event.
- **Apply the gap template** from the front matter, adapted: "I have not led a customer engagement end to end. My closest experience is `<<internal customer or support example>>`, where I `<<what you did>>`. I have practiced the full delivery cycle in `<<lab/project>>`. Here, I would `<<steps>>`, and I'd know it worked when `<<metric>>`."
- **Expect the follow-ups.** "What did the customer say? What would you do differently?" A truthful small example survives follow-ups; an inflated one does not.

## 4. Application in a Real System

Northwind Clinics (fictional) asks: "Can AI read our intake emails?" A realistic three-week path:

- **Week 0:** request VPN, repository and cloud access; ask the privacy officer which vendors are approved (Q-1). Start the security questionnaire.
- **Days 1–3, discovery:** interview the COO, practice manager, IT lead and privacy officer; shadow the front desk; collect 40 anonymized samples. Find two surprises: forwarded chains and relatives booking with two phone numbers.
- **Days 4–5, requirements and decision:** requirements v0.3 with eight acceptance criteria; ADR-0001 chooses rules first, LLM second, human review on doubt, because no vendor is approved and a wrong DOB is costly.
- **Week 2, thin slice:** `POST /intake` → extraction → validation → routing → review queue → metrics, against a fake extractor. Acceptance tests pass. Demo to two front-desk staff; they ask for the reason to be shown first (done the same day).
- **Week 3, pilot prep:** weekly status goes AMBER because vendor approval is late; the sponsor escalates. Eval set of 200 labeled messages created with the front desk. Handover draft reviewed with IT.

## 5. Implementation

### 5.1 Precedence: rules win, conflicts are never silent

```python
for field in fields:
    det = deterministic.get(field)
    guess = llm.get(field)
    if det is not None:
        conflict = (
            guess.value
            if guess is not None
            and not same_value(det.value, guess.value)
            else None
        )
        merged[field] = FieldResult(
            value=det.value,
            source=Source.DETERMINISTIC,
            confidence=det.confidence,
            conflict_with=conflict,
        )
    elif guess is not None:
        merged[field] = FieldResult(
            value=guess.value, source=Source.LLM,
            confidence=guess.confidence,
        )
    else:
        merged[field] = FieldResult(
            value=None, source=Source.NONE, confidence=0.0
        )
```

Every value carries its source. That one decision makes the review screen, the audit log and the correction metrics possible.

### 5.2 Routing: the business rule in a dozen lines

```python
reasons = [f"{n}: {p}" for n, p in sorted(issues.items())]
for field in sorted(merged):
    result = merged[field]
    if result.conflict_with is not None:
        reasons.append(
            f"{field}: extractors disagree (kept deterministic)"
        )
    if (field in REQUIRED_FIELDS and result.value is not None
            and result.confidence < threshold):
        reasons.append(
            f"{field}: confidence {result.confidence:.2f}"
            f" < {threshold:.2f}"
        )
route = Route.REVIEW if reasons else Route.AUTO_ACCEPT
```

Reasons name fields, never values. They show on the review screen and in logs without exposing patient data.

### 5.3 The LLM behind a Protocol

```python
class LLMExtractor(Protocol):
    def extract(
        self, text: str, fields: Sequence[Field]
    ) -> dict[Field, Candidate]:
        """Dates ISO 8601, phones +1XXXXXXXXXX, confidence 0-1.
        Omit a field rather than invent it."""
        ...
```

`FakeExtractor` implements it with heuristics and honest confidences (0.95 for a labeled value, 0.6 for a name guessed from a sign-off). The Unit 9 Anthropic or OpenAI adapter would implement the same method; `build_extractor()` in `app/main.py` is the only place that changes. This is how you keep building while the vendor review runs.

### 5.4 Corrections are audited, field by field

```python
for name, new in sorted(corrections.items()):
    current = sub.fields[name]
    if current.value == new:
        continue                      # re-typing is not a correction
    self._audit(sub.id, reviewer, "correct",
                field=name, old=current.value, new=new)
    sub.fields[name] = FieldResult(
        value=new, source=Source.HUMAN, confidence=1.0
    )
    sub.corrected_fields.append(name)
```

Corrections are validated first (a human can type a future DOB too), and an invalid correction writes nothing.

### 5.5 Requirements become tests

```python
def test_ac3_extractor_conflict_keeps_deterministic_and_flags(
    client: TestClient,
) -> None:
    """AC-3
    Given an intake where the regex and the LLM find different phone
      numbers
    When it is submitted
    Then the regex value is kept, the LLM value is shown as the
      conflicting value, and the intake goes to review.
    """
    body = submit(client, "04_two_phones.txt")
    phone = body["fields"]["phone"]
    assert phone["value"] == "+15550102222"
    assert phone["conflict_with"] == "+15550103333"
    assert body["status"] == "pending_review"
```

The docstring is copied from `requirements.md` section 8. When the customer changes a criterion, the document and the test change in the same pull request.

### 5.6 The metric the sponsor reads

```text
GET /metrics/summary
{"total": 6, "auto_accepted": 2, "sent_to_review": 4,
 "approved": 3, "rejected": 1, "auto_accept_rate": 0.333,
 "field_correction_rates": {"phone": 0.333, "email": 0.333, ...}}
```

Correction rates are per field, never per person, a change-management decision from discovery.

## 6. How It Connects to the Rest of the System

```text
 Unit 12 FDE delivery wraps everything:
   ├─ discovery decides which units you need at all
   ├─ API, validation, auth patterns (U1-U2) build the service
   ├─ data and storage choices (U3) appear in the handover
   ├─ UI for the review queue would follow U4-U5
   ├─ deploy in the customer's cloud account (U6) via their CI (U7)
   ├─ scale and resilience before production (U8)
   ├─ LLM adapters and RAG (U9-U10) plug in behind Protocols
   ├─ dashboards and SLOs (U11) are the pilot's evidence
   └─ ADRs, runbooks and status updates make it all handover-able
```

## FDE Scenario 11 — "Operations wants everything automated, Compliance wants a human on every record, and the board demo is in three weeks"

**Stakeholders:** the COO wants "no human touching intake"; the privacy officer wants "a person approves every record"; the demo date is fixed.

- *Clarify the real goals:* the COO wants staff hours back; the privacy officer wants no wrong data and an audit trail. These conflict only at the extremes.
- *Make the trade-off concrete:* show both on the same data. "With full review, staff time drops from 4 to 1.5 minutes per message. With confidence routing, 40% need no review at all, and every auto-accepted DOB and phone came from a tested rule."
- *Propose a staged option:* pilot with human review of 100% for two weeks while you measure what reviewers change; then auto-accept only categories with zero critical corrections, with the privacy officer's sign-off on the threshold (NFR-3).
- *Decide in writing:* the sponsor makes the call; record it in an ADR and the requirements change log. Do not let the engineer's threshold silently decide a policy question.
- *Protect the date:* cut scope, not quality: the CSV export moves to Should; the demo shows the review queue and the metric.
- *Communicate:* one status update with both positions, the options, your recommendation and the decision needed by a date.

## FDE Scenario 12 — "Our data cannot leave our cloud account, and security just blocked the LLM vendor"

**Stakeholders:** the privacy officer and the IT lead, two weeks into the pilot.

- *Acknowledge and get specifics:* which control failed? Data residency, missing agreement, subprocessors, retention, model training on customer data? Ask for the questionnaire findings in writing.
- *Keep delivering:* the Protocol design means the pilot continues with rules plus the fake extractor; human review covers the rest. Say this immediately so the project does not stall.
- *Options to bring back:* (a) the same models through the customer's own cloud (for example, a model service in their AWS account such as [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/) **[Provider-specific]**), keeping data in their account and region; (b) the vendor's enterprise terms (zero retention, regional processing) after legal review; (c) a self-hosted open-weight model in their VPC, with its accuracy and operations costs; (d) rules only, with more human review.
- *Answer the questionnaire properly:* data-flow diagram, what is sent (only the message text, never attachments), encryption, retention, logging without PHI, audit log, incident process.
- *Re-estimate honestly:* each option changes the timeline; update the RAID log and the status (likely AMBER).
- *What must be deterministic:* the data boundary. Enforce it with network egress rules and configuration, not with a promise.

## FDE Scenario 13 — "The pilot worked. Can we have it for all 5,000 users next month?"

**Stakeholders:** the COO, after a successful pilot at one clinic.

- *Celebrate, then scope:* "Yes, and here is what production needs." List the gaps between pilot and production: persistent database and backups, SSO instead of a name field, security review for production data, monitoring and alerts, on-call ownership, support and training for 5,000 users, rollback plan.
- *Check the numbers:* pilot volume vs production volume (load test, Unit 8), LLM cost per message × volume, rate limits, latency under load.
- *Re-run the eval:* pilot accuracy came from one clinic. Other clinics write differently; build a labeled set from each before raising automation.
- *Propose a phased rollout:* clinic by clinic (or 10% → 50% → 100%), with go/no-go criteria per phase (correction rates, incident count, queue age) and a feature flag to fall back to manual.
- *Change management:* train reviewers per clinic, publish a one-page guide, name local champions, keep the "per field, not per person" metric promise.
- *Ownership:* who runs it after you leave? Start the handover now (`docs/handover.md`), not in the last week.
- *Communicate:* a one-page production plan with phases, dates, risks, costs and the decisions needed. Say clearly what "next month" can and cannot include.

## Comprehension Questions

1. How does an FDE's main output differ from a solutions engineer's?
2. Why write a job-to-be-done statement instead of a feature list during discovery?
3. What is the difference between an assumption and an open question, and why give both owners and due dates?
4. What makes "the system handles missing data gracefully" a poor acceptance criterion? Rewrite it.
5. Why build a thin vertical slice before perfecting extraction accuracy?
6. In this project, why does the deterministic value win on conflict, and why is the conflict still flagged?
7. Why are correction metrics per field and not per staff member?
8. What changes between a pilot and production, beyond more users?

## Comprehension Answers

1. A solutions engineer secures the technical win before a sale, mostly with demos and prototypes. An FDE delivers a working solution after the sale, often writing production code in the customer's environment, and owns the customer outcome.
2. It keeps the focus on the outcome the user needs ("book patients without calling back"), which allows better solutions than the first feature someone asked for, and gives you a measurable success metric.
3. An assumption is something you act on as if true until confirmed; an open question is something you must find out before you can decide. Owners and due dates turn both into tracked work, so they get resolved instead of discovered as surprises later.
4. It is not testable: it names no input, action or observable result. Better: "Given an intake with no date of birth, when it is submitted, then it is placed in the review queue with the reason 'date_of_birth: required field missing'."
5. A slice through every layer exposes integration, access and data problems early, gives the customer something to react to, and makes the success metric measurable. Accuracy work without the slice may optimize the wrong thing.
6. Regex and parser results are deterministic, tested and auditable, so they are the safer default for formatted fields. But a regex can match the wrong number (two phones in one message), so the disagreement goes to a human instead of being resolved silently.
7. Per-field metrics show where the system needs work. Per-person metrics would turn the tool into staff monitoring, which discovery identified as a concern and which would hurt adoption; it is a Won't requirement.
8. Security review for production data, persistent storage and backups, real identity (SSO), monitoring and alerts, on-call ownership, support and training, cost at scale, a rollback plan, and an eval on data from all user groups.

## Interview Questions — Theory-Based

**Q1. What is a Forward Deployed Engineer, and how is it different from a software engineer or a consultant?**

- *Strong answer:* an engineer embedded with customers who builds the solution and owns the outcome. Unlike a product SWE, the work is shaped by one customer's problem and environment; unlike a consultant, the FDE writes and ships production code; unlike a solutions engineer, the work continues after the sale into production. The FDE also feeds product gaps back to the core team.
- *What it tests:* whether you understand the hybrid role.
- *Follow-up:* "What part of the role do you expect to find hardest?" (Answer honestly, with how you are preparing.)

**Q2. How do you run discovery with a new customer?**

- *Strong answer:* stakeholder map (sponsor, users, IT, security, veto holders); jobs to be done; shadow the current process and measure it; agree one business metric plus guardrails; list constraints (security, compliance, residency, integration, change management); collect real samples; end with written notes the customer confirms.
- *Follow-up:* "What if you only get one hour?" (Prioritize the sponsor's metric, the decision maker, data access and the main constraint.)

**Q3. How do you write requirements when things are ambiguous?**

- *Strong answer:* write what you know and mark what you do not: assumptions and open questions with owners and dates, a RAID log, MoSCoW priorities, explicit out-of-scope, and Given/When/Then acceptance criteria with concrete values. Version it and keep a change log. Turn criteria into tests.
- *What it tests:* comfort with ambiguity without freezing or guessing silently.

**Q4. How do you set acceptance criteria for an AI feature?**

- *Strong answer:* deterministic criteria for the deterministic parts (validation, routing, audit, privacy), and eval-based criteria for model behavior: a labeled set from real users, metrics per field or category, and a guardrail such as "zero auto-accepted wrong DOBs". Human review for low confidence. Re-run the eval when the model, prompt or data changes.
- *Follow-up:* "Can you trust the model's confidence score?" (Not directly; calibrate the threshold on labeled data.)

**Q5. How do you handle scope creep?**

- *Strong answer:* log each request, assess impact on dates, risk and the success metric, offer options (trade, defer, decline), get the decision from the scope owner, and update requirements and tests together. Make costs visible instead of saying no.

**Q6. What goes into a good status update for an executive?**

- *Strong answer:* BLUF first, an honest RAG status, outcomes done, next steps, risks with owners and dates, the agreed metric with caveats, and explicit asks. Short. Amber early is better than red as a surprise.

**Q7. What is an ADR and why use one on a customer project?**

- *Strong answer:* a short record of one significant decision: context, options, decision, consequences. It aligns the customer's engineers now and explains the design to whoever maintains it after handover. It also records who decided, which protects everyone when circumstances change.

**Q8. How do you prepare for a customer's security review?**

- *Strong answer:* start early; prepare a data-flow diagram, subprocessor list, encryption, access control, logging without sensitive data, retention and deletion, audit trail and incident process; map to the customer's framework; design so that a blocked component (for example, the LLM vendor) does not stop the whole project.

## Interview Questions — Application / Experience-Based

**A1. Tell me about a time you turned a vague business request into a technical solution.**

- *Cover:* the original ask, what you discovered, the real problem and metric, the options, what you built, how you verified it, the result.
- *Structure:* situation → discovery → requirement → design decision → delivery → result → lesson.
- *Personalize:* "`<<who asked, what they asked for>>`. By `<<how you discovered>>` I found the real problem was `<<problem with a number>>`. I proposed `<<solution>>` instead of `<<original ask>>` because `<<reason>>`. Result: `<<metric>>`."
- *Lab-honest version:* "In a simulated engagement for a fictional clinic, the ask was 'use AI on intake emails'. Discovery notes showed the real cost was retyping and DOB typos, so I designed rules first, LLM second, with human review, and wrote eight acceptance criteria that run as tests."
- *Follow-ups:* "What did you get wrong at first?" "How did you know it worked?"

**A2. Describe a time stakeholders disagreed about what to build.**

- *Cover:* the positions, the underlying goals, how you made trade-offs visible, who decided, how it was recorded.
- *Structure:* conflict → underlying goals → options with costs → decision owner → outcome.
- *Personalize:* "`<<stakeholder A>>` wanted `<<X>>`; `<<stakeholder B>>` wanted `<<Y>>`. I `<<how you showed the trade-off>>`, and `<<decider>>` chose `<<option>>`."
- *Lab-honest version:* use Scenario 11, clearly framed as "here is how I would handle it", not as a past event.
- *Follow-ups:* "What if the decider refused to decide?"

**A3. Tell me about delivering something with incomplete information or a fixed deadline.**

- *Cover:* what was unknown, how you tracked it (assumptions, spikes), what you cut, how you communicated risk.
- *Personalize:* "`<<deadline>>` with `<<unknowns>>`. I timeboxed `<<spike>>`, kept an assumptions list, and moved `<<feature>>` to a later phase. Delivered `<<what>>` on time."
- *Lab-honest version:* "In my project I kept the LLM behind a Protocol so work continued while vendor approval was pending, and the status update flagged it AMBER with a dated ask."
- *Follow-ups:* "Which assumption turned out wrong?"

**A4. Have you ever had to say no to a customer or a senior stakeholder?**

- *Cover:* the request, why it was a problem, the options you offered, the outcome, the relationship afterwards.
- *Personalize:* "`<<request>>` would have `<<cost/risk>>`. I offered `<<options>>`; they chose `<<option>>`."
- *Lab-honest version:* if you have no such example, say so, then walk through the trade-off framing in §3.8 with a concrete example from the project (scanned PDFs in the pilot).
- *Follow-ups:* "What if they insisted?"

**A5. Tell me about an incident that affected a customer or user.**

- *Cover:* detection, first message, containment, root cause, follow-up communication, prevention.
- *Personalize:* "`<<incident>>` affected `<<who>>`. I `<<first response within time>>`, contained it by `<<action>>`, and sent `<<summary>>`."
- *Lab-honest version:* "I have not handled a customer-facing incident in production. My approach follows the incident comms template: acknowledge fast, agreed cadence, facts separate from hypotheses, contain first, blameless summary." Then point to Unit 11 troubleshooting practice.
- *Follow-ups:* "What did you write in the first message?"

**A6. How would you approach your first 30 days as an FDE with a new customer?**

- *Cover:* access requests, discovery, quick win, requirements sign-off, first slice and demo, security review started, rhythm of status updates.
- *Personalize:* tie it to the company's product: "`<<product>>` would come in at `<<integration point>>`."
- *Lab-honest version:* walk through §4 (week 0 to week 3) as your plan.
- *Follow-ups:* "What would make you raise a red flag in week two?"

## Troubleshooting Scenarios

**T1. The demo fails in front of the customer.**

```text
SYMPTOM     live demo errors or hangs (VPN, API, data)
CHECK       is it the network, the dependency, or your code? do
            you have the fixed-data local run or a recording?
CAUSES      live dependency; changed data; untested demo path;
            expired credentials
FIX         switch to the fallback calmly; name what failed; offer
            a follow-up session with the live system
PREVENTION  scripted demo with fixed data and frozen clock; dry run
            the same morning; fallback ready; check credentials
```

**T2. The customer says "this is not what we asked for".**

```text
SYMPTOM     disagreement at a demo or acceptance meeting
CHECK       requirements version and change log; acceptance criteria
            signed by whom; who requested the disputed behavior
CAUSES      criteria too vague; wrong stakeholder signed off;
            requirement changed verbally; no demo until the end
FIX         walk the criteria together; log the gap as a change
            request with impact; agree priority with the sponsor
PREVENTION  concrete Given/When/Then; demo every slice; one owner
            for scope; change log for every change
```

**T3. Pilot users stop using the tool after a week.**

```text
SYMPTOM     review queue grows; staff retype manually again
CHECK       talk to users; correction rates per field; review time;
            any wrong auto-accepted values; training received?
CAUSES      one visible error destroyed trust; review UI slower
            than retyping; fear of monitoring; no local champion
FIX         fix the specific failure; raise the threshold; improve
            the review screen; communicate the change
PREVENTION  involve users in discovery; per-field metrics only;
            show failure handling in demos; champions per site
```

**T4. The project is stuck waiting for access or approvals.**

```text
SYMPTOM     days pass without VPN, repo, cloud or vendor approval
CHECK       who owns each request; is it on the RAID log; does the
            sponsor know it is blocking?
CAUSES      requests made late; wrong approver; unclear ask
FIX         escalate through the sponsor with a dated ask; keep
            building against fakes and local data
PREVENTION  access list in week zero; dependency in status updates
            as AMBER early; design with seams (Protocols, fakes)
```

**T5. Accuracy in production is lower than in the pilot.**

```text
SYMPTOM     correction rate rises after rollout to new sites
CHECK       correction rate by site/channel; new message formats;
            model or prompt version changes; threshold unchanged?
CAUSES      eval set from one site only; new templates; model
            update by the vendor; data drift
FIX         route affected categories to review; label samples from
            the new sites; re-tune threshold; pin model version
PREVENTION  eval set from every user group; per-site metrics;
            re-run evals on every model/prompt change
```

**T6. An executive escalates directly to your manager.**

```text
SYMPTOM     "the customer is unhappy" arrives from above
CHECK       last status update: was the risk visible? what changed?
            what does the exec actually need?
CAUSES      status too optimistic; bad news delivered late; asks
            buried in detail
FIX         call the exec: listen, restate, give facts, options and
            a date; follow up in writing
PREVENTION  BLUF and honest RAG every week; escalate risks early
            yourself, with a proposed mitigation
```

## Unit Practice Project — Intake Automation Kit

### Project Goal

Simulate an FDE engagement for Northwind Clinics (fictional) end to end:

- documents a customer would read: discovery notes, requirements, an ADR, a status update, a handover;
- a service that extracts intake fields from free text, deterministic first and LLM second, merges with precedence rules, validates, and routes to auto-accept or human review;
- an audit log of every reviewer correction and a metrics summary as the pilot's business evidence;
- acceptance tests named after the acceptance criteria, and a scripted demo.

### Architecture

```text
 POST /intake {text}
   │
   ▼
 extract_deterministic()  email · phone · policy · labeled dates
   │                      (confidence 1.0, never guesses)
 LLMExtractor.extract()   name · reason · unlabeled DOB · cross-check
   │                      (FakeExtractor; Unit 9 adapters plug in)
   ▼
 merge()          rules win · conflict_with recorded · gaps filled
   ▼
 validate_values()  required · formats · DOB/preferred date sanity
   ▼
 decide_route()   issues? conflicts? required conf < threshold?
   ├── no  → AUTO_ACCEPTED ──────────────┐
   └── yes → PENDING_REVIEW → /review-queue
                 └ approve (corrections, re-validated) / reject
   ▼                                     │
 InMemoryRepository: submissions + append-only audit log
   ▼
 GET /metrics/summary  auto vs review · field correction rates
```

### Requirements

1. `POST /intake` accepts `{"text", "channel"}` and returns 201 with every field's value, source, confidence and conflict, plus route, reasons and status.
2. Deterministic extraction handles email, five phone formats (normalized to `+1XXXXXXXXXX`), `ABC-1234567` policy numbers, and labeled DOB and preferred dates in five formats.
3. The LLM step goes through the `LLMExtractor` Protocol; `FakeExtractor` is the default.
4. Merge: deterministic wins; disagreements set `conflict_with`; LLM fills gaps; missing fields are explicit.
5. Validation: four required fields, formats, DOB not in the future or over 120 years ago, preferred date not in the past.
6. Routing: auto-accept only with no issues, no conflicts and every required field at or above the threshold.
7. Review: approve with validated corrections, or reject; 409 if not pending, 422 for invalid corrections, 404 for unknown IDs.
8. Audit: one entry per changed field (actor, field, old, new, time), plus system and approve/reject entries.
9. `GET /metrics/summary` reports counts, auto-accept rate and per-field correction rates.
10. No patient data in logs.

### Technical Requirements

- Python 3.12+, FastAPI, Pydantic v2, pydantic-settings (`APP_` prefix).
- In-memory repository (pilot scope; production would use Postgres from Unit 3).
- pytest with an injected frozen clock; ruff (76 columns), mypy strict.
- Documents in Markdown, 76 columns, fictional data only (555-01xx phones, example.com emails).

### Project Structure

{{tree projects/unit12-fde-delivery/solution}}

### Step-by-Step Implementation

1. **Read `docs/discovery_notes.md`.** Note the stakeholders, the metric and the two surprises.
   - *Why:* every later decision should trace back to something here.
2. **TODO 5: acceptance criteria.** Write AC-2 to AC-8 in `docs/requirements.md` in Given/When/Then form.
   - *Check:* compare with the test docstrings in `tests/acceptance/`.
3. **TODO 6: ADR decision.** Choose an option and write consequences.
4. **TODO 1: merge precedence** in `app/merge.py`.
   - *Test:* `pytest -q tests/unit/test_merge.py`.
5. **TODO 2: routing rule** in `app/routing.py`.
   - *Test:* `pytest -q tests/unit/test_routing.py`.
6. **TODO 3: audit corrections** in `app/service.py`.
   - *Test:* `pytest -q tests/unit/test_service_audit.py`.
7. **TODO 4: AC-7 acceptance test.** Turn the Given/When/Then into code.
   - *Test:* `pytest -q tests/acceptance`.
8. **Run the demo:** `python -m scripts.demo`. Read the output as the sponsor would.
9. **TODO 7: status update.** Pick the RAG status and write the BLUF from what the demo and the risks table show.
10. **Finish:** `pytest -q && ruff check . && ruff format --check . && mypy`.

### Starter Code

{{file projects/unit12-fde-delivery/starter/app/merge.py}}

{{file projects/unit12-fde-delivery/starter/app/routing.py}}

The starter also has TODOs in `app/service.py` (`_apply_corrections`), `tests/acceptance/test_acceptance_criteria.py` (AC-7), `docs/requirements.md` (acceptance criteria), `docs/adr/0001-extraction-approach.md` (decision and consequences) and `docs/status_update_week1.md` (RAG and BLUF). The task table is in the starter `README.md`.

### Practice Tasks

1. **Normal behavior:** submit each sample with curl or `/docs`; approve and reject from the queue; read the audit log.
2. **Validation:** an empty text, an extra JSON field, a correction with a future DOB, a correction to an unknown field.
3. **Threshold:** set `APP_AUTO_ACCEPT_THRESHOLD=0.95` and `0.6` (in `scripts/demo.py` or `.env`), rerun, and write one sentence for the sponsor on the trade-off. At 0.6, sample 05 is auto-accepted with the clinic's own email address: why is that a policy decision, not a tuning detail?
4. **Cross-check:** set `APP_LLM_CROSS_CHECK=false` and explain why sample 04 is now auto-accepted with the wrong phone; record it as a consequence in the ADR.
5. **Delivery exercises:**
   - write a change request for "also read scanned PDFs" with impact and options;
   - write an incident update for "a wrong DOB was auto-accepted";
   - write the product-feedback note for the forwarded-chain email bug.
6. **Extend:** a CSV export of approved intakes (FR-8); strip forwarded headers before extraction and add an acceptance test for sample 05's email.

### Hints

1. In `merge`, decide the deterministic case first; the conflict is just "the LLM also answered, with a different value".
2. Use `same_value()` so `" A@Example.com"` and `"a@example.com"` are not a conflict.
3. In `decide_route`, check confidence only for fields in `REQUIRED_FIELDS` that have a value; missing values are already reported by validation.
4. Format confidences with `:.2f` so the reason text matches the tests exactly.
5. In `_apply_corrections`, compare with the current value before writing anything: unchanged fields are not corrections.
6. For TODO 7, the risks table already contains a Red item. Is the overall status Green?

### Expected Behavior

```text
python -m scripts.demo
sample                   route        first reason
--------------------------------------------------------------------------
01_clean_email.txt       auto_accept  -
02_web_form.txt          auto_accept  -
03_missing_dob.txt       review       date_of_birth: required field missing
04_two_phones.txt        review       phone: extractors disagree (kept dete
05_messy_forwarded.txt   review       date_of_birth: confidence 0.60 < 0.85
06_future_dob.txt        review       date_of_birth: date of birth is in th
  ...
  auto-accept rate      33%

POST /review/4/approve {"corrections":{"phone":"123"}} -> 422 + issues
POST /review/4/approve (again, after approval)        -> 409
GET  /intake/999                                      -> 404
APP_LLM_CROSS_CHECK=false   -> sample 04 auto-accepted (no conflict seen)
APP_AUTO_ACCEPT_THRESHOLD=0.6 -> sample 05 auto-accepted, clinic email
```

### Testing Requirements

- **Acceptance (8):** AC-1 to AC-8, one test each, Given/When/Then docstrings copied from `requirements.md`.
- **Unit (41):** date and phone formats, deterministic vs LLM responsibilities, fake confidences; merge precedence (4); validation (5); routing (6); service and audit (6); API (5).

```bash
pytest -q
ruff check . && ruff format --check . && mypy
```

### Final Runnable Solution

{{files projects/unit12-fde-delivery/solution}}

### How to Run

```bash
cd projects/unit12-fde-delivery/solution
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && cp .env.example .env
uvicorn app.main:create_app --factory --reload   # :8000/docs
python -m scripts.demo
# submit a sample file as JSON (jq wraps the text safely)
jq -Rs '{text: .}' data/samples/04_two_phones.txt \
  | curl -s -X POST localhost:8000/intake \
      -H 'Content-Type: application/json' -d @-
curl -s localhost:8000/review-queue
curl -s localhost:8000/metrics/summary
```

### Verify the Solution

1. `pytest -q`: **49 passed** (8 acceptance, 41 unit); ruff, ruff format and mypy clean.
2. Starter: imports, ruff and mypy clean; **27 failed, 22 passed** until TODOs 1–4 are done.
3. `python -m scripts.demo`: 2 auto-accepted, 4 sent to review, auto-accept rate 33%.
4. Against the running server, submit `data/samples/04_two_phones.txt`, approve it with `{"reviewer": "desk.jo", "corrections": {"phone": "+15550103333"}}`, then `GET /intake/{id}/audit` shows `desk.jo` changing `phone` from `+15550102222` to `+15550103333`.
5. The uvicorn log shows `intake id=… route=… reasons=…` lines and no names, dates or phone numbers.
6. Every acceptance criterion in `docs/requirements.md` has a test with the same ID.

### Project Interview Debrief

1. **Why not let the LLM extract everything?**
   A wrong DOB or phone is costly, formatted fields are easy to extract deterministically and test exhaustively, and no vendor was approved yet. The LLM adds value where language understanding is needed (name, reason) and as a cross-check. ADR-0001 records the options and the decision.
2. **Why is the threshold configuration and not a constant?**
   It is a business policy that trades staff time against risk. The practice manager owns it (NFR-3); the engineer provides the data (correction rates) to set it.
3. **How do the acceptance tests help with the customer?**
   They make "done" objective. Each test carries the agreed Given/When/Then text, so a disputed behavior can be checked in minutes, and a changed criterion changes the test in the same review.
4. **What would you change before 5,000 users?**
   Postgres with backups and an append-only audit table, SSO for reviewer identity, the real LLM adapter after security approval, load and cost tests, dashboards and alerts on queue age and correction rates, an eval set from every clinic, a phased rollout with a manual fallback, and a completed handover.
5. **What did the messy sample teach you?**
   The first email in a forwarded chain is the clinic's own address, so a correct-looking value was wrong. Review routing caught it this time, but the fix belongs upstream (strip forwarded headers) and in the product feedback: a real pattern from discovery, not a hypothetical.
