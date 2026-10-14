# Handover — Intake Automation Pilot

Audience: Northwind IT (K. Ito) and the vendor support engineer.

## 1. What it is

A FastAPI service that extracts 7 fields from intake text, routes
each intake to auto-accept or a human review queue, records an
audit log and reports pilot metrics. See README.md and ADR-0001.

## 2. Ownership after handover

| Area | Owner | Escalation |
|---|---|---|
| Service operation | Northwind IT | FDE (until 2026-12-15) |
| Threshold changes | Practice manager | Sponsor |
| LLM vendor and prompts | Northwind IT | Vendor account team |
| Data retention | Privacy officer | — |

## 3. Runbook (short)

- **Start:** uvicorn app.main:create_app --factory (port 8000).
- **Health:** GET /health returns {"status": "ok"}.
- **Queue growing:** check GET /metrics/summary. A sudden drop in
  auto-accept rate usually means a new message format or an LLM
  outage (fields come back empty, so everything is reviewed: safe).
- **Wrong value auto-accepted:** raise the threshold
  (APP_AUTO_ACCEPT_THRESHOLD), restart, then add the message to the
  eval set and file a bug with the audit entry ID.
- **Logs:** contain IDs and counts only. Never add field values.

## 4. Configuration

| Variable | Default | Meaning |
|---|---|---|
| APP_AUTO_ACCEPT_THRESHOLD | 0.85 | Min confidence for required fields |
| APP_LLM_CROSS_CHECK | true | LLM also checks regex fields |
| APP_EXTRACTOR | fake | Which LLM adapter to use |

## 5. Handover checklist

- [x] Code in the customer's GitLab; CI runs ruff, mypy, pytest
- [x] Acceptance tests mapped to requirements.md section 8
- [x] ADR-0001 recorded
- [x] Runbook reviewed with K. Ito
- [ ] LLM adapter enabled after vendor approval (Q-1)
- [ ] Persistent database and SSO (phase 2)
- [ ] Two support engineers have run the demo themselves
- [ ] Access for the FDE removed after 2026-12-15

## 6. Known limitations

- In-memory storage: data is lost on restart (pilot only).
- Reviewer identity comes from the request body, not SSO.
- Forwarded chains: the first email found may be the clinic's own.
- English only; no attachments.

## 7. Product feedback sent

- Strip forwarded headers before extraction (seen in 6 of 40
  samples).
- Booking system API would remove the CSV step.
