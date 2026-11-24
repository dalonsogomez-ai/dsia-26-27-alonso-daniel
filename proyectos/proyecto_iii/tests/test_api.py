from datetime import timedelta

import pytest
from starlette.testclient import TestClient

import logging

from swarmtrade_app.ai_client import AIClient, AIClientError

import dsia_web
from dsia_web.app import create_app

# >> R7: esta tanda es la RC2; el tag v0.9.0-rc2 lo crea el autor tras el CI en verde.
VERSION = "0.9.0-rc2"
AI_OK = {"ai_provider": "mock", "ai_config": "ok", "ai_last_call": "never"}


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
        "version": VERSION, "commit": "local",
        "checks": {"snapshot_loaded": True, "data_kind": "synthetic", "as_of": str(snapshot.as_of),
                   "snapshot_age_days": 3, "journal_available": True, **AI_OK},
    }
    assert str(demo_run.path.parent) not in response.text


def test_health_unavailable_is_503_with_typed_checks(tmp_path):
    with TestClient(create_app(tmp_path / "falta.json", journal_path=tmp_path / "falta.jsonl")) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "version": VERSION, "commit": "local", "checks": {
        "snapshot_loaded": False, "data_kind": None, "as_of": None, "snapshot_age_days": None,
        "journal_available": False, **AI_OK}}
    assert str(tmp_path) not in response.text


def test_health_is_degraded_after_a_failed_provider_call_and_ready_after_a_good_one(demo_run, monkeypatch):
    # >> R9 (tema 4, A3 opción A): el proveedor en fallo deja el servicio en 200 «degraded», no en 503.
    outcome = {"kind": "timeout"}
    original = AIClient.analyze

    def flaky(self, request):
        if outcome["kind"]:
            raise AIClientError("Inferencia fallida", kind=outcome["kind"])
        return original(self, request)

    monkeypatch.setattr(AIClient, "analyze", flaky)
    symbol = demo_run.snapshot.predictions[0].symbol
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        assert client.post("/api/v1/analyze", json={"symbol": symbol}).status_code == 504
        failing = client.get("/health")
        outcome["kind"] = None
        assert client.post("/api/v1/analyze", json={"symbol": symbol}).status_code == 200
        recovered = client.get("/health")
    assert failing.status_code == 200
    assert (failing.json()["status"], failing.json()["checks"]["ai_last_call"]) == ("degraded", "failing:timeout")
    assert failing.json()["run_id"] == demo_run.snapshot.run_id
    assert recovered.status_code == 200
    assert (recovered.json()["status"], recovered.json()["checks"]["ai_last_call"]) == ("ready", "ok")


@pytest.mark.parametrize("env,provider,logged", [
    ({"AI_PROVIDER": "nvidia", "NVIDIA_MAX_TOKENS": "99999"}, "nvidia",
     "config_invalid ai_provider=nvidia NVIDIA_MAX_TOKENS debe ser un número entre 1 y 4096"),
    ({"AI_PROVIDER": "nvidia"}, "nvidia", "config_invalid ai_provider=nvidia Falta NVIDIA_API_KEY en el entorno"),
    ({"AI_PROVIDER": " HuggingFace "}, "hf", "config_invalid ai_provider=hf Falta HF_TOKEN en el entorno"),
    # > Un proveedor desconocido no se publica ni se registra tal cual: solo «invalid» y su longitud.
    ({"AI_PROVIDER": "openai"}, "invalid",
     "config_invalid ai_provider=<no válido, 6 caracteres> Proveedor no soportado; usa mock, hf o nvidia"),
    ({"AI_MOCK_MODE": "explota"}, "mock",
     "config_invalid ai_provider=mock AI_MOCK_MODE debe ser down, timeout, invalid o bug"),
])
def test_invalid_ai_configuration_is_reported_at_startup_without_stopping(demo_run, monkeypatch, caplog,
                                                                          env, provider, logged):
    # >> R9: la errata del panel se ve en /health y en el log al arrancar, no al pulsar «Explicar símbolo».
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path)) as client:
            health = client.get("/health")
            snapshot = client.get("/api/v1/snapshot")
    assert (health.status_code, health.json()["status"]) == (200, "degraded")
    assert {name: health.json()["checks"][name] for name in AI_OK} == {
        "ai_provider": provider, "ai_config": "invalid", "ai_last_call": "never"}
    assert snapshot.status_code == 200  # > El informe se sigue sirviendo.
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert errors == [logged]


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_blank_ai_provider_is_mock_in_health_like_in_the_client(demo_run, monkeypatch, blank):
    # >> AIClient.from_env recorta antes de aplicar «mock»; /health no puede decir «invalid» con el mock activo.
    monkeypatch.setenv("AI_PROVIDER", blank)
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        health = client.get("/health").json()
        answer = client.post("/api/v1/analyze", json={"symbol": demo_run.snapshot.predictions[0].symbol})
    assert health["status"] == "ready"
    assert {name: health["checks"][name] for name in AI_OK} == AI_OK
    assert (answer.status_code, answer.json()["provider"]) == (200, "mock")


