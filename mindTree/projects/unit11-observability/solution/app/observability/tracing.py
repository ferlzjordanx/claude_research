"""OpenTelemetry tracing: provider, sampler, exporter, FastAPI hook."""

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ParentBased,
    TraceIdRatioBased,
)

from app.config import Settings


def build_tracer_provider(
    settings: Settings, exporter: SpanExporter | None = None
) -> TracerProvider:
    """One provider per app instance (tests pass an in-memory exporter).

    We do not call trace.set_tracer_provider(): the global can only be
    set once per process, which would leak spans between tests.
    """
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.service_name,
                "deployment.environment.name": settings.env,
            }
        ),
        # Respect the caller's sampling decision; sample new traces.
        sampler=ParentBased(TraceIdRatioBased(settings.trace_sample_ratio)),
    )
    if exporter is not None:
        # Synchronous export so tests can assert right away.
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    elif settings.otel_exporter == "console":
        provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    elif settings.otel_exporter == "otlp":
        # Reads OTEL_EXPORTER_OTLP_ENDPOINT (default localhost:4318).
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    return provider


def instrument_app(app: FastAPI, provider: TracerProvider) -> None:
    """Auto-instrumentation: a server span per request, named after
    the route template, continuing any incoming W3C traceparent."""
    FastAPIInstrumentor.instrument_app(
        app, tracer_provider=provider, excluded_urls="metrics,health"
    )
