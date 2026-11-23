from datetime import date, datetime
from decimal import Decimal
import json
from types import SimpleNamespace as NS

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

from swarmtrade_app._vendor.conviction import solve_simplex
from swarmtrade_app.paper import PaperBroker, PaperError, notionals


def test_log_optimum_can_be_all_in():
    gross = np.array([[1.10, 1.01, .99], [1.08, 1.02, 1.00]])
    solution = solve_simplex(gross)
    np.testing.assert_allclose(solution.weights, [1, 0, 0], atol=2e-5)
    assert solution.gap < 1e-6


def test_diversification_emerges_from_objective():
    gross = np.array([[1.5, .7], [.7, 1.5]])
    solution = solve_simplex(gross)
    np.testing.assert_allclose(solution.weights, [.5, .5], atol=1e-6)
    assert np.log(gross @ solution.weights).mean() > np.log(gross[:, 0]).mean()


def test_risk_neutral_selects_one_even_if_all_negative():
    solution = solve_simplex(np.array([[.95, .99], [.97, .98]]), gamma=0)
    np.testing.assert_array_equal(solution.weights, [0, 1])


def test_optimizer_matches_independent_scipy():
    gross = np.exp(np.random.default_rng(71).normal(.02, .2, (300, 5)))
    solution = solve_simplex(gross)
    reference = minimize(lambda w: -np.log(gross @ w).mean(), np.full(5, .2),
                         method='SLSQP', bounds=[(0, 1)] * 5,
                         constraints={'type': 'eq', 'fun': lambda w: w.sum() - 1},
                         options={'ftol': 1e-12, 'maxiter': 1000})
    assert reference.success
    assert solution.utility == pytest.approx(-reference.fun, abs=2e-7)
    assert solution.gap <= 1e-7


def test_full_cash_no_caps_rounding_and_minimum():
    assert notionals({'ONE': 1}, '1234.567') == {'ONE': '1234.56'}
    amounts = notionals({'A': .33333333, 'B': .66666667}, '100.01')
    assert sum(Decimal(v) for v in amounts.values()) == Decimal('100.01')
    assert notionals({'A': .9999, 'DUST': .0001}, '100') == {'A': '100.00'}


@pytest.mark.parametrize('weights,budget', [({'A': .5}, '100'), ({'A': -1, 'B': 2}, '100'),
                                           ({'A': float('nan')}, '100'), ({'A': 1}, '.99')])
def test_invalid_orders_rejected(weights, budget):
    with pytest.raises(PaperError):
        notionals(weights, budget)


class FakePaper:
    def __init__(self):
        self.positions = []
        self.open_orders = []
        self.submitted = []
        self.sold = []
        self.is_open = True
        self.fail_submission = False

    def get_account(self):
        return NS(id='fake-paper-only', cash='1000.00', buying_power='4000.00',
                  account_blocked=False, trading_blocked=False, currency='USD')

    def get_asset(self, symbol):
        return NS(tradable=True, fractionable=True)

    def get_clock(self):
        return NS(timestamp=pd.Timestamp('2026-11-12T16:00:00Z'), is_open=self.is_open)

    def get_all_positions(self):
        return self.positions

    def get_calendar(self, request):
        return [NS(date=date(2026, 11, 11), close=datetime(2026, 11, 11, 16)),
                NS(date=date(2026, 11, 12), close=datetime(2026, 11, 12, 16))]

    def get_orders(self, request):
        return self.open_orders

    def close_position(self, symbol):
        self.sold.append(symbol)
        self.positions = []
        return NS(id='sell-paper')

    def submit_order(self, request):
        self.submitted.append(request)
        if self.fail_submission:
            raise RuntimeError('secret-server-body')
        return NS(id='buy-paper', status='accepted')


@pytest.fixture
def broker_report():
    return {'summary': {'as_of': '2026-11-11', 'data_kind': 'local'},
            'allocation': {'mode': 'conviction', 'weights': {'ONE': 1.0}},
            'artifact_sha256': 'fixture', 'research_status': 'ventaja no demostrada'}


@pytest.mark.integration
def test_paper_all_in_is_cash_funded_and_no_implicit_execution(broker_report, tmp_path):
    fake = FakePaper()
    broker = PaperBroker(fake)
    plan = broker.plan(broker_report)
    assert plan['notionals_usd'] == {'ONE': '1000.00'}
    assert not fake.submitted
    result = broker.execute(plan, tmp_path / 'journal.json')
    assert fake.submitted[0].notional == 1000
    assert fake.submitted[0].qty is None
    assert result['status'] == 'submitted_not_confirmed_filled'
    with pytest.raises(PaperError, match='journal ya existe'):
        broker.execute(plan, tmp_path / 'journal.json')
    assert len(fake.submitted) == 1


def test_rotation_sells_before_buying(broker_report, tmp_path):
    fake = FakePaper()
    fake.positions = [NS(symbol='OLD')]
    broker = PaperBroker(fake)
    plan = broker.plan(broker_report)
    with pytest.raises(PaperError, match='liquidate'):
        broker.execute(plan, tmp_path / 'refused.json')
    broker.execute(plan, tmp_path / 'rotation.json', liquidate=True)
    assert fake.sold == ['OLD'] and len(fake.submitted) == 1


@pytest.mark.parametrize('problem', ['closed', 'stale', 'pending', 'other_account'])
def test_execution_preconditions(broker_report, tmp_path, problem):
    fake = FakePaper()
    broker = PaperBroker(fake)
    plan = broker.plan(broker_report)
    if problem == 'closed': fake.is_open = False
    if problem == 'stale': plan['as_of'] = '2020-01-01'
    if problem == 'pending': fake.open_orders = [object()]
    if problem == 'other_account': plan['account_fingerprint'] = 'other'
    with pytest.raises(PaperError):
        broker.execute(plan, tmp_path / 'journal.json')
    assert not fake.submitted


def test_ambiguous_broker_failure_is_redacted_and_journalled(broker_report, tmp_path):
    fake = FakePaper()
    fake.fail_submission = True
    broker = PaperBroker(fake)
    journal = tmp_path / 'ambiguous.json'
    with pytest.raises(PaperError) as error:
        broker.execute(broker.plan(broker_report), journal)
    assert 'secret' not in str(error.value)
    assert json.loads(journal.read_text())['orders'][0]['status'] == 'submitting'
    assert json.loads(journal.read_text())['status'] == 'stopped_reconcile_before_retry'


def test_broker_constructor_is_paper_only(monkeypatch):
    import alpaca.trading.client
    called = {}
    monkeypatch.setenv('ALPACA_PAPER_API_KEY_ID', 'fixture-key')
    monkeypatch.setenv('ALPACA_PAPER_API_SECRET_KEY', 'fixture-secret')
    def factory(key, secret, **kwargs):
        called.update(kwargs)
        return FakePaper()
    monkeypatch.setattr(alpaca.trading.client, 'TradingClient', factory)
    PaperBroker()
    assert called == {'paper': True}
