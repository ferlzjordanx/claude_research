"""Outbound dependency: a currency-rate (FX) HTTP service."""

import httpx
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, Tracer

from app.config import Settings
from app.errors import (  # noqa: F401 (used once TODO(8) is done)
    UpstreamError,
    UpstreamTimeoutError,
)


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    """One pooled client per app, with explicit timeouts and limits.

    httpx.Timeout applies per phase (connect, read, write, pool), not
    to the whole call; wrap in asyncio.timeout() for a total deadline.
    """
    return httpx.AsyncClient(
        base_url=settings.fx_base_url,
        # TODO(7): BUG - "the FX service is sometimes slow, so never
        # time out". One hung upstream now holds a connection and a
        # request forever. Use httpx.Timeout(settings.fx_timeout_seconds).
        timeout=None,
        limits=httpx.Limits(max_connections=20),
    )


class FxClient:
    def __init__(self, http: httpx.AsyncClient, tracer: Tracer) -> None:
        self.http = http
        self._tracer = tracer

    async def get_rate(self, currency: str) -> float:
        with self._tracer.start_as_current_span(
            "fx.get_rate",
            kind=SpanKind.CLIENT,
            attributes={
                "server.address": self.http.base_url.host,
                "app.fx.currency": currency,
            },
        ) as span:
            headers: dict[str, str] = {}
            inject(headers)  # adds W3C `traceparent` for the callee
            # TODO(8): translate failures into domain errors so the
            # client gets problem+json, not a 500 with a stack trace:
            # httpx.TimeoutException -> UpstreamTimeoutError (504),
            # any other httpx.HTTPError (incl. raise_for_status) ->
            # UpstreamError (502). Chain with `raise ... from exc`.
            response = await self.http.get(
                "/rates",
                params={"base": "USD", "symbol": currency},
                headers=headers,
            )
            response.raise_for_status()
            span.set_attribute(
                "http.response.status_code", response.status_code
            )
            return float(response.json()["rate"])
