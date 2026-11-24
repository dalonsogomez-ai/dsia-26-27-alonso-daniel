import hashlib
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from dsia_web.app import STATIC, create_app
from dsia_web.build import main, write_snapshot
from dsia_web.snapshot import read_snapshot


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


def test_dashboard_consumes_operation_and_analysis_endpoints_without_inline_code(report):
    with TestClient(create_app(report[0])) as client:
        script = client.get("/static/dashboard.js").text
        page = client.get("/").text
    for endpoint in ('"/health"', '"/api/v1/metrics"', '"/api/v1/pipeline?limit=20"', '"/api/v1/analyze"'):
        assert endpoint in script
    for anchor in ('id="ops"', 'id="ops-events"', 'id="ops-version"', 'id="inputs"', 'id="analyze-form"',
                   'role="alert"'):
        assert anchor in page
    # > C5: el panel Operación pinta la versión y el commit que devuelve /health.
    assert '"ops-version"' in script and ".commit" in script
    # > R9: la tarjeta «Estado» distingue «degraded» y muestra el proveedor de IA y su última llamada.
    assert 'id="ops-ai"' in page and '"ops-ai"' in script
    for field in ('"degraded"', "ai_provider", "ai_config", "ai_last_call"):
        assert field in script
    # > Grafo del lote en Operación: lista ordenada navegable, panel de detalle y la tabla de eventos se mantiene.
    for anchor in ('<ol id="ops-graph"', 'id="ops-graph-detail"', 'id="ops-flow-alerts"', 'id="ops-events"'):
        assert anchor in page
    for name in ("function pipelineModel", '"generate_bars", "download_bars"', '"publish_snapshot"',
                 "ArrowRight: 1", '"Home"', '"End"', "aria-current"):
        assert name in script
    # > La CSP default-src 'self' bloquearía cualquier script, estilo o manejador inline.
    assert "<script>" not in page and "<style" not in page and " style=" not in page
    assert " on" + "click=" not in page and " on" + "submit=" not in page


CANVAS_SCRIPTS = ("/static/vendor/react.production.min.js", "/static/vendor/react-dom.production.min.js",
                  "/static/jsx-runtime.js", "/static/vendor/xyflow-react.umd.js", "/static/flow_canvas.js")


def test_canvas_view_loads_vendored_react_flow_only_on_demand(report):
    with TestClient(create_app(report[0])) as client:
        page = client.get("/").text
        script = client.get("/static/dashboard.js").text
        canvas = client.get("/static/flow_canvas.js").text
        served = {path: client.get(path) for path in CANVAS_SCRIPTS + ("/static/vendor/xyflow-react.css",)}
    # > «Lienzo interactivo» como vista adicional: la lista nativa sigue siendo la vista por defecto.
    for anchor in ('id="ops-view-list" aria-pressed="true"', 'id="ops-view-canvas" aria-pressed="false"',
                   'id="ops-canvas"', '<ol id="ops-graph"'):
        assert anchor in page
    assert 'class="flow-canvas"' in page and "hidden></div>" in page
    # > Carga diferida: la página no pide React ni React Flow hasta que se abre el lienzo.
    assert "vendor/" not in page and "flow_canvas.js" not in page
    for path in CANVAS_SCRIPTS:
        assert f'"{path}"' in script
        assert served[path].status_code == 200
    assert '"/static/vendor/xyflow-react.css"' in script and served["/static/vendor/xyflow-react.css"].status_code == 200
    # > Mismo modelo y mismo detalle que la lista: el lienzo solo dibuja lo que calcula pipelineModel.
    assert "pipelineModel(" not in canvas and "FLOW_STATES" not in canvas and "selectFlowNode(flowModel, id)" in script
    for name in ("ariaLabelConfig", "domAttributes", "aria-current", "tabIndex", "ArrowRight: 1", '"Home"', '"End"',
                 "deleteKeyCode: null", "nodesDraggable: false"):
        assert name in canvas
    # > Todo desde 'self': ni CDN ni scripts inline (la CSP default-src 'self' los bloquearía).
    for body in (script, canvas, served["/static/jsx-runtime.js"].text):
        body = body.replace("http://www.w3.org/2000/svg", "")  # > Namespace SVG, no una petición.
        assert "https://" not in body and "http://" not in body


def test_vendored_react_flow_matches_lockfile_manifest_and_licenses():
    static = STATIC / "vendor"
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    manifest = json.loads((static / "manifest.json").read_text())
    lock = json.loads((frontend / "package-lock.json").read_text())
    package = json.loads((frontend / "package.json").read_text())
    locked = {path.removeprefix("node_modules/"): info["version"] for path, info in lock["packages"].items()
              if path.startswith("node_modules/") and not path.startswith("node_modules/@types/")}
    assert manifest["packages"] == locked
    # > Versiones exactas (sin ^ ni ~) e iguales a las del lockfile.
    assert package["dependencies"] == {"@xyflow/react": "12.12.1", "react": "18.3.1", "react-dom": "18.3.1"}
    assert all(locked[name] == version for name, version in package["dependencies"].items())
    assert {path.name for path in static.iterdir()} == set(manifest["files"]) | {"manifest.json"}
    for name, info in manifest["files"].items():
        data = (static / name).read_bytes()
        assert (len(data), hashlib.sha256(data).hexdigest()) == (info["bytes"], info["sha256"]), name
    licenses = (static / "THIRD_PARTY_LICENSES.txt").read_text()
    assert all(f"{name}@{version} (" in licenses for name, version in locked.items())


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


def test_journal_reports_order_duration_and_published_snapshot(report):
    path, snapshot = report
    events = [json.loads(line) for line in path.with_name("pipeline.jsonl").read_text().splitlines()]
    stages = ["generate_bars", "prepare", "train", "holdout", "infer_snapshot", "publish_snapshot"]
    assert [(event["stage"], event["status"]) for event in events] == [
        (stage, status) for stage in stages for status in ("started", "succeeded")
    ]
    assert all(event["duration_ms"] >= 0 for event in events[1::2])
    assert events[-1]["run_id"] == snapshot.run_id


def test_failed_batch_retains_journal_and_does_not_publish(tmp_path):
    output = tmp_path / "snapshot.json"
    journal = tmp_path / "pipeline.jsonl"
    work = tmp_path / "work"
    work.mkdir()
    args = ["demo", "--work", str(work), "--output", str(output), "--journal", str(journal)]
    assert main(args) == 2
    original = journal.read_bytes()
    events = [json.loads(line) for line in original.splitlines()]
    assert len(events) == 2
    assert events[-1]["stage"] == "generate_bars"
    assert events[-1]["status"] == "failed"
    assert events[-1]["error_type"] == "FileExistsError"
    assert not output.exists()
    assert main(args) == 2
    assert journal.read_bytes() == original


@pytest.mark.parametrize("relative_journal", ["snapshot.json", "snapshot.json/pipeline.jsonl",
                                              "work/pipeline.jsonl"])
def test_conflicting_journal_path_is_rejected_before_writes(tmp_path, relative_journal):
    assert main(["demo", "--work", str(tmp_path / "work"),
                 "--output", str(tmp_path / "snapshot.json"),
                 "--journal", str(tmp_path / relative_journal)]) == 2
    assert list(tmp_path.iterdir()) == []
