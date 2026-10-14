# Unit 2 Project (STARTER) — Secured Customers API (FastAPI)

CRUD REST API with Pydantic v2 validation, dependency injection,
service/repository layers, JWT authentication, role-based
authorization and RFC 9457 problem-details errors.

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                       # dev settings
uvicorn app.main:create_app --factory --reload
# open http://127.0.0.1:8000/docs
pytest -q
```

Demo users (dev only): `admin / admin-password` (admin) and
`viewer / viewer-password` (viewer).

## Your tasks

Implement every `# TODO` in `app/core/security.py`, `app/api/deps.py`,
`app/services/customer_service.py`, `app/api/routes_customers.py`,
`app/models/customer.py` and `app/core/errors.py`; then write the
tests marked `# TODO`. Run `pytest -q` until everything passes.
