"""-> Límite de uso de POST /api/v1/analyze: ventana por cliente, cupo diario por cliente y tope global.

Con un proveedor real (``AI_PROVIDER=nvidia``) cada análisis gasta la clave del servicio, y la URL
es pública. Por eso se admiten como mucho ``DSIA_ANALYZE_PER_MINUTE`` análisis por minuto y por
cliente (5 por defecto), ``DSIA_ANALYZE_PER_IP_DAY`` al día por cliente (30) y
``DSIA_ANALYZE_PER_DAY`` al día en todo el servicio (200; los contadores diarios vuelven a 0 a las
00:00 UTC). El estado vive en memoria del proceso: se pierde al reiniciar y no se comparte entre
workers, igual que las métricas.

El cliente se identifica por su IP, que solo se toma de lo que escribe un proxy de confianza:

- En Render (``RENDER=true``), ``CF-Connecting-IP``: Cloudflare, delante de todos los servicios
  web de Render, la escribe y sobrescribe la que mande el cliente.
- Si no, el salto ``DSIA_TRUSTED_PROXY_HOPS`` (1 por defecto) contando desde la derecha de
  ``X-Forwarded-For`` (todas sus líneas, en orden): el proxy añade al final la IP que le conectó, y
  lo de la izquierda lo puede inventar el cliente. Con ``0`` (sin proxy delante: ``docker run -p``
  o Uvicorn en local) la cabecera se ignora, porque entera la escribe el cliente.
- Si no hay un valor válido, el par TCP.

La clave agrupa IPv6 por su /64 (un cliente suele tener el /64 entero) e IPv4-mapped como IPv4.
Además, ``AnalyzeSlots`` acota los análisis simultáneos en total (``DSIA_ANALYZE_CONCURRENCY``, 4)
y por cliente (``DSIA_ANALYZE_CONCURRENCY_PER_IP``, 2): una sola IP no ocupa todos los huecos.
"""

from __future__ import annotations

import ipaddress
import math
import os
import re
import threading
import time
from collections import Counter, deque
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Callable, NamedTuple

import anyio
import anyio.to_thread

DEFAULT_PER_MINUTE = 5
DEFAULT_PER_DAY = 200
DEFAULT_PER_IP_DAY = 30
DEFAULT_TRUSTED_PROXY_HOPS = 1
DEFAULT_CONCURRENCY = 4
DEFAULT_CONCURRENCY_PER_IP = 2
WINDOW_SECONDS = 60.0
CF_CONNECTING_IP = "cf-connecting-ip"
# > El histograma de saltos agrupa en 8 los de 8 o más: la cardinalidad no depende del cliente.
MAX_HOPS_TRACKED = 8
_POSITIVE_INT = re.compile(r"[0-9]{1,9}")


class Rejection(NamedTuple):
    """Petición rechazada: qué límite saltó (``per_minute``, ``per_ip_day`` o ``per_day``) y cuánto esperar."""

    scope: str
    retry_after: int


