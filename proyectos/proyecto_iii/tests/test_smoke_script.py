""">> smoke_test.sh con un curl falso en el PATH: timeouts de los GET y del análisis, sin red ni servidor."""

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_test.sh"
# > Registra los argumentos de cada llamada y devuelve el JSON de la ruta pedida (último argumento).
FAKE_CURL = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CURL_LOG"
url="${@: -1}"
case "$url" in
  */health) name=health ;;
  */api/v1/snapshot) name=snapshot ;;
  */api/v1/predictions/*) name=prediction ;;
  */api/v1/analyze) name=analyze ;;
  */api/v1/metrics) name=metrics ;;
  *) exit 22 ;;
esac
cat "$FIXTURES/$name.json"
"""
RESPONSES = {
    "health": {"status": "ready", "run_id": "r1", "as_of": "2026-11-23", "checks": {"snapshot_loaded": True}},
    "snapshot": {"run_id": "r1", "as_of": "2026-11-23", "predictions": [{"symbol": "AAPL"}]},
    "prediction": {"symbol": "AAPL", "run_id": "r1"},
    "analyze": {"symbol": "AAPL", "run_id": "r1", "summary": "ok", "request_id": "smoke-analyze-0001",
                "provider": "mock"},
    "metrics": {"run_id": "r1", "requests_total": 4},
}


def run_smoke(tmp_path, responses=None, expect_ok=True, **env):
    fake = tmp_path / "bin"
    fake.mkdir(parents=True)
    (fake / "curl").write_text(FAKE_CURL)
    (fake / "curl").chmod(stat.S_IRWXU)
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir(parents=True)
    for name, body in {**RESPONSES, **(responses or {})}.items():
        (fixtures / f"{name}.json").write_text(json.dumps(body))
    log = tmp_path / "curl.log"
    result = subprocess.run(
        ["bash", str(SCRIPT), "https://servicio.test/"], capture_output=True, text=True, timeout=60,
        env={"PATH": f"{fake}{os.pathsep}{os.environ['PATH']}", "CURL_LOG": str(log), "FIXTURES": str(fixtures),
             "PYTHON": sys.executable, **env})
    if not expect_ok:
        assert result.returncode != 0
        return result.stderr
    assert result.returncode == 0, result.stderr
    assert "Smoke correcto · run_id=r1 · símbolo=AAPL" in result.stdout
    return log.read_text().splitlines()


def last_max_time(line: str) -> str:
    # > curl usa el último --max-time de la línea de órdenes.
    return re.findall(r"--max-time (\S+)", line)[-1]


@pytest.mark.parametrize("env,get_timeout,analyze_timeout", [
    ({}, "90", "200"),
    ({"SMOKE_TIMEOUT": "120", "ANALYZE_TIMEOUT": "300"}, "120", "300"),
])
def test_gets_wait_for_cold_start_and_analysis_keeps_its_own_timeout(tmp_path, env, get_timeout, analyze_timeout):
    calls = run_smoke(tmp_path, **env)
    gets = [line for line in calls if "-X POST" not in line]
    [analyze] = [line for line in calls if "-X POST" in line]
    assert [line.rsplit(" ", 1)[-1] for line in gets] == [
        "https://servicio.test/health", "https://servicio.test/api/v1/snapshot",
        "https://servicio.test/api/v1/predictions/AAPL", "https://servicio.test/api/v1/metrics"]
    assert {last_max_time(line) for line in gets} == {get_timeout}
    assert last_max_time(analyze) == analyze_timeout


def test_first_health_check_retries_through_cold_start_and_refresh(tmp_path):
    # >> R5: arranque en frío (~50 s) + refresco de Alpaca (hasta DSIA_REFRESH_TIMEOUT=180 s) no caben en
    #    un solo GET de 90 s: el primero se reintenta 6 veces cada 10 s, también si la conexión se rechaza.
    health, *rest = run_smoke(tmp_path)
    assert health.endswith("https://servicio.test/health")
    for flag in ("--retry 6", "--retry-all-errors", "--retry-connrefused", "--retry-delay 10", "--max-time 90"):
        assert flag in health
    assert not [line for line in rest if "--retry" in line]  # > El resto de llamadas no se reintenta.


def test_degraded_health_is_accepted_when_the_analysis_still_works(tmp_path):
    # >> R9: «degraded» (200) es un servicio que responde; el análisis del smoke sigue siendo obligatorio.
    degraded = {**RESPONSES["health"], "status": "degraded"}
    run_smoke(tmp_path / "ok", responses={"health": degraded})
    stderr = run_smoke(tmp_path / "ko", responses={"health": degraded, "analyze": {"error": "ai_unavailable"}},
                       expect_ok=False)
    assert "análisis incoherente" in stderr
    unknown = {**RESPONSES["health"], "status": "unavailable"}
    assert "salud no lista" in run_smoke(tmp_path / "unavailable", responses={"health": unknown}, expect_ok=False)
