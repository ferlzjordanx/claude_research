# Unit 3 Project (STARTER) — Orders Data Layer (SQLAlchemy 2.x + PostgreSQL)

Schema with constraints and indexes, Alembic migrations, repositories,
transactional order placement with an atomic stock decrement,
N+1-free reads, and Redis cache-aside with graceful degradation.

## Run (SQLite, zero setup)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed
uvicorn app.main:create_app --factory --reload
pytest -q
```

## Run against PostgreSQL + Redis

```bash
docker compose up -d
cp .env.example .env
alembic upgrade head          # create schema via migrations
python -m app.seed
uvicorn app.main:create_app --factory --reload
TEST_DATABASE_URL=postgresql+psycopg://orders:orders@localhost:5432/orders \
  pytest -q                   # includes the concurrency test
python -m scripts.explain_demo   # index vs no index query plans
```

## Your tasks

1. Implement the TODOs in `app/repositories.py`, `app/cache.py`,
   `app/services/catalog.py`, `app/services/orders.py`, `app/main.py`.
2. Generate the first migration:
   `alembic revision --autogenerate -m "initial schema"`, review it,
   then `alembic upgrade head` and `alembic downgrade base`.
3. Implement the concurrency test in `tests/test_concurrency.py`.
