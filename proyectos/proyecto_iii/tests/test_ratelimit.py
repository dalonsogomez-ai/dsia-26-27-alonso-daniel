""">> Límite de uso de POST /api/v1/analyze: ventana deslizante por IP y tope global diario (UTC)."""

import logging
from datetime import datetime, timezone

import pytest
from starlette.datastructures import Address, Headers
from starlette.testclient import TestClient

from dsia_web.app import create_app
from dsia_web.ratelimit import (DEFAULT_CONCURRENCY, DEFAULT_CONCURRENCY_PER_IP, DEFAULT_PER_DAY,
                                DEFAULT_PER_IP_DAY, DEFAULT_PER_MINUTE, DEFAULT_TRUSTED_PROXY_HOPS,
                                AnalyzeRateLimiter, AnalyzeSlots, Rejection, client_address, client_key,
                                read_limit)

URL = "/api/v1/analyze"
NOON = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc).timestamp()


class Clock:
    """> Reloj de pared inyectable (segundos desde la época, como time.time)."""

    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def symbol(demo_run):
    return demo_run.snapshot.predictions[0].symbol


def post(client, symbol, ip=None, request_id=None, api_key=None, forged=None, headers=None):
    headers = dict(headers or {})
    if ip:
        # > Lo que llega tras el proxy de confianza: lo que mandó el cliente (forged) y, al final, la IP
        #   que añade el proxy. Con DSIA_TRUSTED_PROXY_HOPS=1 cuenta esa última.
        headers["X-Forwarded-For"] = f"{forged}, {ip}" if forged else ip
    if request_id:
        headers["X-Request-ID"] = request_id
    if api_key:
        headers["X-API-Key"] = api_key
    return client.post(URL, json={"symbol": symbol}, headers=headers)


# --- Limitador en memoria -------------------------------------------------------------------------

def test_defaults_are_five_per_minute_two_hundred_per_day_and_thirty_per_ip_and_day():
    limiter = AnalyzeRateLimiter.from_env({})
    assert (DEFAULT_PER_MINUTE, DEFAULT_PER_DAY, DEFAULT_PER_IP_DAY, DEFAULT_TRUSTED_PROXY_HOPS) == (5, 200, 30, 1)
    assert (limiter.per_minute, limiter.per_day, limiter.per_ip_day, limiter.trusted_hops) == (5, 200, 30, 1)
    assert limiter.trust_cf is False
    limiter = AnalyzeRateLimiter.from_env({"DSIA_ANALYZE_PER_MINUTE": " 12 ", "DSIA_ANALYZE_PER_DAY": "900",
                                           "DSIA_ANALYZE_PER_IP_DAY": "40", "DSIA_TRUSTED_PROXY_HOPS": "2",
                                           "RENDER": "true"})
    assert (limiter.per_minute, limiter.per_day, limiter.per_ip_day, limiter.trusted_hops) == (12, 900, 40, 2)
    assert limiter.trust_cf is True  # > Render define RENDER=true en todos sus servicios.


def test_daily_cap_per_client_stops_one_ip_from_spending_the_global_cap():
    clock = Clock(datetime(2026, 11, 24, 23, 0, tzinfo=timezone.utc).timestamp())
    limiter = AnalyzeRateLimiter(per_minute=100, per_day=10, per_ip_day=3, clock=clock)
    assert [limiter.acquire("203.0.113.7") for _ in range(3)] == [None] * 3
    assert limiter.acquire("203.0.113.7") == Rejection("per_ip_day", 3600)
    assert limiter.acquire("198.51.100.2") is None  # > Las demás conexiones siguen teniendo cupo.
    assert limiter.summary()["used_today"] == 4
    assert limiter.summary()["rejected"] == {"per_minute": 0, "per_day": 0, "per_ip_day": 1}
    clock.now += 3600  # 25/11/2026 00:00 UTC: el cupo por IP también vuelve a 0.
    assert limiter.acquire("203.0.113.7") is None


