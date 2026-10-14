# Unit 12 Project — Intake Automation Kit (FDE engagement)

A simulated Forward Deployed Engineering engagement, end to end, for
a fictional customer, Northwind Clinics. The code is one part; the
documents in `docs/` are the other half of the deliverable.

```
free text ─► regex/parsers ─► LLMExtractor ─► merge ─► validate
             (formats)        (name, reason)  (rules   (Pydantic)
                                               win)        │
                     auto-accept ◄── route (confidence) ───┘
                     review queue ──► approve/reject + audit log
                                  ──► GET /metrics/summary
```

## What is in the box

| Path | What it is |
|---|---|
| `docs/discovery_notes.md` | Stakeholders, process, metrics, constraints |
| `docs/requirements.md` | Scope, FR/NFR, RAID, acceptance criteria |
| `docs/adr/0001-...md` | Rules + LLM + human review decision |
| `docs/status_update_week1.md` | BLUF status with RAG |
| `docs/handover.md` | Runbook, ownership, checklist |
| `app/` | FastAPI service (factory `create_app`) |
| `tests/acceptance/` | One test per AC in requirements.md |
| `tests/unit/` | Extractors, merge, validation, routing, API |
| `scripts/demo.py` | Scripted demo over `data/samples/*.txt` |

All customer names, messages, phones (555-01xx) and emails
(example.com/org/net) are fictional.

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload   # :8000/docs
python -m scripts.demo                           # scripted demo
```

## Test and verify

```bash
pytest -q          # 49 passed (8 acceptance + 41 unit)
ruff check . && ruff format --check . && mypy
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/intake` | Submit `{"text": ..., "channel": ...}` |
| GET | `/intake/{id}` | One submission with field provenance |
| GET | `/intake/{id}/audit` | Audit entries for one submission |
| GET | `/review-queue` | Pending human review |
| POST | `/review/{id}/approve` | `{"reviewer", "corrections", "note"}` |
| POST | `/review/{id}/reject` | `{"reviewer", "reason"}` |
| GET | `/metrics/summary` | Auto vs review, field correction rates |

## Where a real LLM plugs in

`app/extraction/llm.py` defines the `LLMExtractor` Protocol and a
deterministic `FakeExtractor`. The Anthropic and OpenAI adapters
from Unit 9 implement the same `extract(text, fields)` method using
structured output plus Pydantic validation. Wire one in
`build_extractor()` in `app/main.py` and add its name to
`Settings.extractor`. Nothing else changes. Do not send real patient
data to any vendor until the customer's privacy officer has approved
it (requirements.md Q-1).

## Pilot limitations (by design)

In-memory storage, reviewer name in the request body instead of SSO,
English text only. See `docs/handover.md`.
