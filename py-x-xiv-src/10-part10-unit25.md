# Part X — DevOps and Cloud

**What this part teaches.** How a Python/FastAPI system leaves your laptop and runs the same way everywhere. Unit 25 packages the API, worker and their dependencies (PostgreSQL, Redis, Kafka) into containers with deterministic local startup. Unit 26 automates quality and delivery: lint, types, tests, integration tests, image builds, deployment checks and rollback. Unit 27 runs the stack on AWS with managed databases, secrets, logging and the compute model that fits each workload, including Bedrock for AI.

**Why it matters.** "Works on my machine" failures, slow and flaky pipelines, leaked secrets, connection storms against the database, and deployments nobody can roll back are some of the most common causes of production incidents and wasted engineering time. Interviewers for backend and FDE roles expect you to reason about images, environments, pipelines and cloud services as confidently as you reason about code.

**Where it appears.** Every production service: the Dockerfile in the repo, the `compose.yaml` new engineers run on day one, the CI workflow that gates every pull request, and the ECS service or Lambda function that serves traffic. FDEs often deploy into a customer's AWS account under that customer's constraints (private subnets, no internet egress, mandated scanners).

**Connections.** Builds on earlier units on FastAPI internals (ASGI, lifespan, Uvicorn/Gunicorn workers), PostgreSQL/SQLAlchemy, Redis, Kafka and pytest. Feeds every later part: the LLM client (Part XI) needs secrets and egress, the RAG service (Part XII) needs PostgreSQL with pgvector, and the agent platform (Part XIV) needs workers, queues and observability.

## Unit 25 — Docker and Local Production Environments

### 1. Learning Objectives

By the end of this unit you will be able to:

1. **Explain** images, layers, containers, networks and volumes, and what the kernel features (namespaces, cgroups, union filesystems) actually provide.
2. **Write** a multi-stage Dockerfile for a FastAPI service with `uv`, producing a small, non-root, reproducible runtime image, and **measure** the effect of each decision on image size and build time.
3. **Optimize** layer caching by ordering `COPY` instructions and using BuildKit cache mounts, and **explain** why a one-line source change should not reinstall dependencies.
4. **Implement** liveness and readiness endpoints in FastAPI and Docker `HEALTHCHECK`/Compose `healthcheck` definitions, and **distinguish** "process alive" from "ready for traffic".
5. **Design** a `compose.yaml` that runs API, worker, PostgreSQL (pgvector), Redis and Kafka (KRaft) with deterministic startup (`depends_on` with `condition: service_healthy`), migrations, named volumes and isolated networks.
6. **Choose** a production server command (`fastapi run`, `uvicorn` with workers, or Gunicorn with Uvicorn workers) and **configure** graceful shutdown, signal handling and proxy headers.
7. **Debug** common container failures: exits on start, `ModuleNotFoundError`, connection refused between services, permission errors on volumes, OOM kills and slow builds.

### 2. Prerequisite Knowledge

- **FastAPI runtime.** FastAPI is an ASGI application (built on Starlette). An ASGI server (Uvicorn) runs the event loop, accepts connections and calls the app. The `lifespan` context manager creates shared resources (DB engine, Redis client, HTTP clients) at startup and closes them at shutdown.
- **Processes and signals.** `SIGTERM` asks a process to stop gracefully, and `SIGKILL` cannot be caught. The process with PID 1 in a container receives signals from `docker stop`. If that process is a shell that doesn't forward signals, your app never sees `SIGTERM` and is killed after the grace period.
- **Python packaging.** `pyproject.toml` declares dependencies. A lockfile (`uv.lock`) pins every transitive dependency with hashes. A virtual environment isolates installed packages. Wheels are prebuilt distributions; source distributions may need compilers.
- **Networking basics.** Ports, DNS, `localhost` meaning "this network namespace", and TCP connection refused vs timeout.

**Refresher: what `localhost` means in a container.** Inside a container, `localhost` is the container itself, not your laptop and not another container. Services on the same Compose network reach each other by **service name** (`postgres:5432`). This one fact explains a large share of beginner container bugs.

### 3. Mental Model

An **image** is a read-only, layered snapshot of a filesystem plus metadata (entrypoint, environment, user). A **container** is a running process (or process tree) started from an image, with its own isolated view of the system and a thin writable layer on top.

```
Dockerfile ──build──▶ Image (layers, content-addressed, immutable)
                         │
                         ├── run ──▶ Container A (process + writable layer + namespaces + cgroup limits)
                         └── run ──▶ Container B
Volumes  ──mount──▶ persistent data outside the container's writable layer
Networks ──attach─▶ DNS by service name, isolated from other stacks
```

It is like a class and its instances: the image is the class definition, built once and versioned. Containers are instances, cheap to create and destroy, and you never patch an instance by hand. Persistent state belongs in volumes or managed services, never in the container's writable layer.

A local production environment is a **small, honest copy of production topology**. The same images, the same startup ordering rules and the same health checks, with the same failure modes visible on your laptop.

```
compose.yaml
 ├── postgres (pgvector) ── healthcheck: pg_isready ──┐
 ├── redis ──────────────── healthcheck: redis-cli ping ┤
 ├── kafka (KRaft) ──────── healthcheck: broker API ────┤
 ├── migrate (one-shot) ─── depends_on healthy postgres ┤
 ├── api ────────────────── depends_on migrate completed + healthy deps; readiness /health/ready
 └── worker ─────────────── depends_on healthy kafka + postgres
```

### 4. Comprehensive Theory

#### 4.1 Images, Layers, Containers, Networks, Volumes

**Images and layers.** Each filesystem-changing Dockerfile instruction (`RUN`, `COPY`, `ADD`) creates a layer: a tar of changed files, identified by a content hash. Layers are shared across images and cached across builds. An image manifest lists the layers plus a config (env, user, entrypoint, exposed ports). Tags (`supportdesk-api:1.4.2`) are mutable pointers. **Digests** (`@sha256:…`) are immutable, so production deployments should reference digests or immutable tags.

**Containers.** At runtime, the container engine (containerd/runc) creates:

- **Namespaces**: isolated views of PIDs, network interfaces, mounts, hostname, users and IPC.
- **cgroups**: resource limits and accounting (memory, CPU shares/quotas, PIDs).
- **A union/overlay filesystem**: image layers (read-only) plus a writable layer that is discarded when the container is removed.