def test_a_key_pasted_into_ai_provider_is_neither_published_nor_logged(demo_run, monkeypatch, caplog):
    # >> /health es público: si alguien pega la clave en el campo AI_PROVIDER del panel, no se expone.
    pasted = "clave.pegada.por.error." + "Z" * 40
    monkeypatch.setenv("AI_PROVIDER", pasted)
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            health = client.get("/health")
            failed = client.post("/api/v1/analyze", json={"symbol": demo_run.snapshot.predictions[0].symbol})
    assert (health.json()["status"], health.json()["checks"]["ai_provider"]) == ("degraded", "invalid")
    assert failed.status_code == 503
    for text in (health.text, failed.text, caplog.text):
        assert pasted.lower()[:20] not in text.lower()
    assert "config_invalid ai_provider=<no válido, 63 caracteres>" in caplog.text
    assert "analyze_failed request_id=" in caplog.text and " provider=invalid " in caplog.text


def test_ai_configuration_with_its_key_is_ok_and_the_key_never_leaks(demo_run, monkeypatch, caplog):
    key = "clave.falsa.nvidia.solo.para.esta.prueba"
    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", key)
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app(demo_run.path)) as client:
            health = client.get("/health")
    assert health.json()["status"] == "ready"
    assert {name: health.json()["checks"][name] for name in AI_OK} == {
        "ai_provider": "nvidia", "ai_config": "ok", "ai_last_call": "never"}
    assert key not in health.text and key not in caplog.text


@pytest.mark.parametrize("env,commit", [
    ({}, "local"),
    ({"DSIA_COMMIT": " abc1234 "}, "abc1234"),
    ({"RENDER_GIT_COMMIT": "  ", "DSIA_COMMIT": "abc1234"}, "abc1234"),
    ({"RENDER_GIT_COMMIT": "e433fae5f1d2c3b4a5968778695a4b3c2d1e0f9a", "DSIA_COMMIT": "abc1234"}, "e433fae"),
    ({"DSIA_COMMIT": "e433fae5f1d2c3b4a5968778695a4b3c2d1e0f9a"}, "e433fae5f1d2c3b4a5968778695a4b3c2d1e0f9a"),
    # > Solo se publica un hash hexadecimal de 7 a 40 caracteres; lo demás sale como «invalid».
    ({"DSIA_COMMIT": "v" * 60}, "invalid"),
    ({"DSIA_COMMIT": "abc123"}, "invalid"),
    ({"DSIA_COMMIT": "a" * 41}, "invalid"),
    ({"DSIA_COMMIT": "release-0.9.0-rc2"}, "invalid"),
    ({"RENDER_GIT_COMMIT": "main", "DSIA_COMMIT": "abc1234"}, "invalid"),
])
def test_health_and_metrics_expose_version_and_deployed_commit(demo_run, monkeypatch, env, commit):
    # >> Versión del III y commit desplegado: RENDER_GIT_COMMIT[:7] en Render, DSIA_COMMIT fuera de él, o local.
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app(demo_run.path)) as client:
        health, metrics = client.get("/health").json(), client.get("/api/v1/metrics").json()
    assert dsia_web.__version__ == VERSION
    assert (health["version"], health["commit"]) == (metrics["version"], metrics["commit"]) == (VERSION, commit)


@pytest.mark.parametrize("name", ["DSIA_COMMIT", "RENDER_GIT_COMMIT"])
def test_a_key_pasted_into_the_commit_variable_is_neither_published_nor_logged(demo_run, monkeypatch, caplog, name):
    # >> Misma política que AI_PROVIDER: /health y /api/v1/metrics son públicos; en el log, solo la longitud.
    key = "nvapi-clave.falsa.commit.0123456789"  # > 35 caracteres: cabe en los 40 que antes se publicaban
    monkeypatch.setenv(name, key)
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app(demo_run.path)) as client:
            health, metrics = client.get("/health"), client.get("/api/v1/metrics")
    assert health.json()["commit"] == metrics.json()["commit"] == "invalid"
    for fragment in (key, key[:7], key[:20]):
        assert fragment not in health.text and fragment not in metrics.text and fragment not in caplog.text
    assert f"{name} no válido ({len(key)} caracteres)" in caplog.text


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
        "version": VERSION, "commit": "local",
        "requests": [{"route": "/api/v1/predictions/{symbol}", "status": 404, "count": 1},
                     {"route": "/api/v1/predictions/{symbol}", "status": 422, "count": 1},
                     {"route": "/health", "status": 200, "count": 2}],
        "rate_limit": {"per_minute": 5, "per_day": 200, "per_ip_day": 30, "trusted_proxy_hops": 1, "used_today": 0,
                       "concurrency": 4, "concurrency_per_ip": 2, "in_flight": 0,
                       "rejected": {"per_minute": 0, "per_day": 0, "per_ip_day": 0, "busy": 0, "busy_per_ip": 0},
                       "xff_hops_seen": {}, "client_ip_source": {}},
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
