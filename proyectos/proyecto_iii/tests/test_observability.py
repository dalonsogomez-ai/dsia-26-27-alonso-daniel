import logging
import re

import pytest
from starlette.testclient import TestClient

from dsia_web.app import create_app
from dsia_web.observability import ObservabilityMiddleware, RequestMetrics, route_logs_to_uvicorn

SECURITY = {
    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


@pytest.fixture
def client(report):
    with TestClient(create_app(report[0])) as client:
        yield client


@pytest.mark.parametrize("path", ["/", "/health", "/api/v1/snapshot", "/static/style.css", "/no-existe"])
def test_every_response_carries_security_headers(client, path):
    response = client.get(path)
    for name, value in SECURITY.items():
        assert response.headers[name] == value


def test_security_headers_also_on_unavailable_service(tmp_path):
    with TestClient(create_app(tmp_path / "falta.json")) as client:
        response = client.get("/api/v1/snapshot")
    assert response.status_code == 503
    assert response.headers["x-content-type-options"] == "nosniff"


def test_valid_incoming_request_id_is_propagated(client):
    response = client.get("/health", headers={"X-Request-ID": "demo-req.0001"})
    assert response.headers["x-request-id"] == "demo-req.0001"


@pytest.mark.parametrize("incoming", [None, "corto", "con espacios 12345", "a" * 129, "x\r\nSet-Cookie: 1"])
def test_missing_or_unsafe_request_id_is_replaced_by_uuid4(client, incoming):
    headers = {} if incoming is None else {"X-Request-ID": incoming}
    try:
        response = client.get("/health", headers=headers)
    except Exception:  # httpx rechaza cabeceras con saltos de línea antes de enviarlas
        assert "\n" in incoming
        return
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_counters_group_by_route_template_and_status(client):
    for path in ("/health", "/health", "/api/v1/snapshot", "/static/style.css", "/no-existe"):
        client.get(path)
    counts = client.app.state.metrics.counts
    assert dict(counts) == {("/health", 200): 2, ("/api/v1/snapshot", 200): 1,
                            ("/static", 200): 1, ("unmatched", 404): 1}


def test_each_request_is_logged_with_request_id_and_latency(client, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        client.get("/health", headers={"X-Request-ID": "trazable-123"})
    lines = [record.getMessage() for record in caplog.records if "request_id=trazable-123" in record.getMessage()]
    assert len(lines) == 1
    assert re.search(r"method=GET route=/health status=200 latency_ms=\d+\.\d{2}$", lines[0])


@pytest.mark.parametrize("method,path,kwargs,status,level", [
    ("GET", "/health", {}, 200, logging.INFO),
    # >> Tema 4, A1: lo que arregla el cliente cambiando la petición (4xx) va en WARNING, no en INFO.
    ("POST", "/api/v1/analyze", {"json": {"symbol": "bad sym"}}, 422, logging.WARNING),
    ("GET", "/api/v1/predictions/ZZZZ", {}, 404, logging.WARNING),
    ("GET", "/no-existe", {}, 404, logging.WARNING),
])
def test_request_line_level_follows_the_error_taxonomy(client, caplog, method, path, kwargs, status, level):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        response = client.request(method, path, headers={"X-Request-ID": "nivel-log-0001"}, **kwargs)
    assert response.status_code == status
    [record] = [record for record in caplog.records if record.getMessage().startswith("request request_id=nivel")]
    assert record.levelno == level and f"status={status}" in record.getMessage()


def error_lines(caplog):
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.parametrize("method,path,kwargs", [
    ("GET", "/health", {}),
    ("GET", "/api/v1/snapshot", {}),
    ("GET", "/api/v1/predictions/AAPL", {}),
    ("POST", "/api/v1/analyze", {"json": {"symbol": "AAPL"}}),
])
def test_every_5xx_without_its_own_error_line_logs_the_request_in_error(tmp_path, caplog, method, path, kwargs):
    # >> Tema 4, A1 y niveles: 5xx => ERROR. Sin snapshot el servicio está caído y cada 503 debe alertar.
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(tmp_path / "falta.json")) as client:
            caplog.clear()
            response = client.request(method, path, headers={"X-Request-ID": "nivel-5xx-0001"}, **kwargs)
    assert response.status_code == 503
    # > Exactamente una línea ERROR por petición, con su request_id.
    [line] = error_lines(caplog)
    assert line.startswith(f"request request_id=nivel-5xx-0001 method={method} ") and " status=503 " in line


def test_startup_without_snapshot_is_an_error(tmp_path, caplog):
    # >> Un servicio sin informe válido no sirve nada: el arranque deja una línea ERROR, no un WARNING.
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(tmp_path / "falta.json")):
            pass
    assert error_lines(caplog) == ["snapshot_unavailable error_type=FileNotFoundError"]


