"""Request IDs: one ID follows a request from browser to logs."""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
log = logging.getLogger("access")


class RequestIdFilter(logging.Filter):
    """Adds request_id to every log record emitted during a request."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(request_id)s] %(name)s "
            "%(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # TODO(5): read X-Request-ID; keep it only if SAFE_ID matches
        # (prevents log injection), else uuid.uuid4().hex. Set
        # request_id_var for the duration of the request, put the ID on
        # the response header, log one access line, reset the var.
        _ = (uuid, time, SAFE_ID, request_id_var)
        return await call_next(request)
