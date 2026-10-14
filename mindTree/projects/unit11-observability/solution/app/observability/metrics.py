"""Prometheus RED metrics: Rate, Errors, Duration per route."""

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Seconds. Pick buckets around your SLO (here: p95 < 300 ms).
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.3, 0.5, 1, 2.5, 5)
UNMATCHED = "<unmatched>"


class HttpMetrics:
    """All HTTP metrics, in a registry owned by one app instance.

    A dedicated CollectorRegistry (not the global REGISTRY) keeps
    tests isolated: two apps never share or double-register series.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()
        self.requests = Counter(  # exposed as http_requests_total
            "http_requests",
            "HTTP requests by method, route template and status.",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request latency by method and route template.",
            ["method", "route"],
            buckets=BUCKETS,
            registry=self.registry,
        )
        self.in_flight = Gauge(
            "http_requests_in_flight",
            "Requests currently being processed.",
            registry=self.registry,
        )

    def render(self) -> tuple[bytes, str]:
        return generate_latest(self.registry), CONTENT_TYPE_LATEST


def route_template(scope: Scope) -> str:
    """'/customers/{customer_id}/summary', never '/customers/42/...'.

    The router stores the matched route in the scope. Unmatched paths
    (404 scans, bots) all share one label value.
    """
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) else UNMATCHED


class MetricsMiddleware:
    """Pure ASGI middleware: count and time every HTTP request."""

    def __init__(self, app: ASGIApp, metrics: HttpMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = 500  # if the app raises before responding

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        self.metrics.in_flight.inc()
        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            self.metrics.in_flight.dec()
            # Read the template AFTER the app ran: routing sets it.
            route = route_template(scope)
            if route != "/metrics":  # don't measure the scraper
                method = scope["method"]
                self.metrics.requests.labels(
                    method, route, str(status)
                ).inc()
                self.metrics.duration.labels(method, route).observe(elapsed)
