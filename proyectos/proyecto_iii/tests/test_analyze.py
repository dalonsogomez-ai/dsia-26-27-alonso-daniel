import dataclasses
import logging
import re
import statistics
from types import SimpleNamespace

import anyio
import huggingface_hub
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient
from swarmtrade_app.ai_client import AIClient, AIClientError, AIResponse

from dsia_web.app import analysis_request, create_app, read_limited_body

URL = "/api/v1/analyze"


@pytest.fixture
def symbol(demo_run):
    return sorted(demo_run.snapshot.predictions, key=lambda row: -row.predicted_return)[0]


def report_aggregates(snapshot):
    """> Agregados de todo el informe, calculados aquí de forma independiente a app.py."""
    values = [row.predicted_return for row in snapshot.predictions]
    return statistics.fmean(values), statistics.pstdev(values), max(values) - min(values)


def test_analyze_returns_mock_explanation_with_trace(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    snapshot = demo_run.snapshot
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "analisis-0001"})
    assert response.status_code == 200
    body = response.json()
    latency = body.pop("latency_ms")
    assert isinstance(latency, float) and latency >= 0
    rmse = snapshot.validation[snapshot.model].rmse
    mean, std, spread = report_aggregates(snapshot)
    assert body == {
        "symbol": symbol.symbol, "predicted_return": symbol.predicted_return, "run_id": snapshot.run_id,
        "as_of": str(snapshot.as_of), "provider": "mock", "model": "mock-determinista-v1",
        "request_id": "analisis-0001",
        # >> C4: el texto describe el informe entero (8 símbolos) y sitúa el símbolo pedido en el ranking.
        "summary": (f"[mock] Modelo {snapshot.model}; horizonte 21 sesiones; 8 símbolos; "
                    f"media predicha {mean:.4%}; dispersión entre símbolos {std:.4%}; "
                    f"rango de predicciones {spread:.4%}; mejor señal {symbol.symbol}; "
                    f"símbolo analizado {symbol.symbol}: predicción {symbol.predicted_return:.4%}, puesto 1 de 8; "
                    f"RMSE validación {rmse:.6f}. "
                    "La predicción no demuestra rentabilidad ni incluye costes de ejecución."),
    }
    assert response.headers["x-request-id"] == "analisis-0001"


class RecordingClient:
    """> Doble de AIClient: guarda el AnalysisRequest que construye la API y responde sin red."""

    def __init__(self):
        self.requests = []

    def analyze(self, request):
        self.requests.append(request)
        return AIResponse("mock", "chat_completion", "registro", "ok")


def test_analyze_sends_report_aggregates_and_the_focused_symbol(demo_run):
    snapshot = demo_run.snapshot
    ranked = sorted(snapshot.predictions, key=lambda row: -row.predicted_return)
    chosen = ranked[2]
    recorder = RecordingClient()
    with TestClient(create_app(demo_run.path, api_key="", ai_client_factory=lambda: recorder)) as client:
        assert client.post(URL, json={"symbol": chosen.symbol}).status_code == 200
    mean, std, spread = report_aggregates(snapshot)
    [sent] = recorder.requests
    sent = dataclasses.asdict(sent)
    numbers = {name: sent.pop(name) for name in ("mean_prediction", "prediction_std", "prediction_spread")}
    assert numbers == pytest.approx({"mean_prediction": mean, "prediction_std": std, "prediction_spread": spread},
                                    rel=1e-12, abs=1e-15)
    assert sent == {
        "as_of": str(snapshot.as_of), "model": snapshot.model, "horizon": 21, "symbols": 8,
        "validation_rmse": snapshot.validation[snapshot.model].rmse, "data_kind": "synthetic",
        "top_symbol": ranked[0].symbol, "focus_symbol": chosen.symbol,
        "focus_prediction": chosen.predicted_return, "focus_rank": 3}
    # > El puesto coincide con el de GET /api/v1/predictions/{symbol}.
    with TestClient(create_app(demo_run.path)) as client:
        assert client.get(f"/api/v1/predictions/{chosen.symbol}").json()["rank"] == sent["focus_rank"]


