"""-> Adaptador Alpaca paper: plan revisable, órdenes nocionales e informe persistente."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
import hashlib
import json
import math
import os
from pathlib import Path
import time

import pandas as pd


class PaperError(RuntimeError):
    """Error redactado en el borde del broker."""


def notionals(weights: dict[str, float], budget: str) -> dict[str, str]:
    """> Distribuir céntimos sin topes por posición y sin superar el presupuesto."""
    if not weights or any(not math.isfinite(float(w)) or w < 0 for w in weights.values()):
        raise PaperError('Pesos no válidos')
    if not math.isclose(sum(weights.values()), 1, abs_tol=1e-7):
        raise PaperError('Los pesos deben sumar uno')
    cash = Decimal(str(budget)).quantize(Decimal('.01'), rounding=ROUND_DOWN)
    if not cash.is_finite() or cash < 1:
        raise PaperError('Presupuesto inferior al mínimo nocional de 1 USD')
    amounts = {s: (cash * Decimal(str(w))).quantize(Decimal('.01'), rounding=ROUND_DOWN)
               for s, w in sorted(weights.items()) if w > 0}
    largest = max(amounts, key=lambda s: amounts[s])
    # > Reasignación técnica de importes inferiores al mínimo; visible en el plan.
    amounts = {s: value for s, value in amounts.items() if value >= 1}
    if not amounts:
        amounts = {largest: cash}
    else:
        amounts[largest] += cash - sum(amounts.values())
    return {s: str(value) for s, value in amounts.items()}


def _account_fingerprint(account) -> str:
    return hashlib.sha256(str(account.id).encode()).hexdigest()


class PaperBroker:
    """No acepta URL alternativa ni parámetro live; TradingClient siempre paper=True."""
    def __init__(self, client=None):
        if client is None:
            key = os.getenv('ALPACA_PAPER_API_KEY_ID', '').strip()
            secret = os.getenv('ALPACA_PAPER_API_SECRET_KEY', '').strip()
            if not key or not secret:
                raise PaperError('Faltan credenciales ALPACA_PAPER en el entorno')
            from alpaca.trading.client import TradingClient
            client = TradingClient(key, secret, paper=True)
        self.client = client

    def plan(self, report: dict, *, buffer_bps: float = 0) -> dict:
        if not math.isfinite(buffer_bps) or not 0 <= buffer_bps < 10000:
            raise PaperError('buffer_bps debe estar entre 0 y 10000')
        if report.get('summary', {}).get('data_kind') == 'synthetic':
            raise PaperError('Datos sintéticos no definen activos de broker')
        if report.get('allocation', {}).get('mode') != 'conviction':
            raise PaperError('El informe no contiene una asignación conviction')
        try:
            account = self.client.get_account()
            if account.trading_blocked or account.account_blocked:
                raise PaperError('Cuenta paper bloqueada por el broker')
            currency = str(getattr(account, 'currency', 'USD'))
            if currency != 'USD':
                raise PaperError('Este adaptador requiere cuenta USD')
            budget = min(Decimal(str(account.cash)), Decimal(str(account.buying_power)))
            budget *= 1 - Decimal(str(buffer_bps)) / 10000
            weights = report['allocation']['weights']
            amounts = notionals(weights, str(budget))
            for symbol in amounts:
                asset = self.client.get_asset(symbol)
                if not asset.tradable or not asset.fractionable:
                    raise PaperError('Un activo elegido no admite órdenes nocionales fraccionarias')
            clock = self.client.get_clock()
            return {'schema': 1, 'broker': 'alpaca-paper', 'account_fingerprint': _account_fingerprint(account),
                    'as_of': report['summary']['as_of'], 'weights': weights, 'notionals_usd': amounts,
                    'budget_usd': str(budget.quantize(Decimal('.01'), rounding=ROUND_DOWN)),
                    'buffer_bps': buffer_bps, 'clock': str(clock.timestamp),
                    'positions': len(self.client.get_all_positions()),
                    'model_sha256': report['artifact_sha256'], 'report_sha256': hashlib.sha256(
                        json.dumps(report, sort_keys=True).encode()).hexdigest(),
                    'rounding': 'Céntimos y órdenes inferiores a 1 USD se reasignan al mayor importe',
                    'status': 'plan_only', 'evidence': report['research_status']}
        except PaperError:
            raise
        except Exception:
            raise PaperError('No se pudo consultar Alpaca paper; comprueba conexión y permisos') from None

    def execute(self, plan: dict, journal: Path, *, liquidate: bool = False, wait_seconds: float = 30) -> dict:
        """> Opt-in separado. Ventas confirmadas antes de compras; nunca se presume un fill."""
        from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
        from alpaca.trading.requests import GetCalendarRequest, GetOrdersRequest, MarketOrderRequest
        journal = Path(journal)
        if journal.exists():
            raise PaperError('El journal ya existe: inspecciona las órdenes antes de reintentar')
        if plan.get('broker') != 'alpaca-paper' or plan.get('status') != 'plan_only':
            raise PaperError('Plan paper incompatible')
        state = {'status': 'started', 'broker': 'alpaca-paper', 'orders': [], 'liquidations': []}
        journal.parent.mkdir(parents=True, exist_ok=True)

        def save():
            journal.write_text(json.dumps(state, indent=2))

        save()
        try:
            account = self.client.get_account()
            if _account_fingerprint(account) != plan['account_fingerprint']:
                raise PaperError('El plan corresponde a otra cuenta paper')
            if account.trading_blocked or account.account_blocked:
                raise PaperError('Cuenta paper bloqueada por el broker')
            clock = self.client.get_clock()
            if not clock.is_open:
                raise PaperError('Mercado cerrado: el adaptador envía market/day durante sesión regular')
            now = pd.Timestamp(clock.timestamp)
            calendar = self.client.get_calendar(GetCalendarRequest(
                start=(now - timedelta(days=10)).date(), end=now.date()))
            closed = []
            for day in calendar:
                close = pd.Timestamp(day.close)
                close = close.tz_localize('America/New_York') if close.tzinfo is None else close
                if close.tz_convert('UTC') < now:
                    closed.append(day.date)
            if not closed or pd.Timestamp(plan['as_of']).date() != max(closed):
                raise PaperError('Informe histórico: se exige la última sesión cerrada del calendario del broker')
            if self.client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)):
                raise PaperError('Hay órdenes abiertas; reconcílialas antes de iniciar otra rotación')
            positions = self.client.get_all_positions()
            if positions and not liquidate:
                raise PaperError('Hay posiciones previas: requiere --liquidate para rotarlas')
            for position in positions:
                order = self.client.close_position(position.symbol)
                state['liquidations'].append({'symbol': position.symbol, 'id': str(order.id)})
                save()
            deadline = time.monotonic() + wait_seconds
            while positions:
                if time.monotonic() >= deadline:
                    raise PaperError('Ventas no confirmadas a tiempo; no se han enviado compras')
                positions = self.client.get_all_positions()
                if positions:
                    time.sleep(.25)
            # > Releer saldo tras liquidaciones: la liberación de efectivo no se presupone.
            account = self.client.get_account()
            budget = min(Decimal(str(account.cash)), Decimal(str(account.buying_power)))
            budget *= 1 - Decimal(str(plan['buffer_bps'])) / 10000
            amounts = notionals(plan['weights'], str(budget))
            # > Identidad del plan, independiente del nombre local del journal.
            # Reenviar el mismo plan conserva client_order_id y el broker rechaza duplicados.
            run_id = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:16]
            for i, (symbol, amount) in enumerate(amounts.items()):
                asset = self.client.get_asset(symbol)
                if not asset.tradable or not asset.fractionable:
                    raise PaperError('Activo no operable o no fraccionable al ejecutar')
                order_id = f'dsia-{run_id}-{i}'
                state['orders'].append({'symbol': symbol, 'notional': amount,
                                        'client_order_id': order_id, 'status': 'submitting'})
                save()
                order = self.client.submit_order(MarketOrderRequest(
                    symbol=symbol, notional=float(amount), side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY, client_order_id=order_id))
                state['orders'][-1].update(id=str(order.id), status=str(order.status))
                save()
            state['status'] = 'submitted_not_confirmed_filled'
            state['budget_usd'] = str(budget)
            save()
            return state
        except Exception as exc:
            state['status'] = 'stopped_reconcile_before_retry'
            save()
            if isinstance(exc, PaperError):
                raise
            raise PaperError('Alpaca paper falló; consulta el journal y reconcilia por client_order_id sin reenviar') from None
