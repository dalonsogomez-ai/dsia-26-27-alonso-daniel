from pathlib import Path
import json
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from ml_pipeline import guard
from swarmtrade_app.ai_client import AIClient, AIClientError
from swarmtrade_app.data import DataError, FEATURES, feature_panel, labelled_panel, load_bars
from swarmtrade_app.pipeline import conviction, infer, run_pipeline
from swarmtrade_app.preparation import prepare
from swarmtrade_app.training import evaluate_holdout, train_prepared


@pytest.fixture
def trained(bars_file, tmp_path):
    run = tmp_path / 'run'
    prepared = prepare(bars_file, run, data_kind='synthetic')
    report = train_prepared(run)
    return bars_file, run, prepared, report


def test_causal_factors_do_not_see_future(bars):
    original = feature_panel(bars)
    boundary = bars['date'].drop_duplicates().iloc[400]
    changed = bars.copy()
    changed.loc[changed['date'] > boundary, 'close'] *= 3
    changed.loc[changed['date'] > boundary, 'volume'] *= 7
    updated = feature_panel(changed)
    pd.testing.assert_frame_equal(original.loc[original['date'] <= boundary],
                                  updated.loc[updated['date'] <= boundary])


def test_target_is_exact_forward_return(bars):
    panel = labelled_panel(bars)
    row = panel.iloc[3]
    prices = bars.set_index(['date', 'symbol'])['close']
    assert row['target'] == pytest.approx(prices.loc[(row.target_end, row.symbol)] /
                                         prices.loc[(row.date, row.symbol)] - 1)


def test_incomplete_panel_rejected(bars):
    with pytest.raises(DataError, match='Panel incompleto'):
        feature_panel(bars.iloc[1:])


def test_purged_whole_date_split_and_train_only_scaler(trained):
    _, run, p, _ = trained
    assert p.train['target_end'].max() < p.validation['date'].min()
    assert p.validation['target_end'].max() < p.holdout['date'].min()
    assert not set(p.train.date) & set(p.validation.date)
    assert not set(p.validation.date) & set(p.holdout.date)
    assert all(f.groupby('date').size().eq(6).all() for f in (p.train, p.validation, p.holdout))
    state = json.loads((run / '.guard_state.json').read_text())
    assert state['test_touches'] == 0
    from swarmtrade_app.models import SwarmRegressor
    swarm = SwarmRegressor().fit(p.train.loc[:, FEATURES], p.train.target)
    for columns, model in swarm.models_.values():
        np.testing.assert_allclose(model[0].mean_, p.train[columns].mean().to_numpy(), atol=1e-12)


@pytest.mark.integration
def test_load_inference_mock_and_conviction(trained, tmp_path):
    data, run, _, report = trained
    output = tmp_path / 'inference.json'
    result = run_pipeline(data, run / 'model.joblib', output, AIClient(), scenarios=100)
    assert result['analysis']['provider'] == 'mock'
    assert result['summary']['model'] == report['selected']
    assert len(result['predictions']) == 6
    assert sum(result['allocation']['weights'].values()) == pytest.approx(1)
    assert result['allocation']['info']['n_candidates'] == 6
    assert result['allocation']['evidence'] == 'ventaja no demostrada'
    assert result['execution'] == 'none'
    assert json.loads(output.read_text())['ai_status'] == 'completed'
    with pytest.raises(DataError, match='no se sobrescribe'):
        run_pipeline(data, run / 'model.joblib', output, AIClient())


def test_test_set_frozen_and_only_once(trained):
    _, run, p, report = trained
    altered = p.holdout.copy()
    altered.loc[0, 'target'] += .1
    with pytest.raises(guard.TestSetTampered):
        guard.final_test(lambda f: np.zeros(len(f)), altered, target='target',
                         metric_fn=lambda a, b: 0, state_dir=run, pipeline_md=run / 'PIPELINE.md')
    result = evaluate_holdout(run)
    assert result['touches'] == 1 and result['selected'] == report['selected']
    with pytest.raises(guard.TestSetAlreadyUsed):
        evaluate_holdout(run)