def test_sliding_window_is_per_client():
    clock = Clock(NOON)
    limiter = AnalyzeRateLimiter(per_minute=3, per_day=100, clock=clock)
    for offset in (0, 10, 20):
        clock.now = NOON + offset
        assert limiter.acquire("203.0.113.7") is None
    clock.now = NOON + 30
    # > La más antigua (NOON) sale de la ventana a los 60 s: faltan 30.
    assert limiter.acquire("203.0.113.7") == Rejection("per_minute", 30)
    assert limiter.acquire("198.51.100.2") is None
    clock.now = NOON + 60
    assert limiter.acquire("203.0.113.7") is None
    clock.now = NOON + 60.5
    # > Ventana [10, 20, 60]: la de +10 caduca en +70, dentro de 9,5 s (se redondea hacia arriba).
    assert limiter.acquire("203.0.113.7") == Rejection("per_minute", 10)


def test_daily_cap_is_global_and_resets_at_utc_midnight():
    late = datetime(2026, 11, 24, 23, 59, tzinfo=timezone.utc).timestamp()
    clock = Clock(late)
    limiter = AnalyzeRateLimiter(per_minute=5, per_day=2, clock=clock)
    assert limiter.acquire("203.0.113.1") is None
    assert limiter.acquire("203.0.113.2") is None
    assert limiter.acquire("203.0.113.3") == Rejection("per_day", 60)
    clock.now = late + 59.5
    assert limiter.acquire("203.0.113.3") == Rejection("per_day", 1)
    clock.now = late + 60  # 25/11/2026 00:00:00 UTC
    assert limiter.acquire("203.0.113.3") is None
    assert limiter.summary() == {"per_minute": 5, "per_day": 2, "per_ip_day": 30, "trusted_proxy_hops": 1,
                                 "used_today": 1, "rejected": {"per_minute": 0, "per_day": 2, "per_ip_day": 0},
                                 "xff_hops_seen": {}, "client_ip_source": {}}
    clock.now = late + 60 + 86_400  # 26/11/2026 00:00:00 UTC, sin peticiones ese día
    assert limiter.summary()["used_today"] == 0


def test_exhausted_daily_cap_is_reported_before_the_minute_window():
    clock = Clock(NOON)
    limiter = AnalyzeRateLimiter(per_minute=1, per_day=1, clock=clock)
    assert limiter.acquire("203.0.113.7") is None
    assert limiter.acquire("203.0.113.7") == Rejection("per_day", 43_200)


def test_stale_clients_are_forgotten_when_the_day_changes():
    clock = Clock(NOON)
    limiter = AnalyzeRateLimiter(per_minute=1, per_day=10, clock=clock)
    for index in range(3):
        assert limiter.acquire(f"203.0.113.{index}") is None
    clock.now = NOON + 86_400
    assert limiter.acquire("198.51.100.2") is None
    assert limiter.tracked_clients == 1


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "2.5", "1e3", "+3", "٣", "12345678901"])
def test_invalid_limit_is_a_clear_configuration_error(raw):
    with pytest.raises(ValueError, match="^DSIA_ANALYZE_PER_MINUTE debe ser un entero mayor que 0"):
        read_limit({"DSIA_ANALYZE_PER_MINUTE": raw}, "DSIA_ANALYZE_PER_MINUTE", 5)


PASTED = "clave.falsa.nvidia.0123456789"  # > Sin forma de clave real (AGENTS.md): simula una clave pegada.


def test_invalid_limit_message_gives_the_length_but_never_the_value():
    # >> Una clave pegada por error en una variable numérica no debe acabar, ni en parte, en el log.
    with pytest.raises(ValueError) as error:
        read_limit({"DSIA_ANALYZE_PER_MINUTE": PASTED}, "DSIA_ANALYZE_PER_MINUTE", 5)
    assert str(error.value) == ("DSIA_ANALYZE_PER_MINUTE debe ser un entero mayor que 0 "
                                f"(recibido un valor no válido de {len(PASTED)} caracteres)")
    assert "clave" not in str(error.value)


def test_empty_limit_uses_the_default():
    assert read_limit({}, "DSIA_ANALYZE_PER_DAY", 200) == 200
    assert read_limit({"DSIA_ANALYZE_PER_DAY": "  "}, "DSIA_ANALYZE_PER_DAY", 200) == 200


