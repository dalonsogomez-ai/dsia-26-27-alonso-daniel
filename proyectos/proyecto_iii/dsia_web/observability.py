"""Middleware ASGI: request_id, latencia por petición, contadores en memoria y cabeceras de seguridad."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter, deque
from time import monotonic, perf_counter
from typing import Callable
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOG = logging.getLogger("uvicorn.error").getChild("dsia")
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
SCOPE_KEY = "dsia.request_id"
SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


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
        status = 500
        start = perf_counter()

        async def send_with_headers(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = MutableHeaders(scope=message)
                headers["x-request-id"] = rid
                for name, value in SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        finally:
            latency_ms = (perf_counter() - start) * 1000
            route = route_label(scope)
            self.metrics.record(route, status, latency_ms)
            LOG.info("request request_id=%s method=%s route=%s status=%s latency_ms=%.2f",
                     rid, scope["method"], route, status, latency_ms)