def test_unreadable_journal_logs_one_error_and_a_warning_with_the_request_id(demo_run, tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, journal_path=tmp_path)) as client:  # > Un directorio: OSError.
            response = client.get("/api/v1/pipeline", headers={"X-Request-ID": "diario-roto-01"})
    assert (response.status_code, response.json()["error"]) == (503, "journal_unavailable")
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert warnings == ["journal_unavailable request_id=diario-roto-01 error_type=IsADirectoryError"]
    [line] = error_lines(caplog)
    assert line.startswith("request request_id=diario-roto-01 method=GET route=/api/v1/pipeline status=503 ")


def test_request_metrics_summary_exact_values():
    now = [100.0]
    metrics = RequestMetrics(clock=lambda: now[0])
    for latency in range(1, 21):
        metrics.record("/health", 200, float(latency))
    metrics.record("/api/v1/analyze", 503, 40.0)
    now[0] = 112.5
    assert metrics.summary() == {
        "uptime_s": 12.5,
        "requests_total": 21,
        "requests": [{"route": "/api/v1/analyze", "status": 503, "count": 1},
                     {"route": "/health", "status": 200, "count": 20}],
        "latency_ms": {"samples": 21, "mean": 11.905, "p95": 20.0},  # 250 / 21
    }


def test_request_metrics_without_samples():
    assert RequestMetrics(clock=lambda: 5.0).summary()["latency_ms"] == {"samples": 0, "mean": None, "p95": None}


def test_latency_window_is_bounded():
    metrics = RequestMetrics(window=3)
    for latency in (100.0, 1.0, 2.0, 3.0):
        metrics.record("/health", 200, latency)
    assert metrics.summary()["latency_ms"] == {"samples": 3, "mean": 2.0, "p95": 3.0}
    assert metrics.summary()["requests_total"] == 4


def test_logs_are_routed_to_uvicorn_once_and_only_without_root_handlers():
    # >> R11 en el despliegue: el reenvío solo se instala si el root no tiene handlers (CLI de Uvicorn),
    #    una sola vez, y respeta el nivel de Uvicorn (aquí, como con --log-level warning).
    root, uvicorn_error = logging.getLogger(), logging.getLogger("uvicorn.error")
    name = "dsia.prueba.reenvio"
    logger = logging.getLogger(name)
    seen = []

    class Collect(logging.Handler):
        def emit(self, record):
            seen.append((record.levelname, record.getMessage()))

    collector, placeholder = Collect(), logging.NullHandler()
    saved_root, saved_level = root.handlers[:], uvicorn_error.level
    try:
        for handler in saved_root:
            root.removeHandler(handler)
        root.addHandler(placeholder)
        assert route_logs_to_uvicorn(name) is False  # > Root con handler (lote, CLI, pytest): no se toca.
        root.removeHandler(placeholder)
        uvicorn_error.addHandler(collector)
        uvicorn_error.setLevel(logging.WARNING)
        assert route_logs_to_uvicorn(name) is True
        assert route_logs_to_uvicorn(name) is False  # > Idempotente: varias apps no duplican líneas.
        assert (logger.level, logger.propagate) == (logging.WARNING, False)
        logger.info("no sale")
        logger.warning("sí sale")
        logger.handlers[0].handle(logging.makeLogRecord({"levelno": logging.INFO, "levelname": "INFO",
                                                         "msg": "por debajo del nivel de Uvicorn"}))
    finally:
        root.removeHandler(placeholder)
        for handler in saved_root:
            root.addHandler(handler)
        uvicorn_error.removeHandler(collector)
        uvicorn_error.setLevel(saved_level)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
    assert seen == [("WARNING", "sí sale")]