@pytest.mark.parametrize("forwarded,hops,expected", [
    # >> R1: el cliente fija lo que va a la izquierda; el proxy de confianza añade el último salto.
    ("203.0.113.7", 1, "203.0.113.7"),
    ("198.51.100.1, 203.0.113.9", 1, "203.0.113.9"),
    ("198.51.100.1, 203.0.113.9, 10.0.0.2", 2, "203.0.113.9"),
    (" 192.0.2.50 , 2001:DB8:1:2::7 ", 1, "2001:db8:1:2::/64"),
    ("192.0.2.50, no-es-una-ip", 1, "10.1.2.3"),
    ("203.0.113.9", 2, "10.1.2.3"),  # > Menos saltos que proxies de confianza: no se fía de ninguno.
    (",, ", 1, "10.1.2.3"),
    (None, 1, "10.1.2.3"),
])
def test_client_address_is_the_hop_added_by_the_trusted_proxy(forwarded, hops, expected):
    headers = Headers({} if forwarded is None else {"x-forwarded-for": forwarded})
    assert client_address(headers, Address("10.1.2.3", 5555), trusted_hops=hops) == expected


@pytest.mark.parametrize("raw,expected", [
    ("203.0.113.7", "203.0.113.7"),
    # >> R3: un cliente IPv6 suele tener un /64 entero; se agrupa por /64 y IPv4-mapped vuelve a IPv4.
    ("2001:db8:1:2::1", "2001:db8:1:2::/64"),
    ("2001:DB8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
    ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
    ("::ffff:203.0.113.7", "203.0.113.7"),
    ("no-es-una-ip", None),
    ("", None),
])
def test_client_key_groups_ipv6_by_64_and_unmaps_ipv4(raw, expected):
    assert client_key(raw) == expected


def test_client_address_without_peer_or_header():
    assert client_address(Headers({}), None) == "desconocido"
    assert client_address(Headers({}), Address("testclient", 50000)) == "testclient"


@pytest.mark.parametrize("trust_cf,expected", [(True, "198.51.100.77"), (False, "203.0.113.9")])
def test_cf_connecting_ip_is_used_only_on_render(trust_cf, expected):
    # >> En Render, Cloudflare escribe CF-Connecting-IP y sobrescribe lo que mande el cliente.
    headers = Headers({"cf-connecting-ip": "198.51.100.77", "x-forwarded-for": "192.0.2.1, 203.0.113.9"})
    assert client_address(headers, Address("10.1.2.3", 5555), trust_cf=trust_cf) == expected
    invalid = Headers({"cf-connecting-ip": "basura", "x-forwarded-for": "203.0.113.9"})
    assert client_address(invalid, None, trust_cf=trust_cf) == "203.0.113.9"


@pytest.mark.parametrize("name", ["DSIA_ANALYZE_PER_IP_DAY", "DSIA_ANALYZE_CONCURRENCY_PER_IP"])
def test_new_settings_are_validated_like_the_other_limits(name):
    with pytest.raises(ValueError, match=f"^{name} debe ser un entero mayor que 0"):
        AnalyzeRateLimiter.from_env({name: "0"}) if name.endswith("IP_DAY") else AnalyzeSlots.from_env({name: "0"})


@pytest.mark.parametrize("raw", ["-1", "uno", "1.5"])
def test_trusted_proxy_hops_accepts_zero_but_not_other_values(raw):
    # >> 0 = sin proxy delante (docker run -p, uvicorn en local): X-Forwarded-For lo escribe el cliente.
    assert AnalyzeRateLimiter.from_env({"DSIA_TRUSTED_PROXY_HOPS": "0"}).trusted_hops == 0
    with pytest.raises(ValueError, match="^DSIA_TRUSTED_PROXY_HOPS debe ser un entero mayor o igual que 0"):
        AnalyzeRateLimiter.from_env({"DSIA_TRUSTED_PROXY_HOPS": raw})


def test_zero_trusted_hops_ignores_forwarded_for_and_uses_the_peer():
    headers = Headers({"x-forwarded-for": "198.51.100.1, 203.0.113.9"})
    assert client_address(headers, Address("10.1.2.3", 5555), trusted_hops=0) == "10.1.2.3"
    assert client_address(Headers({}), Address("10.1.2.3", 5555), trusted_hops=0) == "10.1.2.3"


def test_forwarded_for_split_across_several_lines_is_read_in_order():
    # >> RFC 9110 §5.3: varias líneas con el mismo nombre equivalen a su lista separada por comas, en orden.
    #    Si el proxy añade su propia línea, el último salto es el suyo, no el de la primera línea.
    headers = Headers(raw=[(b"x-forwarded-for", b"198.51.100.1"), (b"x-forwarded-for", b"203.0.113.9")])
    assert client_address(headers, Address("10.1.2.3", 5555)) == "203.0.113.9"
    limiter = AnalyzeRateLimiter()
    assert limiter.client(headers, None) == "203.0.113.9"
    assert limiter.summary()["xff_hops_seen"] == {"2": 1}


def test_hops_histogram_groups_eight_or_more_hops_under_one_key():
    # > La cardinalidad de /api/v1/metrics no depende de lo que mande el cliente.
    limiter = AnalyzeRateLimiter()
    for count in (9, 50, 300):
        forwarded = ", ".join(f"10.{index // 65536}.{index // 256 % 256}.{index % 256}" for index in range(count))
        limiter.client(Headers({"x-forwarded-for": forwarded}), None)
    assert limiter.summary()["xff_hops_seen"] == {"8": 3}


def test_concurrency_per_client_defaults_to_two_and_is_released():
    slots = AnalyzeSlots.from_env({})
    assert (slots.total, slots.per_client) == (DEFAULT_CONCURRENCY, DEFAULT_CONCURRENCY_PER_IP) == (4, 2)
    assert [slots.try_enter("203.0.113.7") for _ in range(3)] == [None, None, "busy_per_ip"]
    assert slots.try_enter("198.51.100.2") is None
    assert slots.try_enter("192.0.2.50") is None
    assert slots.try_enter("192.0.2.51") == "busy"  # > 4 en curso: cupo global lleno.
    assert (slots.in_flight, slots.rejected, slots.rejected_per_client) == (4, 1, 1)
    slots.leave("203.0.113.7")
    assert slots.try_enter("203.0.113.7") is None
    for client in ("203.0.113.7", "203.0.113.7", "198.51.100.2", "192.0.2.50"):
        slots.leave(client)
    # > Sin análisis en curso no queda ninguna clave: la memoria no crece con los clientes.
    assert (slots.in_flight, slots.clients_in_flight) == (0, 0)


# --- Integración con la API -----------------------------------------------------------------------

def test_analyze_returns_typed_429_with_retry_after_and_counts_it(demo_run, symbol, monkeypatch, caplog):
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "2")
    clock = Clock(NOON)
    with caplog.at_level(logging.INFO, logger="uvicorn.error.dsia"):
        with TestClient(create_app(demo_run.path, api_key="", rate_clock=clock)) as client:
            first = post(client, symbol, "203.0.113.7")
            clock.now += 15
            second = post(client, symbol, "203.0.113.7")
            limited = post(client, symbol, "203.0.113.7", request_id="limite-0001")
            other = post(client, symbol, "198.51.100.2")
            metrics = client.get("/api/v1/metrics").json()
    assert [response.status_code for response in (first, second, other)] == [200, 200, 200]
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "45"
    assert limited.json() == {"error": "rate_limited", "request_id": "limite-0001", "detail": {
        "code": "rate_limited",
        "message": "Demasiados análisis seguidos desde tu conexión: máximo 2 por minuto. Reintenta en 45 s."}}
    assert {"route": "/api/v1/analyze", "status": 429, "count": 1} in metrics["requests"]
    assert metrics["rate_limit"] == {
        "per_minute": 2, "per_day": 200, "per_ip_day": 30, "trusted_proxy_hops": 1, "used_today": 3,
        "concurrency": 4, "concurrency_per_ip": 2, "in_flight": 0,
        "rejected": {"per_minute": 1, "per_day": 0, "per_ip_day": 0, "busy": 0, "busy_per_ip": 0},
        # > Solo enteros: cuántos saltos traía X-Forwarded-For y de dónde salió la IP; nunca la IP.
        "xff_hops_seen": {"1": 4}, "client_ip_source": {"x-forwarded-for": 4}}
    warnings = [record.getMessage() for record in caplog.records
                if record.getMessage().startswith("analyze_rate_limited")]
    assert warnings == ["analyze_rate_limited request_id=limite-0001 scope=per_minute retry_after_s=45"]
    assert "203.0.113.7" not in caplog.text  # > La IP del cliente no se registra.


