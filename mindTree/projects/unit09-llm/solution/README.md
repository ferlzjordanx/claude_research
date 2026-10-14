# Unit 9 Project — Ticket Triage Service (LLM)

A FastAPI service that classifies support tickets with an LLM and
treats the model as an unreliable dependency: structured output
validated by Pydantic, timeouts, bounded retries with backoff, one
repair attempt, a deterministic fallback, business rules in code,
token and cost tracking, and an offline eval that gates CI.

```
POST /triage {"text": "..."}
  -> prompt (version, <ticket> delimiters)
  -> LLMClient: fake | anthropic | openai  (APP_LLM_PROVIDER)
  -> validate -> retry / repair / fallback -> business rules
  -> {"result": {...}, "meta": {prompt_version, model, tokens,
      cost_estimate_usd, fallback_used, attempts, ...}}
```

## Run (no API key needed)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                 # APP_LLM_PROVIDER=fake
uvicorn app.main:create_app --factory --reload
curl -s localhost:8000/triage -H 'content-type: application/json' \
  -d '{"text": "Checkout is down for all users!"}'
```

## Use a real provider

```bash
# Anthropic (default model claude-opus-5-5)
APP_LLM_PROVIDER=anthropic APP_ANTHROPIC_API_KEY=sk-ant-... \
  uvicorn app.main:create_app --factory
# OpenAI (you must choose the model ID)
APP_LLM_PROVIDER=openai APP_OPENAI_API_KEY=sk-... \
  APP_OPENAI_MODEL=<model-id> uvicorn app.main:create_app --factory
```

## Test, lint, eval

```bash
pytest -q                 # 56 tests, offline (fakes and stubs)
ruff check . && ruff format --check . && mypy
python -m evals.run_eval  # golden set; exit 1 below threshold
```

The fake provider is a keyword heuristic. The eval passing with it
proves the harness works, not that a model is good. Run the eval
against the real provider before changing the prompt, the model or
the schema, and compare with the previous run.

## Layout

- `app/llm/base.py`: `LLMClient` Protocol, `LLMResult`, errors
- `app/llm/anthropic_client.py`: `messages.parse(output_format=)`
- `app/llm/openai_client.py`: `responses.parse(text_format=)`
- `app/llm/fake.py`: scripted fake for tests and offline runs
- `app/triage.py`: schema, prompt, call policy, business rules
- `app/main.py`: FastAPI factory, `POST /triage`, `GET /health`
- `evals/`: golden set and CI-friendly eval runner
