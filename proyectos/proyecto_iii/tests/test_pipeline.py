import json

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app
from dsia_web.journal import read_recent_events


def event(stage, status, **fields):
    return json.dumps({"timestamp": "2026-11-23T10:00:00+00:00", "stage": stage, "status": status, **fields})


def test_pipeline_returns_last_events_of_the_demo_batch(demo_run):
    lines = [json.loads(line) for line in demo_run.journal.read_text().splitlines()]
    with TestClient(create_app(demo_run.path, journal_path=demo_run.journal)) as client:
        response = client.get("/api/v1/pipeline", params={"limit": 4})
    assert response.status_code == 200
    body = response.json()
    assert body == {"events": lines[-4:], "returned": 4, "skipped_lines": 0,
                    "last_run_id": demo_run.snapshot.run_id}
    assert [(e["stage"], e["status"]) for e in body["events"]] == [
        ("infer_snapshot", "started"), ("infer_snapshot", "succeeded"),
        ("publish_snapshot", "started"), ("publish_snapshot", "succeeded")]
    assert str(demo_run.journal.parent) not in response.text


def test_pipeline_default_limit_is_20_and_whole_demo_fits(demo_run):
    with TestClient(create_app(demo_run.path, journal_path=demo_run.journal)) as client:
        body = client.get("/api/v1/pipeline").json()
    assert body["returned"] == 12


def test_corrupt_lines_are_skipped_and_unknown_fields_dropped(tmp_path, demo_run):
    journal = tmp_path / "pipeline.jsonl"
    journal.write_text("\n".join([
        event("prepare", "started", path="/home/privado/barras.csv"),
        "{corrupta",
        "[1, 2]",
        json.dumps({"stage": "train"}),
        event("train", "succeeded", duration_ms=12.5, rows=True, error_type="x" * 200),
        "\xff no utf8",
        "",
        event("publish_snapshot", "succeeded", run_id="a" * 64, symbols=8),
    ]) + "\n")
    with TestClient(create_app(demo_run.path, journal_path=journal)) as client:
        body = client.get("/api/v1/pipeline").json()
    assert body == {
        "events": [
            {"timestamp": "2026-11-23T10:00:00+00:00", "stage": "prepare", "status": "started"},
            {"timestamp": "2026-11-23T10:00:00+00:00", "stage": "train", "status": "succeeded",
             "duration_ms": 12.5},
            {"timestamp": "2026-11-23T10:00:00+00:00", "stage": "publish_snapshot", "status": "succeeded",
             "run_id": "a" * 64, "symbols": 8},
        ],
        "returned": 3, "skipped_lines": 4, "last_run_id": "a" * 64,
    }


def test_reader_is_bounded_in_bytes_and_drops_the_cut_line(tmp_path):
    journal = tmp_path / "pipeline.jsonl"
    lines = [event("train", "succeeded", rows=index) for index in range(2000)]
    journal.write_text("\n".join(lines) + "\n")
    window = sum(len(line) + 1 for line in lines[-10:]) + 5  # 10 líneas completas + 5 bytes de otra
    events, skipped = read_recent_events(journal, limit=50, max_bytes=window)
    assert [item["rows"] for item in events] == list(range(1990, 2000))
    assert skipped == 0


@pytest.mark.parametrize("limit", ["0", "51", "-1", "diez", ""])
def test_pipeline_limit_must_be_between_1_and_50(demo_run, limit):
    with TestClient(create_app(demo_run.path, journal_path=demo_run.journal)) as client:
        response = client.get("/api/v1/pipeline", params={"limit": limit})
    assert (response.status_code, response.json()["error"]) == (422, "invalid_limit")


def test_pipeline_without_journal_is_404_and_unreadable_is_503(demo_run, tmp_path, monkeypatch):
    monkeypatch.delenv("DSIA_JOURNAL", raising=False)
    with TestClient(create_app(demo_run.path)) as client:
        missing = client.get("/api/v1/pipeline")
    assert (missing.status_code, missing.json()["error"]) == (404, "journal_not_configured")
    with TestClient(create_app(demo_run.path, journal_path=tmp_path / "privado.jsonl")) as client:
        absent = client.get("/api/v1/pipeline")
    assert (absent.status_code, absent.json()["error"]) == (503, "journal_unavailable")
    assert "privado" not in absent.text
