# syntax=docker/dockerfile:1
# Build:  docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD)
#           -t inventory-api:1.0.0 .
ARG PYTHON_IMAGE=python:3.13-slim

# ---- Stage 1: builder. Has pip and build tools; never shipped. ----
FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
# Copy only the dependency list first: this layer (and the slow
# install below) stays cached until requirements.txt changes.
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt

# ---- Stage 2: runtime. Only the venv and the app code. ----
FROM ${PYTHON_IMAGE} AS runtime
ARG GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_GIT_SHA=${GIT_SHA}
# Fixed numeric UID/GID so Kubernetes runAsNonRoot can verify it.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /srv
COPY --from=builder /opt/venv /opt/venv
# Code stays owned by root: the app user can read it, not modify it.
COPY app ./app
USER 10001:10001
EXPOSE 8000
# Used by `docker run` and compose. Kubernetes ignores it and uses
# the probes in the Deployment instead.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
  CMD ["python", "-m", "app.healthcheck"]
# Exec form: uvicorn is PID 1 and receives SIGTERM directly.
# The shell form (CMD uvicorn ...) would wrap it in /bin/sh -c,
# which does not forward signals, so pods hit SIGKILL after the
# grace period instead of shutting down cleanly.
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--timeout-graceful-shutdown", "20", "--no-access-log"]