def test_model_roundtrip_and_schema(trained, tmp_path):
    data, run, p, _ = trained
    artifact = joblib.load(run / 'model.joblib')
    before = artifact['estimator'].predict(p.validation.loc[:, FEATURES])
    copy = tmp_path / 'copy.joblib'
    joblib.dump(artifact, copy)
    np.testing.assert_array_equal(before, joblib.load(copy)['estimator'].predict(p.validation.loc[:, FEATURES]))
    artifact['features'] = ('target',)
    joblib.dump(artifact, copy)
    with pytest.raises(DataError, match='incompatible'):
        infer(data, copy)


def test_universe_and_past_prediction_rejected(trained, tmp_path):
    data, run, _, _ = trained
    bars = load_bars(data)
    small = tmp_path / 'small.csv'
    bars.loc[bars.symbol != bars.symbol.iloc[0]].to_csv(small, index=False)
    with pytest.raises(DataError, match='universo'):
        infer(small, run / 'model.joblib')
    artifact = joblib.load(run / 'model.joblib')
    artifact['trained_until'] = '2099-01-01'
    future = tmp_path / 'future.joblib'
    joblib.dump(artifact, future)
    with pytest.raises(DataError, match='precede'):
        infer(data, future)


def test_hf_failure_preserves_predictions(trained, tmp_path, monkeypatch):
    data, run, _, _ = trained
    monkeypatch.delenv('HF_TOKEN', raising=False)
    output = tmp_path / 'failed.json'
    with pytest.raises(AIClientError, match='HF_TOKEN'):
        run_pipeline(data, run / 'model.joblib', output, AIClient('hf'), decision='research')
    assert json.loads(output.read_text())['predictions']
    assert json.loads(output.read_text())['ai_status'] == 'pending'


@pytest.mark.integration
def test_prepare_module_artifact_reload(bars_file, tmp_path):
    run = tmp_path / 'module-run'
    result = subprocess.run([sys.executable, '-m', 'swarmtrade_app.preparation', '--data', str(bars_file),
                             '--run', str(run)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert isinstance(joblib.load(run / 'prepared.joblib'), dict)
    train_prepared(run)
    infer(bars_file, run / 'model.joblib')


def test_run_not_overwritten(trained):
    data, run, _, _ = trained
    with pytest.raises(DataError, match='ya existe'):
        prepare(data, run)
    with pytest.raises(DataError, match='ya está entrenado'):
        train_prepared(run)


def test_conviction_risk_neutral_uses_model_argmax(trained):
    data, run, _, _ = trained
    report, artifact, bars = infer(data, run / 'model.joblib')
    result = conviction(report, artifact, bars, risk_aversion=0, scenarios=100)
    best = max(report['predictions'], key=lambda r: r['predicted_return'])['symbol']
    assert result['weights'] == {best: 1.0}
    assert result['info']['converged']
    for row in result['table']:
        expected = next(r['predicted_return'] for r in report['predictions'] if r['symbol'] == row['symbol'])
        assert row['mu'] == pytest.approx(expected)


def test_empirical_mode_keeps_upstream_small_universe_diagnostic(trained):
    data, run, _, _ = trained
    report, artifact, bars = infer(data, run / 'model.joblib')
    result = conviction(report, artifact, bars, scenarios=100, mean_source='empirical')
    assert result['info']['map_bins'] == 0
    assert result['mean_source'] == 'empirical'
    assert sum(result['weights'].values()) == pytest.approx(1)


@pytest.mark.integration
def test_cli_training_inference_and_evaluation(bars_file, tmp_path, capsys):
    from swarmtrade_app.cli import main
    run = tmp_path / 'cli-run'
    assert main(['train', '--data', str(bars_file), '--run', str(run), '--data-kind', 'synthetic']) == 0
    assert main(['evaluate', '--run', str(run)]) == 0
    assert main(['run', '--data', str(bars_file), '--artifact', str(run / 'model.joblib'),
                 '--output', str(run / 'report.json'), '--scenarios', '100', '--provider', 'mock']) == 0
    assert json.loads((run / 'report.json').read_text())['summary']['data_kind'] == 'synthetic'
