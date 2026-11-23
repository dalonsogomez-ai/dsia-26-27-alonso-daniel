""">> Reglas financieras de validación, sin acceso a una API ni al reloj."""

import pandas as pd
import pytest

from acciones_app.validator import ValidationError, validate_bars, vwap_outside_range


def test_valid_bars_are_sorted_and_input_is_unchanged(bars_frame):
    original = bars_frame.copy(deep=True)
    valid, invalid = validate_bars(bars_frame.iloc[::-1])
    assert len(valid) == 6 and invalid.empty
    assert valid["symbol"].tolist() == ["AAA"] * 3 + ["BBB"] * 3
    assert str(valid["timestamp"].dt.tz) == "UTC"
    pd.testing.assert_frame_equal(bars_frame, original)


@pytest.mark.parametrize("column,value,reason", [
    ("symbol", None, "símbolo"), ("symbol", "!", "símbolo"),
    ("timestamp", "no-fecha", "fecha"), ("open", 0, "open"),
    ("close", -1, "close"), ("vwap", None, "vwap"),
    ("vwap", float("inf"), "vwap"), ("volume", -1, "volume"),
    ("volume", 1.5, "volume"), ("trade_count", "mal", "trade_count"),
    ("trade_count", float("inf"), "trade_count"), ("high", 1, "OHLC"),
    ("low", 101, "OHLC"),
])
def test_invalid_values_have_reason(bars_frame, column, value, reason):
    frame = bars_frame.iloc[:1].copy().astype({column: "object"})
    frame.loc[0, column] = value
    valid, invalid = validate_bars(frame)
    assert valid.empty and len(invalid) == 1
    assert reason in invalid.iloc[0]["motivo"]


@pytest.mark.parametrize("column,value", [
    ("timestamp", "no-fecha"), ("volume", "mal"), ("symbol", " a!a "), ("close", "-1"),
])
def test_invalid_rows_keep_original_values(bars_frame, column, value):
    frame = bars_frame.iloc[:2].copy().astype({column: "object"})
    frame.loc[1, column] = value
    valid, invalid = validate_bars(frame)
    assert len(valid) == 1 and len(invalid) == 1
    assert invalid.iloc[0][column] == value


@pytest.mark.parametrize("vwap,warned", [(500.0, True), (98.9, True), (99.0, False), (101.0, False), (100.0, False)])
def test_vwap_outside_range_only_warns(bars_frame, caplog, vwap, warned):
    frame = bars_frame.iloc[:1].copy()  # low = 99, high = 101
    frame.loc[0, "vwap"] = vwap
    with caplog.at_level("WARNING", logger="acciones_app.validator"):
        valid, invalid = validate_bars(frame)
    assert len(valid) == 1 and invalid.empty
    assert ("vwap fuera de [low, high]" in caplog.text) is warned
    assert vwap_outside_range(valid).tolist() == [warned]


def test_vwap_warning_ignores_rejected_bars(bars_frame, caplog):
    frame = bars_frame.iloc[:1].copy()
    frame.loc[0, ["vwap", "volume"]] = [500.0, -1]
    with caplog.at_level("WARNING", logger="acciones_app.validator"):
        valid, invalid = validate_bars(frame)
    assert valid.empty and len(invalid) == 1
    assert "vwap" not in caplog.text


def test_zero_counts_are_valid(bars_frame):
    frame = bars_frame.iloc[:1].copy()
    frame.loc[0, ["volume", "trade_count"]] = 0
    valid, invalid = validate_bars(frame)
    assert len(valid) == 1 and invalid.empty


def test_all_duplicate_members_are_rejected(bars_frame):
    # Arrange: se repite la primera barra (misma clave symbol/timestamp).
    frame = pd.concat([bars_frame, bars_frame.iloc[:1]], ignore_index=True)

    # Act
    valid, invalid = validate_bars(frame)

    # Assert: se rechazan las dos copias, no solo la segunda.
    assert len(valid) == 5 and len(invalid) == 2
    assert invalid["motivo"].str.contains("duplicados").all()


def test_distinct_invalid_dates_are_not_reported_as_duplicates(bars_frame):
    # Arrange: dos barras del mismo símbolo con fechas inválidas distintas (ambas quedan en NaT).
    frame = bars_frame.iloc[:2].copy().astype({"timestamp": "object"})
    frame.loc[0, "timestamp"] = "2026-02-30"
    frame.loc[1, "timestamp"] = "mal"

    # Act
    valid, invalid = validate_bars(frame)

    # Assert: el único motivo es la fecha; no son duplicados.
    assert valid.empty and len(invalid) == 2
    assert invalid["motivo"].tolist() == ["fecha inválida", "fecha inválida"]


def test_symbol_normalization(bars_frame):
    frame = bars_frame.iloc[:1].copy()
    frame.loc[0, "symbol"] = " aaa "
    valid, invalid = validate_bars(frame)
    assert valid.iloc[0]["symbol"] == "AAA" and invalid.empty


def test_missing_schema(bars_frame):
    with pytest.raises(ValidationError, match="volume"):
        validate_bars(bars_frame.drop(columns="volume"))


def test_empty_input_with_schema(bars_frame):
    valid, invalid = validate_bars(bars_frame.iloc[:0])
    assert valid.empty and invalid.empty and "motivo" in invalid
