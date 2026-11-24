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


AI_FAILURES = [
    ("timeout", 504, "ai_timeout", "El proveedor de IA no respondió a tiempo. Inténtalo más tarde."),
    ("invalid_response", 502, "ai_bad_response",
     "El proveedor de IA devolvió una respuesta no válida. Inténtalo más tarde."),
    *[(kind, 503, "ai_unavailable", "El proveedor de IA no está disponible. Inténtalo más tarde.")
      for kind in ("unavailable", "rate_limited", "auth", "not_found", "config")],
]


@pytest.mark.parametrize(("kind", "status", "code", "message"), AI_FAILURES)
def test_ai_failure_kind_maps_to_typed_gateway_error_logged_as_error(demo_run, symbol, monkeypatch, caplog,
                                                                     kind, status, code, message):
    def failing(self, request):
        raise AIClientError("Inferencia fallida", kind=kind)

    monkeypatch.setattr(AIClient, "analyze", failing)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "fallo-ia-01"})
    assert response.status_code == status
    assert response.json() == {"error": code, "request_id": "fallo-ia-01",
                               "detail": {"code": code, "message": message}}
    # >> Fallo externo => ERROR con request_id, proveedor, kind y latencia (tema 4, A1 y A2); sin el mensaje.
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert re.fullmatch(rf"analyze_failed request_id=fallo-ia-01 provider=mock kind={kind} status={status} "
                        rf"code={code} latency_ms=\d+\.\d{{2}}", errors[0])


@pytest.mark.parametrize(("mode", "status", "code", "level"), [
    ("timeout", 504, "ai_timeout", "analyze_failed"),
    ("invalid", 502, "ai_bad_response", "analyze_failed"),
    ("down", 503, "ai_unavailable", "analyze_failed"),
    ("bug", 500, "internal_error", "unhandled_error"),
])
def test_mock_failure_modes_reproduce_each_error_without_network(demo_run, symbol, monkeypatch, caplog,
                                                                 mode, status, code, level):
    # >> Tema 4, B2 y B9: el mock simula cada fallo por variable de entorno, sin red ni clave.
    monkeypatch.setenv("AI_MOCK_MODE", mode)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="")) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": f"modo-{mode}-0001"})
    assert (response.status_code, response.json()["error"]) == (status, code)
    assert response.json()["request_id"] == f"modo-{mode}-0001"
    for leak in ("Traceback", "RuntimeError", "AI_MOCK_MODE", "simulado"):
        assert leak not in response.text  # > Ni traza ni causa en el cuerpo: solo en el log.
    errors = [record.getMessage() for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1 and errors[0].startswith(f"{level} request_id=modo-{mode}-0001")


def test_mock_failure_mode_is_ignored_with_a_real_provider(demo_run, symbol, monkeypatch):
    # > Solo actúa con AI_PROVIDER=mock: en Render (nvidia) la variable no cambia nada.
    monkeypatch.setenv("AI_MOCK_MODE", "down")
    monkeypatch.setenv("AI_PROVIDER", "nvidia")
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", lambda **kwargs: SimpleNamespace(
        chat_completion=lambda **request: SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Resumen real"))])))
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        response = client.post(URL, json={"symbol": symbol.symbol})
    assert (response.status_code, response.json()["provider"]) == (200, "nvidia")


def nvidia_failure(error):
    """> Error HTTP real del SDK contra integrate.api.nvidia.com, sin red."""
    import httpx
    from huggingface_hub.errors import HfHubHTTPError
    request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
    if isinstance(error, int):
        return HfHubHTTPError(f"{error} Server Error", response=httpx.Response(error, request=request))
    return httpx.ConnectError("conexión rechazada", request=request)


@pytest.mark.parametrize(("answer", "status", "code"), [
    ("timeout", 504, "ai_timeout"),
    # >> R4: la cola de NVIDIA agotada llega como 504 del proveedor => también es un timeout.
    (nvidia_failure(504), 504, "ai_timeout"),
    # >> R10: una conexión rechazada no es un timeout; el proveedor no está disponible.
    (nvidia_failure("connect"), 503, "ai_unavailable"),
    (SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, reasoning_content="..."))]),
     502, "ai_bad_response"),
])
def test_real_nvidia_path_maps_timeout_to_504_and_reasoning_only_to_502(demo_run, symbol, monkeypatch,
                                                                        answer, status, code):
    from huggingface_hub.errors import InferenceTimeoutError

    class FakeNvidia:
        def __init__(self, **kwargs):
            pass

        def chat_completion(self, **kwargs):
            if answer == "timeout":
                raise InferenceTimeoutError("lento")
            if isinstance(answer, Exception):
                raise answer
            return answer

    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", FakeNvidia)
    factory = lambda: AIClient("nvidia", sleep=lambda seconds: None)  # noqa: E731 - sin esperas reales
    with TestClient(create_app(demo_run.path, api_key="", ai_client_factory=factory)) as client:
        response = client.post(URL, json={"symbol": symbol.symbol})
    assert (response.status_code, response.json()["error"]) == (status, code)
    assert NVIDIA_KEY not in response.text


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


# --- R6: error no controlado con la forma común ----------------------------------------------------

