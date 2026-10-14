# Requirements — Intake Automation Pilot (Northwind Clinics)

Version 0.3 · Status: agreed with L. Moreno, pending sponsor sign-off
Owner: FDE `<<your name>>` · Last change: 2026-10-09

## 1. Problem

Front-desk staff retype seven fields from every intake message into
the booking system. It takes 3 to 6 minutes per message and causes
typos in dates of birth and phone numbers.

## 2. Users

- **Front-desk reviewer:** checks and corrects queued intakes.
- **Practice manager:** watches quality and the review queue.
- **Sponsor (COO):** reads the weekly metrics summary.

## 3. Scope

In scope (pilot, 6 weeks, 1 clinic):

- free-text email and web-form text submitted to an API;
- extraction of the 7 fields in FR-1;
- review queue with approve/reject and corrections;
- audit log and metrics summary.

Out of scope (for now):

- writing into the booking system (CSV export is phase 2);
- reading the shared inbox automatically;
- attachments, scanned forms, languages other than English;
- persistent production database and SSO (phase 2).

## 4. Functional requirements (MoSCoW)

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Extract the 7 fields (see section 4a) | Must |
| FR-2 | Name, DOB, phone and reason are required | Must |
| FR-3 | Validate formats and date sanity | Must |
| FR-4 | Auto-accept only complete, confident, conflict-free | Must |
| FR-5 | Review queue with approve (with corrections) and reject | Must |
| FR-6 | Audit log: who, field, old value, new value, when | Must |
| FR-7 | Metrics: auto vs review counts, field correction rates | Must |
| FR-8 | CSV export of approved intakes | Should |
| FR-9 | Suggested reply email for missing fields | Could |
| FR-10 | Per-staff productivity metrics | Won't |

## 4a. Fields

patient_name, date_of_birth, phone, email, insurance_policy_number,
reason_for_visit, preferred_date. Required: the first three plus
reason_for_visit.

## 5. Non-functional requirements

- **NFR-1 Accuracy first:** a wrong DOB or phone must not be
  auto-accepted knowingly; when unsure, route to a human.
- **NFR-2 Privacy:** no PHI in logs or metrics; data stays in the
  customer's account; synthetic data until the vendor agreement.
- **NFR-3 Tunable:** the auto-accept threshold is configuration,
  changed only with the practice manager's agreement.
- **NFR-4 Latency:** p95 under 5 s per intake (LLM call included).
- **NFR-5 Replaceable model:** the LLM sits behind one interface.

## 6. Assumptions (A) and open questions (Q)

| ID | Item | Owner | Due |
|---|---|---|---|
| A-1 | Pilot volume <= 300 messages/day | L. Moreno | confirmed |
| A-2 | Policy numbers look like ABC-1234567 | K. Ito | 10-12 |
| A-3 | Booking system CSV import is enough for phase 2 | K. Ito | 10-16 |
| A-4 | Slash dates are month-first (US only) | L. Moreno | confirmed |
| Q-1 | Which LLM vendor is already approved, if any? | R. Diaz | 10-14 |
| Q-2 | Who may reject an intake, and what next? | L. Moreno | 10-12 |
| Q-3 | Retention period for raw message text? | R. Diaz | 10-16 |

## 7. Risks (RAID summary)

| Risk | Impact | Mitigation |
|---|---|---|
| Vendor approval slips | No real-data tests | Fake LLM; rules first |
| Staff distrust | Low adoption | Human review; per-field metrics |
| Forwarded chains | Wrong email | Review; strip headers (phase 2) |

## 8. Acceptance criteria

Each criterion is an executable test in
tests/acceptance/test_acceptance_criteria.py with the same ID.

- **AC-1** Given an intake email with name, DOB, phone and reason
  clearly stated, when it is submitted, then it is auto-accepted,
  does not appear in the review queue, and every field records its
  source and confidence.
- **AC-2** Given an intake with no date of birth, when it is
  submitted, then it is placed in the review queue with the reason
  "date_of_birth: required field missing".
- **AC-3** Given an intake where the regex and the LLM find
  different phone numbers, when it is submitted, then the regex
  value is kept, the LLM value is shown as the conflicting value,
  and the intake goes to review.
- **AC-4** Given a messy forwarded email where the name is only
  guessed from the sign-off, when it is submitted, then it goes to
  review with a confidence reason for that field.
- **AC-5** Given an intake whose date of birth is in the future,
  when it is submitted, then it is not auto-accepted and the reason
  names the field.
- **AC-6** Given an intake in the review queue, when reviewer
  "desk.jo" approves it with a corrected phone number, then the
  audit log shows desk.jo, the field, the old value and the new
  value, and the intake leaves the queue as approved.
- **AC-7** Given two auto-accepted intakes and two reviewed intakes,
  one of which needed a phone correction, when the sponsor opens the
  metrics summary, then it shows 2 auto-accepted, 2 sent to review,
  a 50% auto-accept rate and a 50% phone correction rate.
- **AC-8** Given an intake containing a name, DOB, phone and email,
  when it is submitted and reviewed, then no application log line
  contains any of those values.

Pilot exit criterion (eval-based, measured on 200 anonymized
messages labeled by the front desk): zero auto-accepted intakes with
a wrong DOB or phone, and >= 40% auto-accepted overall.

## 9. Change log

| Version | Date | Change | Agreed by |
|---|---|---|---|
| 0.1 | 10-07 | First draft after discovery | — |
| 0.2 | 10-08 | Added AC-8 (privacy officer) | R. Diaz |
| 0.3 | 10-09 | FR-10 moved to Won't (staff concern) | L. Moreno |
