import json

import pytest

from dsia_web.evidence import aggregate_evidence, main


def test_evidence_keeps_identity_metrics_and_stages_but_no_prices_or_predictions(demo_run, tmp_path):
    output = tmp_path / "evidencia.json"
    assert main(["--snapshot", str(demo_run.path), "--journal", str(demo_run.journal),
                 "--output", str(output)]) == 0
    document = json.loads(output.read_text())
    snapshot = demo_run.snapshot
    assert {key: document[key] for key in ("run_id", "data_kind", "input_sha256", "artifact_sha256",
                                           "symbols", "model", "holdout_touches")} == {
        "run_id": snapshot.run_id, "data_kind": "synthetic", "input_sha256": snapshot.input_sha256,
        "artifact_sha256": snapshot.artifact_sha256, "symbols": 8, "model": snapshot.model,
        "holdout_touches": 1}
    assert document["tickers"] == [f"DEMO0{index}" for index in range(1, 9)]
    assert document["holdout"] == snapshot.holdout.model_dump()
    assert [(stage["stage"], stage["status"]) for stage in document["journal"]] == [
        (name, "succeeded") for name in ("generate_bars", "prepare", "train", "holdout", "infer_snapshot",
                                         "publish_snapshot")]
    assert all(stage["duration_ms"] >= 0 for stage in document["journal"])
    text = output.read_text()
    for forbidden in ("predicted_return", "last_close", "input_summary\":", "[mock]", str(tmp_path)):
        assert forbidden not in text
    for row in snapshot.input_summary:
        assert repr(row.last_close) not in text


def test_evidence_records_failed_stage_and_validate_input_aggregates(demo_run):
    events = [{"stage": "validate_input", "status": "started"},
              {"stage": "validate_input", "status": "succeeded", "duration_ms": 3.0, "rows": 10,
               "symbols": 5, "input_sha256": "a" * 64},
              {"stage": "infer_snapshot", "status": "failed", "duration_ms": 1.0, "error_type": "DataError"}]
    assert aggregate_evidence(demo_run.snapshot, events)["journal"] == [
        {"stage": "validate_input", "status": "succeeded", "duration_ms": 3.0, "rows": 10, "symbols": 5,
         "input_sha256": "a" * 64},
        {"stage": "infer_snapshot", "status": "failed", "duration_ms": 1.0, "error_type": "DataError"}]


def test_evidence_refuses_to_overwrite_or_to_use_a_corrupt_journal(demo_run, tmp_path):
    existing = tmp_path / "evidencia.json"
    existing.write_text("previa")
    with pytest.raises(SystemExit):
        main(["--snapshot", str(demo_run.path), "--journal", str(demo_run.journal), "--output", str(existing)])
    assert existing.read_text() == "previa"
    corrupt = tmp_path / "pipeline.jsonl"
    corrupt.write_text(demo_run.journal.read_text() + "{rota\n")
    with pytest.raises(SystemExit):
        main(["--snapshot", str(demo_run.path), "--journal", str(corrupt), "--output", str(tmp_path / "x.json")])
    assert not (tmp_path / "x.json").exists()