Containers are **not VMs**. They share the host kernel, so isolation is weaker than a hypervisor's. Security depends on running as non-root, dropping capabilities, using read-only filesystems where possible, and keeping images patched.

**Networks.** The default bridge network on Linux gives containers private IPs and NAT to the outside. User-defined networks, which Compose creates per project, add **DNS by service name** and isolation between projects. Port publishing (`ports: "8000:8000"`) maps a host port to a container port. It's only needed for traffic from outside the Docker network. Service-to-service traffic uses the internal port and doesn't need publishing.

**Volumes.** *Named volumes* are managed by Docker, persist across container recreation, and are best for databases locally. *Bind mounts* map a host path into the container. They suit live-reload development, but they're a common source of permission problems and of accidental differences from production. *tmpfs* mounts give in-memory scratch space.

**Common mistakes.** Storing data in the writable layer (lost on `docker compose down`). Using `latest` tags. Publishing database ports to `0.0.0.0` on shared machines. Assuming `depends_on` waits for readiness (it only waits for *start* unless you use `condition: service_healthy`).

**Interview perspective.** "Container vs image?" checks whether you understand immutability, layers and runtime isolation, not just Docker commands.

#### 4.2 Multi-Stage Python Builds

**Definition.** A Dockerfile with several `FROM` stages. Early stages build (install compilers, resolve dependencies, compile wheels). The final stage copies only the runtime artifacts.

