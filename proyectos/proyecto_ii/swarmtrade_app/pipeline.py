"""-> Inferencia recargada, asignación por convicción v1.4 y explicación HF."""
from __future__ import annotations

from dataclasses import asdict
import json
import logging
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from ._vendor.conviction import (ConvictionConfig, _ScenarioBank, allocate,
                                 certainty_equivalent, solve_simplex)
from .ai_client import AIClient, AnalysisRequest
from .data import DataError, FEATURES, feature_panel, file_sha256, load_bars

LOG = logging.getLogger(__name__)
# > Pesos por debajo de este umbral son residuo numérico del solver, no una decisión de cartera.
MIN_WEIGHT = 1e-6


def significant_weights(weights, threshold: float = MIN_WEIGHT) -> np.ndarray:
    """Anula pesos residuales (< threshold) y renormaliza a 1 sin cambiar el orden de los activos."""
    weights = np.clip(np.asarray(weights, dtype=float), 0, None)
    kept = np.where(weights >= threshold, weights, 0.0)
    if kept.sum() <= 0:
        raise DataError('El optimizador no produjo pesos significativos')
    return kept / kept.sum()


def infer(data: Path, artifact_path: Path) -> tuple[dict, dict, pd.DataFrame]:
    try:
        artifact = joblib.load(artifact_path)
    except Exception:
        raise DataError('No se pudo cargar el modelo; usa solo artefactos propios y de confianza') from None
    if not isinstance(artifact, dict) or artifact.get('schema') != 1 or tuple(artifact.get('features', ())) != FEATURES:
        raise DataError('Contrato de artefacto incompatible')
    if artifact['report']['sklearn_version'] != sklearn.__version__:
        raise DataError('Versión sklearn diferente; reinstala el entorno fijado o reentrena')
    bars = load_bars(data)
    if sorted(bars['symbol'].unique()) != artifact['symbols']:
        raise DataError('El universo debe coincidir exactamente con el usado al entrenar')
    panel = feature_panel(bars)
    latest = panel.loc[panel['date'] == panel['date'].max()].sort_values('symbol')
    as_of = latest['date'].iloc[0]
    if as_of < pd.Timestamp(artifact['trained_until']):
        raise DataError('La fecha de inferencia precede las etiquetas usadas al entrenar')
    prediction = artifact['estimator'].predict(latest.loc[:, FEATURES])
    if not np.isfinite(prediction).all():
        raise DataError('Predicción no finita')
    name = artifact['report']['selected']
    summary = AnalysisRequest(str(as_of.date()), name, artifact['horizon'], len(latest),
                              float(prediction.mean()), artifact['report']['validation'][name]['rmse'],
                              artifact['report']['metadata']['data_kind'])
    report = {'schema': 1, 'summary': asdict(summary), 'input_sha256': file_sha256(data),
              'artifact_sha256': file_sha256(artifact_path),
              'predictions': [{'symbol': s, 'predicted_return': float(p)}
                              for s, p in zip(latest['symbol'], prediction)],
              'research_status': 'NO ACCIONABLE / ventaja no demostrada',
              'upstream_version': '1.4.0', 'execution': 'none'}
    LOG.info('Inferencia as_of=%s model=%s symbols=%d artifact_sha256=%s mean_prediction=%.6f',
             summary.as_of, name, summary.symbols, report['artifact_sha256'][:12], summary.mean_prediction)
    return report, artifact, bars


