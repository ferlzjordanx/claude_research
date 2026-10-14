# Unit 10 Project — Support Assistant (RAG + Tools + Agent)

A support assistant that answers from a markdown knowledge base with
citations, abstains when it does not know, and runs a bounded agent
that can look up orders and propose refunds. Pure Python retrieval:
no vector database and no network needed. Works with the Anthropic
Messages API and the OpenAI Responses API through adapters; tests
use fakes and stub clients only.

```
POST /ask       question ─► permission filter ─► BM25 + vectors ─► RRF
                ─► rerank ─► abstain? ─► answer with [doc#chunk]
POST /agent/run message ─► LLM ⇄ tools (search_kb, get_order,
                issue_refund) under guards ─► answer + trace
POST /approvals/{id}  a second human approves a pending refund
```

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # APP_PROVIDER=fake: fully offline
uvicorn app.main:create_app --factory --reload   # :8000/docs
```

Demo tokens (dev only): `t-alice`, `t-bob` (customers), `t-sam`,
`t-pat` (support agents). Send `Authorization: Bearer t-alice`.

```bash
curl -s localhost:8000/ask -H 'Authorization: Bearer t-alice' \
  -H 'content-type: application/json' \
  -d '{"question": "Is return shipping free?"}'
```

### Real providers [Provider-specific]

```bash
export ANTHROPIC_API_KEY=...       # read by the anthropic SDK
APP_PROVIDER=anthropic uvicorn app.main:create_app --factory
export OPENAI_API_KEY=...          # read by the openai SDK
APP_PROVIDER=openai APP_OPENAI_MODEL=<model-id> \
  uvicorn app.main:create_app --factory
```

The Anthropic default model is `claude-opus-5-5`. Take the OpenAI
model ID from <https://platform.openai.com/docs/models>.

## Test and verify

```bash
pytest -q                 # 69 passed
ruff check . && ruff format --check . && mypy
python -m evals.retrieval_eval            # recall@3, MRR, leaks
python -m evals.retrieval_eval --min-recall 0.95; echo $?   # 1
```

## Layout

| Path | What it does |
|------|--------------|
| `app/rag/` | load, chunk, BM25, hashing embedder, hybrid + RRF, answers |
| `app/tools/` | tool registry (schema, validation, authz) and tools |
| `app/agent/` | neutral types, bounded loop, fake + provider adapters |
| `app/main.py` | FastAPI factory: `/ask`, `/agent/run`, `/approvals` |
| `evals/` | offline retrieval eval with a CI exit code |
| `data/kb/` | 8 help-center docs with `audience` front matter |
