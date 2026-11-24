"""-> Inspección de solo lectura y EDA anterior al entrenamiento."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from ml_pipeline import guard
from .data import DataError, file_sha256

LOG = logging.getLogger(__name__)


def inspect_dataset(path: Path, output: Path, horizon: int = 21) -> dict:
    output = Path(output)
    # > Como train y run, inspect no mezcla ni sobrescribe evidencias de una ejecución anterior.
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise DataError('La salida de inspect ya existe; usa un directorio nuevo')
    raw = pd.read_csv(path)
    if not {'symbol', 'close'} <= set(raw):
        raise ValueError('La inspección requiere symbol y close')
    date_column = 'date' if 'date' in raw else 'timestamp'
    frame = raw.rename(columns={date_column: 'date'}).copy()
    frame['date'] = pd.to_datetime(frame['date'], utc=True).dt.tz_convert(None)
    frame = frame.sort_values(['symbol', 'date'])
    # > Target exploratorio; nunca se incluye como feature ni se rellenan sus NaN finales.
    frame['return_21_sessions'] = frame.groupby('symbol')['close'].shift(-horizon) / frame['close'] - 1
    output.mkdir(parents=True, exist_ok=True)
    profile = guard.profile(frame, target='return_21_sessions', time_col='date', state_dir=output)
    guard.eda_figures(frame, target='return_21_sessions', time_col='date', state_dir=output)
    summary = {'source_file': path.name, 'sha256': file_sha256(path), 'raw_rows': len(raw),
               'raw_columns': list(raw.columns), 'symbols': int(raw['symbol'].nunique()),
               'dates': int(frame['date'].nunique()), 'start': str(frame['date'].min()),
               'end': str(frame['date'].max()), 'missing_raw': raw.isna().sum().to_dict(),
               'duplicate_keys': int(frame.duplicated(['date', 'symbol']).sum()),
               'labelled_rows': int(frame['return_21_sessions'].notna().sum()),
               'horizon': horizon, 'leakage_suspects': profile['leakage_suspects'],
               'traits': profile['traits']}
    LOG.info('Perfil de inspección rows=%d symbols=%d start=%s end=%s labelled_rows=%d leakage_suspects=%s',
             summary['raw_rows'], summary['symbols'], frame['date'].min().date(), frame['date'].max().date(),
             summary['labelled_rows'], summary['leakage_suspects'])
    (output / 'inspection_summary.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    return summary
