# Unit 12 Starter — Intake Automation Kit (FDE engagement)

A simulated Forward Deployed Engineering engagement for a fictional
customer, Northwind Clinics. You finish both halves of the
deliverable: the documents a customer reads and the code that
proves them.

```
free text ─► regex/parsers ─► LLMExtractor ─► merge ─► validate
             (formats)        (name, reason)  (rules   (Pydantic)
                                               win)        │
                     auto-accept ◄── route (confidence) ───┘
                     review queue ──► approve/reject + audit log
                                  ──► GET /metrics/summary
```

## Your tasks

Extraction, validation, the API and most tests already work.
Complete the TODOs (`grep -rn "TODO(" .`):

| # | File | Task |
|---|------|------|
| 1 | `app/merge.py` | precedence: rules win, flag conflicts |
| 2 | `app/routing.py` | auto-accept vs review, with reasons |
| 3 | `app/service.py` | audit each reviewer correction |
| 4 | `tests/acceptance/test_acceptance_criteria.py` | write AC-7 |
| 5 | `docs/requirements.md` | acceptance criteria AC-2 to AC-8 |
| 6 | `docs/adr/0001-extraction-approach.md` | decision + consequences |
| 7 | `docs/status_update_week1.md` | RAG status and BLUF |

Suggested order: read `docs/discovery_notes.md` first, then 5 and 6
(decide before you build), then 1, 2, 3, 4, and finally 7 after
running the demo. Done when `pytest -q` shows 49 passed and every
doc TODO is replaced with your own words.

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload   # :8000/docs
python -m scripts.demo                           # after TODO 1-3
```

## Test

```bash
pytest -q          # starter: 27 failed, 22 passed
pytest -q tests/unit/test_merge.py      # TODO(1)
pytest -q tests/unit/test_routing.py    # TODO(2)
pytest -q tests/unit/test_service_audit.py  # TODO(3)
ruff check . && ruff format --check . && mypy
```

## Where a real LLM plugs in

`app/extraction/llm.py` defines the `LLMExtractor` Protocol and a
deterministic `FakeExtractor`. The Anthropic and OpenAI adapters
from Unit 9 implement the same `extract(text, fields)` method. Wire
one in `build_extractor()` in `app/main.py`. Do not send real
patient data to any vendor without the customer's approval.

All customer names, messages, phones (555-01xx) and emails
(example.com/org/net) are fictional.
