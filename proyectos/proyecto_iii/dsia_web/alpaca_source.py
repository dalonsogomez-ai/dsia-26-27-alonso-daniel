"""-> Ingesta de barras diarias de Alpaca para el lote del III.

Las credenciales se leen del entorno o de un secret file y solo viven en memoria: nunca se
escriben en disco, en el snapshot ni en los logs. El CSV resultante contiene únicamente
``date, symbol, close, volume`` (el contrato mínimo del II) y se queda en el directorio de
trabajo del lote; el informe público no publica precios.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import pandas as pd
from dotenv import dotenv_values
from swarmtrade_app.data import DataError

LOG = logging.getLogger(__name__)

KEY_ENV = "ALPACA_PAPER_API_KEY_ID"
SECRET_ENV = "ALPACA_PAPER_API_SECRET_KEY"
# >> Universo del histórico del Proyecto I (ALPACA.md): grandes compañías con datos desde 2018.
DEFAULT_SYMBOLS = ("AAPL", "AMZN", "GOOGL", "JNJ", "JPM", "META", "MSFT", "NVDA", "TSLA", "XOM")
DEFAULT_START = date(2018, 1, 1)
FEEDS = ("sip", "iex")


@dataclass(frozen=True)
class AlpacaCredentials:
    """> Par de claves de Alpaca; ``repr`` no muestra ninguna de las dos."""

    key: str = field(repr=False)
    secret: str = field(repr=False)


def load_credentials(secrets_file: Path | None = None,
                     environ: Mapping[str, str] | None = None) -> AlpacaCredentials | None:
    """> Claves del entorno o, si faltan, del secret file (formato ``.env``); ``None`` si no hay par completo."""
    environ = os.environ if environ is None else environ
    stored: Mapping[str, str | None] = {}
    if secrets_file is not None and Path(secrets_file).is_file():
        stored = dotenv_values(secrets_file)
    key = (environ.get(KEY_ENV) or stored.get(KEY_ENV) or "").strip()
    secret = (environ.get(SECRET_ENV) or stored.get(SECRET_ENV) or "").strip()
    return AlpacaCredentials(key, secret) if key and secret else None


def parse_symbols(raw: str | None) -> tuple[str, ...]:
    """> ``"AAPL, msft"`` → ``("AAPL", "MSFT")``; vacío → universo por defecto."""
    symbols = tuple(dict.fromkeys(part.strip().upper() for part in (raw or "").split(",") if part.strip()))
    return symbols or DEFAULT_SYMBOLS


def default_client(credentials: AlpacaCredentials) -> Any:
    """> Cliente real de datos históricos (import diferido: las pruebas usan un doble)."""
    from alpaca.data.historical import StockHistoricalDataClient

    return StockHistoricalDataClient(api_key=credentials.key, secret_key=credentials.secret)


def _request(symbols: Sequence[str], start: date, end: datetime, feed: str) -> Any:
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    return StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day,
                            start=datetime.combine(start, time.min, timezone.utc), end=end,
                            adjustment=Adjustment.SPLIT, feed=DataFeed(feed))


def _download(client: Any, symbols: Sequence[str], start: date, end: datetime, feed: str) -> tuple[pd.DataFrame, str]:
    """> Pide SIP y, si la suscripción no lo permite, repite con IEX. Los errores no exponen la respuesta."""
    order = [feed] + [other for other in FEEDS if other != feed]
    for attempt, current in enumerate(order):
        try:
            return client.get_stock_bars(_request(symbols, start, end, current)).df, current
        except Exception as exc:  # noqa: BLE001 - el SDK lanza varios tipos; se redacta en el borde
            if attempt + 1 < len(order):
                LOG.warning("Feed %s de Alpaca no disponible (%s); se reintenta con %s",
                            current, type(exc).__name__, order[attempt + 1])
                continue
            raise DataError(f"No se pudieron descargar las barras de Alpaca ({type(exc).__name__})") from None
    raise AssertionError("inalcanzable")


def fetch_daily_bars(output: Path, credentials: AlpacaCredentials, *,
                     symbols: Sequence[str] = DEFAULT_SYMBOLS, start: date = DEFAULT_START,
                     today: date | None = None, feed: str = "sip",
                     client_factory: Callable[[AlpacaCredentials], Any] = default_client) -> dict:
    """Descargar barras diarias hasta ayer y escribir un panel común ``date, symbol, close, volume``.

    Devuelve solo agregados (filas, símbolos, fechas, rango, feed y fechas descartadas) para el journal.
    """
    if feed not in FEEDS:
        raise DataError(f"Feed de Alpaca no soportado: {feed}")
    output = Path(output)
    if output.exists():
        raise DataError("El CSV de barras ya existe")
    today = today or datetime.now(timezone.utc).date()
    # -> Corte a medianoche UTC de hoy: solo barras diarias cerradas (hasta ayer).
    end = datetime.combine(today, time.min, timezone.utc)
    frame, used_feed = _download(client_factory(credentials), symbols, start, end, feed)
    if frame is None or len(frame) == 0:
        raise DataError("Alpaca no devolvió barras para el periodo pedido")
    bars = frame.reset_index()
    missing = sorted(set(symbols) - set(bars["symbol"]))
    if missing:
        raise DataError(f"Alpaca no devolvió barras para: {', '.join(missing)}")
    # >> Fecha de sesión en Nueva York: la barra diaria llega con la medianoche local en UTC.
    stamps = pd.to_datetime(bars["timestamp"], utc=True).dt.tz_convert("America/New_York")
    bars = pd.DataFrame({"date": stamps.dt.strftime("%Y-%m-%d"), "symbol": bars["symbol"].astype(str),
                         "close": bars["close"].astype(float), "volume": bars["volume"].astype(float)})
    bars = bars.drop_duplicates(["date", "symbol"], keep="last")
    complete = bars.groupby("date")["symbol"].nunique() == len(symbols)
    dropped = int((~complete).sum())
    bars = bars[bars["date"].isin(complete[complete].index)].sort_values(["date", "symbol"])
    if dropped:
        LOG.warning("Se descartan %d fechas sin barra para todos los símbolos", dropped)
    output.parent.mkdir(parents=True, exist_ok=True)
    bars.to_csv(output, index=False)
    LOG.info("Barras de Alpaca rows=%d symbols=%d dates=%d start=%s end=%s feed=%s", len(bars),
             len(symbols), bars["date"].nunique(), bars["date"].min(), bars["date"].max(), used_feed)
    return {"rows": int(len(bars)), "symbols": len(symbols), "dates": int(bars["date"].nunique()),
            "start": str(bars["date"].min()), "end": str(bars["date"].max()), "feed": used_feed,
            "dropped_dates": dropped}
