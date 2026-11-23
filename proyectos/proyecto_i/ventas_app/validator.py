"""-> Reglas de validación de ventas."""

from __future__ import annotations

import pandas as pd


REQUIRED_COLUMNS = {"region", "producto", "unidades", "precio_unitario", "cliente_id"}
CATEGORICAL_COLUMNS = ("region", "producto", "cliente_id")
DATE_COLUMN = "fecha"
DATE_PATTERN = r"\d{4}-\d{2}-\d{2}"
MINIMUM_POSITIVE_VALUE = 0


class ValidationError(Exception):
    """-> Se lanza cuando la estructura de las ventas no permite validarlas."""


def validate_sales(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """> Separa ventas válidas e inválidas y calcula el importe de las válidas.

    Las válidas llevan `unidades` y `precio_unitario` numéricos e `importe`.
    Las inválidas conservan los valores originales de cada columna y añaden
    `motivo` con todas las reglas incumplidas, separadas por "; ".
    La columna `fecha` es opcional; si existe, debe seguir el formato YYYY-MM-DD.
    """
    missing_columns = REQUIRED_COLUMNS.difference(frame.columns)
    if missing_columns:
        missing_names = ", ".join(sorted(missing_columns))
        raise ValidationError(f"Faltan columnas obligatorias: {missing_names}")

    sales = frame.reset_index(drop=True)
    units = pd.to_numeric(sales["unidades"], errors="coerce").astype(float)
    prices = pd.to_numeric(sales["precio_unitario"], errors="coerce").astype(float)
    amounts = units * prices

    valid_units = _positive_finite(units) & units.mod(1).eq(0)
    valid_prices = _positive_finite(prices)
    checks = {
        "unidades inválidas": valid_units,
        "precio_unitario inválido": valid_prices,
    }
    for column in CATEGORICAL_COLUMNS:
        checks[f"{column} vacío"] = _non_blank(sales[column])
    if DATE_COLUMN in sales.columns:
        checks["fecha inválida"] = _iso_date(sales[DATE_COLUMN])
    # => El importe solo se señala cuando unidades y precio son válidos por separado.
    checks["importe inválido"] = _positive_finite(amounts) | ~(valid_units & valid_prices)

    results = pd.DataFrame(checks, index=sales.index).fillna(False).astype(bool)
    valid_mask = results.all(axis=1)

    valid_sales = sales.loc[valid_mask].copy()
    valid_sales["unidades"] = units.loc[valid_mask]
    valid_sales["precio_unitario"] = prices.loc[valid_mask]
    valid_sales["importe"] = amounts.loc[valid_mask]

    invalid_sales = sales.loc[~valid_mask].copy()
    invalid_sales["motivo"] = _reasons(results.loc[~valid_mask])
    return valid_sales.reset_index(drop=True), invalid_sales.reset_index(drop=True)


def _positive_finite(values: pd.Series) -> pd.Series:
    """> Marca los valores numéricos finitos y estrictamente positivos."""
    return values.gt(MINIMUM_POSITIVE_VALUE) & values.abs().lt(float("inf"))


def _non_blank(values: pd.Series) -> pd.Series:
    """> Marca los textos no nulos que no quedan vacíos tras quitar espacios."""
    return values.astype("string").str.strip().fillna("").ne("")


def _iso_date(values: pd.Series) -> pd.Series:
    """> Marca las fechas YYYY-MM-DD que además existen en el calendario."""
    text = values.astype("string")
    well_formed = text.str.fullmatch(DATE_PATTERN).fillna(False).astype(bool)
    parsed = pd.to_datetime(text.where(well_formed), format="%Y-%m-%d", errors="coerce")
    return well_formed & parsed.notna()


def _reasons(failed_checks: pd.DataFrame) -> pd.Series:
    """> Describe qué reglas incumple cada fila inválida."""
    reasons = [
        "; ".join(name for name, passed in row.items() if not passed)
        for _, row in failed_checks.iterrows()
    ]
    return pd.Series(reasons, index=failed_checks.index, dtype="object")
