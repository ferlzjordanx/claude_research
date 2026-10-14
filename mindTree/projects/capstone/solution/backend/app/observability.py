"""JSON logs, request IDs and Prometheus metrics (see Unit 11)."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Histogram,
)
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
log = logging.getLogger("access")


class JsonFormatter(logging.Formatter):
    """One JSON object per line: easy to search in CloudWatch/Loki."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(json_logs: bool) -> None:
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class Metrics:
    """Own registry per app: no global state shared between tests."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "http_requests_total",
            "HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency",
            ["route"],
            registry=self.registry,
        )
        self.llm_calls = Counter(
            "llm_calls_total",
            "LLM calls by outcome",
            ["operation", "outcome"],
            registry=self.registry,
        )
        self.llm_tokens = Counter(
            "llm_tokens_total",
            "LLM tokens",
            ["direction"],
            registry=self.registry,
        )


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics: Metrics) -> None:
        super().__init__(app)
        self.metrics = metrics

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = (
            incoming if SAFE_ID.match(incoming) else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed = time.perf_counter() - start
            # Route TEMPLATE (/tickets/{ticket_id}), never the raw path:
            # one series per endpoint, not one per ticket ID.
            route = getattr(request.scope.get("route"), "path", "other")
            self.metrics.requests.labels(
                request.method, route, str(response.status_code)
            ).inc()
            self.metrics.latency.labels(route).observe(elapsed)
            response.headers["X-Request-ID"] = request_id
            log.info(
                "request",
                extra={
                    "fields": {
                        "method": request.method,
                        "route": route,
                        "status": response.status_code,
                        "ms": round(elapsed * 1000, 1),
                    }
                },
            )
            return response
        finally:
            request_id_var.reset(token)
