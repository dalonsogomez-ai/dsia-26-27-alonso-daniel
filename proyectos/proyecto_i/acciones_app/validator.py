"""-> Reglas de calidad de barras diarias OHLCV, independientes del proveedor."""

from __future__ import annotations

import logging

import pandas as pd


LOGGER = logging.getLogger(__name__)

PRICES = ("open", "high", "low", "close", "vwap")
COUNTS = ("volume", "trade_count")
REQUIRED_COLUMNS = {"symbol", "timestamp", *PRICES, *COUNTS}


class ValidationError(Exception):
    """-> El esquema recibido no permite validar las barras."""


def validate_bars(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """> Separa barras válidas e inválidas, sin modificar el DataFrame original.

    Se rechazan todos los miembros de una clave duplicada (symbol, timestamp),
    evitando escoger de forma arbitraria entre observaciones contradictorias.
    Las válidas salen normalizadas (símbolo en mayúsculas, fecha UTC, números);
    las inválidas conservan los valores originales y añaden `motivo`.
    """
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValidationError(f"Faltan columnas obligatorias: {', '.join(sorted(missing))}")
    original = frame.reset_index(drop=True)
    bars = original.copy()
    bars["symbol"] = bars["symbol"].astype("string").str.strip().str.upper()
    bars["timestamp"] = pd.to_datetime(bars["timestamp"], format="ISO8601", utc=True, errors="coerce")
    for column in (*PRICES, *COUNTS):
        bars[column] = pd.to_numeric(bars[column], errors="coerce")

    rules = {
        "símbolo inválido": bars["symbol"].str.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", na=False),
        "fecha inválida": bars["timestamp"].notna(),
    }
    for column in PRICES:
        rules[f"{column} debe ser positivo y finito"] = bars[column].gt(0) & bars[column].abs().lt(float("inf"))
    for column in COUNTS:
        value = bars[column]
        rules[f"{column} debe ser entero no negativo"] = value.ge(0) & value.abs().lt(float("inf")) & value.mod(1).eq(0)
    rules["precios OHLC incoherentes"] = (
        bars["high"].ge(bars["open"]) & bars["high"].ge(bars["close"])
        & bars["high"].ge(bars["low"]) & bars["low"].le(bars["open"])
        & bars["low"].le(bars["close"])
    )
    rules["símbolo y fecha duplicados"] = ~bars.duplicated(["symbol", "timestamp"], keep=False)
    checks = pd.DataFrame(rules, index=bars.index).fillna(False)
    mask = checks.all(axis=1)
    _warn_vwap_outside_range(bars.loc[mask])
    valid =bars.loc[mask].sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    # => Los rechazos se exportan con los valores recibidos, no con los convertidos.
    invalid = original.loc[~mask].copy()
    invalid["motivo"] = checks.loc[~mask].apply(
        lambda row: "; ".join(row.index[~row]), axis=1
    ) if len(invalid) else pd.Series(dtype="string")
    return valid, invalid.reset_index(drop=True)


def vwap_outside_range(bars: pd.DataFrame) -> pd.Series:
    """> Marca las barras cuyo vwap queda fuera de [low, high].

    Es solo un aviso: el vwap diario de Alpaca puede incluir operaciones fuera
    del horario regular, cuyos precios no siempre caen en el rango de la sesión.
    """
    return ~bars["vwap"].between(bars["low"], bars["high"])


def _warn_vwap_outside_range(valid_bars: pd.DataFrame) -> None:
    """> Registra un aviso con las barras válidas de vwap atípico, sin rechazarlas."""
    outside = vwap_outside_range(valid_bars)
    if outside.any():
        LOGGER.warning(
            "%s barras válidas con vwap fuera de [low, high] (se conservan; solo aviso): %s",
            int(outside.sum()), ", ".join(sorted(valid_bars.loc[outside, "symbol"].unique())),
        )
