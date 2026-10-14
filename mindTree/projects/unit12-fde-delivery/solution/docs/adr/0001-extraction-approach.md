# ADR-0001: Extraction approach — rules first, LLM second, human review

- Status: Accepted (2026-10-09)
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

Option 3. Rules own every field with a format. The LLM fills gaps
and cross-checks. Any conflict, validation issue or required field
below the confidence threshold (0.85, NFR-3) goes to a human.

## Consequences

- Positive: the riskiest fields (DOB, phone) are deterministic and
  unit-tested; the pilot can start with a fake extractor while the
  vendor review runs; every value records its source.
- Negative: two extraction paths to maintain; LLM self-reported
  confidence is not calibrated, so the threshold must be tuned on
  labeled data; cross-checking costs extra tokens (can be switched
  off with APP_LLM_CROSS_CHECK=false).
- Follow-up: calibrate the threshold with the 200-message eval set;
  revisit if correction rates for rule-owned fields exceed 5%.
