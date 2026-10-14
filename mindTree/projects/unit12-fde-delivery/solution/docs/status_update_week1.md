# Status Update — Intake Pilot, Week 1 (to 2026-10-09)

To: Dr. A. Patel (sponsor) · Cc: L. Moreno, K. Ito, R. Diaz

**Overall: AMBER** — on track for the week-3 demo; LLM vendor
approval (Q-1) is not yet scheduled and blocks real-data testing.

## Bottom line

The intake service works end to end on synthetic data: 2 of 6 demo
messages are auto-accepted, 4 go to review with a clear reason. We
need a decision on the LLM vendor by 2026-10-14 to stay on plan.

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
