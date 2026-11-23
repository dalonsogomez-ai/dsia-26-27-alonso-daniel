import json

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app
from dsia_web.build import demo, write_snapshot
from dsia_web.snapshot import read_snapshot


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    root = tmp_path_factory.mktemp("flow")
    path = root / "snapshot.json"
    snapshot = demo(root / "work")
    write_snapshot(snapshot, path)
    return path, snapshot


def test_pipeline_backend_and_dashboard(report):
    path, snapshot = report
    with TestClient(create_app(path)) as client:
        response = client.get("/api/v1/snapshot")
        assert response.status_code == 200
        document = response.json()
        assert document == snapshot.model_dump(mode="json")
        assert client.get("/health").json()["run_id"] == document["run_id"]
        assert document["data_kind"] == "synthetic"
        assert document["horizon_sessions"] == 21
        assert document["holdout_touches"] == 1
        assert document["explanation"]["provider"] == "mock"
        assert len(document["predictions"]) == 8
        for earlier, later in (("train", "validation"), ("validation", "test")):
            assert document["splits"][earlier]["max_target_end"] < document["splits"][later]["start"]
        assert "run_id" in client.get("/api/v1/snapshot/schema").json()["required"]
        assert client.get("/").status_code == 200
        assert 'fetch("/api/v1/snapshot"' in client.get("/static/dashboard.js").text


@pytest.mark.parametrize("contents", [None, "{invalid", "{}"])
def test_unavailable_is_visible_and_does_not_echo_disk_path(tmp_path, contents):
    path = tmp_path / "snapshot-privado.json"
    if contents is not None:
        path.write_text(contents)
    with TestClient(create_app(path)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 503
        report = client.get("/api/v1/snapshot")
        assert report.status_code == 503
        assert report.json()["detail"]["code"] == "snapshot_unavailable"
        assert str(path) not in report.text


def test_existing_snapshot_is_not_overwritten(report):
    path, snapshot = report
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_snapshot(snapshot, path)
    assert path.read_bytes() == before


def test_report_detects_content_mismatch(report, tmp_path):
    path, _ = report
    document = json.loads(path.read_text())
    document["predictions"][0]["predicted_return"] = 0.9
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="hash del informe"):
        read_snapshot(changed)
