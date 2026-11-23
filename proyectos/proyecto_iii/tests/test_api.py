from datetime import timedelta

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app


def fixed_clock(snapshot, days=3):
    return lambda: snapshot.generated_at + timedelta(days=days, hours=1)


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


def test_oversized_snapshot_is_rejected_and_service_reports_503(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_bytes(b" " * 2_000_001)
    with TestClient(create_app(path)) as client:
        assert client.get("/health").status_code == 503
        response = client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.json()["error"] == "snapshot_unavailable"
    assert response.json()["request_id"] == response.headers["x-request-id"]
