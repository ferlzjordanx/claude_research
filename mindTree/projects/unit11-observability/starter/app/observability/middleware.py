"""Request-ID middleware and the access log line."""

import logging
import re
import time
import uuid

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.context import request_id_var
from app.observability.metrics import route_template

# Only accept client IDs that cannot inject newlines or JSON.
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_log = logging.getLogger("app.access")


class RequestIdMiddleware:
    """Accept or create X-Request-ID, echo it, log one line per call."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = (
            incoming if SAFE_ID.match(incoming) else uuid.uuid4().hex
        )
        token = request_id_var.set(request_id)
        # Link the trace to the request ID (search by either one).
        trace.get_current_span().set_attribute("app.request_id", request_id)
        status = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append(
                    "X-Request-ID", request_id
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Logs may carry high-cardinality values (path, IDs);
            # metric labels may not.
            access_log.info(
                "request completed",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "route": route_template(scope),
                    "status": status,
                    "duration_ms": round(
                        (time.perf_counter() - start) * 1000, 2
                    ),
                },
            )
            request_id_var.reset(token)