@pytest.mark.parametrize(("kwargs", "status", "code"), [
    ({"content": b"{no es json", "headers": {"Content-Type": "application/json"}}, 400, "invalid_json"),
    ({"json": ["AAPL"]}, 400, "invalid_json"),
    ({"content": b"\xff\xfe", "headers": {"Content-Type": "application/json"}}, 400, "invalid_json"),
    ({"json": {}}, 422, "validation_error"),
    ({"json": {"symbol": "aapl"}}, 422, "validation_error"),
    ({"json": {"symbol": "A" * 33}}, 422, "validation_error"),
    ({"json": {"symbol": 7}}, 422, "validation_error"),
    ({"json": {"symbol": "AAPL", "question": "¿Compro?"}}, 422, "validation_error"),
    ({"content": b'{"symbol": "AAPL"}', "headers": {"Content-Type": "text/plain"}}, 415, "unsupported_media_type"),
    ({"content": b'{"symbol": "' + b"A" * 3000 + b'"}', "headers": {"Content-Type": "application/json"}},
     413, "payload_too_large"),
])
def test_analyze_rejects_invalid_input(demo_run, kwargs, status, code):
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, **kwargs)
    assert response.status_code == status
    assert response.json()["error"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_validation_error_lists_fields_without_echoing_input(demo_run):
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": "secreto-en-minúsculas"})
    assert response.json()["detail"]["fields"] == [{"loc": ["symbol"], "type": "string_pattern_mismatch"}]
    assert "secreto" not in response.text


def test_body_larger_than_declared_limit_is_rejected_while_streaming(demo_run):
    chunks = iter([b'{"symbol": "', b"A" * 2100, b'"}'])
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, content=chunks, headers={"Content-Type": "application/json"})
    assert (response.status_code, response.json()["error"]) == (413, "payload_too_large")


@pytest.mark.parametrize("declared", [b"9" * 5000, b"abc"])
def test_absurd_content_length_is_rejected_without_a_500(demo_run, declared):
    # >> 5000 cifras pasan str.isdigit() pero superan el límite de int() (4300 cifras): 413, no 500.
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, content=b'{"symbol": "AAPL"}',
                               headers={"Content-Type": "application/json", "Content-Length": declared})
    assert (response.status_code, response.json()["error"]) == (413, "payload_too_large")


@pytest.mark.parametrize("declared", [b"\xb2", b"\xb9", b"18"])
def test_content_length_must_be_ascii_digits(declared):
    # >> Starlette decodifica las cabeceras en latin-1: 0xB2 es «²», que pasa str.isdigit() y rompe int().
    #    TestClient recodifica la cabecera en UTF-8, así que se prueba con un scope ASGI en bruto.
    body = b'{"symbol": "AAPL"}'

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request({"type": "http", "method": "POST", "path": URL, "headers": [(b"content-length", declared)]},
                      receive)
    expected = body if declared == b"18" else None
    assert anyio.run(read_limited_body, request) == expected


def test_analyze_unknown_symbol_is_404_and_without_snapshot_is_503(demo_run, tmp_path):
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        missing = client.post(URL, json={"symbol": "ZZZZ"})
    assert (missing.status_code, missing.json()["error"]) == (404, "symbol_not_found")
    with TestClient(create_app(tmp_path / "falta.json", api_key="")) as client:
        unavailable = client.post(URL, json={"symbol": "ZZZZ"})
    assert (unavailable.status_code, unavailable.json()["error"]) == (503, "snapshot_unavailable")
    assert set(unavailable.json()) == {"error", "detail", "request_id"}


def test_ai_client_error_becomes_typed_503(demo_run, symbol, monkeypatch, caplog):
    def failing(self, request):
        raise AIClientError("Inferencia HF fallida")

    monkeypatch.setattr(AIClient, "analyze", failing)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "fallo-ia-01"})
    assert response.status_code == 503
    assert response.json() == {"error": "ai_unavailable", "request_id": "fallo-ia-01", "detail": {
        "code": "ai_unavailable", "message": "El proveedor de IA no está disponible. Inténtalo más tarde."}}
    assert any("analyze_unavailable request_id=fallo-ia-01 error_type=AIClientError" in record.getMessage()
               for record in caplog.records)


def test_invalid_ai_configuration_is_also_503(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("HF_TIMEOUT", "infinito")
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol})
    assert (response.status_code, response.json()["error"]) == (503, "ai_unavailable")


