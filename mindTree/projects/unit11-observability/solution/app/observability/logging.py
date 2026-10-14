"""Structured JSON logging: one JSON object per line on stdout."""

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

from app.observability.context import request_id_var

# Attributes every LogRecord has. Anything else came from `extra=`.
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", None, None)))
_STANDARD |= {"message", "asctime", "taskName", "color_message"}

# Never write these values, even if someone passes them in `extra=`.
SENSITIVE_KEYS = frozenset(
    {"password", "authorization", "token", "secret", "api_key", "cookie"}
)


class ContextFilter(logging.Filter):
    """Stamp request_id, trace_id and span_id on every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            # W3C format: 32 hex chars for the trace, 16 for the span.
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = None
            record.span_id = None
        return True


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        created = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, Any] = {
            "timestamp": created.isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
        }
        for key, value in vars(record).items():
            if key in _STANDARD or key in payload:
                continue
            if key.lower() in SENSITIVE_KEYS:
                value = "[REDACTED]"
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send all logs (ours and uvicorn's) through the JSON handler."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"context": {"()": ContextFilter}},
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                    "filters": ["context"],
                }
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                # We write our own access log with route + duration.
                "uvicorn.access": {"handlers": [], "propagate": False},
            },
        }
    )
