"""-> Verificar reanudación, integridad y cobertura sin red ni credenciales."""

from datetime import date
import gzip
import json
from types import SimpleNamespace

import pytest

import alpaca_io
from alpaca_io import ApiError, DiskLimit, Storage, Task, download, paths, read_pages
from auditar_alpaca import inspect_manifest
from descargar_alpaca_completo import end_timestamp, months, news_tasks, option_catalog_tasks
from descargar_alpaca_completo import options_after_catalogs, work_queue


@pytest.fixture(autouse=True)
def controlled_disk_space(monkeypatch):
    """> Evitar que la suite dependa del disco libre del runner de CI."""
    monkeypatch.setattr(alpaca_io.shutil, "disk_usage", lambda _: SimpleNamespace(free=10**12))


@pytest.fixture
def task():
    return Task("noticias", "2026-10", ("data", "news", "--include-content"), "news", True, "news")


def test_resume_uses_next_token_and_preserves_all_fields(tmp_path, monkeypatch, task):
    requests = []
    def fake(command, **kwargs):
        requests.append(kwargs["token"])
        if kwargs["token"] is None:
            return {"news": [{"id": 1, "content": "texto", "unknown_field": 42}], "next_page_token": "two"}
        return {"news": [{"id": 2}], "next_page_token": None}
    monkeypatch.setattr(alpaca_io, "call", fake)
    storage = Storage(tmp_path)
    first = download(task, tmp_path, storage, page_budget=1)
    assert first["status"] == "partial"
    final, manifest, partial, checkpoint = paths(tmp_path, task)
    assert not manifest.exists() and not final.exists()
    with partial.open("ab") as sink:
        sink.write(b"uncommitted crash bytes")
    second = download(task, tmp_path, storage, page_budget=1)
    assert requests == [None, "two"]
    assert second["status"] == "complete" and second["rows"] == 2
    assert not checkpoint.exists() and not partial.exists()
    assert list(read_pages(final))[0]["news"][0]["unknown_field"] == 42
    assert inspect_manifest(manifest, deep=True)["valid"]


def test_failed_page_keeps_previous_checkpoint(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"news": [{"id": 1}], "next_page_token": "two"})
    download(task, tmp_path, Storage(tmp_path), page_budget=1)
    def fail(*args, **kwargs):
        raise ApiError("offline", 503)
    monkeypatch.setattr(alpaca_io, "call", fail)
    with pytest.raises(ApiError):
        download(task, tmp_path, Storage(tmp_path))
    _, manifest, partial, checkpoint = paths(tmp_path, task)
    assert not manifest.exists() and partial.exists()
    assert json.loads(checkpoint.read_text())["next_page_token"] == "two"


def test_repeated_token_is_not_published(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"news": [], "next_page_token": "loop"})
    with pytest.raises(ValueError, match="repetido"):
        download(task, tmp_path, Storage(tmp_path))
    _, manifest, _, checkpoint = paths(tmp_path, task)
    assert not manifest.exists()
    assert json.loads(checkpoint.read_text())["pages"] == 1


def test_missing_payload_is_error_not_empty_dataset(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"something_else": []})
    with pytest.raises(ValueError, match="news"):
        download(task, tmp_path, Storage(tmp_path))
    assert not paths(tmp_path, task)[1].exists()


def test_completed_task_does_not_call_api_again(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"news": [], "next_page_token": None})
    result = download(task, tmp_path, Storage(tmp_path))
    def fail(*args, **kwargs):
        pytest.fail("Consulta ya completada")
    monkeypatch.setattr(alpaca_io, "call", fail)
    assert download(task, tmp_path, Storage(tmp_path)) == result


def test_truncated_completed_file_is_rejected(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"news": []})
    download(task, tmp_path, Storage(tmp_path))
    final, manifest, _, _ = paths(tmp_path, task)
    final.write_bytes(b"broken")
    with pytest.raises(ValueError, match="datos ausentes"):
        download(task, tmp_path, Storage(tmp_path))
    assert not inspect_manifest(manifest, deep=True)["valid"]