def read_limit(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    """> Entero desde ``minimum`` (1); vacío = valor por defecto. Cualquier otro valor detiene el arranque."""
    raw = str(env.get(name) or "").strip()
    if not raw:
        return default
    if not _POSITIVE_INT.fullmatch(raw) or int(raw) < minimum:
        # ~> Sin «0 = sin límite»: una errata no puede dejar la clave del proveedor sin protección.
        bound = "mayor que 0" if minimum == 1 else f"mayor o igual que {minimum}"
        # > Solo la longitud: una clave pegada por error en la variable no debe llegar al log.
        raise ValueError(f"{name} debe ser un entero {bound} (recibido un valor no válido de {len(raw)} caracteres)")
    return int(raw)


def client_key(raw: str) -> str | None:
    """> Clave de límite de una IP: IPv4 tal cual, IPv4-mapped como IPv4 e IPv6 como su /64; ``None`` si no es IP."""
    try:
        ip = ipaddress.ip_address(raw.strip())
    except ValueError:
        return None
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def forwarded_hops(headers: Mapping[str, str]) -> list[str]:
    """> Saltos de X-Forwarded-For de todas sus líneas, en orden (RFC 9110 §5.3: equivalen a una lista)."""
    getlist = getattr(headers, "getlist", None)
    lines = getlist("x-forwarded-for") if getlist else [headers.get("x-forwarded-for", "")]
    return [part.strip() for part in ",".join(lines).split(",") if part.strip()]


def resolve_client(headers: Mapping[str, str], client, *, trusted_hops: int = DEFAULT_TRUSTED_PROXY_HOPS,
                   trust_cf: bool = False) -> tuple[str, str]:
    """> (clave del cliente, origen): ``cf-connecting-ip``, ``x-forwarded-for`` o ``peer``."""
    if trust_cf:
        key = client_key(headers.get(CF_CONNECTING_IP, ""))
        if key:
            return key, "cf-connecting-ip"
    hops = forwarded_hops(headers)
    # > trusted_hops=0: sin proxy de confianza, la cabecera entera la escribe el cliente.
    if trusted_hops > 0 and len(hops) >= trusted_hops:
        # >> R1: el salto que añadió el proxy de confianza, contado desde la derecha.
        key = client_key(hops[-trusted_hops])
        if key:
            return key, "x-forwarded-for"
    if client is None:
        return "desconocido", "peer"
    return client_key(client.host) or client.host, "peer"


def client_address(headers: Mapping[str, str], client, *, trusted_hops: int = DEFAULT_TRUSTED_PROXY_HOPS,
                   trust_cf: bool = False) -> str:
    """> Clave del cliente sin registrar métricas (ver ``resolve_client``)."""
    return resolve_client(headers, client, trusted_hops=trusted_hops, trust_cf=trust_cf)[0]


class AnalyzeRateLimiter:
    """Ventana deslizante de 60 s y cupo diario por cliente, y tope diario global; reloj de pared inyectable."""

    def __init__(self, per_minute: int = DEFAULT_PER_MINUTE, per_day: int = DEFAULT_PER_DAY,
                 clock: Callable[[], float] = time.time, *, per_ip_day: int = DEFAULT_PER_IP_DAY,
                 trusted_hops: int = DEFAULT_TRUSTED_PROXY_HOPS, trust_cf: bool = False) -> None:
        self.per_minute, self.per_day, self.per_ip_day, self.clock = per_minute, per_day, per_ip_day, clock
        self.trusted_hops, self.trust_cf = trusted_hops, trust_cf
        self.rejected = {"per_minute": 0, "per_day": 0, "per_ip_day": 0}
        # > Solo enteros y orígenes, nunca IPs: sirven para comprobar en Render cuántos saltos llegan.
        self.hops_seen: Counter[int] = Counter()
        self.sources: Counter[str] = Counter()
        self._recent: dict[str, deque[float]] = {}
        self._client_today: Counter[str] = Counter()
        self._day = None
        self._next_day = 0.0
        self._used_today = 0
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None,
                 clock: Callable[[], float] = time.time) -> AnalyzeRateLimiter:
        env = os.environ if env is None else env
        return cls(read_limit(env, "DSIA_ANALYZE_PER_MINUTE", DEFAULT_PER_MINUTE),
                   read_limit(env, "DSIA_ANALYZE_PER_DAY", DEFAULT_PER_DAY), clock,
                   per_ip_day=read_limit(env, "DSIA_ANALYZE_PER_IP_DAY", DEFAULT_PER_IP_DAY),
                   trusted_hops=read_limit(env, "DSIA_TRUSTED_PROXY_HOPS", DEFAULT_TRUSTED_PROXY_HOPS, minimum=0),
                   # > Render define RENDER=true en todos sus servicios (documentación de Render).
                   trust_cf=str(env.get("RENDER") or "").strip().lower() == "true")

    @property
    def tracked_clients(self) -> int:
        return len(self._recent)

    def client(self, headers: Mapping[str, str], peer) -> str:
        """> Clave del cliente de una petición; cuenta los saltos de X-Forwarded-For y el origen usado."""
        key, source = resolve_client(headers, peer, trusted_hops=self.trusted_hops, trust_cf=self.trust_cf)
        with self._lock:
            self.hops_seen[min(len(forwarded_hops(headers)), MAX_HOPS_TRACKED)] += 1
            self.sources[source] += 1
        return key

    def limit(self, scope: str) -> int:
        return {"per_minute": self.per_minute, "per_day": self.per_day, "per_ip_day": self.per_ip_day}[scope]

    def acquire(self, client: str) -> Rejection | None:
        """Admite y registra la petición (``None``) o la rechaza sin registrarla."""
        with self._lock:
            now = self.clock()
            self._roll_day(now)
            until_midnight = max(1, math.ceil(self._next_day - now))
            # > Primero los cupos diarios: si uno está agotado, la espera real es hasta las 00:00 UTC.
            if self._used_today >= self.per_day:
                self.rejected["per_day"] += 1
                return Rejection("per_day", until_midnight)
            if self._client_today[client] >= self.per_ip_day:
                self.rejected["per_ip_day"] += 1
                return Rejection("per_ip_day", until_midnight)
            window = self._recent.setdefault(client, deque())
            while window and window[0] <= now - WINDOW_SECONDS:
                window.popleft()
            if len(window) >= self.per_minute:
                self.rejected["per_minute"] += 1
                return Rejection("per_minute", max(1, math.ceil(window[0] + WINDOW_SECONDS - now)))
            window.append(now)
            self._used_today += 1
            self._client_today[client] += 1
            return None

    def summary(self) -> dict:
        with self._lock:
            self._roll_day(self.clock())
            return {"per_minute": self.per_minute, "per_day": self.per_day, "per_ip_day": self.per_ip_day,
                    "trusted_proxy_hops": self.trusted_hops, "used_today": self._used_today,
                    "rejected": dict(self.rejected),
                    "xff_hops_seen": {str(hops): count for hops, count in sorted(self.hops_seen.items())},
                    "client_ip_source": dict(sorted(self.sources.items()))}

    def _roll_day(self, now: float) -> None:
        today = datetime.fromtimestamp(now, timezone.utc).date()
        if today == self._day:
            return
        self._day, self._used_today = today, 0
        # > El cupo diario por cliente se reinicia a la vez: como solo se cuentan los admitidos, no pasa de per_day claves.
        self._client_today = Counter()
        self._next_day = datetime.combine(today + timedelta(days=1), datetime.min.time(), timezone.utc).timestamp()
        # > Se olvidan los clientes sin peticiones en la última ventana: la memoria no crece día a día.
        self._recent = {client: window for client, window in self._recent.items()
                        if window and window[-1] > now - WINDOW_SECONDS}