def test_daily_cap_returns_429_until_utc_midnight(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("DSIA_ANALYZE_PER_DAY", "2")
    clock = Clock(datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc).timestamp())
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=clock)) as client:
        statuses = [post(client, symbol, f"203.0.113.{index}").status_code for index in range(1, 3)]
        limited = post(client, symbol, "198.51.100.9")
    assert statuses == [200, 200]
    assert (limited.status_code, limited.headers["retry-after"]) == (429, "7200")
    assert limited.json()["detail"] == {"code": "rate_limited", "message": (
        "El servicio alcanzó su límite diario de 2 análisis. "
        "Reintenta en 7200 s (el contador se reinicia a las 00:00 UTC).")}


def test_rotating_a_forged_forwarded_for_does_not_avoid_the_429(demo_run, symbol, monkeypatch):
    # >> R1: el cliente puede inventar lo que va a la izquierda, pero no el salto que añade el proxy.
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "5")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        statuses = [post(client, symbol, "203.0.113.9", forged=f"10.0.0.{index}").status_code
                    for index in range(10)]
        metrics = client.get("/api/v1/metrics").json()["rate_limit"]
    assert statuses == [200] * 5 + [429] * 5
    assert metrics["xff_hops_seen"] == {"2": 10}


def test_a_forged_first_forwarded_for_line_does_not_avoid_the_429(demo_run, symbol, monkeypatch):
    # >> El proxy añade su propia línea X-Forwarded-For en vez de concatenar: cuenta la suya, la última.
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "5")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        statuses = [client.post(URL, json={"symbol": symbol}, headers=[
            ("X-Forwarded-For", f"198.51.100.{index}"), ("X-Forwarded-For", "203.0.113.9")]).status_code
            for index in range(10)]
    assert statuses == [200] * 5 + [429] * 5


