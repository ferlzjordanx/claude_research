"""Structured JSON logging: one JSON object per line on stdout."""

import json
import logging
import logging.config

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
        # TODO(2): set record.request_id from request_id_var
        # (app.observability.context). Read the current span with
        # opentelemetry.trace.get_current_span().get_span_context();
        # if it is valid, set record.trace_id to 32 lowercase hex chars
        # and record.span_id to 16 (format(n, "032x") / "016x"),
        # otherwise set both to None. Always return True.
        record.request_id = None
        record.trace_id = None
        record.span_id = None
        return True


class JsonFormatter(logging.Formatter):
    """Render a LogRecord as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        # TODO(1): build a dict with "timestamp" (record.created as
        # ISO 8601 in UTC, millisecond precision), "level", "logger",
        # "message" (record.getMessage()), "request_id", "trace_id",
        # "span_id" (getattr with default None). Then add every other
        # attribute of the record that is not in _STANDARD (these
        # came from `extra=`), replacing values whose key is in
        # SENSITIVE_KEYS with "[REDACTED]". Add "exc" from
        # self.formatException() when record.exc_info is set.
        # Serialize with json.dumps(..., default=str).
        return json.dumps({"message": record.getMessage()})


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
