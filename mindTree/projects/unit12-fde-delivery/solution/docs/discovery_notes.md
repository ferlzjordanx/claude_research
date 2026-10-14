# Discovery Notes — Northwind Clinics Intake Pilot

Northwind Clinics is a fictional customer. All names, numbers and
quotes in this kit are invented for training.

- Dates: 2026-10-05 to 2026-10-07 (on site, two clinics)
- FDE: `<<your name>>`
- Sources: 5 interviews, 2 hours shadowing the front desk, 40
  anonymized sample messages provided by the practice manager

## 1. Stakeholder map

| Person (role) | Wants | Influence | Interest |
|---|---|---|---|
| Dr. A. Patel (COO, sponsor) | Cut front-desk overtime | High | High |
| L. Moreno (practice manager) | Fewer booking errors | Med | High |
| Front-desk team (6 people) | Less retyping, no blame | Low | High |
| K. Ito (IT lead) | Nothing breaks, no new vendors | High | Med |
| R. Diaz (privacy officer) | No PHI leaves approved systems | High | Med |

Decision maker for scope: Dr. Patel. Veto on data handling: R. Diaz.
Day-to-day contact: L. Moreno.

## 2. Job to be done

"When a patient emails or fills in the web form, I want their
details in the booking system correctly, so I can book them without
calling back." (front desk)

## 3. Current process (as observed)

    patient email / web form
      -> shared inbox (about 180 messages/day across 4 clinics)
      -> staff reads, retypes 7 fields into the booking system
      -> missing info: staff phones the patient (about 1 in 4)
      -> booking confirmed by email

Measured during shadowing (small sample, treat as estimates):

- 3 to 6 minutes per message to read and retype;
- about 25% of messages miss at least one required field;
- the practice manager estimates 1 in 20 bookings has a typo in DOB
  or phone, found later at check-in.

## 4. Success metrics (proposed, to confirm with sponsor)

| Metric | Baseline | Pilot target |
|---|---|---|
| Messages needing no human edit | 0% | >= 40% |
| Field correction rate in review | n/a | measured, trending down |
| Wrong DOB/phone reaching booking | ~5% | <= 1% |
| Time per reviewed message | 3-6 min | <= 1.5 min |

## 5. Constraints

- **Security/privacy:** messages contain PHI. Data must stay in the
  customer's cloud account; no PHI in logs; audit who changed what.
- **Compliance:** US healthcare privacy rules apply; any LLM vendor
  needs an approved agreement before real data is sent. Until then:
  synthetic and anonymized data only.
- **Data residency:** US region only.
- **Integration:** the booking system has a CSV import, no API.
- **Change management:** the front desk fears "the robot" will be
  used to measure them. Metrics are per field, never per person.
- **Access:** customer VPN, no admin rights, their GitLab CI.

## 6. Quotes worth keeping

- "If it's wrong even once on a date of birth, my team will stop
  trusting it." (practice manager)
- "Don't make me approve a new vendor this quarter." (IT lead)
- "I need a number I can show the board in six weeks." (COO)

## 7. Surprises

- Many emails are forwarded chains: the first email address in the
  text is often the clinic's own, not the patient's.
- Relatives book for patients ("booking for my dad"): two phone
  numbers in one message is common.
