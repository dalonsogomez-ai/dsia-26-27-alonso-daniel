""">> Arranque del contenedor: refresco con datos reales antes de Uvicorn, sin romper el servicio si falla."""

import json
import os
import subprocess
import sys
import time
from datetime import date

import pytest

from dsia_web import alpaca_source, serve
from dsia_web.build import main as build_main
from test_alpaca import SYMBOLS, FakeClient, sdk_frame

TODAY = date(2026, 11, 24)
# > Sin el access log de Uvicorn: escribiría la IP del par TCP en cada petición (dato personal fuera de
#   Render), y la línea «request request_id=…» del middleware ya registra método, ruta, estado y latencia.
UVICORN = ["uvicorn", "dsia_web.app:app", "--host", "0.0.0.0", "--port", "9123", "--no-access-log"]


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


@pytest.fixture
def credentials(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_API_KEY_ID", "clave-falsa")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET_KEY", "secreto-falso")


@pytest.fixture
def fake_subprocess(monkeypatch):
    """> Sustituye subprocess.run en serve: registra la orden y delega en ``behaviour``."""
    calls = []

    def install(behaviour):
        def fake_run(command, **kwargs):
            calls.append((command, kwargs))
            return behaviour(command, kwargs)
        monkeypatch.setattr(serve.subprocess, "run", fake_run)
        return calls
    return install


def in_process_build(command, kwargs):
    """> El «hijo» ejecuta la CLI real del lote en este proceso, con la descarga de Alpaca simulada."""
    assert command[:3] == [sys.executable, "-m", "dsia_web.build"]
    return subprocess.CompletedProcess(command, build_main(command[3:]))


def test_without_credentials_serves_the_baked_snapshot(baked, monkeypatch, fake_subprocess):
    output, calls = baked
    monkeypatch.delenv("ALPACA_PAPER_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET_KEY", raising=False)
    spawned = fake_subprocess(in_process_build)
    serve.main()
    assert calls == [UVICORN] and spawned == []
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output)


def test_with_credentials_refreshes_in_a_subprocess_before_serving(baked, tmp_path, monkeypatch, credentials,
                                                                   fake_subprocess):
    output, calls = baked
    (tmp_path / "sdk").mkdir()
    monkeypatch.setattr(alpaca_source, "default_client", lambda creds: FakeClient(sdk_frame(tmp_path / "sdk")))
    spawned = fake_subprocess(in_process_build)
    serve.main()
    [(command, kwargs)] = spawned
    # >> C3: la descarga corre en un proceso hijo con timeout (180 s por defecto) y sin --secrets-file si no existe.
    assert command[3] == "alpaca" and "--secrets-file" not in command
    assert kwargs == {"timeout": 180.0, "check": False}
    fresh = serve.os.environ["DSIA_SNAPSHOT"]
    assert fresh != str(output) and calls == [UVICORN]
    document = json.loads(open(fresh).read())
    assert document["data_kind"] == "alpaca" and document.get("input_summary") is None
    journal = open(serve.os.environ["DSIA_JOURNAL"]).read()
    assert '"download_bars"' in journal and "secreto-falso" not in journal
    # -> El CSV descargado no se queda en disco tras publicar el informe.
    assert not list(serve.Path(fresh).parent.glob("**/bars.csv"))


def test_failed_refresh_keeps_the_baked_snapshot(baked, credentials, fake_subprocess, caplog):
    output, calls = baked

    def published_then_failed(command, kwargs):
        # > build.py puede devolver 2 con el snapshot ya escrito (falla el cierre de publish_snapshot o
        #   del journal): solo el código 0 da por bueno el informe del hijo.
        target = serve.Path(command[command.index("--output") + 1])
        target.write_bytes(output.read_bytes())
        return subprocess.CompletedProcess(command, 2)

    fake_subprocess(published_then_failed)
    serve.main()
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output) and calls == [UVICORN]
    assert "Refresco con Alpaca terminó con código 2" in caplog.text
    assert "se sirve el informe del build" in caplog.text


