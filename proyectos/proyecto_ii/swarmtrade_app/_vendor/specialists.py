"""~> Cinco especialistas de SwarmTrader; procedencia en THIRD_PARTY.md."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Specialist:
    """Un agente: un nombre, una tesis, un subconjunto de factores."""
    name: str
    factors: tuple[str, ...]
    thesis: str
    reference: str
    requires_external: bool = False
    kind: str = 'linear'
    requires_torch: bool = False

    def available(self, columns: list[str]) -> tuple[str, ...]:
        if self.factors == ('__all__',):
            return tuple(columns)
        return tuple((f for f in self.factors if f in columns))

DEFAULT_ROSTER: tuple[Specialist, ...] = (Specialist(name='momentum', factors=('mom_12_1', 'mom_6_1', 'accel', 'dist_52w_high'), thesis='los ganadores de 12 meses siguen ganando durante 1-3 meses; la cercania al maximo de 52 semanas captura el anclaje de los inversores', reference='Jegadeesh-Titman 1993; George-Hwang 2004'), Specialist(name='reversal', factors=('reversal_21', 'reversal_5', 'idio_skew_63'), thesis='el movimiento extremo de corto plazo revierte por presion de liquidez; la asimetria idiosincratica positiva se paga de mas', reference='Jegadeesh 1990; Boyer-Mitton-Vorkink 2010'), Specialist(name='lowrisk', factors=('low_vol_60', 'low_beta_60', 'anti_lottery'), thesis='beta y volatilidad altas rinden menos de lo que predice el CAPM; las acciones tipo loteria tienen retorno esperado negativo', reference='Frazzini-Pedersen 2014; Bali-Cakici-Whitelaw 2011'), Specialist(name='liquidity', factors=('illiq_amihud', 'vol_trend', 'vol_price_div'), thesis='prima por iliquidez y confirmacion por volumen: un movimiento sin volumen detras es menos persistente', reference='Amihud 2002'), Specialist(name='seasonal', factors=('seasonal_12m',), thesis='los retornos del mismo mes del calendario reaparecen por patrones recurrentes de flujo institucional', reference='Heston-Sadka 2008'))