def conviction(report: dict, artifact: dict, bars: pd.DataFrame, *, risk_aversion: float = 1,
               scenarios: int = 3000, seed: int = 0, mean_source: str = 'model') -> dict:
    if not math.isfinite(risk_aversion) or not 0 <= risk_aversion <= 10:
        raise DataError('risk_aversion debe estar entre 0 y 10')
    if not 100 <= scenarios <= 10000:
        raise DataError('scenarios debe estar entre 100 y 10000')
    as_of = pd.Timestamp(report['summary']['as_of'])
    oos = artifact['oos']
    # > No se usan etiquetas cuyo horizonte no esté cerrado al decidir.
    oos = oos.loc[oos['target_end'] <= as_of].copy()
    scores = pd.Series({r['symbol']: r['predicted_return'] for r in report['predictions']}).sort_index()
    prices = bars.pivot(index='date', columns='symbol', values='close').loc[:as_of, scores.index]
    cfg = ConvictionConfig(risk_aversion=risk_aversion, allow_cash=False,
                           n_scenarios=scenarios, min_weight=0, seed=seed)
    if mean_source == 'empirical':
        result = allocate(oos, scores, prices, artifact['horizon'], cfg)
        if result.weights.empty or not np.isclose(result.weights.sum(), 1, atol=1e-7):
            raise DataError('El optimizador no produjo una asignación completa')
        output = result.to_dict()
        output['weights'] = {s: float(w) for s, w in result.weights.items()}
    elif mean_source == 'model':
        # ~> Adaptación explícita: media del sklearn, dependencia/incertidumbre del banco v1.4.
        # El mapa empírico original queda plano en universos pequeños; se ofrece como alternativa.
        pct = (scores.rank(method='average') - .5) / len(scores)
        bank = _ScenarioBank(oos, pct, prices, artifact['horizon'], cfg, np.random.default_rng(seed))
        names = bank.symbols
        gross = bank.gross(range(len(names)))
        mu = scores.reindex(names).to_numpy()
        if (mu <= -1).any():
            raise DataError('La media predicha queda fuera del dominio de retornos brutos positivos')
        gross *= (1 + mu) / gross.mean(axis=0)
        sol = solve_simplex(gross, gamma=risk_aversion, tol=cfg.tol, max_iter=cfg.max_iter)
        weights = significant_weights(sol.weights)
        best_single = max(range(len(names)), key=lambda j: certainty_equivalent(gross[:, j], risk_aversion))
        output = {'weights': {s: float(w) for s, w in zip(names, weights) if w > 0},
                  'cash': 0.0, 'gap': float(sol.gap),
                  'certainty_equivalent': certainty_equivalent(gross @ weights, risk_aversion),
                  'alternatives': {'best_single_symbol': names[best_single],
                                   'best_single': certainty_equivalent(gross[:, best_single], risk_aversion),
                                   'equal_universe': certainty_equivalent(gross.mean(axis=1), risk_aversion)},
                  'table': [{'symbol': s, 'weight': float(w), 'mu': float(mu[j]),
                             'sd': float(gross[:, j].std()), 'p_success': float((gross[:, j] > 1.05).mean())}
                            for j, (s, w) in enumerate(zip(names, weights))],
                  'info': {**bank.info, 'n_candidates': len(names), 'n_scenarios': scenarios,
                           'risk_aversion': risk_aversion, 'converged': bool(sol.converged),
                           'iterations': sol.iterations, 'allow_cash': False,
                           'min_weight_reported': MIN_WEIGHT},
                  'notes': ['Las medias sklearn se usan como estimaciones, sin acreditar calibración. '
                            'El óptimo es condicional a estos escenarios, no a todos los futuros reales.'] + bank.notes}
    else:
        raise DataError('mean_source debe ser model o empirical')
    info = output.get('info', {})
    LOG.info('Convicción mean_source=%s risk_aversion=%g weights=%s converged=%s gap=%s',
             mean_source, risk_aversion, {s: round(w, 6) for s, w in output['weights'].items()},
             info.get('converged'), output.get('gap'))
    output.update(mode='conviction', evidence='ventaja no demostrada',
                  mean_source=mean_source,
                  calibration_source='validation seleccionada; no es auditoría independiente de cartera',
                  success_definition=f'retorno > 5% en {artifact["horizon"]} sesiones; probabilidad de escenarios no calibrada')
    return output


def run_pipeline(data: Path, artifact_path: Path, output: Path, client: AIClient, *,
                 decision: str = 'conviction', risk_aversion: float = 1, scenarios: int = 3000,
                 mean_source: str = 'model') -> dict:
    if Path(output).exists():
        raise DataError('El informe de salida ya existe; no se sobrescribe')
    report, artifact, bars = infer(data, artifact_path)
    if decision == 'conviction':
        report['allocation'] = conviction(report, artifact, bars, risk_aversion=risk_aversion,
                                          scenarios=scenarios, mean_source=mean_source)
    elif decision != 'research':
        raise DataError('decision debe ser conviction o research')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # > Se conserva la inferencia aunque falle el servicio explicativo.
    report['ai_status'] = 'pending'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    LOG.info('Informe provisional output=%s ai_status=pending', output.name)
    report['analysis'] = asdict(client.analyze(AnalysisRequest(**report['summary'])))
    report['ai_status'] = 'completed'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    LOG.info('Informe final output=%s ai_status=completed', output.name)
    return report