def test_global_budget_includes_nested_and_partial_files(tmp_path):
    folder = tmp_path / "other"
    folder.mkdir()
    (folder / "old.part.jsonl.gz").write_bytes(b"x" * 200)
    with pytest.raises(DiskLimit):
        Storage(tmp_path, max_gb=0.0000001).check()


def test_free_space_reserve_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(alpaca_io.shutil, "disk_usage", lambda _: SimpleNamespace(free=19_000_000_000))
    with pytest.raises(DiskLimit):
        Storage(tmp_path, min_free_gb=20).check()


def test_forbidden_does_not_publish_manifest(tmp_path, monkeypatch, task):
    def fail(*a, **k):
        raise ApiError("subscription does not permit", 403)
    monkeypatch.setattr(alpaca_io, "call", fail)
    with pytest.raises(ApiError) as exc:
        download(task, tmp_path, Storage(tmp_path))
    assert exc.value.status == 403
    assert not paths(tmp_path, task)[1].exists()


@pytest.mark.parametrize("command", [("order", "submit"), ("position", "close-all"),
                                     ("api", "POST", "/v2/orders"), ("asset", "get")])
def test_writer_and_private_commands_rejected(command):
    with pytest.raises(ValueError):
        alpaca_io.call(command)


def test_invalid_symbol_does_not_drop_other_symbols(tmp_path, monkeypatch):
    task = Task("stocks", "test", ("data", "multi-bars", "--symbols", "BAD,AAPL"), "bars", True)
    def fake(command, **kwargs):
        if "BAD,AAPL" in command:
            raise ApiError("invalid symbol: BAD", 400)
        assert "AAPL" in command
        return {"bars": {"AAPL": [{"c": 5}]}, "next_page_token": None}
    monkeypatch.setattr(alpaca_io, "call", fake)
    result = download(task, tmp_path, Storage(tmp_path))
    assert result["rows"] == 1 and result["rejected_symbols"][0]["symbol"] == "BAD"


def test_query_parameters_change_identity(task):
    other = Task(task.family, task.name, task.command + ("--symbols", "AAPL"), task.key, True)
    assert task.identity != other.identity


def test_month_boundaries_and_leap_year():
    result = list(months(date(2024, 2, 1), date(2024, 3, 5)))
    assert result == [("2024-02", date(2024, 2, 1), date(2024, 2, 29)),
                      ("2024-03", date(2024, 3, 1), date(2024, 3, 5))]
    assert end_timestamp(result[0][2]) == "2024-02-29T23:59:59.999999Z"


def test_news_reuses_only_existing_covered_months(tmp_path):
    folder = tmp_path / "noticias"
    folder.mkdir()
    meta = {"mode": "news", "start": "2015-01-01T00:00:00Z", "end": "2015-02-01T00:00:00Z",
            "data_file": "2015-01.jsonl.gz", "rows": 0}
    (folder / "2015-01.manifest.json").write_text(json.dumps(meta))
    assert len(list(news_tasks(date(2015, 2, 5), tmp_path))) == 2
    (folder / "2015-01.jsonl.gz").write_bytes(gzip.compress(b""))
    chosen = list(news_tasks(date(2015, 2, 5), tmp_path))
    assert len(chosen) == 1 and chosen[0].name == "2015-02"


def test_option_catalog_removes_default_weekend_limit():
    tasks = list(option_catalog_tasks())
    assert len(tasks) == 2
    for task in tasks:
        assert "2099-12-31" in task.command and "--show-deliverables" in task.command
        assert task.paginated


def test_audit_rejects_wrong_legacy_count(tmp_path):
    data = tmp_path / "news.jsonl.gz"
    data.write_bytes(gzip.compress(b'{"id":1}\n'))
    manifest = tmp_path / "news.manifest.json"
    manifest.write_text(json.dumps({"data_file": data.name, "rows": 2, "mode": "news"}))
    report = inspect_manifest(manifest, deep=True)
    assert not report["valid"] and report["actual_rows"] == 1


