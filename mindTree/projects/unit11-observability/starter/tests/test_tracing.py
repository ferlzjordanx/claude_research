import httpx
import respx
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind


def test_revenue_report_has_service_and_db_spans(
    client: TestClient, spans: InMemorySpanExporter
) -> None:
    client.get("/reports/revenue")
    by_name = {s.name: s for s in spans.get_finished_spans()}
    server = by_name["GET /reports/revenue"]  # auto-instrumentation
    service = by_name["reports.revenue_by_customer"]
    db = by_name["SELECT customers"]

    assert service.parent is not None
    assert service.parent.span_id == server.context.span_id
    assert db.parent is not None
    assert db.parent.span_id == service.context.span_id
    assert db.kind is SpanKind.CLIENT
    assert db.attributes is not None
    assert db.attributes["db.system.name"] == "sqlite"
    assert db.attributes["db.response.returned_rows"] == 25
    assert service.attributes is not None
    assert service.attributes["app.report.rows"] == 25
    trace_ids = {server.context.trace_id, db.context.trace_id}
    assert len(trace_ids) == 1


def test_fx_call_is_traced_and_propagates_traceparent(
    client: TestClient,
    spans: InMemorySpanExporter,
    fx_mock: respx.MockRouter,
) -> None:
    route = fx_mock.get("/rates").mock(
        return_value=httpx.Response(200, json={"rate": 0.5})
    )
    response = client.get("/reports/revenue-fx?currency=EUR")
    assert response.status_code == 200
    fx_span = next(
        s for s in spans.get_finished_spans() if s.name == "fx.get_rate"
    )
    sent = route.calls.last.request.headers["traceparent"]
    trace_hex = format(fx_span.context.trace_id, "032x")
    span_hex = format(fx_span.context.span_id, "016x")
    # version-trace_id-parent_span_id-flags; the callee's parent is
    # our fx span, so the callee joins the same trace.
    assert sent.split("-")[1:3] == [trace_hex, span_hex]
