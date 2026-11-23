"""-> Panel causal, split temporal y purga; ninguna transformación se ajusta aquí."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import logging
from pathlib import Path

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from ml_pipeline import guard
from .data import DataError, FEATURES, WARMUP, file_sha256, labelled_panel, load_bars

LOG = logging.getLogger(__name__)


@dataclass
class Prepared:
    train: pd.DataFrame
    validation: pd.DataFrame
    holdout: pd.DataFrame
    metadata: dict


def prepare(data: Path, run: Path, *, horizon: int = 21, data_kind: str = 'local',
            ledger: Path | None = None) -> Prepared:
    if data_kind not in {'synthetic', 'alpaca', 'local'}:
        raise DataError('data_kind debe ser synthetic, alpaca o local')
    run = Path(run)
    if run.exists():
        raise DataError('El directorio run ya existe; no se sobrescriben experimentos')
    bars = load_bars(data)
    panel = labelled_panel(bars, horizon)
    dates = panel['date'].drop_duplicates().sort_values().to_numpy()
    n_val = n_holdout = len(dates) // 5
    # > El panel completo garantiza igual número de símbolos en cada fecha.
    train, validation, holdout = guard.split(
        panel, target='target', time_col='date', val_size=n_val / len(dates),
        test_size=n_holdout / len(dates), state_dir=run)
    before = [len(train), len(validation), len(holdout)]
    train = train.loc[train['target_end'] < validation['date'].min()].reset_index(drop=True)
    validation = validation.loc[validation['target_end'] < holdout['date'].min()].reset_index(drop=True)
    if len(train) < 50 or len(validation) < 20 or len(holdout) < 20:
        raise DataError('Split insuficiente después de purgar el horizonte')
    frames = [train, validation, holdout]
    if any(not frame.loc[:, FEATURES].notna().all().all() for frame in frames):
        raise DataError('Features no disponibles después del warmup')
    metadata = {
        'data_sha256': file_sha256(data), 'data_kind': data_kind, 'horizon': horizon,
        'raw_rows': len(bars), 'raw_dates': bars['date'].nunique(),
        'symbols': sorted(bars['symbol'].unique().tolist()), 'warmup_sessions': WARMUP,
        'features': list(FEATURES), 'labelled_rows': len(panel),
        'warmup_rows_removed': WARMUP * bars['symbol'].nunique(),
        'unobserved_target_rows': horizon * bars['symbol'].nunique(),
        'purged_rows': {'train': before[0] - len(train), 'validation': before[1] - len(validation)},
        'splits': {name: {'rows': len(frame), 'dates': frame['date'].nunique(),
                         'start': str(frame['date'].min().date()), 'end': str(frame['date'].max().date()),
                         'max_target_end': str(frame['target_end'].max().date())}
                   for name, frame in zip(('train', 'validation', 'test'), frames)},
    }
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(['raw', 'warmup', 'sin target', 'purga', 'train', 'val', 'test'],
           [len(bars), metadata['warmup_rows_removed'], metadata['unobserved_target_rows'],
            sum(metadata['purged_rows'].values()), *[len(f) for f in frames]])
    ax.set(ylabel='Filas', title='Reglas prefijadas: sin imputar ni duplicar observaciones')
    fig.tight_layout()
    guard.fig(4, 'preparation', fig,
              f"{len(bars)} barras válidas; warmup={metadata['warmup_rows_removed']}, "
              f"sin target futuro={metadata['unobserved_target_rows']}, purga={metadata['purged_rows']}. "
              'Los huecos se rechazan; no se elimina ningún precio por su valor futuro.',
              state_dir=ledger or run)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 3))
    for i, (name, frame) in enumerate(zip(('train', 'validation', 'test'), frames)):
        ax.plot([frame['date'].min(), frame['date'].max()], [i, i], linewidth=12, label=name)
    ax.set(yticks=[0, 1, 2], yticklabels=['train', 'validation', 'test'], title='Fechas completas con embargo de etiquetas')
    fig.autofmt_xdate()
    fig.tight_layout()
    guard.fig(6, 'temporal_split', fig,
              'Los tres bloques son cronológicos. target_end de train precede validation y el de validation precede test.',
              state_dir=ledger or run)
    plt.close(fig)
    LOG.info('Split purgado train=%d validation=%d test=%d purged_train=%d purged_validation=%d horizon=%d',
             *[len(frame) for frame in frames], metadata['purged_rows']['train'],
             metadata['purged_rows']['validation'], horizon)
    result = Prepared(*frames, metadata)
    # > Un dict evita serializar una clase bajo __main__ al usar python -m.
    joblib.dump({'train': train, 'validation': validation, 'holdout': holdout,
                 'metadata': metadata}, run / 'prepared.joblib')
    (run / 'preparation.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    return result


def load_prepared(run: Path) -> Prepared:
    return Prepared(**joblib.load(Path(run) / 'prepared.joblib'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='> Preparar sin entrenar')
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--data-kind', default='local')
    args = parser.parse_args()
    print(json.dumps(prepare(args.data, args.run, ledger=args.ledger,
                             data_kind=args.data_kind).metadata, indent=2))
