# syntax=docker/dockerfile:1
# Multi-stage build: dependencies in a builder, slim non-root runtime.
FROM python:3.13-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim
# CI passes these so /version can prove which commit is running.
ARG GIT_SHA=unknown
ARG APP_VERSION=0.0.0-dev
ENV APP_GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.revision=${GIT_SHA}
COPY --from=builder /install /usr/local
WORKDIR /srv
COPY app ./app
RUN useradd --uid 10001 --no-create-home appuser
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000"]
