"""Application factory: wiring only, no business logic."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from opentelemetry.sdk.trace.export import SpanExporter
from sqlalchemy.orm import sessionmaker

from app import routes
from app.config import Settings, get_settings
from app.db import Base, make_engine, seed
from app.errors import register_error_handlers
from app.fx import FxClient, build_http_client
from app.observability.logging import configure_logging
from app.observability.metrics import HttpMetrics, MetricsMiddleware
from app.observability.middleware import RequestIdMiddleware
from app.observability.tracing import build_tracer_provider, instrument_app


def create_app(
    settings: Settings | None = None,
    *,
    span_exporter: SpanExporter | None = None,
) -> FastAPI:
    """Run with: uvicorn app.main:create_app --factory"""
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    seed(session_factory, settings.seed_customers)
    provider = build_tracer_provider(settings, span_exporter)
    tracer = provider.get_tracer("app")
    metrics = HttpMetrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        http = build_http_client(settings)
        app.state.fx = FxClient(http, tracer)
        yield
        await http.aclose()
        provider.shutdown()  # flush buffered spans
        engine.dispose()

    app = FastAPI(title="Orders API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.tracer = tracer
    app.state.metrics = metrics

    register_error_handlers(app)
    # Last added runs first: RequestId wraps Metrics wraps the app.
    app.add_middleware(MetricsMiddleware, metrics=metrics)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(routes.router)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        body, content_type = metrics.render()
        return Response(body, media_type=content_type)

    instrument_app(app, provider)  # outermost: the server span
    return app