def test_without_a_proxy_zero_hops_keys_on_the_peer_and_rotation_does_not_help(demo_run, symbol, monkeypatch):
    # >> docker run -p o uvicorn sin proxy: con DSIA_TRUSTED_PROXY_HOPS=0 se ignora X-Forwarded-For.
    monkeypatch.setenv("DSIA_TRUSTED_PROXY_HOPS", "0")
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "5")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        statuses = [post(client, symbol, f"203.0.113.{index}").status_code for index in range(10)]
        metrics = client.get("/api/v1/metrics").json()["rate_limit"]
    assert statuses == [200] * 5 + [429] * 5
    assert (metrics["trusted_proxy_hops"], metrics["client_ip_source"]) == (0, {"peer": 10})


def test_a_victim_ip_in_a_forged_header_is_not_blocked(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "5")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        attacker = [post(client, symbol, "198.51.100.66", forged="192.0.2.50").status_code for _ in range(6)]
        victim = post(client, symbol, "192.0.2.50")
    assert attacker == [200] * 5 + [429]
    assert victim.status_code == 200


def test_one_ip_cannot_spend_the_whole_daily_cap(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "100")
    monkeypatch.setenv("DSIA_ANALYZE_PER_IP_DAY", "3")
    clock = Clock(datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc).timestamp())
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=clock)) as client:
        greedy = [post(client, symbol, "203.0.113.7") for _ in range(4)]
        other = post(client, symbol, "198.51.100.2")
        metrics = client.get("/api/v1/metrics").json()["rate_limit"]
    assert [response.status_code for response in greedy] == [200, 200, 200, 429]
    assert greedy[-1].headers["retry-after"] == "7200"
    assert greedy[-1].json()["detail"]["message"] == (
        "Tu conexión alcanzó su límite diario de 3 análisis. "
        "Reintenta en 7200 s (el contador se reinicia a las 00:00 UTC).")
    assert other.status_code == 200
    assert (metrics["used_today"], metrics["rejected"]["per_ip_day"]) == (4, 1)


