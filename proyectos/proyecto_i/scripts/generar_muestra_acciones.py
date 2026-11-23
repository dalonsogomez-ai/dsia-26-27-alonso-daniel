"""-> Generar una muestra SINTÉTICA de barras diarias con el esquema de la Parte B.

Los datos son inventados con una semilla fija: no contienen cotizaciones de
Alpaca ni de ningún otro proveedor y los símbolos (`FICT.A`...) son ficticios.
Sirven para ejecutar `acciones_app` sin red, sin cuenta y sin el binario
`alpaca`. El script no accede a la red y produce siempre el mismo fichero.

Además de las barras correctas incluye, a propósito, filas sucias:

> un duplicado `symbol`/`timestamp` con cierre contradictorio (se rechazan las dos);
> una barra con OHLC incoherente (`high < low`);
> una barra con volumen negativo;
> una barra con fecha inexistente (30 de febrero);
> una barra válida con `vwap` fuera de `[low, high]`, que solo genera un aviso.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
import math
from pathlib import Path
import random


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT / "data" / "sample" / "acciones_muestra.csv"
DEFAULT_SEED = 20261123
DEFAULT_SESSIONS = 75
SYMBOLS = ("FICT.A", "FICT.B", "FICT.C", "FICT.D")
START_PRICES = {"FICT.A": 100.0, "FICT.B": 50.0, "FICT.C": 20.0, "FICT.D": 250.0}
FIRST_SESSION = date(2026, 1, 2)
COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume", "trade_count", "vwap")


def sessions(first: date, count: int) -> list[date]:
    """> Devuelve `count` días laborables (lunes a viernes) desde `first`, incluido."""
    days: list[date] = []
    current = first
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _floor(value: float) -> float:
    """> Redondea hacia abajo a 4 decimales para que low no supere el precio real."""
    return math.floor(value * 10_000) / 10_000


def _ceil(value: float) -> float:
    """> Redondea hacia arriba a 4 decimales para que high no quede por debajo del precio real."""
    return math.ceil(value * 10_000) / 10_000


def generate_bars(seed: int = DEFAULT_SEED, count: int = DEFAULT_SESSIONS) -> list[dict[str, object]]:
    """> Genera barras OHLCV coherentes con un paseo aleatorio por símbolo.

    Cada símbolo usa su propio generador derivado de la semilla, así que añadir
    sesiones no altera las ya generadas. Se garantiza low ≤ open, close ≤ high
    y vwap dentro de [low, high].
    """
    rows: list[dict[str, object]] = []
    days = sessions(FIRST_SESSION, count)
    for offset, symbol in enumerate(SYMBOLS):
        rng = random.Random(seed * 100 + offset)
        previous = START_PRICES[symbol]
        for day in days:
            open_ = round(previous * (1 + rng.gauss(0, 0.004)), 4)
            close = round(open_ * (1 + rng.gauss(0.0004, 0.015)), 4)
            high = _ceil(max(open_, close) * (1 + rng.uniform(0, 0.01)))
            low = _floor(min(open_, close) * (1 - rng.uniform(0, 0.01)))
            volume = rng.randint(200_000, 5_000_000)
            rows.append({
                "symbol": symbol, "timestamp": f"{day.isoformat()}T05:00:00Z",
                "open": open_, "high": high, "low": low, "close": close,
                "volume": volume, "trade_count": volume // rng.randint(80, 160),
                "vwap": round((high + low + close) / 3, 4),
            })
            previous = close
    return rows


def inject_dirty_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """> Estropea filas concretas y añade un duplicado, sin depender del azar.

    Devuelve una lista nueva; las posiciones son fijas respecto a cada símbolo.
    """
    dirty = [dict(row) for row in rows]
    per_symbol = len(dirty) // len(SYMBOLS)

    def at(symbol: str, session: int) -> dict[str, object]:
        """> Devuelve la barra de `symbol` en la sesión `session` dentro de la lista plana."""
        return dirty[SYMBOLS.index(symbol) * per_symbol + session]

    incoherent = at("FICT.B", 20)
    incoherent["high"], incoherent["low"] = incoherent["low"], incoherent["high"]
    at("FICT.C", 30)["volume"] = -500
    at("FICT.D", 40)["timestamp"] = "2026-02-30T05:00:00Z"
    outlier = at("FICT.A", 50)
    outlier["vwap"] = round(float(outlier["high"]) * 1.02, 4)
    duplicate = dict(at("FICT.A", 10))
    duplicate["close"] = round(float(duplicate["close"]) * 0.97, 4)
    duplicate["low"] = min(float(duplicate["low"]), float(duplicate["close"]))
    dirty.append(duplicate)
    return dirty


def write_sample(path: Path, rows: list[dict[str, object]]) -> None:
    """> Escribe el CSV con saltos de línea `\\n` para que sea idéntico en cualquier SO."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """> Lee la ruta de salida, la semilla y el número de sesiones por símbolo."""
    parser = argparse.ArgumentParser(
        description="Genera una muestra sintética (sin datos de Alpaca) para acciones_app.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="CSV a escribir")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="semilla del generador")
    parser.add_argument(
        "--sessions", type=int, default=DEFAULT_SESSIONS,
        help="sesiones por símbolo (mínimo 51 para poder inyectar todas las filas sucias)",
    )
    args = parser.parse_args(argv)
    if args.sessions < 51:
        parser.error("--sessions debe ser al menos 51")
    return args


def main(argv: list[str] | None = None) -> int:
    """> Genera la muestra y escribe un resumen por la salida estándar."""
    args = parse_arguments(argv)
    rows = inject_dirty_rows(generate_bars(args.seed, args.sessions))
    write_sample(args.output, rows)
    print(f"Muestra sintética: {len(rows)} filas, {len(SYMBOLS)} símbolos ficticios -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
