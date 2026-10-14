# Unit 6 Project — Deployable Inventory API (Docker, K8s, AWS)

A small FastAPI service built to be operated, not just run:
12-factor settings (`APP_*`), JSON logs on stdout, liveness vs
readiness endpoints, graceful shutdown, a multi-stage non-root
image, a compose stack with Postgres, and Kubernetes manifests
(kustomize base + dev overlay) for EKS. Policy tests check the
Dockerfile, compose file and manifests without Docker or a cluster.

```
ALB ─► Service :80 ─► pods :8000 (2..10, HPA) ─► Postgres (RDS)
        /health/live   process up, no dependencies
        /health/ready  SELECT 1 + not draining, else 503
```

## Run locally (no containers)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload   # :8000/docs
pytest -q && ruff check . && mypy
```

## Run with Docker Compose (API + Postgres 18)

```bash
GIT_SHA=$(git rev-parse --short HEAD) docker compose up --build
curl -s localhost:8000/health/ready     # {"status":"ready",...}
curl -s localhost:8000/version
docker compose stop db                  # ready -> 503, live -> 200
```

## Run on a local cluster (kind)

```bash
docker build -t inventory-api:dev .
kind create cluster --name inventory
kind load docker-image inventory-api:dev --name inventory
kubectl apply -k k8s/overlays/dev
kubectl -n inventory rollout status deploy/inventory-api
kubectl -n inventory port-forward svc/inventory-api 8080:80
```

The dev overlay uses SQLite in each pod's `/tmp`, so every pod
has its own data. That is a smoke test, not a deployment.

## Verify

- `pytest -q`: 35 passed (app, Kubernetes policy, container policy).
- Optional, if installed: `kustomize build k8s/base | kubeconform
  -strict -summary` validates against the Kubernetes schemas.
