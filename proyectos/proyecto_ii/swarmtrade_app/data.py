"""-> Datos diarios y factores causales reutilizados de SwarmTrader."""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ._vendor.features import FACTOR_NAMES, compute_features, forward_returns

FEATURES = tuple(FACTOR_NAMES)
WARMUP = 252
LOG = logging.getLogger(__name__)


class DataError(ValueError):
    """Datos que incumplen el contrato de barras diarias."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_bars(path: Path) -> pd.DataFrame:
    """CSV largo: date/timestamp, symbol, close y volume; OHLC opcional."""
    try:
        bars = pd.read_csv(path)
    except (OSError, ValueError) as exc:
        raise DataError('No se pudo leer el CSV de barras') from exc
    if 'date' not in bars and 'timestamp' in bars:
        bars = bars.rename(columns={'timestamp': 'date'})
    required = {'date', 'symbol', 'close', 'volume'}
    if not required <= set(bars):
        raise DataError(f'Faltan columnas: {sorted(required - set(bars))}')
    try:
        bars['date'] = pd.to_datetime(bars['date'], utc=True, errors='raise', format='ISO8601').dt.tz_convert(None).dt.normalize()
        bars['symbol'] = bars['symbol'].astype('string').str.strip()
        numeric = [c for c in ('open', 'high', 'low', 'close', 'volume') if c in bars]
        bars[numeric] = bars[numeric].apply(pd.to_numeric, errors='raise')
    except (ValueError, TypeError) as exc:
        raise DataError('Fecha o número no válido') from exc
    if bars[list(required)].isna().any().any() or (bars['symbol'] == '').any():
        raise DataError('Hay datos obligatorios vacíos')
    if not np.isfinite(bars[numeric].to_numpy(float)).all():
        raise DataError('Hay valores no finitos')
    prices = [c for c in numeric if c != 'volume']
    if (bars[prices] <= 0).any().any() or (bars['volume'] < 0).any():
        raise DataError('Precios no positivos o volumen negativo')
    if bars.duplicated(['date', 'symbol']).any():
        raise DataError('Claves date/symbol duplicadas; se requieren barras diarias')
    if {'open', 'high', 'low'} <= set(bars):
        if ((bars['low'] > bars[['open', 'close']].min(axis=1)) |
                (bars['high'] < bars[['open', 'close']].max(axis=1))).any():
            raise DataError('Relaciones OHLC incoherentes')
    if bars['symbol'].nunique() < 5:
        raise DataError('Se requieren cinco símbolos para los factores cross-sectional')
    LOG.info('Barras cargadas file=%s rows=%d symbols=%d dates=%d start=%s end=%s', Path(path).name, len(bars),
             bars['symbol'].nunique(), bars['date'].nunique(), bars['date'].min().date(), bars['date'].max().date())
    return bars.sort_values(['date', 'symbol']).reset_index(drop=True)


def feature_panel(bars: pd.DataFrame) -> pd.DataFrame:
    prices = bars.pivot(index='date', columns='symbol', values='close')
    volumes = bars.pivot(index='date', columns='symbol', values='volume')
    # > Impedir relleno silencioso de precios en el código upstream.
    if prices.isna().any().any() or volumes.isna().any().any():
        raise DataError('Panel incompleto: selecciona un periodo/universo común sin huecos')
    if len(prices) <= WARMUP + 1:
        raise DataError('Histórico insuficiente para 252 sesiones de warmup')
    panel = compute_features(prices, volumes).loc[prices.index[WARMUP:]]
    return panel.loc[:, list(FEATURES)].reset_index().sort_values(['date', 'symbol'])


def labelled_panel(bars: pd.DataFrame, horizon: int = 21) -> pd.DataFrame:
    if not 1 <= horizon <= 32:
        raise DataError('horizon debe estar entre 1 y 32 sesiones')
    features = feature_panel(bars)
    prices = bars.pivot(index='date', columns='symbol', values='close')
    target = forward_returns(prices, horizon).rename('target').reset_index()
    end = pd.Series(prices.index, index=prices.index).shift(-horizon)
    features['target_end'] = features['date'].map(end)
    panel = features.merge(target, on=['date', 'symbol'], validate='one_to_one').dropna()
    if panel['date'].nunique() < 150:
        raise DataError('Se requieren 150 fechas etiquetadas después de warmup y horizonte')
    return panel.sort_values(['date', 'symbol']).reset_index(drop=True)


def generate_demo(path: Path, sessions: int = 900, symbols: int = 8, seed: int = 42) -> Path:
    """Datos sintéticos propios para reproducir el flujo sin redistribuir Alpaca."""
    if sessions < 450 or symbols < 5:
        raise DataError('La demo requiere 450 sesiones y cinco símbolos como mínimo')
    path = Path(path)
    if path.exists():
        raise DataError('El fichero de salida ya existe')
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range('2020-01-02', periods=sessions)
    market = rng.normal(0.0002, 0.009, (sessions, 1))
    prices = 100 * np.exp(np.cumsum(market + rng.normal(0, 0.012, (sessions, symbols)), axis=0))
    # -> 6 decimales: np.exp difiere en el último ULP entre x86 y ARM; así el CSV es idéntico byte a byte.
    prices = np.round(prices, 6)
    volume = rng.integers(100_000, 5_000_000, (sessions, symbols))
    frames = [pd.DataFrame({'date': dates, 'symbol': f'DEMO{i + 1:02}',
                           'close': prices[:, i], 'volume': volume[:, i]}) for i in range(symbols)]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(frames).sort_values(['date', 'symbol']).to_csv(path, index=False)
    return path
