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
        incoming = request.headers.get("X-Request-ID", "")
        # Accept the client's ID only if it is well-formed (prevents log
        # injection); otherwise generate one.
        request_id = (
            incoming if SAFE_ID.match(incoming) else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            # Logged before the reset, so the filter stamps the same ID.
            log.info(
                "%s %s -> %s in %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - start) * 1000,
            )
            return response
        finally:
            request_id_var.reset(token)
