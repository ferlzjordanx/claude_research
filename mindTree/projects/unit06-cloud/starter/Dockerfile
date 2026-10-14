# syntax=docker/dockerfile:1
# Build:  docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD)
#           -t inventory-api:1.0.0 .
ARG PYTHON_IMAGE=python:3.13-slim

# TODO(3): make this a multi-stage build.
#   Stage "builder" (FROM ${PYTHON_IMAGE} AS builder): create a venv
#   in /opt/venv and pip install requirements.txt into it, copying
#   requirements.txt *before* the code so the layer stays cached.
#   Stage "runtime": a fresh FROM ${PYTHON_IMAGE} that does
#   COPY --from=builder /opt/venv /opt/venv and puts it on PATH.
#   Today this single stage ships pip and the build cache.
FROM ${PYTHON_IMAGE}
ARG GIT_SHA=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_GIT_SHA=${GIT_SHA}
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
# TODO(4): run as a non-root user. Create a system group and user
#   with a fixed numeric UID/GID (10001) and switch with
#   USER 10001:10001 (numeric, so Kubernetes can verify it).
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
