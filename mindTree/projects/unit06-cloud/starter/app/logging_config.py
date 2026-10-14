"""JSON logs to stdout: the container runtime ships them (12-factor)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has; anything else came from `extra=`.
_STANDARD = set(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName", "color_message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # One JSON format for uvicorn too, instead of its text format.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers[:] = []
        logger.propagate = True
    # Our middleware writes structured access logs; skip uvicorn's.
    logging.getLogger("uvicorn.access").disabled = True
