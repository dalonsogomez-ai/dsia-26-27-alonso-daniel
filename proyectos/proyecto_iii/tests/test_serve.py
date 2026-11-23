""">> Arranque del contenedor: refresco con datos reales antes de Uvicorn, sin romper el servicio si falla."""

import json
from datetime import date, datetime, timezone

import pytest

from dsia_web import alpaca_source, serve
from dsia_web.build import main as build_main
from test_alpaca import SYMBOLS, FakeClient, sdk_frame

TODAY = date(2026, 11, 24)


def write_snapshot(path, data_kind, generated):
    path.write_text(json.dumps({"data_kind": data_kind, "generated_at": generated}))
    return path


@pytest.mark.parametrize("data_kind,generated,expected", [
    ("synthetic", "2026-11-24T08:00:00+00:00", True),
    ("alpaca", "2026-11-24T08:00:00+00:00", False),
    ("alpaca", "2026-11-23T23:59:00+00:00", True),
])
def test_needs_refresh_unless_real_and_from_today(tmp_path, data_kind, generated, expected):
    snapshot = write_snapshot(tmp_path / "s.json", data_kind, generated)
    assert serve.needs_refresh(snapshot, today=TODAY) is expected


def test_missing_or_invalid_snapshot_needs_refresh(tmp_path):
    assert serve.needs_refresh(tmp_path / "falta.json", today=TODAY)
    (tmp_path / "roto.json").write_text("{")
    assert serve.needs_refresh(tmp_path / "roto.json", today=TODAY)


@pytest.fixture
def baked(tmp_path, monkeypatch):
    """Snapshot demo «horneado» en el build y exec de Uvicorn capturado."""
    output = tmp_path / "baked" / "snapshot.json"
    assert build_main(["demo", "--work", str(tmp_path / "w"), "--output", str(output)]) == 0
    monkeypatch.setenv("DSIA_SNAPSHOT", str(output))
    monkeypatch.setenv("DSIA_JOURNAL", str(tmp_path / "baked" / "pipeline.jsonl"))
    monkeypatch.setenv("PORT", "9123")
    monkeypatch.setenv("DSIA_SYMBOLS", ",".join(SYMBOLS))
    calls = []
    monkeypatch.setattr(serve.os, "execvp", lambda file, args: calls.append(args))
    monkeypatch.setattr(serve, "SECRET_FILE", tmp_path / "no-existe.env")
    return output, calls


def test_without_credentials_serves_the_baked_snapshot(baked, monkeypatch):
    output, calls = baked
    monkeypatch.delenv("ALPACA_PAPER_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET_KEY", raising=False)
    serve.main()
    assert calls == [["uvicorn", "dsia_web.app:app", "--host", "0.0.0.0", "--port", "9123"]]
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output)


def test_with_credentials_refreshes_real_data_before_serving(baked, tmp_path, monkeypatch):
    output, calls = baked
    (tmp_path / "sdk").mkdir()
    monkeypatch.setattr(alpaca_source, "default_client", lambda creds: FakeClient(sdk_frame(tmp_path / "sdk")))
    monkeypatch.setenv("ALPACA_PAPER_API_KEY_ID", "clave-falsa")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET_KEY", "secreto-falso")
    serve.main()
    fresh = serve.os.environ["DSIA_SNAPSHOT"]
    assert fresh != str(output) and len(calls) == 1
    document = json.loads(open(fresh).read())
    assert document["data_kind"] == "alpaca" and document.get("input_summary") is None
    journal = open(serve.os.environ["DSIA_JOURNAL"]).read()
    assert '"download_bars"' in journal and "secreto-falso" not in journal
    # -> El CSV descargado no se queda en disco tras publicar el informe.
    assert not list(serve.Path(fresh).parent.glob("**/bars.csv"))


def test_failed_refresh_keeps_the_baked_snapshot(baked, tmp_path, monkeypatch, caplog):
    output, calls = baked
    (tmp_path / "sdk").mkdir()
    failing = FakeClient(sdk_frame(tmp_path / "sdk"), fail_feeds={"sip", "iex"})
    monkeypatch.setattr(alpaca_source, "default_client", lambda creds: failing)
    monkeypatch.setenv("ALPACA_PAPER_API_KEY_ID", "clave-falsa")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET_KEY", "secreto-falso")
    serve.main()
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output) and len(calls) == 1
    assert "se sirve el informe del build" in caplog.text
