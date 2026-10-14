"""Outbound dependency: a currency-rate (FX) HTTP service."""

import httpx
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, Tracer

from app.config import Settings
from app.errors import UpstreamError, UpstreamTimeoutError


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    """One pooled client per app, with explicit timeouts and limits.

    httpx.Timeout applies per phase (connect, read, write, pool), not
    to the whole call; wrap in asyncio.timeout() for a total deadline.
    """
    return httpx.AsyncClient(
        base_url=settings.fx_base_url,
        timeout=httpx.Timeout(settings.fx_timeout_seconds),
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
            try:
                response = await self.http.get(
                    "/rates",
                    params={"base": "USD", "symbol": currency},
                    headers=headers,
                )
                response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise UpstreamTimeoutError(
                    "FX service did not answer in time."
                ) from exc
            except httpx.HTTPError as exc:
                raise UpstreamError("FX service call failed.") from exc
            span.set_attribute(
                "http.response.status_code", response.status_code
            )
            return float(response.json()["rate"])
