# Unit 2 Project — Secured Customers API (FastAPI)

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