class AnalyzeSlots:
    """>> R2: análisis simultáneos acotados, en total y por cliente, sin cola y en hilos propios.

    ``try_enter`` responde al momento (sin esperar a que se libere un hueco), y ``run`` ejecuta la
    llamada al proveedor con un ``anyio.CapacityLimiter`` propio: así un análisis lento nunca ocupa
    los hilos de ``FileResponse`` y ``StaticFiles``, y el dashboard sigue respondiendo. El cupo por
    cliente evita que una sola IP, sin salirse de su límite por minuto, ocupe todos los huecos
    mientras el proveedor tarda.
    """

    def __init__(self, total: int = DEFAULT_CONCURRENCY, per_client: int = DEFAULT_CONCURRENCY_PER_IP) -> None:
        self.total, self.per_client = total, per_client
        self.in_flight = 0
        self.rejected = 0
        self.rejected_per_client = 0
        self._clients: Counter[str] = Counter()
        self._threads = anyio.CapacityLimiter(total)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AnalyzeSlots:
        env = os.environ if env is None else env
        return cls(read_limit(env, "DSIA_ANALYZE_CONCURRENCY", DEFAULT_CONCURRENCY),
                   read_limit(env, "DSIA_ANALYZE_CONCURRENCY_PER_IP", DEFAULT_CONCURRENCY_PER_IP))

    @property
    def clients_in_flight(self) -> int:
        return len(self._clients)

    def try_enter(self, client: str) -> str | None:
        """``None`` si entra; ``busy_per_ip`` si ese cliente ya tiene su cupo en curso; ``busy`` si no queda hueco."""
        # > Sin await entre la comprobación y el incremento: en el bucle de eventos es atómico.
        if self._clients[client] >= self.per_client:
            self.rejected_per_client += 1
            return "busy_per_ip"
        if self.in_flight >= self.total:
            self.rejected += 1
            return "busy"
        self.in_flight += 1
        self._clients[client] += 1
        return None

    def leave(self, client: str) -> None:
        self.in_flight -= 1
        self._clients[client] -= 1
        if self._clients[client] <= 0:
            del self._clients[client]

    async def run(self, function, *args):
        return await anyio.to_thread.run_sync(function, *args, limiter=self._threads)