def test_hf_token_never_reaches_response_or_logs(demo_run, symbol, monkeypatch, caplog):
    # > Valor falso sin forma de clave real: el git grep de secretos del curso sale vacío.
    credencial_falsa = "clave.falsa.hf.0123456789"
    monkeypatch.setenv("AI_PROVIDER", "hf")
    monkeypatch.setenv("HF_TOKEN", credencial_falsa)

    class LeakyClient:
        def __init__(self, **kwargs):
            raise RuntimeError(f"401 para el token {kwargs['api_key']}")

    monkeypatch.setattr(huggingface_hub, "InferenceClient", LeakyClient)
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            response = client.post(URL, json={"symbol": symbol.symbol})
    assert response.status_code == 503
    assert credencial_falsa not in response.text
    assert all(credencial_falsa not in record.getMessage() for record in caplog.records)


NVIDIA_KEY = "clave.falsa.nvidia.0123456789"


def test_analyze_with_nvidia_provider_returns_provider_nvidia(demo_run, symbol, monkeypatch):
    # >> AI_PROVIDER=nvidia llega por AIClient.from_env; el doble sustituye al SDK y no hay red.
    seen = {}

    class FakeNvidia:
        def __init__(self, **kwargs):
            seen["config"] = kwargs

        def chat_completion(self, **kwargs):
            seen["request"] = kwargs
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Resumen NVIDIA"))])

    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.delenv("NVIDIA_MODEL", raising=False)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", FakeNvidia)
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol})
    assert response.status_code == 200
    body = response.json()
    assert (body["provider"], body["model"], body["summary"]) == (
        "nvidia", "nvidia/nemotron-3.5-super-vl-120b-a12b", "Resumen NVIDIA")
    assert seen["config"]["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert seen["request"]["extra_body"] == {"reasoning_effort": "low"}
    assert NVIDIA_KEY not in response.text


def test_nvidia_failure_is_503_without_leaking_the_key(demo_run, symbol, monkeypatch, caplog):
    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)

    class LeakyNvidia:
        def __init__(self, **kwargs):
            raise RuntimeError(f"401 para la clave {kwargs['api_key']}")

    monkeypatch.setattr(huggingface_hub, "InferenceClient", LeakyNvidia)
    with caplog.at_level(logging.DEBUG):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            response = client.post(URL, json={"symbol": symbol.symbol})
    assert (response.status_code, response.json()["error"]) == (503, "ai_unavailable")
    assert NVIDIA_KEY not in response.text
    assert all(NVIDIA_KEY not in record.getMessage() for record in caplog.records)


def test_nvidia_without_key_is_503(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol})
    assert (response.status_code, response.json()["error"]) == (503, "ai_unavailable")


@pytest.mark.parametrize(("headers", "status"), [
    ({}, 401), ({"X-API-Key": "otra-clave"}, 401), ({"X-API-Key": "clave-demo"}, 200)])
def test_api_key_is_required_when_configured(demo_run, symbol, headers, status):
    with TestClient(create_app(demo_run.path, api_key="clave-demo")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol}, headers=headers)
    assert response.status_code == status
    if status == 401:
        assert response.json()["error"] == "unauthorized"
        assert "clave-demo" not in response.text


def test_api_key_from_environment_and_compared_in_constant_time(demo_run, symbol, monkeypatch):
    import dsia_web.app as module

    calls = []
    original = module.hmac.compare_digest
    monkeypatch.setattr(module.hmac, "compare_digest", lambda a, b: calls.append((a, b)) or original(a, b))
    monkeypatch.setenv("DSIA_API_KEY", "desde-entorno")
    with TestClient(create_app(demo_run.path)) as client:
        assert client.post(URL, json={"symbol": symbol.symbol}).status_code == 401
        ok = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-API-Key": "desde-entorno"})
    assert ok.status_code == 200
    assert calls == [(b"", b"desde-entorno"), (b"desde-entorno", b"desde-entorno")]


def test_analyze_only_accepts_post(demo_run):
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        assert client.get(URL).status_code == 405


def test_analyze_request_is_logged_with_latency(demo_run, symbol, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "log-analisis"})
    messages = [record.getMessage() for record in caplog.records if record.getMessage().startswith("analyze ")]
    assert len(messages) == 1
    assert re.fullmatch(rf"analyze request_id=log-analisis symbol={re.escape(symbol.symbol)} provider=mock "
                        r"model=mock-determinista-v1 latency_ms=\d+\.\d{2}", messages[0])
