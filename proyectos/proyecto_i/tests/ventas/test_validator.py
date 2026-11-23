""">> Validación, bordes y checkpoint del CSV del curso."""

from pathlib import Path

import pandas as pd
import pytest

from ventas_app.loader import load
from ventas_app.validator import ValidationError, validate_sales


def test_valid_invalid_amount_and_no_mutation(sales_frame):
    original = sales_frame.copy(deep=True)
    valid, invalid = validate_sales(sales_frame)
    assert len(valid) == 2
    assert len(invalid) == 1
    assert valid["importe"].tolist() == [20.0, 30.0]
    assert "unidades" in invalid.iloc[0]["motivo"]
    pd.testing.assert_frame_equal(sales_frame, original)


@pytest.mark.parametrize("column", ["unidades", "precio_unitario"])
@pytest.mark.parametrize("value, expected", [(0, 0), (-1, 0), (None, 0), ("mal", 0), (float("inf"), 0), (-float("inf"), 0), (1, 1)])
def test_numeric_boundaries(sales_frame, column, value, expected):
    frame = sales_frame.iloc[:1].copy().astype({column: "object"})
    frame.loc[0, column] = value
    valid, invalid = validate_sales(frame)
    assert len(valid) == expected
    assert len(invalid) == 1 - expected
    if not expected:
        assert column in invalid.iloc[0]["motivo"]


@pytest.mark.parametrize("units, price, reason", [
    (1e308, 1e308, "importe inválido"),
    # => Con unidades enteras el subdesbordamiento del importe ya no es alcanzable:
    # 1e-300 unidades se rechaza antes por no ser un número entero.
    (1e-300, 1e-300, "unidades inválidas"),
])
def test_unrepresentable_amount_is_rejected(sales_frame, units, price, reason):
    frame = sales_frame.iloc[:1].copy().astype({"unidades": float, "precio_unitario": float})
    frame.loc[0, ["unidades", "precio_unitario"]] = [units, price]
    valid, invalid = validate_sales(frame)
    assert valid.empty
    assert invalid.iloc[0]["motivo"] == reason


@pytest.mark.parametrize("value, expected", [(1.5, 0), (0.999, 0), ("2.5", 0), (2.0, 1), ("3", 1)])
def test_units_must_be_whole_numbers(sales_frame, value, expected):
    frame = sales_frame.iloc[:1].copy().astype({"unidades": "object"})
    frame.loc[0, "unidades"] = value
    valid, invalid = validate_sales(frame)
    assert len(valid) == expected
    if not expected:
        assert invalid.iloc[0]["motivo"] == "unidades inválidas"


@pytest.mark.parametrize("column", ["region", "producto", "cliente_id"])
@pytest.mark.parametrize("value, expected", [(None, 0), ("", 0), ("   ", 0), ("\t", 0), (" X ", 1)])
def test_categorical_columns_must_not_be_blank(sales_frame, column, value, expected):
    frame = sales_frame.iloc[:1].copy().astype({column: "object"})
    frame.loc[0, column] = value
    valid, invalid = validate_sales(frame)
    assert len(valid) == expected
    if not expected:
        assert invalid.iloc[0]["motivo"] == f"{column} vacío"


@pytest.mark.parametrize("value, expected", [
    ("2026-01-09", 1), ("2024-02-29", 1), ("2026-02-30", 0), ("2026-13-01", 0),
    ("2026-1-9", 0), ("09/01/2026", 0), ("", 0), (None, 0), ("2026-01-09T10:00", 0),
])
def test_optional_date_must_be_iso(sales_frame, value, expected):
    frame = sales_frame.iloc[:1].copy()
    frame.insert(0, "fecha", pd.Series([value], dtype="object"))
    valid, invalid = validate_sales(frame)
    assert len(valid) == expected
    if not expected:
        assert invalid.iloc[0]["motivo"] == "fecha inválida"


def test_invalid_rows_keep_original_values_and_all_reasons(sales_frame):
    frame = sales_frame.astype({"unidades": "object"})
    frame.loc[1, ["unidades", "region"]] = ["na", " "]
    valid, invalid = validate_sales(frame)
    assert len(valid) == 2
    assert invalid.iloc[0]["unidades"] == "na"
    assert invalid.iloc[0]["region"] == " "
    assert invalid.iloc[0]["motivo"] == "unidades inválidas; region vacío"


def test_missing_columns(sales_frame):
    with pytest.raises(ValidationError, match="cliente_id"):
        validate_sales(sales_frame.drop(columns="cliente_id"))


def test_empty_input_with_schema(sales_frame):
    valid, invalid = validate_sales(sales_frame.iloc[:0])
    assert valid.empty and invalid.empty
    assert "importe" in valid and "motivo" in invalid


@pytest.mark.integration
def test_course_csv_has_140_valid_and_10_invalid():
    source = Path(__file__).resolve().parents[2] / "data" / "ventas.csv"
    valid, invalid = validate_sales(load(source))
    assert len(valid) == 140
    assert len(invalid) == 10
    # >> La fila con unidades='na' conserva su valor original en los rechazos.
    assert invalid["unidades"].isin(["na"]).sum() == 1
