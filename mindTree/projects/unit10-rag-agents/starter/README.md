# Unit 10 Starter — Support Assistant (RAG + Tools + Agent)

A support assistant that answers from a markdown knowledge base with
citations, abstains when it does not know, and runs a bounded agent
that can look up orders and propose refunds. Pure Python retrieval:
no vector database and no network needed. Adapters target the
Anthropic Messages API and the OpenAI Responses API; tests use fakes
and stub clients only.

```
POST /ask       question ─► permission filter ─► BM25 + vectors ─► RRF
                ─► rerank ─► abstain? ─► answer with [doc#chunk]
POST /agent/run message ─► LLM ⇄ tools under guards ─► answer + trace
POST /approvals/{id}  a second human approves a pending refund
```

## Your tasks

Loading, chunking, BM25, the hashing embedder, the tools, the API
and the OpenAI adapter already work. Complete the TODOs that make the
system safe and grounded (`grep -rn "TODO(" app`):

| # | File | Task |
|---|------|------|
| 1 | `app/rag/retriever.py` | Reciprocal Rank Fusion (`rrf`) |
| 2 | `app/rag/retriever.py` | permission filter by role |
| 3 | `app/rag/answer.py` | abstain below the relevance threshold |
| 4a | `app/tools/registry.py` | expose only the role's tools |
| 4b | `app/tools/registry.py` | refuse tool calls the role may not make |
| 5 | `app/tools/support.py` | large refunds wait for human approval |
| 6 | `app/agent/loop.py` | run guards: turns, timeout, token budget |
| 7 | `app/agent/loop.py` | call guards: repeats, max tool calls |
| 8 | `app/agent/anthropic_llm.py` | neutral messages -> Messages API |

Done when `pytest -q` shows 69 passed. A good order: 1, 2, 3
(`pytest -q tests/test_rag.py`), 4, 5 (`tests/test_tools.py`),
6, 7 (`tests/test_agent.py`), 8 (`tests/test_adapters.py`), then the
API and eval tests.

## Run

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # APP_PROVIDER=fake: fully offline
uvicorn app.main:create_app --factory --reload   # :8000/docs
pytest -q && ruff check . && mypy
python -m evals.retrieval_eval
```

Demo tokens (dev only): `t-alice`, `t-bob` (customers), `t-sam`,
`t-pat` (support agents). Send `Authorization: Bearer t-alice`.

## Verify by hand

1. `POST /ask` as `t-bob` with "goodwill store credit for late
   delivery": no `refund-exceptions-internal` source. As `t-sam`: it
   is the top citation.
2. `POST /ask` with "What is the capital of France?": `abstained`.
3. `POST /agent/run` as `t-sam`: "Please refund $300 on ORD-1002"
   returns a `pending_approvals` id. Approving it as `t-sam` gives
   403 (four-eyes); as `t-pat` it pays exactly once.
