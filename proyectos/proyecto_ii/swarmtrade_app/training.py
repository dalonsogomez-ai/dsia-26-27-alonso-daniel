"""-> Selección en validation y persistencia; test aislado hasta su evaluación final."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from ml_pipeline import guard
from .data import DataError, FEATURES
from .models import SwarmRegressor, ridge_model
from .preparation import load_prepared

LOG = logging.getLogger(__name__)


def metrics(y, prediction) -> dict[str, float]:
    return {'rmse': float(root_mean_squared_error(y, prediction)),
            'mae': float(mean_absolute_error(y, prediction)),
            'r2': float(r2_score(y, prediction)),
            'sign_accuracy': float(np.mean((np.asarray(y) > 0) == (np.asarray(prediction) > 0)))}


def train_prepared(run: Path, *, ledger: Path | None = None) -> dict:
    """> Cargar únicamente Prepared y joblib propios de confianza."""
    run = Path(run)
    if (run / 'model.joblib').exists() or (run / 'validation.json').exists():
        raise DataError('El experimento ya está entrenado; no se sobrescribe')
    prepared = load_prepared(run)
    train, validation = prepared.train, prepared.validation
    X, y = train.loc[:, FEATURES], train['target']
    candidates = {'dummy': DummyRegressor(strategy='mean'), 'ridge': ridge_model(), 'swarm': SwarmRegressor()}
    scores, predictions = {}, {}
    for name, model in candidates.items():
        model.fit(X, y)
        predictions[name] = model.predict(validation.loc[:, FEATURES])
        scores[name] = metrics(validation['target'], predictions[name])
        LOG.info('Validation model=%s rmse=%.6f', name, scores[name]['rmse'])
    winner = min(scores, key=lambda name: scores[name]['rmse'])
    diagnostic = validation[['date', 'symbol', 'target_end', 'target']].copy()
    diagnostic['prediction'] = predictions[winner]
    diagnostic['error'] = diagnostic['prediction'] - diagnostic['target']
    diagnostic.to_csv(run / 'validation_predictions.csv', index=False)
    slices = diagnostic.assign(abs_error=diagnostic['error'].abs()).groupby('symbol')['abs_error'].agg(['mean', 'max', 'count'])
    slices.to_csv(run / 'validation_slices.csv')
    report = {'selected': winner, 'selection_metric': 'validation.rmse', 'alpha': 10,
              'hyperparameter_search': False, 'validation': scores, 'metadata': prepared.metadata,
              'sklearn_version': sklearn.__version__, 'created_utc': datetime.now(timezone.utc).isoformat()}
    # > Mapa de asignación: solo validation fuera de muestra, cada h sesiones, nunca test.
    calibration_dates = sorted(diagnostic['date'].unique())[::prepared.metadata['horizon']]
    oos = diagnostic.loc[diagnostic['date'].isin(calibration_dates), ['date', 'prediction', 'target', 'target_end']]
    oos = oos.rename(columns={'prediction': 'score', 'target': 'fwd'})
    artifact = {'schema': 1, 'estimator': candidates[winner], 'features': FEATURES, 'report': report,
                'symbols': prepared.metadata['symbols'], 'horizon': prepared.metadata['horizon'],
                'trained_until': prepared.metadata['splits']['train']['max_target_end'], 'oos': oos}
    artifact_path = run / 'model.joblib'
    joblib.dump(artifact, artifact_path)
    restored = joblib.load(artifact_path)
    np.testing.assert_allclose(restored['estimator'].predict(validation.loc[:, FEATURES]), predictions[winner], atol=1e-12)
    (run / 'validation.json').write_text(json.dumps(report, indent=2))
    figures = ledger or run
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].bar(list(scores), [value['rmse'] for value in scores.values()])
    axes[0].set(title='RMSE validation: menor es mejor', ylabel='Retorno decimal')
    axes[1].scatter(predictions[winner], diagnostic['error'], s=4, alpha=.15)
    axes[1].axhline(0, color='black', linewidth=1)
    axes[1].set(title=f'Residuos de {winner}', xlabel='Predicción', ylabel='Predicción − target')
    fig.tight_layout()
    guard.fig(12, 'validation', fig,
              f"Ganador por validation: {winner}; RMSE={scores[winner]['rmse']:.6f}; "
              f"Dummy={scores['dummy']['rmse']:.6f}. Residuos predictivos, sin medir rentabilidad.", state_dir=figures)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    slices['mean'].sort_values().plot.bar(ax=ax)
    ax.set(title='MAE validation por símbolo', ylabel='Error absoluto medio')
    fig.tight_layout()
    guard.fig(13, 'error_slices', fig,
              'El error por símbolo muestra dónde falla más; no se reajusta el modelo usando estas diferencias.', state_dir=figures)
    plt.close(fig)
    return report


def evaluate_holdout(run: Path, *, ledger: Path | None = None) -> dict:
    """> Evaluar una sola vez el ganador congelado, sin selección posterior."""
    run = Path(run)
    artifact = joblib.load(run / 'model.joblib')
    prepared = load_prepared(run)
    result = {}
    # > Referencia fija de train (DummyRegressor mean): no entra en la selección y comparte el único toque.
    train_mean = float(prepared.train['target'].mean())

    def evaluate(y, prediction):
        result.update(metrics(y, prediction))
        result['baseline'] = {'model': 'dummy_mean_train', 'prediction': train_mean,
                              **metrics(y, np.full(len(y), train_mean))}
        return result['rmse']

    def predict(frame):
        return artifact['estimator'].predict(frame.loc[:, FEATURES])

    guard.final_test(predict, prepared.holdout, target='target', metric_fn=evaluate,
                     state_dir=run, pipeline_md=(ledger or run) / 'PIPELINE.md')
    result.update(selected=artifact['report']['selected'], touches=1)
    LOG.info('Holdout model=%s rmse=%.6f baseline_rmse=%.6f touches=1', result['selected'], result['rmse'],
             result['baseline']['rmse'])
    (run / 'test_metrics.json').write_text(json.dumps(result, indent=2))
    return result
