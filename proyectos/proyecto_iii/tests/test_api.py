from datetime import timedelta

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app


def fixed_clock(snapshot, days=3):
    # -> Días exactos: con horas extra, un snapshot generado después de las 23:00 UTC cruzaría otro día.
    return lambda: snapshot.generated_at + timedelta(days=days)


def test_health_ready_reports_checks_without_paths(demo_run):
    snapshot = demo_run.snapshot
    app = create_app(demo_run.path, journal_path=demo_run.journal, clock=fixed_clock(snapshot))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready", "run_id": snapshot.run_id, "as_of": str(snapshot.as_of),
        "checks": {"snapshot_loaded": True, "data_kind": "synthetic", "as_of": str(snapshot.as_of),
                   "snapshot_age_days": 3, "journal_available": True},
    }
    assert str(demo_run.path.parent) not in response.text


def test_health_unavailable_is_503_with_typed_checks(tmp_path):
    with TestClient(create_app(tmp_path / "falta.json", journal_path=tmp_path / "falta.jsonl")) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "checks": {
        "snapshot_loaded": False, "data_kind": None, "as_of": None, "snapshot_age_days": None,
        "journal_available": False}}
    assert str(tmp_path) not in response.text


def test_health_reads_journal_from_environment(demo_run, monkeypatch):
    monkeypatch.setenv("DSIA_JOURNAL", str(demo_run.journal))
    with TestClient(create_app(demo_run.path)) as client:
        assert client.get("/health").json()["checks"]["journal_available"] is True
    monkeypatch.delenv("DSIA_JOURNAL")
    with TestClient(create_app(demo_run.path)) as client:
        assert client.get("/health").json()["checks"]["journal_available"] is False


def test_prediction_by_symbol_returns_rank_and_input_summary(demo_run):
    snapshot = demo_run.snapshot
    ranked = sorted(snapshot.predictions, key=lambda row: -row.predicted_return)
    chosen = ranked[2]
    summary = next(row for row in snapshot.input_summary if row.symbol == chosen.symbol)
    with TestClient(create_app(demo_run.path)) as client:
        response = client.get(f"/api/v1/predictions/{chosen.symbol}")
    assert response.status_code == 200
    assert response.json() == {
        "run_id": snapshot.run_id, "as_of": str(snapshot.as_of), "model": snapshot.model,
        "horizon_sessions": 21, "symbol": chosen.symbol, "predicted_return": chosen.predicted_return,
        "rank": 3, "universe": 8, "input": summary.model_dump(mode="json"),
    }


@pytest.mark.parametrize("symbol", ["aapl", "A" * 33, "A$B", "AAPL%0A", "%20"])
def test_prediction_rejects_invalid_symbol_with_422(demo_run, symbol):
    with TestClient(create_app(demo_run.path)) as client:
        response = client.get(f"/api/v1/predictions/{symbol}")
    assert response.status_code == 422
    assert response.json()["error"] == "invalid_symbol"


def test_prediction_unknown_symbol_is_404_and_without_snapshot_is_503(demo_run, tmp_path):
    with TestClient(create_app(demo_run.path)) as client:
        missing = client.get("/api/v1/predictions/ZZZZ")
    assert (missing.status_code, missing.json()["error"]) == (404, "symbol_not_found")
    with TestClient(create_app(tmp_path / "falta.json")) as client:
        unavailable = client.get("/api/v1/predictions/AAPL")
        invalid = client.get("/api/v1/predictions/aapl")
    assert (unavailable.status_code, unavailable.json()["error"]) == (503, "snapshot_unavailable")
    assert invalid.status_code == 422


def test_metrics_report_counters_uptime_latency_and_loaded_run(demo_run):
    ticks = iter([1000.0, 1042.5])
    with TestClient(create_app(demo_run.path, metrics_clock=lambda: next(ticks))) as client:
        client.get("/health")
        client.get("/health")
        client.get("/api/v1/predictions/ZZZZ")
        client.get("/api/v1/predictions/aapl")
        response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    body = response.json()
    latency = body.pop("latency_ms")
    assert body == {
        "uptime_s": 42.5, "requests_total": 4, "run_id": demo_run.snapshot.run_id,
        "requests": [{"route": "/api/v1/predictions/{symbol}", "status": 404, "count": 1},
                     {"route": "/api/v1/predictions/{symbol}", "status": 422, "count": 1},
                     {"route": "/health", "status": 200, "count": 2}],
    }
    assert latency["samples"] == 4
    assert 0 <= latency["mean"] and 0 <= latency["p95"]


def test_metrics_without_snapshot_have_null_run_id(tmp_path):
    with TestClient(create_app(tmp_path / "falta.json")) as client:
        body = client.get("/api/v1/metrics").json()
    assert (body["run_id"], body["requests_total"], body["latency_ms"]["mean"]) == (None, 0, None)


def test_oversized_snapshot_is_rejected_and_service_reports_503(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_bytes(b" " * 2_000_001)
    with TestClient(create_app(path)) as client:
        assert client.get("/health").status_code == 503
        response = client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.json()["error"] == "snapshot_unavailable"
    assert response.json()["request_id"] == response.headers["x-request-id"]


@pytest.mark.parametrize("method,path,status,code", [
    ("GET", "/no-existe", 404, "not_found"),
    ("GET", "/static/no-existe.css", 404, "not_found"),
    ("GET", "/api/v1/analyze", 405, "method_not_allowed"),
    ("DELETE", "/health", 405, "method_not_allowed"),
])
def test_router_errors_share_the_typed_json_shape(demo_run, method, path, status, code):
    # Arrange
    with TestClient(create_app(demo_run[0])) as client:
        # Act
        response = client.request(method, path, headers={"X-Request-ID": "router-error-1"})
    # Assert: misma forma que el resto de errores de API.md.
    assert response.status_code == status
    assert response.json() == {"error": code, "detail": {"code": code, "message": response.json()["detail"]["message"]},
                               "request_id": "router-error-1"}
    if status == 405:
        assert response.headers["allow"]