def test_ipv6_clients_of_the_same_64_share_the_window(demo_run, symbol, monkeypatch):
    # >> R3: rotar la parte de interfaz de una IPv6 no da ventanas nuevas.
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "5")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        same_64 = [post(client, symbol, f"2001:db8:1:2::{index:x}").status_code for index in range(1, 11)]
        other_64 = post(client, symbol, "2001:db8:1:3::1")
        mapped = [post(client, symbol, ip).status_code
                  for ip in ["203.0.113.5"] * 5 + ["::ffff:203.0.113.5"]]
    assert same_64 == [200] * 5 + [429] * 5
    assert other_64.status_code == 200
    assert mapped == [200] * 5 + [429]


def test_on_render_the_key_comes_from_cf_connecting_ip(demo_run, symbol, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "2")
    with TestClient(create_app(demo_run.path, api_key="", rate_clock=Clock(NOON))) as client:
        statuses = [post(client, symbol, f"203.0.113.{index}",
                         headers={"CF-Connecting-IP": "198.51.100.77"}).status_code for index in range(3)]
        metrics = client.get("/api/v1/metrics").json()["rate_limit"]
    assert statuses == [200, 200, 429]
    assert metrics["client_ip_source"] == {"cf-connecting-ip": 3}


def test_rejected_requests_do_not_consume_the_quota(demo_run, symbol, monkeypatch):
    # >> Solo cuenta lo que llegaría al proveedor: 401, 422 y 404 no gastan la clave ni el cupo.
    monkeypatch.setenv("DSIA_ANALYZE_PER_MINUTE", "1")
    with TestClient(create_app(demo_run.path, api_key="clave-demo")) as client:
        assert post(client, symbol).status_code == 401
        assert post(client, "aapl", api_key="clave-demo").status_code == 422
        assert post(client, "ZZZZ", api_key="clave-demo").status_code == 404
        assert post(client, symbol, api_key="clave-demo").status_code == 200
        assert post(client, symbol, api_key="clave-demo").status_code == 429


def test_default_limits_admit_the_three_smoke_analyses(demo_run, symbol):
    # >> smoke_test.sh (1) + browser_smoke.py (2) en el mismo minuto y desde la misma IP: por debajo de 5.
    with TestClient(create_app(demo_run.path, api_key="")) as client:
        statuses = [post(client, symbol).status_code for _ in range(6)]
    assert statuses == [200] * 5 + [429]


@pytest.mark.parametrize("name,raw", [
    *[(name, raw) for name in ("DSIA_ANALYZE_PER_MINUTE", "DSIA_ANALYZE_PER_DAY", "DSIA_ANALYZE_PER_IP_DAY",
                               "DSIA_ANALYZE_CONCURRENCY", "DSIA_ANALYZE_CONCURRENCY_PER_IP")
      for raw in ("0", "-5", "muchos")],
    # > DSIA_TRUSTED_PROXY_HOPS admite 0 (sin proxy), pero no negativos ni texto.
    ("DSIA_TRUSTED_PROXY_HOPS", "-5"), ("DSIA_TRUSTED_PROXY_HOPS", "muchos"),
])
def test_invalid_limit_stops_the_service_at_startup(demo_run, monkeypatch, caplog, name, raw):
    monkeypatch.setenv(name, raw)
    expected = "mayor o igual que 0" if name == "DSIA_TRUSTED_PROXY_HOPS" else "mayor que 0"
    with pytest.raises(ValueError, match=f"^{name} debe ser un entero {expected}"):
        with TestClient(create_app(demo_run.path)):
            pass
    assert f"config_invalid {name} debe ser un entero {expected}" in caplog.text


@pytest.mark.parametrize("name", ["DSIA_ANALYZE_PER_MINUTE", "DSIA_ANALYZE_PER_DAY", "DSIA_ANALYZE_PER_IP_DAY",
                                  "DSIA_ANALYZE_CONCURRENCY", "DSIA_ANALYZE_CONCURRENCY_PER_IP",
                                  "DSIA_TRUSTED_PROXY_HOPS"])
def test_a_key_pasted_into_a_limit_stops_startup_without_reaching_the_log(demo_run, monkeypatch, caplog, name):
    monkeypatch.setenv(name, PASTED)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ValueError) as error:
            with TestClient(create_app(demo_run.path)):
                pass
    assert f"config_invalid {name} debe ser un entero" in caplog.text
    assert f"de {len(PASTED)} caracteres" in caplog.text
    for text in (str(error.value), caplog.text):
        assert "clave.falsa" not in text
