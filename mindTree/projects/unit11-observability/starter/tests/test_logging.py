import json
import logging

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider

from app.observability.context import request_id_var
from app.observability.logging import ContextFilter, JsonFormatter
from tests.conftest import parse


def _format(record: logging.LogRecord) -> dict[str, object]:
    ContextFilter().filter(record)
    result: dict[str, object] = json.loads(JsonFormatter().format(record))
    return result


def _record(msg: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        "app.test", logging.WARNING, __file__, 1, msg, None, None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_required_fields() -> None:
    tracer = TracerProvider().get_tracer("test")
    token = request_id_var.set("req-abcdef12")
    try:
        with tracer.start_as_current_span("work") as span:
            data = _format(_record("hello", customer_id=7))
            ctx = span.get_span_context()
    finally:
        request_id_var.reset(token)
    assert data["level"] == "WARNING"
    assert data["logger"] == "app.test"
    assert data["message"] == "hello"
    assert str(data["timestamp"]).endswith("+00:00")
    assert data["request_id"] == "req-abcdef12"
    assert data["trace_id"] == format(ctx.trace_id, "032x")
    assert data["span_id"] == format(ctx.span_id, "016x")
    assert data["customer_id"] == 7  # extras become fields


def test_secrets_in_extra_are_redacted() -> None:
    data = _format(_record("login", password="hunter2", api_key="sk-1"))
    assert data["password"] == "[REDACTED]"
    assert data["api_key"] == "[REDACTED]"
    assert "hunter2" not in json.dumps(data)


def test_access_log_is_json_with_request_id_and_trace_id(
    client: TestClient, json_logs: list[str]
) -> None:
    client.get("/customers/1/summary", headers={"X-Request-ID": "abc-1234"})
    access = [r for r in parse(json_logs) if r["logger"] == "app.access"]
    assert len(access) == 1
    line = access[0]
    assert line["request_id"] == "abc-1234"
    assert len(str(line["trace_id"])) == 32
    assert line["route"] == "/customers/{customer_id}/summary"
    assert line["status"] == 200
    assert isinstance(line["duration_ms"], float)


def test_incoming_traceparent_continues_the_trace(
    client: TestClient, json_logs: list[str]
) -> None:
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    client.get(
        "/reports/revenue",
        headers={"traceparent": f"00-{trace_id}-b7ad6b7169203331-01"},
    )
    access = [r for r in parse(json_logs) if r["logger"] == "app.access"]
    assert access[0]["trace_id"] == trace_id


def test_request_id_echoed_or_replaced(client: TestClient) -> None:
    good = client.get("/health", headers={"X-Request-ID": "abc-1234"})
    assert good.headers["X-Request-ID"] == "abc-1234"
    bad = client.get("/health", headers={"X-Request-ID": "bad id {}"})
    assert bad.headers["X-Request-ID"] != "bad id {}"
    assert len(bad.headers["X-Request-ID"]) == 32