def test_unexpected_error_is_a_typed_500_with_request_id_and_security_headers(demo_run, symbol, caplog):
    class Broken:
        def analyze(self, request):
            raise KeyError("campo_interno")

    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="", ai_client_factory=lambda: Broken())) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "fallo-interno-1"})
            metrics = client.get("/api/v1/metrics").json()
    assert response.status_code == 500
    assert response.json() == {"error": "internal_error", "request_id": "fallo-interno-1",
                               "detail": {"code": "internal_error", "message": "Error interno."}}
    assert response.headers["x-request-id"] == "fallo-interno-1"
    assert response.headers["content-security-policy"] == "default-src 'self'; frame-ancestors 'none'"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "KeyError" not in response.text and "campo_interno" not in response.text
    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert [record.getMessage() for record in errors] == [
        "unhandled_error request_id=fallo-interno-1 route=/api/v1/analyze"]
    assert errors[0].exc_info is not None  # > La traza queda en el log del servidor, no en la respuesta.
    assert {"route": "/api/v1/analyze", "status": 500, "count": 1} in metrics["requests"]


# --- R11: request_id en las líneas del cliente del II ----------------------------------------------

def test_provider_attempt_and_retry_lines_carry_the_request_id(demo_run, symbol, monkeypatch, caplog):
    class FailingNvidia:
        def __init__(self, **kwargs):
            pass

        def chat_completion(self, **kwargs):
            raise nvidia_failure(502)

    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", FailingNvidia)
    factory = lambda: AIClient("nvidia", sleep=lambda seconds: None)  # noqa: E731 - sin esperas reales
    with caplog.at_level(logging.INFO):
        with TestClient(create_app(demo_run.path, api_key="", ai_client_factory=factory)) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "trazado-ia-01"})
        AIClient("mock").analyze(analysis_request(demo_run.snapshot, symbol.symbol))
    assert response.status_code == 503
    lines = [record.getMessage() for record in caplog.records if record.name == "swarmtrade_app.ai_client"]
    provider_lines = [line for line in lines if line.startswith("IA provider=nvidia")]
    # > 3 intentos fallidos (WARNING) y 2 reintentos (INFO), todos con el request_id de la petición.
    assert len(provider_lines) == 5
    assert all(line.endswith(" request_id=trazado-ia-01") for line in provider_lines), provider_lines
    # > Fuera de una petición (CLI, lote) la línea no cambia.
    assert [line for line in lines if line.startswith("IA provider=mock")] == [
        "IA provider=mock model=mock-determinista-v1 latency_ms=0 ai_status=completed"]
    failed = [record.getMessage() for record in caplog.records if record.getMessage().startswith("analyze_failed")]
    assert len(failed) == 1 and failed[0].startswith("analyze_failed request_id=trazado-ia-01 provider=nvidia ")
    assert NVIDIA_KEY not in caplog.text


def test_provider_lines_reach_uvicorn_handlers_when_the_root_logger_has_none(demo_run, symbol, monkeypatch, capfd):
    # >> R11 en el despliegue: serve.py y el Procfile lanzan el CLI de Uvicorn, cuyo LOGGING_CONFIG solo da
    #    handler a «uvicorn» y deja el root sin ninguno. Sin reenvío, las INFO del cliente del II se pierden y
    #    las WARNING salen por logging.lastResort, sin nivel. caplog no lo ve: instala su handler en el root.
    import logging.config

    import uvicorn.config

    class FailingNvidia:
        def __init__(self, **kwargs):
            pass

        def chat_completion(self, **kwargs):
            raise nvidia_failure(502)

    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    monkeypatch.setattr(huggingface_hub, "InferenceClient", FailingNvidia)
    factory = lambda: AIClient("nvidia", sleep=lambda seconds: None)  # noqa: E731 - sin esperas reales
    root = logging.getLogger()
    names = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "swarmtrade_app")
    saved = {name: (logging.getLogger(name).handlers[:], logging.getLogger(name).level,
                    logging.getLogger(name).propagate) for name in names}
    try:
        # > Mismo estado que un proceso nuevo de `uvicorn`: su configuración y el root sin handlers, en WARNING.
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        root.setLevel(logging.WARNING)
        with TestClient(create_app(demo_run.path, api_key="", ai_client_factory=factory)) as client:
            response = client.post(URL, json={"symbol": symbol.symbol}, headers={"X-Request-ID": "trazado-uvicorn-1"})
    finally:
        for name, (handlers, level, propagate) in saved.items():
            logger = logging.getLogger(name)
            for handler in logger.handlers[:]:
                if handler not in handlers:
                    logger.removeHandler(handler)
                    handler.close()
            for handler in handlers:
                if handler not in logger.handlers:
                    logger.addHandler(handler)
            logger.setLevel(level)
            logger.propagate = propagate
    assert response.status_code == 503
    err = capfd.readouterr().err
    lines = [line for line in err.splitlines() if "IA provider=nvidia" in line]
    attempts = [line for line in lines if "ai_status=failed" in line]
    retries = [line for line in lines if " reintento=" in line]

    def level(line):
        return (re.match(r"([A-Z]+): ", line) or [None, None])[1]  # > None = sin prefijo (lastResort)

    # > Los 3 intentos (WARNING) y los 2 reintentos (INFO) salen con el formato de Uvicorn y el request_id.
    assert [level(line) for line in attempts] == ["WARNING"] * 3, err
    assert [level(line) for line in retries] == ["INFO"] * 2, err
    assert [re.search(r" attempt=(\d)", line).group(1) for line in attempts] == ["1", "2", "3"]
    assert all(line.endswith(" request_id=trazado-uvicorn-1") for line in attempts + retries), lines
    assert re.search(r"^ERROR: +analyze_failed request_id=trazado-uvicorn-1 provider=nvidia ", err, re.M)
    assert NVIDIA_KEY not in err
