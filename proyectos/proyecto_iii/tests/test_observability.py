import logging
import re

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app
from dsia_web.observability import RequestMetrics

SECURITY = {
    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


@pytest.fixture
def client(report):
    with TestClient(create_app(report[0])) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/health", "/api/v1/snapshot", "/static/style.css", "/no-existe"])
def test_every_response_carries_security_headers(client, path):
    response = client.get(path)
    for name, value in SECURITY.items():
        assert response.headers[name] == value


def test_security_headers_also_on_unavailable_service(tmp_path):
    with TestClient(create_app(tmp_path / "falta.json")) as client:
        response = client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.headers["x-content-type-options"] == "nosniff"


def test_valid_incoming_request_id_is_propagated(client):
    response = client.get("/health", headers={"X-Request-ID": "demo-req.0001"})
    assert response.headers["x-request-id"] == "demo-req.0001"


@pytest.mark.parametrize("incoming", [None, "corto", "con espacios 12345", "a" * 129, "x\r\nSet-Cookie: 1"])
def test_missing_or_unsafe_request_id_is_replaced_by_uuid4(client, incoming):
    headers = {} if incoming is None else {"X-Request-ID": incoming}
    try:
        response = client.get("/health", headers=headers)
    except Exception:  # httpx rechaza cabeceras con saltos de línea antes de enviarlas
        assert "\n" in incoming
        return
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_counters_group_by_route_template_and_status(client):
    for path in ("/health", "/health", "/api/v1/snapshot", "/static/style.css", "/no-existe"):
        client.get(path)
    counts = client.app.state.metrics.counts
    assert dict(counts) == {("/health", 200): 2, ("/api/v1/snapshot", 200): 1,
                            ("/static", 200): 1, ("unmatched", 404): 1}


def test_each_request_is_logged_with_request_id_and_latency(client, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        client.get("/health", headers={"X-Request-ID": "trazable-123"})
    lines = [record.getMessage() for record in caplog.records if "request_id=trazable-123" in record.getMessage()]
    assert len(lines) == 1
    assert re.search(r"method=GET route=/health status=200 latency_ms=\d+\.\d{2}$", lines[0])


def test_request_metrics_summary_exact_values():
    now = [100.0]
    metrics = RequestMetrics(clock=lambda: now[0])
    for latency in range(1, 21):
        metrics.record("/health", 200, float(latency))
    metrics.record("/api/v1/analyze", 503, 40.0)
    now[0] = 112.5
    assert metrics.summary() == {
        "uptime_s": 12.5,
        "requests_total": 21,
        "requests": [{"route": "/api/v1/analyze", "status": 503, "count": 1},
                     {"route": "/health", "status": 200, "count": 20}],
        "latency_ms": {"samples": 21, "mean": 11.905, "p95": 20.0},  # 250 / 21
    }


def test_request_metrics_without_samples():
    assert RequestMetrics(clock=lambda: 5.0).summary()["latency_ms"] == {"samples": 0, "mean": None, "p95": None}


def test_latency_window_is_bounded():
    metrics = RequestMetrics(window=3)
    for latency in (100.0, 1.0, 2.0, 3.0):
        metrics.record("/health", 200, latency)
    assert metrics.summary()["latency_ms"] == {"samples": 3, "mean": 2.0, "p95": 3.0}
    assert metrics.summary()["requests_total"] == 4
