# Unit 6 Starter — Deployable Inventory API (Docker, K8s, AWS)

A small FastAPI service that must be packaged and operated:
12-factor settings (`APP_*`), JSON logs on stdout, liveness vs
readiness, graceful shutdown, a container image, a compose stack
with Postgres, and Kubernetes manifests for EKS. Policy tests check
the Dockerfile, compose file and manifests without Docker or a
cluster.

```
ALB ─► Service :80 ─► pods :8000 (2..10, HPA) ─► Postgres (RDS)
        /health/live   process up, no dependencies
        /health/ready  SELECT 1 + not draining, else 503
```

## Your tasks

The items API, logging, settings, compose file and most manifests
already work. Complete the TODOs (`grep -rn "TODO(" .`):

| # | File | Task |
|---|------|------|
| 1 | `app/health.py` | readiness: draining, `SELECT 1`, 503 |
| 2 | `app/main.py` | mark draining in the lifespan shutdown |
| 3 | `Dockerfile` | multi-stage build (builder venv → runtime) |
| 4 | `Dockerfile` | non-root numeric `USER` |
| 5 | `k8s/base/deployment.yaml` | startup, liveness, readiness probes |
| 6 | `k8s/base/deployment.yaml` | resource requests and limits |
| 7 | `k8s/base/hpa.yaml` | `scaleTargetRef` and CPU metric |
| 8 | `tests/test_k8s_policy.py` | policy: image pinned, not `:latest` |
| 9 | `tests/test_k8s_policy.py` | policy: HPA targets the Deployment |

Done when `pytest -q` shows 35 passed and `ruff check .` and `mypy`
are clean. Order that works well: 1, 2 (app tests), 3, 4
(container policy), 5, 6, 7 (Kubernetes policy), then 8, 9.
For TODO 8 and 9, also break the manifest on purpose and watch your
test fail: a policy test that cannot fail is worthless.

## Run locally (no containers)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:create_app --factory --reload   # :8000/docs
pytest -q && ruff check . && mypy
```

## Run with Docker Compose (after TODO 3-4)

```bash
GIT_SHA=$(git rev-parse --short HEAD) docker compose up --build
curl -s localhost:8000/health/ready
docker compose stop db                  # ready -> 503, live -> 200
```

## Run on a local cluster (kind, after TODO 5-7)

```bash
docker build -t inventory-api:dev .
kind create cluster --name inventory
kind load docker-image inventory-api:dev --name inventory
kubectl apply -k k8s/overlays/dev
kubectl -n inventory rollout status deploy/inventory-api
kubectl -n inventory port-forward svc/inventory-api 8080:80
```
