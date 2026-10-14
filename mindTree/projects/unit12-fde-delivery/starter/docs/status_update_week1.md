# Status Update — Intake Pilot, Week 1 (to 2026-10-09)

To: Dr. A. Patel (sponsor) · Cc: L. Moreno, K. Ito, R. Diaz

**Overall: TODO(7)** (GREEN, AMBER or RED, plus one line why)

## Bottom line

<!-- TODO(7): BLUF in 2-3 sentences for the sponsor: where we are,
the one decision you need from them, and by when. Use the risks
table below to pick the RAG status honestly. -->

TODO(7)

## Done this week

- Discovery: 5 interviews, front-desk shadowing, 40 samples.
- Requirements v0.3 with 8 acceptance criteria (all automated).
- ADR-0001: rules first, LLM second, human review on doubt.
- Working API: intake, review queue, audit log, metrics.

## Next week

- Label 200 anonymized messages with the front desk (eval set).
- Draft the CSV export format with K. Ito (FR-8).
- Demo the review queue to two front-desk staff for feedback.

## Risks and asks

| Item | RAG | Ask / owner |
|---|---|---|
| LLM vendor approval | Red | R. Diaz: book review by 10-14 |
| Eval set labeling time | Amber | L. Moreno: 2 h of staff time |
| Booking CSV format | Green | K. Ito: sample file by 10-16 |

## Metrics (synthetic demo data, not real performance)

Auto-accept rate 33% (target 40%). Corrections needed most on DOB
and phone in forwarded or relative-booked messages.
