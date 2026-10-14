# ADR-0001: Extraction approach — rules first, LLM second, human review

- Status: Proposed
- Deciders: FDE, K. Ito (IT lead), L. Moreno (practice manager)
- Consulted: R. Diaz (privacy officer)

## Context

We must turn free-text intake messages into 7 structured fields.
Some fields have strict formats (email, phone, dates, policy
number). Others need language understanding (name, reason for
visit). A wrong DOB or phone is costly and erodes staff trust
(requirements.md NFR-1). No LLM vendor is approved yet (Q-1).

## Options considered

1. **Pure rules (regex and parsers).** Cheap, fast, fully testable,
   no vendor. Fails on names and reasons written in free text;
   brittle on messy messages.
2. **Pure LLM.** Handles any wording. Probabilistic: can return a
   plausible but wrong DOB; needs a vendor agreement before real
   data; per-message cost; harder to audit.
3. **Rules first, LLM for the rest, human review on doubt.**
   Deterministic extraction for formatted fields, LLM for the
   others, a merge step where rules win on conflict and conflicts
   are flagged, then validation and confidence-based routing.

## Decision

<!-- TODO(6): choose one option and say why in 2-4 sentences. Tie
the reason to the context above (NFR-1 accuracy, vendor not yet
approved, auditability), not to personal preference. State the
threshold and what happens on a conflict. -->

TODO(6)

## Consequences

<!-- TODO(6): list positive and negative consequences, and at least
one follow-up action with a trigger ("revisit if ..."). -->

TODO(6)
