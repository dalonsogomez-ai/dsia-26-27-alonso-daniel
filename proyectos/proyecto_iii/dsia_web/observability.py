"""Middleware ASGI: request_id, latencia, contadores en memoria, cabeceras de seguridad y error 500 tipado."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter, deque
from contextvars import ContextVar
from time import monotonic, perf_counter
from typing import Callable
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOG = logging.getLogger("uvicorn.error").getChild("dsia")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
SCOPE_KEY = "dsia.request_id"
# > Marca de que el handler ya dejó su línea ERROR (analyze_failed, unhandled_error) para ese 5xx.
ERROR_LOGGED_KEY = "dsia.error_logged"
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
# >> R11: request_id de la petición en curso; anyio copia el contexto al hilo de client.analyze.
_REQUEST_ID: ContextVar[str] = ContextVar("dsia_request_id", default="")
AI_CLIENT_LOGGER = "swarmtrade_app.ai_client"
AI_CLIENT_PACKAGE = "swarmtrade_app"
UVICORN_LOGGER = "uvicorn.error"


def current_request_id() -> str:
    return _REQUEST_ID.get()


class RequestIdFilter(logging.Filter):
    """> Añade ``request_id=…`` a las líneas de un logger ajeno (el cliente del II) durante una petición."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = _REQUEST_ID.get()
        if rid and not getattr(record, "request_id", None):
            record.request_id = rid
            record.msg = f"{record.getMessage()} request_id={rid}"
            record.args = None
        return True


def install_request_id_filter(logger_name: str = AI_CLIENT_LOGGER) -> None:
    """> Idempotente: crear varias apps (pruebas) no duplica el sufijo."""
    logger = logging.getLogger(logger_name)
    if not any(isinstance(existing, RequestIdFilter) for existing in logger.filters):
        logger.addFilter(RequestIdFilter())


class ForwardToUvicorn(logging.Handler):
    """> Entrega cada línea al logger de Uvicorn: sale con su formato («INFO:     …») y su nivel mínimo."""

    def emit(self, record: logging.LogRecord) -> None:
        target = logging.getLogger(UVICORN_LOGGER)
        if target.isEnabledFor(record.levelno):
            target.handle(record)


def route_logs_to_uvicorn(package: str = AI_CLIENT_PACKAGE) -> bool:
    """>> R11 en el despliegue: el CLI de Uvicorn (serve.py, Procfile) deja el root sin handlers.

    Su ``LOGGING_CONFIG`` solo da handler a «uvicorn». Sin este reenvío, las INFO del cliente del II
    (intento completado, reintento) se pierden y sus WARNING salen por ``logging.lastResort``, sin
    nivel. Si el root ya tiene handlers (``basicConfig`` del lote o de la CLI, pytest), no se toca nada:
    las líneas llegan por propagación. Idempotente; devuelve si instaló el reenvío.
    """
    logger = logging.getLogger(package)
    if logging.getLogger().handlers or logger.handlers:
        return False
    logger.addHandler(ForwardToUvicorn())
    logger.setLevel(logging.getLogger(UVICORN_LOGGER).getEffectiveLevel())  # > INFO salvo --log-level
    logger.propagate = False  # > Si después se configura el root, las líneas no salen dos veces.
    return True


class RequestMetrics:
    """Contadores por ruta y estado y ventana acotada de latencias para media y p95 aproximado."""

    def __init__(self, clock: Callable[[], float] = monotonic, window: int = 1024) -> None:
        self.clock = clock
        self.started = clock()
        self.counts: Counter[tuple[str, int]] = Counter()
        self.latencies: deque[float] = deque(maxlen=window)

    def record(self, route: str, status: int, latency_ms: float) -> None:
        self.counts[(route, status)] += 1
        self.latencies.append(latency_ms)

    def summary(self) -> dict:
        ordered = sorted(self.latencies)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else None
        return {
            "uptime_s": round(self.clock() - self.started, 3),
            "requests_total": sum(self.counts.values()),
            "requests": [{"route": route, "status": status, "count": count}
                         for (route, status), count in sorted(self.counts.items())],
            "latency_ms": {
                "samples": len(ordered),
                "mean": round(sum(ordered) / len(ordered), 3) if ordered else None,
                "p95": round(p95, 3) if p95 is not None else None,
            },
        }


def request_id(scope: Scope) -> str:
    return scope.get(SCOPE_KEY, "")


def mark_error_logged(scope: Scope) -> None:
    """> El handler ya registró en ERROR la causa de este 5xx: la línea ``request`` no la repite."""
    scope[ERROR_LOGGED_KEY] = True


def request_level(status: int, scope: Scope) -> int:
    """> Tema 4, A1: 5xx => ERROR (una sola línea por petición), 4xx => WARNING y el resto, INFO."""
    if status >= 500:
        return logging.INFO if scope.get(ERROR_LOGGED_KEY) else logging.ERROR
    return logging.WARNING if status >= 400 else logging.INFO


def route_label(scope: Scope) -> str:
    """Plantilla de ruta (sin parámetros) para no disparar la cardinalidad de los contadores."""
    route = scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp, metrics: RequestMetrics) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = Headers(scope=scope).get("x-request-id", "")
        rid = incoming if REQUEST_ID.fullmatch(incoming) else uuid4().hex
        scope[SCOPE_KEY] = rid
        context = _REQUEST_ID.set(rid)
        status = 500
        started = False
        start = perf_counter()

        async def send_with_headers(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = rid
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            # >> R6: handler central. Si ya salieron las cabeceras no cabe otro cuerpo: se relanza.
            if started:
                raise
            # > La traza queda en el log con el request_id; la respuesta no la incluye.
            LOG.exception("unhandled_error request_id=%s route=%s", rid, route_label(scope))
            mark_error_logged(scope)
            response = JSONResponse({"error": "internal_error", "detail": {
                "code": "internal_error", "message": "Error interno."}, "request_id": rid}, status_code=500)
            await response(scope, receive, send_with_headers)
        finally:
            _REQUEST_ID.reset(context)
            latency_ms = (perf_counter() - start) * 1000
            route = route_label(scope)
            self.metrics.record(route, status, latency_ms)
            # > Tema 4, A1: 4xx (lo arregla el cliente) => WARNING; 5xx => ERROR. Si el handler ya dejó la
            #   suya (analyze_failed o unhandled_error), esta queda en INFO: una sola alerta por 5xx. Así
            #   también alertan los 503 de disponibilidad (snapshot_unavailable, journal_unavailable,
            #   analyze_busy) y el /health sin informe, que no tienen línea ERROR propia.
            LOG.log(request_level(status, scope),
                    "request request_id=%s method=%s route=%s status=%s latency_ms=%.2f",
                    rid, scope["method"], route, status, latency_ms)
