from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEMPLATE = 'route="/customers/{customer_id}/summary"'


def test_metrics_use_route_template_not_raw_path(
    client: TestClient,
) -> None:
    for customer_id in (1, 2, 3, 999):
        client.get(f"/customers/{customer_id}/summary")
    text = client.get("/metrics").text
    assert (
        'http_requests_total{method="GET",' + TEMPLATE + ',status="200"}'
        " 3.0"
    ) in text
    assert TEMPLATE + ',status="404"} 1.0' in text
    assert "/customers/1/summary" not in text  # no IDs in labels


def test_unmatched_paths_share_one_label(client: TestClient) -> None:
    for n in range(5):
        client.get(f"/wp-admin/{n}.php")
    text = client.get("/metrics").text
    assert 'route="<unmatched>",status="404"} 5.0' in text
    assert "wp-admin" not in text


def test_metrics_endpoint_exposes_histogram_and_gauge(
    client: TestClient,
) -> None:
    client.get("/reports/revenue")
    response = client.get("/metrics")
    assert response.headers["content-type"].startswith("text/plain")
    text = response.text
    assert "# TYPE http_request_duration_seconds histogram" in text
    assert (
        'http_request_duration_seconds_bucket{le="0.3",method="GET",'
        'route="/reports/revenue"}'
    ) in text
    assert "# TYPE http_requests_in_flight gauge" in text
    assert 'route="/metrics"' not in text  # scrapes are not counted


def test_each_app_has_its_own_registry(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first:
        first.get("/reports/revenue")
    with TestClient(create_app(settings)) as second:
        text = second.get("/metrics").text
    assert 'route="/reports/revenue"' not in text