def test_refresh_that_exceeds_the_timeout_is_cancelled_and_the_baked_snapshot_served(
        baked, credentials, monkeypatch, fake_subprocess, caplog):
    output, calls = baked
    monkeypatch.setenv("DSIA_REFRESH_TIMEOUT", "45")

    def hang(command, kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    spawned = fake_subprocess(hang)
    serve.main()
    assert spawned[0][1]["timeout"] == 45.0
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output) and calls == [UVICORN]
    assert "Refresco con Alpaca cancelado: superó DSIA_REFRESH_TIMEOUT=45 s" in caplog.text
    assert "se sirve el informe del build" in caplog.text


def test_refresh_that_cannot_start_serves_the_baked_snapshot(baked, credentials, fake_subprocess, caplog):
    output, calls = baked

    def missing(command, kwargs):
        raise FileNotFoundError("python")

    fake_subprocess(missing)
    serve.main()
    assert serve.os.environ["DSIA_SNAPSHOT"] == str(output) and calls == [UVICORN]
    assert "Refresco con Alpaca no se pudo lanzar: FileNotFoundError" in caplog.text


def test_secret_file_is_passed_to_the_refresh(baked, tmp_path, monkeypatch, fake_subprocess):
    secret = tmp_path / "alpaca.env"
    secret.write_text("ALPACA_PAPER_API_KEY_ID=clave-falsa\nALPACA_PAPER_API_SECRET_KEY=secreto-falso\n")
    monkeypatch.setattr(serve, "SECRET_FILE", secret)
    monkeypatch.delenv("ALPACA_PAPER_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET_KEY", raising=False)
    spawned = fake_subprocess(lambda command, kwargs: subprocess.CompletedProcess(command, 2))
    serve.main()
    [(command, _)] = spawned
    assert command[-2:] == ["--secrets-file", str(secret)]


@pytest.mark.parametrize("raw,expected", [(None, 180.0), ("", 180.0), (" 30 ", 30.0), ("0.5", 0.5),
                                          ("0", 180.0), ("-3", 180.0), ("abc", 180.0), ("nan", 180.0),
                                          ("inf", 180.0)])
def test_refresh_timeout_from_environment(raw, expected, caplog):
    env = {} if raw is None else {"DSIA_REFRESH_TIMEOUT": raw}
    assert serve.refresh_timeout(env) == expected
    invalid = raw is not None and raw.strip() and expected == 180.0
    assert ("DSIA_REFRESH_TIMEOUT no válido" in caplog.text) == bool(invalid)


def test_invalid_refresh_timeout_logs_its_length_but_never_the_value(caplog):
    # >> Una clave pegada por error en DSIA_REFRESH_TIMEOUT no debe llegar al log, ni en parte.
    pasted = "clave.falsa.nvidia.0123456789"
    assert serve.refresh_timeout({"DSIA_REFRESH_TIMEOUT": pasted}) == 180.0
    assert f"DSIA_REFRESH_TIMEOUT no válido ({len(pasted)} caracteres)" in caplog.text
    assert "clave.falsa" not in caplog.text


FAKE_BUILD = """import os, sys, time
open(os.environ["FAKE_BUILD_PID"], "w").write(str(os.getpid()))
time.sleep(60)
"""


def test_hung_build_process_is_killed_at_the_timeout(tmp_path, monkeypatch, caplog):
    # >> Subproceso falso real: un «lote» que se cuelga; refresh() lo mata al vencer el timeout.
    (tmp_path / "fake_build.py").write_text(FAKE_BUILD)
    monkeypatch.setenv("PYTHONPATH", f"{tmp_path}{os.pathsep}{os.environ.get('PYTHONPATH', '')}")
    monkeypatch.setenv("FAKE_BUILD_PID", str(tmp_path / "pid"))
    monkeypatch.setattr(serve, "BUILD_MODULE", "fake_build")
    monkeypatch.setattr(serve, "SECRET_FILE", tmp_path / "no-existe.env")
    started = time.monotonic()
    assert serve.refresh(timeout=3) is None
    assert time.monotonic() - started < 20
    pid = int((tmp_path / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert "Refresco con Alpaca cancelado: superó DSIA_REFRESH_TIMEOUT=3 s" in caplog.text