**Why it exists.** Build tools (gcc, headers, uv's cache, test dependencies) are not needed at runtime. Leaving them in the image adds hundreds of MB, increases attack surface and slows pulls and cold starts.

**How it works with uv.**

```dockerfile
# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /uvx /bin/        # pin uv (or by digest)
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
# 1) Dependencies only: cached unless pyproject.toml / uv.lock change
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable
# 2) Project source: cheap layer that changes often
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM python:${PYTHON_VERSION}-slim AS runtime
RUN groupadd --system app && useradd --system --gid app --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/app /app/app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status==200 else 1)"]
CMD ["fastapi", "run", "app/main.py", "--port", "8000", "--proxy-headers"]
```

**Key lines.**

- `uv sync --locked`: fails if `uv.lock` is stale relative to `pyproject.toml`, so the image is exactly what the lockfile says (reproducibility). `--frozen` would skip that check. Prefer `--locked` in CI and Docker.
- `--no-install-project` in the first sync installs only third-party dependencies, so a source change doesn't invalidate the dependency layer.
- `--no-editable` installs the project as a regular package so the `.venv` is self-contained and copyable.
- `UV_COMPILE_BYTECODE=1` precompiles `.pyc` files at build time, which makes startup faster.
- BuildKit `--mount=type=cache` keeps the uv download cache between builds *without* putting it in the image.
- The runtime stage has no compiler, no uv and no cache, and it runs as a **non-root** user with a fixed UID (important for volume permissions and Kubernetes `runAsNonRoot`).
- **Same Python minor version** in builder and runtime stages, because compiled extensions and the venv's interpreter path depend on it.

**Base image choices.**

| Base | Size | Pros | Cons |
|---|---|---|---|
| `python:3.13-slim` (Debian) | ~45 MB compressed | glibc → manylinux wheels just work; familiar | Some CVEs from Debian packages |
| `python:3.13-alpine` | smaller | Tiny | musl libc: many wheels unavailable (musllinux improving), slower builds, subtle DNS/locale differences |
| Distroless / Chainguard Python | small, no shell | Minimal attack surface | Harder debugging (no shell); different update cadence |

Default to `-slim`. Choose distroless when the security team requires minimal images, and plan for debugging with ephemeral debug containers.

**Trade-offs.** Multi-stage builds add Dockerfile complexity. Reproducibility requires pinning base images (tag + digest), uv version and lockfile.

#### 4.3 Dependency Installation and Image Size

**Why images get big:** build tools left in, pip/uv caches inside layers, dev dependencies (pytest, mypy) in production, large ML libraries (torch alone can be gigabytes), copying `.git`, `.venv` or test data into the build context, and deleting files in a *later* layer (the data still exists in the earlier layer).

**Techniques.**

1. **`.dockerignore`**: exclude `.git`, `.venv`, `__pycache__`, `tests/` (if not needed), `*.ipynb`, local data. This also speeds up the context upload.
2. **Separate dependency groups** in `pyproject.toml` (`[dependency-groups] dev = [...]`), with `--no-dev` in the image.
3. **Multi-stage builds** so compilers never reach the runtime stage.
4. **Cache mounts** instead of cache directories in layers.
5. **Avoid heavy dependencies in the API image**: put embedding models in a separate worker image, or call an embedding API.
6. **Inspect**: `docker image ls`, `docker history <image>`, and `dive` to see what each layer adds.

**Layer cache rules.** The cache key for `COPY` is the checksum of the copied files. For `RUN` it's the command string plus the parent layer. Once a layer changes, every later layer rebuilds. **Order instructions from least to most frequently changed**: base image → system packages → dependency manifests → dependency install → source code.

```
Bad:   COPY . .          → RUN uv sync   (any source edit reinstalls all dependencies)
Good:  COPY uv.lock pyproject.toml → RUN uv sync --no-install-project → COPY . . → RUN uv sync
```

#### 4.4 Health and Readiness Checks

**Definitions.**

- **Liveness**: "is this process stuck beyond recovery?" If it fails, the orchestrator **restarts** the container.
- **Readiness**: "can this instance serve traffic right now?" If it fails, the orchestrator **stops routing** traffic to it but doesn't restart it.
- **Startup** (Kubernetes): "has it finished starting?" Protects slow starters from premature liveness failures.

**Design rules.**

- Liveness must be cheap and must **not** depend on external services. If PostgreSQL blips and liveness checks the DB, every API container restarts at once, which turns a dependency hiccup into a full outage.
- Readiness checks the dependencies the instance **needs to serve requests** (DB pool can get a connection, Redis ping), with **short timeouts**. It reports "not ready" during startup and during graceful shutdown (drain).
- Health endpoints are excluded from auth and from verbose access logs, and return small JSON payloads.

**FastAPI implementation.**

```python
# app/api/health.py
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.deps import get_engine, get_redis, get_lifecycle
from app.core.lifecycle import Lifecycle

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    # No I/O: if the event loop can run this, the process is alive.
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    redis: Annotated[Redis, Depends(get_redis)],
    lifecycle: Annotated[Lifecycle, Depends(get_lifecycle)],
) -> dict[str, object]:
    if lifecycle.draining:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "draining"}

    async def check_db() -> bool:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis.ping())

    results: dict[str, bool] = {}
    for name, check in {"postgres": check_db, "redis": check_redis}.items():
        try:
            results[name] = await asyncio.wait_for(check(), timeout=1.0)
        except Exception:
            results[name] = False
    if not all(results.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if all(results.values()) else "not_ready", "checks": results}
```

**Docker `HEALTHCHECK` vs Compose `healthcheck` vs orchestrator probes.** The Dockerfile `HEALTHCHECK` sets a default health status (`healthy`/`unhealthy`) that Docker and Compose use. Compose `healthcheck:` overrides it per service. ECS uses container health checks (from the task definition) plus **ALB target-group health checks**. Kubernetes ignores Docker `HEALTHCHECK` and uses its own probes. Know which system acts on which signal.

#### 4.5 Docker Compose for Service Stacks

**Definition.** A declarative file (`compose.yaml`; the Compose Specification, Docker Compose v2 plugin `docker compose`) describing services, networks, volumes, configs and secrets for one application stack.

**Deterministic startup.**

- `depends_on: {postgres: {condition: service_healthy}}` waits for the dependency's healthcheck to pass.
- `condition: service_completed_successfully` waits for a one-shot job, such as migrations, to exit 0.
- Apps should still **retry connections on startup** (with backoff), because health in Compose doesn't guarantee health forever, and production orchestrators don't order startup at all.

**The full SupportDesk stack.**

```yaml
# compose.yaml
name: supportdesk

x-app-env: &app-env
  DATABASE_URL: postgresql+psycopg://app:app@postgres:5432/supportdesk
  REDIS_URL: redis://redis:6379/0
  KAFKA_BOOTSTRAP_SERVERS: kafka:9092
  LOG_LEVEL: INFO

services:
  postgres:
    image: pgvector/pgvector:0.8.1-pg17        # pin; includes the pgvector extension
    environment:
      POSTGRES_DB: supportdesk
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app                   # local only; never real secrets in compose files
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d supportdesk"]
      interval: 5s
      timeout: 3s
      retries: 20
    networks: [backend]

  redis:
    image: redis:8.2-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    networks: [backend]

  kafka:
    image: apache/kafka:4.1.0                  # KRaft mode, single node for local dev
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 > /dev/null 2>&1"]
      interval: 10s
      timeout: 10s
      retries: 20
      start_period: 20s
    volumes:
      - kafkadata:/var/lib/kafka/data
    networks: [backend]

  migrate:
    build: { context: ., target: runtime }
    image: supportdesk-app:dev
    command: ["alembic", "upgrade", "head"]
    environment: *app-env
    depends_on:
      postgres: { condition: service_healthy }
    networks: [backend]
    restart: "no"

  api:
    image: supportdesk-app:dev
    environment: *app-env
    ports: ["127.0.0.1:8000:8000"]             # bind to localhost only
    depends_on:
      migrate:  { condition: service_completed_successfully }
      redis:    { condition: service_healthy }
      kafka:    { condition: service_healthy }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2).status==200 else 1)"]
      interval: 10s
      timeout: 3s
      retries: 6
      start_period: 15s
    stop_grace_period: 30s
    networks: [backend, edge]

  worker:
    image: supportdesk-app:dev
    command: ["python", "-m", "worker.main"]
    environment: *app-env
    depends_on:
      migrate: { condition: service_completed_successfully }
      kafka:   { condition: service_healthy }
    stop_grace_period: 45s
    networks: [backend]

volumes:
  pgdata: {}
  redisdata: {}
  kafkadata: {}

networks:
  backend: {}
  edge: {}
```

**Developer ergonomics.** A `compose.override.yaml` (loaded automatically) can add bind-mounted source and `fastapi dev` with reload for local work. Alternatively, use Compose's `develop.watch` to sync files. Use **profiles** (`profiles: ["observability"]`) for optional services such as an OpenTelemetry collector and Grafana. Keep secrets out of the YAML: use an `.env` file that is git-ignored, or Compose `secrets:` that mount files.

#### 4.6 Production Server Command

**Options.**

| Command | Process model | When |
|---|---|---|
| `fastapi run app/main.py --port 8000 --proxy-headers` | Uvicorn, 1 process by default (`--workers N` available) | Containers where the orchestrator scales by adding containers (one process per container is simplest) |
| `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*'` | Uvicorn's own multiprocess manager | Single VM / fewer, larger containers |
| `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 --graceful-timeout 30` | Gunicorn master + Uvicorn workers | Mature process management (worker recycling via `--max-requests`); the Uvicorn worker class is also available from the `uvicorn-worker` package [Version-dependent] |

**Principles.**

- **One process per container** is the default in orchestrated environments. Scale with more tasks/pods, and let the orchestrator handle restarts and placement. Multi-worker containers make sense when cores per container > 1 and per-container overhead matters.
- **CPU-bound work** blocks the event loop. Offload it to worker processes, not more async.
- **Exec form** (`CMD ["fastapi", "run", …]`) makes your server PID 1 so it receives `SIGTERM`. The shell form (`CMD fastapi run …`) wraps it in `/bin/sh -c`, which may not forward signals. If you need a shell script entrypoint, end it with `exec "$@"`. For zombie reaping with child processes, use `docker run --init` or `tini`.
- **Graceful shutdown**: on `SIGTERM`, Uvicorn stops accepting new connections, waits for in-flight requests, then runs lifespan shutdown (close pools, flush telemetry). The orchestrator's grace period (`stop_grace_period`, ECS `stopTimeout`, Kubernetes `terminationGracePeriodSeconds`) must exceed your longest request plus cleanup.
- **Proxy headers**: behind a load balancer, enable `--proxy-headers` and restrict `--forwarded-allow-ips` to trusted proxies so `request.client` and the scheme are correct without trusting arbitrary clients.
- **Don't run `--reload` in production.**

### 5. Internal Mechanics

#### 5.1 What `docker build` does

```
CLI sends build context (respecting .dockerignore) to BuildKit
→ parse Dockerfile into a DAG of steps (stages can build in parallel)
→ for each step: compute cache key (parent + instruction + file checksums for COPY)
     hit  → reuse layer
     miss → execute in a temporary container, snapshot filesystem diff as a new layer
→ final stage layers + config → image manifest → tag
→ (push) upload missing layers to registry, by digest
```

Only the final stage's layers ship. Builder layers stay in the local build cache.

#### 5.2 What `docker run` / Compose `up` does

```
pull image (if missing) → create container: overlay fs (image layers + writable layer)
→ create namespaces (pid, net, mnt, uts, ipc, user optional), cgroup with limits
→ attach to network(s) → DNS entries for service name → mount volumes
→ exec ENTRYPOINT/CMD as configured USER → PID 1 in the container
→ healthcheck loop runs the probe command inside the container on interval
→ on stop: send SIGTERM to PID 1 → wait grace period → SIGKILL
```

#### 5.3 Inside the Python container at startup

```
fastapi run → Uvicorn imports app.main → module-level code executes (keep it light)
→ Uvicorn starts event loop → ASGI lifespan "startup": create engine, Redis, Kafka producer, HTTP client
→ bind socket, accept connections → readiness becomes 200 once dependencies are reachable
→ on SIGTERM: lifespan sets draining=True (readiness 503), Uvicorn finishes in-flight requests,
   lifespan "shutdown": close producer (flush), dispose engine, close clients → exit 0
```

### 6. Implementation Examples

#### Example 1 — Minimal: Containerize a FastAPI app

```toml
# pyproject.toml
[project]
name = "supportdesk"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi[standard]==0.141.1",   # pin exact; FastAPI is pre-1.0
  "pydantic>=2.13,<3",
  "pydantic-settings>=2.6,<3",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.13", "mypy>=1.18", "httpx>=0.28"]
```

```python
# app/main.py
from fastapi import FastAPI

app = FastAPI(title="SupportDesk")


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}
```

```
# .dockerignore
.git
.venv
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
tests/
*.ipynb
.env
```

Build and run:

```bash
uv lock                                   # create/refresh uv.lock locally, commit it
docker build -t supportdesk-app:dev .
docker run --rm -p 127.0.0.1:8000:8000 supportdesk-app:dev
curl -s localhost:8000/health/live
docker image ls supportdesk-app:dev       # check size
docker history supportdesk-app:dev        # what each layer adds
```

#### Example 2 — Realistic: Settings, lifespan-managed resources, readiness and the full stack

```python
# app/core/settings.py
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: PostgresDsn
    redis_url: RedisDsn
    kafka_bootstrap_servers: str = "kafka:9092"
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # reads env vars; fails fast at startup if required ones are missing
```

```python
# app/core/lifecycle.py
from dataclasses import dataclass


@dataclass
class Lifecycle:
    draining: bool = False
```

```python
# app/main.py
import signal
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from app.api import health
from app.core.lifecycle import Lifecycle
from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,              # detect dead connections after DB restarts/failovers
        pool_recycle=1800,
    )
    redis = Redis.from_url(str(settings.redis_url), socket_timeout=2, socket_connect_timeout=2)
    lifecycle = Lifecycle()
    app.state.engine, app.state.redis, app.state.lifecycle = engine, redis, lifecycle
    try:
        yield
    finally:
        lifecycle.draining = True        # readiness → 503 while we clean up
        await redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="SupportDesk", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
```

```python
# app/core/deps.py
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.lifecycle import Lifecycle


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_lifecycle(request: Request) -> Lifecycle:
    return request.app.state.lifecycle
```

The `draining` flag in the `finally` block is set when lifespan shutdown begins. For true drain-before-stop on ECS/Kubernetes, also deregister from the load balancer first (the platform does this when the task/pod starts terminating). You can add a short `preStop` sleep so in-flight load-balancer state catches up before Uvicorn stops accepting.

Deterministic local startup:

```bash
docker compose build
docker compose up -d --wait          # --wait blocks until services are healthy (or fails)
docker compose ps                    # STATUS shows (healthy)
docker compose logs -f api worker
docker compose down                  # keeps named volumes
docker compose down -v               # also deletes data volumes (reset)
```

#### Example 3 — Production-oriented: Worker with graceful shutdown, startup retries, resource limits and a smoke test

```python
# worker/main.py
import asyncio
import logging
import signal

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.settings import get_settings

log = logging.getLogger("worker")


async def connect_with_retry(consumer: AIOKafkaConsumer, attempts: int = 20) -> None:
    delay = 0.5
    for attempt in range(1, attempts + 1):
        try:
            await consumer.start()
            return
        except KafkaConnectionError:
            log.warning("kafka not ready (attempt %d/%d), retrying in %.1fs", attempt, attempts, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 10)
    raise RuntimeError("Kafka unavailable after retries")


async def run() -> None:
    settings = get_settings()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    consumer = AIOKafkaConsumer(
        "kb.ingest.requested",
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id="ingestion-worker",
        enable_auto_commit=False,          # commit only after successful processing
        auto_offset_reset="earliest",
    )
    await connect_with_retry(consumer)
    try:
        while not stop.is_set():
            batch = await consumer.getmany(timeout_ms=1000, max_records=50)
            for _tp, records in batch.items():
                for record in records:
                    await handle(record.value)        # must be idempotent (redelivery happens)
            if batch:
                await consumer.commit()
    finally:
        await consumer.stop()                         # leaves the group cleanly → fast rebalance
        log.info("worker stopped cleanly")


async def handle(payload: bytes) -> None:
    ...


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
```

Resource limits in Compose (honored by `docker compose up`; deploy-time limits on ECS/Kubernetes are set in their own specs):

```yaml
  api:
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 512M }
    read_only: true                  # root filesystem read-only
    tmpfs: ["/tmp"]
    security_opt: ["no-new-privileges:true"]
    cap_drop: ["ALL"]
```

**Smoke test the stack in CI or locally** (pytest against the running Compose stack):

```python
# tests/smoke/test_stack.py
import httpx
import pytest

BASE = "http://127.0.0.1:8000"


@pytest.mark.smoke
def test_ready_reports_all_dependencies() -> None:
    r = httpx.get(f"{BASE}/health/ready", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"postgres": True, "redis": True}


@pytest.mark.smoke
def test_api_runs_as_non_root() -> None:
    import subprocess
    uid = subprocess.run(["docker", "compose", "exec", "-T", "api", "id", "-u"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert uid != "0"
```

### 7. Comparative Analysis

| Comparison | Key difference | When to use | Interview trap |
|---|---|---|---|
| Image vs container | Immutable template vs running instance with writable layer | Build once, run many | "I SSH into the container and fix it" |
| Container vs VM | Shared kernel, namespaces/cgroups vs hypervisor + guest kernel | Containers for app packaging; VMs for strong isolation/different kernels | "Containers are lightweight VMs" (security implications) |
| `COPY` vs `ADD` | Plain copy vs copy + URL fetch + tar auto-extract | `COPY` almost always | `ADD` surprises (auto-extraction, remote fetch without checksum) |
| `CMD` vs `ENTRYPOINT` | Default args vs fixed executable | `ENTRYPOINT` for the binary, `CMD` for defaults; or `CMD` alone | Shell form breaks signal handling |
| Named volume vs bind mount | Docker-managed vs host path | Volumes for DB data; bind mounts for dev hot reload | Permission/UID issues with bind mounts |
| Liveness vs readiness | Restart vs stop routing | Liveness: no deps; readiness: needed deps | DB check in liveness → restart storms |
| `depends_on` (start) vs `service_healthy` | Ordering vs readiness | Always `service_healthy` (+ app retries) | Assuming plain `depends_on` waits for readiness |
| slim vs alpine vs distroless | glibc vs musl vs no shell | slim default; distroless for hardening | Alpine wheel/musl surprises |
| `uv sync --locked` vs `--frozen` | Verify lock matches manifest vs trust lock | `--locked` in CI/Docker | Stale lockfiles silently shipping |
| `fastapi run` vs `uvicorn --workers` vs Gunicorn | 1 proc vs Uvicorn multiproc vs Gunicorn manager | One process per container under orchestrators | Many workers × many containers → DB connection explosion |

### 8. Failure Modes and Debugging

**Failure 1 — API container exits immediately.**

- SYMPTOM: `docker compose ps` shows `Exited (1)`.
- LIKELY CAUSE: missing required environment variable (Pydantic settings validation error), import error, wrong `CMD` path.
- INVESTIGATE: `docker compose logs api`; `docker compose run --rm api python -c "import app.main"`; `docker inspect --format '{{json .Config}}' supportdesk-app:dev`.
- FIX: Provide the variable; fix the module path.
- PREVENT: Settings validation at startup (fail fast, which is good), a CI smoke test that starts the stack.

**Failure 2 — `Connection refused` to PostgreSQL.**

- CAUSE: Using `localhost` in `DATABASE_URL` inside the container, or the app started before Postgres was ready.
- INVESTIGATE: `docker compose exec api getent hosts postgres`; check `depends_on` conditions; healthcheck status.
- FIX: Use the service name; `condition: service_healthy`; startup retries.

**Failure 3 — Every source edit triggers a full dependency reinstall (8-minute builds).**

- CAUSE: `COPY . .` before dependency installation; `.dockerignore` missing so `.git` changes bust the cache.
- INVESTIGATE: `docker build --progress=plain .` shows which step misses the cache.
- FIX: Reorder; add `.dockerignore`; cache mounts.

**Failure 4 — Container killed with exit code 137.**

- CAUSE: OOM kill (cgroup memory limit) or `SIGKILL` after the grace period.
- INVESTIGATE: `docker inspect -f '{{.State.OOMKilled}}' <container>`; memory metrics; whether shutdown exceeded `stop_grace_period`.
- FIX: Raise the limit or reduce memory (fewer workers, streaming instead of loading whole files); ensure exec-form CMD so `SIGTERM` reaches Python.

**Failure 5 — Permission denied writing to a volume.**

- CAUSE: The image runs as UID 10001 but the bind-mounted directory is owned by your host user (or root).
- FIX: Use named volumes, set ownership in the image (`--chown`), or align UIDs in development.

**Failure 6 — Image is 2.3 GB.**

- INVESTIGATE: `dive supportdesk-app:dev` or `docker history --no-trunc`.
- CAUSE: torch/sentence-transformers in the API image; build tools in the runtime stage; caches in layers.
- FIX: Split images per workload; multi-stage; call embedding APIs or use a dedicated worker image.

**Failure 7 — Kafka healthy but clients can't connect from the host.**

- CAUSE: Advertised listener is `kafka:9092`, which the host can't resolve.
- FIX: Add a second listener (`EXTERNAL://localhost:29092`) for host tools, or run tools inside the network (`docker compose exec kafka …`).

**Debugging toolkit.** `docker compose logs -f --tail=200`, `docker compose exec <svc> sh` (or `python`) on slim images, `docker inspect`, `docker stats`, `docker events`, `docker build --progress=plain --no-cache-filter <stage>`, `dive`, `docker compose config` (renders the effective config after overrides and env substitution).

### 9. Guided Practice

#### Level 1 — Concept Reinforcement

**1.1 Layer cache prediction.** For a given Dockerfile and a list of changes (edit `app/api/x.py`; add a dependency; change base image tag; touch README), predict which steps rebuild.
*Hints:* Cache keys depend on parents and copied file checksums. What's in your `.dockerignore`?

**1.2 Liveness or readiness?** Classify: event loop blocked for 60 s; DB unreachable; Redis unreachable for an optional cache; app is draining; migrations not applied.
*Hints:* Ask "would restarting help?" and "should traffic go here?"

#### Level 2 — Implementation

**2.1 Multi-stage image under 200 MB.**
- Objective: build the SupportDesk image with uv, non-root, healthcheck, `fastapi run`.
- Requirements: dependency layer cached across source edits; runtime image without uv/compilers.
- Constraints: Python 3.13 slim; pinned uv; `uv sync --locked`.
- Expected behavior: second build after a source edit takes < 10 s.
- Tests: script that edits a file, rebuilds, and asserts the dependency step is `CACHED`; `id -u` ≠ 0.
- Hints: `--no-install-project`; `.dockerignore`; `docker build --progress=plain`.

**2.2 Readiness with timeouts.** Implement `/health/ready` checking PostgreSQL and Redis with 1 s timeouts, returning 503 with per-check detail. Write pytest tests using dependency overrides to simulate failures.
*Hints:* `app.dependency_overrides[get_engine] = lambda: FailingEngine()`; use `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`.

#### Level 3 — Integration

**3.1 Full stack with deterministic startup.** Write `compose.yaml` for API, worker, PostgreSQL (pgvector), Redis, Kafka and a migration job. `docker compose up --wait` must succeed from a clean state (`down -v`) three times in a row. Add a smoke test that creates a ticket via the API and verifies the worker consumed the resulting event.
*Hints:* `service_completed_successfully` for migrations; Kafka KRaft single-node env; idempotent consumer.

#### Level 4 — Debugging / Production Scenario

**4.1 Diagnose this Dockerfile.**

```dockerfile
FROM python:latest
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y gcc
ENV DATABASE_PASSWORD=supersecret
CMD uvicorn app.main:app --reload --host 0.0.0.0 --workers 8
```

Find at least eight problems.
*Hints:* tag; order; cache; secrets in image layers (visible in `docker history`); root user; shell form; reload in production; workers vs reload conflict; no lockfile; build tools at runtime; no healthcheck; no `.dockerignore`.

**4.2 Restart storm.** During a 2-minute RDS failover, all API containers restarted repeatedly and the outage lasted 9 minutes. The health check configuration points liveness at `/health/ready`. Explain the chain of events and the fix.

### 10. Independent Implementation Project — SupportDesk Local Production Environment

**Goal.** A one-command, deterministic local environment for SupportDesk that mirrors production topology.

**Requirements.**

1. Multi-stage uv-based image shared by `api`, `worker` and `migrate`.
2. `compose.yaml` with PostgreSQL + pgvector, Redis, Kafka (KRaft), migration job, API and worker; named volumes; two networks; localhost-only published ports.
3. Liveness and readiness endpoints; Compose healthchecks; `docker compose up --wait` succeeds from clean.
4. Graceful shutdown for API and worker, verified by test.
5. `compose.override.yaml` for development (reload, bind mount); an `observability` profile with an OpenTelemetry collector + Grafana LGTM.
6. `Makefile` or `justfile`: `up`, `down`, `reset`, `logs`, `smoke`, `shell`.

**Technical requirements.** Python 3.13, FastAPI 0.14x (pinned), Pydantic 2.13, SQLAlchemy 2.0 async + psycopg 3, Alembic, redis-py asyncio, aiokafka, uv, Docker BuildKit, Compose v2.

**Suggested project structure.**

```
supportdesk/
├── Dockerfile  .dockerignore  compose.yaml  compose.override.yaml  Makefile
├── pyproject.toml  uv.lock  alembic.ini
├── app/  main.py  core/{settings.py,lifecycle.py,deps.py,logging.py}  api/health.py
├── worker/  main.py
├── migrations/  env.py  versions/0001_init.py
└── tests/  unit/test_health.py  smoke/test_stack.py  smoke/test_shutdown.py
```

**Milestones.** (1) Image + healthcheck. (2) Settings + lifespan resources. (3) Compose with healthy dependencies. (4) Migrations job. (5) Worker with graceful shutdown. (6) Override + profiles. (7) Smoke tests + Makefile.

**Testing requirements.** Unit tests for health endpoints with overrides. A smoke suite against the running stack. A shutdown test: send `SIGTERM` during a slow request, and assert the request completes and the exit code is 0. A build-cache test.

**Definition of done.** `make reset && make up && make smoke` passes three times consecutively. Image < 250 MB and non-root. No secrets in images (`docker history` clean). Source-only rebuild < 15 s.

**Optional extensions.** Distroless runtime variant. SBOM generation (`docker buildx build --sbom=true`) and provenance. Multi-arch build (amd64/arm64). Toxiproxy service to inject latency between API and PostgreSQL.

### 11. Testing Strategy

- **Unit tests** for health logic with FastAPI dependency overrides (no Docker needed).
- **Container build tests**: Dockerfile lint (`hadolint`), image size budget, non-root user, no secrets in history, cache behavior.
- **Integration tests** with real services: `testcontainers-python` (PostgreSQL with pgvector, Redis, Kafka) for repository and consumer tests in CI. Use the Compose stack for smoke tests.
- **Shutdown tests**: start the container, issue a slow request, `docker stop`, assert completion.
- **Security tests**: image vulnerability scan (Trivy/Grype), `no-new-privileges`, read-only root filesystem works.

```python
# tests/unit/test_health.py
import httpx
import pytest

from app.core.deps import get_engine, get_redis
from app.main import create_app


class FailingConn:
    async def __aenter__(self): raise ConnectionError("db down")
    async def __aexit__(self, *exc): return False

class FailingEngine:
    def connect(self): return FailingConn()

class OkRedis:
    async def ping(self) -> bool: return True


@pytest.mark.anyio
async def test_ready_returns_503_when_db_down() -> None:
    app = create_app()
    app.state.lifecycle = type("L", (), {"draining": False})()
    app.dependency_overrides[get_engine] = lambda: FailingEngine()
    app.dependency_overrides[get_redis] = lambda: OkRedis()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"] == {"postgres": False, "redis": True}
```

(`ASGITransport` doesn't run lifespan by default, which is why the test sets `app.state.lifecycle` directly. Use `asgi-lifespan`'s `LifespanManager` when you need lifespan in tests.)

### 12. Engineering Scenarios

**Scenario 1 — Slow onboarding (FDE).** A customer's team says new engineers take two days to get the service running. *Questions:* what fails, which services are needed, what's undocumented? *Expected reasoning:* Ask for the actual failure log first. Then provide a Compose stack with health-gated startup, seed data, `make up`, and a README with troubleshooting. Measure time-to-first-request before and after. Demonstrate in a 15-minute screen-share as evidence.

**Scenario 2 — Image too large for Lambda/fast autoscaling.** The image is 3 GB because of local embedding models. *Options:* split API and embedding worker images; use a managed embedding API; slim the base image. *Trade-offs:* latency and cost of API calls vs cold-start and scaling time; operational burden of GPU workers.

**Scenario 3 — Alpine or slim?** A security team mandates "minimal images". *Reasoning:* Alpine's musl causes wheel incompatibilities and subtle behavior differences. Propose `-slim` with automated scanning and patching, or distroless/Chainguard images with a debugging plan. Base the decision on CVE counts and operational cost, not image size alone.

**Scenario 4 — Health check flapping.** Readiness fails intermittently under load because the DB check times out when the pool is exhausted. *Reasoning:* Readiness reflects real capacity, so flapping indicates saturation. Fix pool sizing and slow queries. Consider a dedicated small pool for health checks, or a cached readiness result refreshed every few seconds, so health checks don't add load.

### 13. Interview Preparation

#### Quick Questions

**Q: Container vs image?**
*Strong answer:* An image is an immutable, layered filesystem plus config, addressed by digest. A container is a running process created from it, with namespaces, cgroup limits and a disposable writable layer.
*Why asked:* Baseline understanding. *Trap:* "A container is a small VM."

**Q: How do you make Docker builds fast?**
*Strong answer:* Order layers by change frequency, copy lockfiles before source, use BuildKit cache mounts and `.dockerignore`, and use multi-stage builds so heavy steps are isolated and cached.

**Q: What's the difference between a volume and a bind mount?**
*Strong answer:* Volumes are managed by Docker and portable, ideal for persistent service data. Bind mounts map host paths, which suits development but is tied to the host's filesystem and permissions.

#### Intermediate Questions

**Q: Design health checks for a FastAPI service that depends on PostgreSQL and Redis.**
*Strong answer:* Liveness with no dependencies. Readiness checks DB and Redis with short timeouts and reports draining during shutdown. Exclude both from auth and noisy logs. Wire liveness to restart policies and readiness to load balancer routing. Optional dependencies (cache) may degrade instead of failing readiness.
*Trap:* One `/health` endpoint that checks everything, used for liveness.

**Q: What production command do you use for FastAPI in a container, and why?**
*Strong answer:* Exec-form `fastapi run` (or `uvicorn`) with proxy headers configured for trusted proxies, one process per container under an orchestrator, graceful shutdown within the grace period, and no reload. Mention Gunicorn with Uvicorn workers for VM-style deployments, and DB connection math (workers × pool size × containers).

**Q: How does Compose guarantee startup order?**
*Strong answer:* `depends_on` with `condition: service_healthy` or `service_completed_successfully`. Apps still retry, because production orchestrators don't order startup.

#### Advanced Questions

**Q: Your container ignores `docker stop` for 10 seconds and then dies with 137. Why?**
*Strong answer:* PID 1 is a shell (shell-form CMD) that doesn't forward `SIGTERM`, or the app ignores it, so Docker sends `SIGKILL` after the grace period. Use exec form or `exec` in entrypoints, `--init`/`tini` for reaping, and handle `SIGTERM` (Uvicorn does).

**Q: How would you make image builds reproducible?**
*Strong answer:* Pin the base image by digest, pin the uv version (or digest), use `uv sync --locked` against a committed lockfile, avoid `apt-get upgrade` without pinned versions, use deterministic build args, and produce an SBOM and provenance. Rebuild from the same commit and compare digests (bit-for-bit reproducibility needs extra care, such as `SOURCE_DATE_EPOCH`).

#### Coding Questions

1. Write a multi-stage Dockerfile for a FastAPI app with uv, non-root user, and healthcheck.
2. Write the `/health/ready` endpoint with per-dependency timeouts.
3. Write a Compose service definition for PostgreSQL with a healthcheck and named volume.

#### Scenario Questions

**Q: A teammate wants to put the `.env` with production secrets into the image "to simplify deployment". Respond.**
*Strong answer:* Image layers are permanent and distributed to every registry pull, and anyone can `docker history` or extract them. Inject secrets at runtime from a secrets manager (Unit 27) or orchestrator secrets, rotate any secret that was baked in, and add a CI check (secret scanning) to prevent recurrence.

### 14. Explain-It-at-Three-Levels

**Concept: Docker layers and caching**

- *30 seconds:* Each Dockerfile step creates a cached, content-addressed layer. Once a step changes, everything after it rebuilds, so copy lockfiles and install dependencies before copying source code.
- *2 minutes:* Add cache keys (instruction + parent + file checksums), `.dockerignore`, BuildKit cache mounts, multi-stage builds, and why deleting files in a later layer doesn't shrink the image.
- *Deep:* Walk the BuildKit DAG, parallel stages, registry layer dedupe by digest, and reproducibility (pinning base/uv by digest, `--locked`, SBOM), with measured before/after build times and sizes.

**Concept: Health checks**

- *30 seconds:* Liveness answers "restart me?" and must not depend on other services. Readiness answers "send me traffic?" and checks the dependencies needed to serve, with short timeouts and draining during shutdown.
- *2 minutes:* Docker vs Compose vs ECS/ALB vs Kubernetes probes, and the restart-storm failure.
- *Deep:* Graceful shutdown sequence, load-balancer deregistration timing, health check load, partial degradation for optional dependencies, and testing.

### 15. Knowledge Check

1. What isolation do namespaces provide, and what do cgroups provide?
2. Why does `COPY . .` before dependency installation hurt build times?
3. Why should liveness checks avoid external dependencies?
4. What does `uv sync --locked` guarantee that `--frozen` doesn't?
5. Why is the exec form of `CMD` preferred?
6. *Code reading:* In the Compose file, why does `api` depend on `migrate` with `service_completed_successfully`?
7. *Code reading:* Why does the worker disable auto-commit and commit after processing?
8. *Code reading:* Why is the published API port bound to `127.0.0.1`?
9. *Debugging:* Exit code 137 with `OOMKilled: false`. Likely cause?
10. *Debugging:* The API can't reach Kafka at `localhost:9092` inside Compose. Why?
11. *Design:* One process per container or multiple workers per container on ECS Fargate?
12. *Design:* Should Redis being down fail readiness if Redis is only a cache?

#### Knowledge Check Answers

1. Namespaces isolate what a process can *see* (PIDs, network, mounts, hostname, users, IPC). cgroups limit and account what it can *use* (memory, CPU, PIDs, I/O).
2. Any source change alters the checksum of the copied files, invalidating that layer and every later one, including the expensive dependency install.
3. A dependency outage would fail liveness everywhere and trigger mass restarts, which don't fix the dependency and remove capacity during recovery.
4. That the lockfile is consistent with `pyproject.toml`. A stale lockfile fails the build instead of silently installing something different from what the manifest declares.
5. The server becomes PID 1 and receives `SIGTERM` directly for graceful shutdown. The shell form wraps it in `/bin/sh -c`, which may not forward signals.
6. So the API starts only after migrations have been applied successfully, avoiding errors from schema mismatches at startup.
7. To get at-least-once processing: if the worker crashes mid-batch, uncommitted messages are redelivered. Handlers must be idempotent.
8. To avoid exposing the service on all host interfaces (for example on shared networks). It's only reachable from the developer's machine.
9. `SIGKILL` after the stop grace period (the app didn't exit in time or didn't receive `SIGTERM`), or killed by the host for other reasons. Check signal handling and shutdown duration.
10. `localhost` inside the API container refers to the API container itself. Use the service name `kafka:9092`, and make sure the advertised listener matches.
11. Usually one process per task, scaling by task count (simpler, better isolation, clearer metrics). Multiple workers per task if each task has several vCPUs and you want to amortize per-task overhead, while watching DB connection totals.
12. Usually no: degrade gracefully (bypass the cache) and report it as a degraded check. Fail readiness only for dependencies without which requests cannot be served correctly.

### 16. Common Interview Traps

- **"Containers are lightweight VMs."** They share the host kernel. Isolation and security properties differ.
- **"`depends_on` waits until the database is ready."** Only with health conditions, and production doesn't order startup at all.
- **"One `/health` endpoint is enough."** Liveness and readiness serve different decisions.
- **"Deleting files in a later layer makes the image smaller."** The earlier layer still contains them.
- **"`latest` is fine for base images."** It's non-reproducible and drifts silently.
- **"`--reload` is harmless in production."** It adds file watching, isn't meant for production, and conflicts with multi-worker setups.
- **"Secrets in environment variables baked into the image are OK."** Image layers are permanent and widely distributed.
- **"`async def` endpoints don't need more processes."** CPU-bound work still blocks the event loop, and a single process uses one core.

### 17. Cheat Sheet

- **Build:** `docker build -t app:tag .`, `--progress=plain`, `docker history`, `dive`, `.dockerignore`.
- **Run/inspect:** `docker run --rm -p 127.0.0.1:8000:8000 app:tag`, `docker logs`, `docker exec -it <c> sh`, `docker inspect`, `docker stats`.
- **Compose:** `docker compose up -d --wait`, `ps`, `logs -f`, `exec`, `run --rm`, `down [-v]`, `config`, profiles, `depends_on.condition: service_healthy | service_completed_successfully`.
- **Dockerfile pattern:** pinned base → pinned uv → `uv sync --locked --no-install-project --no-dev --no-editable` with cache/bind mounts → `COPY . .` → `uv sync --locked --no-dev --no-editable` → runtime stage copies `.venv` + app → non-root `USER` → `HEALTHCHECK` → exec-form `CMD`.
- **Server:** `fastapi run app/main.py --port 8000 --proxy-headers` (one process per container); Gunicorn + Uvicorn workers for VMs; graceful shutdown < grace period.
- **Health:** `/health/live` (no deps) vs `/health/ready` (deps, timeouts, draining).
- **Rules:** service names not localhost; no secrets in images; pin by digest; volumes for state; exec form; one process per container (default).

### 18. Completion Checklist

- [ ] I can explain images, layers, containers, networks and volumes, and what namespaces and cgroups do.
- [ ] I can write a multi-stage uv Dockerfile producing a small, non-root, reproducible image.
- [ ] I can predict and optimize layer caching.
- [ ] I can implement liveness and readiness correctly and explain why they differ.
- [ ] I can run API, worker, PostgreSQL, Redis and Kafka with deterministic, health-gated startup.
- [ ] I can choose and configure a production server command with graceful shutdown.
- [ ] I can debug exits, connection errors, OOM kills, permission errors and slow builds.
- [ ] I can identify when not to containerize something (for example a managed service that should stay managed).

### 19. Further Research

**Essential**

- Docker docs: Dockerfile best practices and build cache — <https://docs.docker.com/build/building/best-practices/>, <https://docs.docker.com/build/cache/>. How caching and multi-stage builds work.
- Compose Specification and startup order — <https://docs.docker.com/compose/how-tos/startup-order/>. Health-gated dependencies.
- uv Docker integration guide — <https://docs.astral.sh/uv/guides/integration/docker/>. The canonical uv-in-Docker patterns (`--locked`, `--no-install-project`, cache mounts).
- FastAPI deployment docs (Docker, workers, proxies) — <https://fastapi.tiangolo.com/deployment/docker/>. Production command and proxy header guidance.
- Uvicorn deployment docs — <https://www.uvicorn.org/deployment/>. Workers, signals and proxy headers.

**Deeper Study**

- Linux namespaces and cgroups (man pages `namespaces(7)`, `cgroups(7)`). What containers actually are.
- OCI Image and Runtime specifications — <https://github.com/opencontainers/image-spec>. Manifests, layers and digests.
- Kubernetes probes documentation — <https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/>. Liveness/readiness/startup semantics you'll meet in production.

**Practice**

- `hadolint` — <https://github.com/hadolint/hadolint>. Lint your Dockerfiles.
- `dive` — <https://github.com/wagoodman/dive>. Explore what each layer contains.
- Testcontainers for Python — <https://testcontainers-python.readthedocs.io/>. Real dependencies in tests.

### Unit Completion Standard

Before moving on, you must be able to:

- **Explain** images vs containers, layers and caching, networks, volumes, multi-stage builds, health vs readiness, and production server choices.
- **Implement** a multi-stage uv Dockerfile and a Compose stack running FastAPI, a worker, PostgreSQL (pgvector), Redis and Kafka with deterministic, health-gated startup and graceful shutdown.
- **Test** health endpoints with dependency overrides, the running stack with smoke tests, shutdown behavior, image size/user/secret hygiene, and build caching.
- **Debug** startup exits, inter-service connection failures, OOM/137 exits, volume permissions and slow or bloated builds.
- **Defend** in an interview your Dockerfile ordering, base image, health check design, Compose startup strategy and production server command.