def test_resume_after_final_rename_before_manifest(tmp_path, monkeypatch, task):
    monkeypatch.setattr(alpaca_io, "call", lambda *a, **k: {"news": [{"id": 1}]})
    original = alpaca_io.atomic_json
    def crash(path, data):
        if path.name.endswith(".manifest.json"):
            raise OSError("simulated crash")
        original(path, data)
    monkeypatch.setattr(alpaca_io, "atomic_json", crash)
    with pytest.raises(OSError):
        download(task, tmp_path, Storage(tmp_path))
    monkeypatch.setattr(alpaca_io, "atomic_json", original)
    assert download(task, tmp_path, Storage(tmp_path))["rows"] == 1


def test_work_queue_resumes_partial_after_initial_source(tmp_path, task):
    source = work_queue(iter([task]), tmp_path, {})
    assert next(source) == task
    checkpoint = paths(tmp_path, task)[3]
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}")
    assert next(source) == task
    checkpoint.unlink()
    assert list(source) == []


def test_work_queue_does_not_retry_denied_partial(tmp_path, task):
    denied = {}
    source = work_queue(iter([task]), tmp_path, denied)
    assert next(source) == task
    checkpoint = paths(tmp_path, task)[3]
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("{}")
    denied[task.access] = {"status": "forbidden"}
    assert list(source) == []


def test_options_wait_for_catalog_but_stop_on_permission_error(tmp_path):
    denied = {}
    source = options_after_catalogs(tmp_path, date(2026, 10, 18), denied)
    assert next(source) is None
    denied["option_contracts"] = {"status": "forbidden"}
    assert list(source) == []


@pytest.fixture
def snapshot_script(monkeypatch):
    """> Script de capturas con la CLI de Alpaca sustituida por un doble sin red."""
    import descargar_alpaca_actual

    calls = []
    def fake_call(*parts):
        calls.append(parts)
        if parts[0] == "multi-snapshots":
            symbols = parts[parts.index("--symbols") + 1].split(",")
            return {symbol: {"latestTrade": {"p": 1.0}} for symbol in symbols}
        return {"reference": parts[-1]}
    monkeypatch.setattr(descargar_alpaca_actual, "call", fake_call)
    monkeypatch.setattr(descargar_alpaca_actual.time, "sleep", lambda _: None)
    return descargar_alpaca_actual, calls


def test_snapshot_help_does_not_run_anything(tmp_path, snapshot_script, capsys):
    module, calls = snapshot_script
    with pytest.raises(SystemExit) as stop:
        module.main(["--help", "--raw", str(tmp_path)])
    assert stop.value.code == 0
    assert "--raw" in capsys.readouterr().out
    assert calls == [] and list(tmp_path.iterdir()) == []


def test_snapshot_without_assets_catalog_fails_before_creating_folders(tmp_path, snapshot_script, capsys):
    module, calls = snapshot_script
    assert module.main(["--raw", str(tmp_path)]) == 1
    assert "alpaca_activos.json" in capsys.readouterr().err
    assert calls == [] and list(tmp_path.iterdir()) == []


def test_snapshot_filters_assets_and_writes_summary(tmp_path, snapshot_script):
    module, calls = snapshot_script
    assets = [
        {"symbol": "AAA", "class": "us_equity", "status": "active", "exchange": "NYSE"},
        {"symbol": "BBB", "class": "us_equity", "status": "inactive", "exchange": "NYSE"},
        {"symbol": "CCC", "class": "us_equity", "status": "active", "exchange": "OTC"},
        {"symbol": "ddd", "class": "us_equity", "status": "active", "exchange": "NYSE"},
    ]
    (tmp_path / "alpaca_activos.json").write_text(json.dumps(assets), encoding="utf-8")
    assert module.main(["--raw", str(tmp_path)]) == 0
    out = tmp_path / "masivo" / "estado_actual"
    summary = json.loads((out / "resumen.json").read_text(encoding="utf-8"))
    assert summary["requested_symbols"] == 1 and summary["returned_snapshots"] == 1
    assert calls[0][:3] == ("multi-snapshots", "--symbols", "AAA")
    assert json.loads((out / "fallos.json").read_text(encoding="utf-8")) == []
