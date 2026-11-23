import hashlib
import json
import math

import pandas as pd
import pytest

from dsia_web.build import summarize_inputs
from dsia_web.snapshot import Snapshot, read_snapshot


def test_summarize_inputs_exact_values_and_short_histories():
    growth = [100 * 1.01 ** k for k in range(30)]
    bars = pd.DataFrame({
        "date": list(pd.bdate_range("2026-01-01", periods=30)) + list(pd.bdate_range("2026-01-01", periods=10))
        + [pd.Timestamp("2026-01-01")],
        "symbol": ["BBB"] * 30 + ["AAA"] * 10 + ["CCC"],
        "close": growth + [10.0, 11.0, 12.1, 11.0, 12.0, 13.0, 12.0, 14.0, 15.0, 16.0] + [5.0],
    }).sample(frac=1, random_state=3)
    rows = {row.symbol: row for row in summarize_inputs(bars)}
    assert list(rows) == ["AAA", "BBB", "CCC"]
    assert rows["BBB"].sessions == 30
    assert rows["BBB"].last_close == pytest.approx(100 * 1.01 ** 29)
    assert rows["BBB"].return_21_sessions == pytest.approx(1.01 ** 21 - 1)
    assert rows["BBB"].volatility_annualized == pytest.approx(0.0, abs=1e-12)
    assert (rows["AAA"].sessions, rows["AAA"].last_close, rows["AAA"].return_21_sessions) == (10, 16.0, None)
    daily = [11 / 10 - 1, 12.1 / 11 - 1, 11 / 12.1 - 1, 12 / 11 - 1, 13 / 12 - 1, 12 / 13 - 1,
             14 / 12 - 1, 15 / 14 - 1, 16 / 15 - 1]
    mean = sum(daily) / len(daily)
    std = math.sqrt(sum((value - mean) ** 2 for value in daily) / (len(daily) - 1))
    assert rows["AAA"].volatility_annualized == pytest.approx(std * math.sqrt(252))
    assert rows["CCC"].model_dump() == {"symbol": "CCC", "sessions": 1, "last_close": 5.0,
                                        "return_21_sessions": None, "volatility_annualized": None}


def test_volatility_uses_only_the_last_63_daily_returns():
    closes = [100.0, 50.0] + [100 * 1.01 ** k for k in range(64)]
    bars = pd.DataFrame({"date": pd.bdate_range("2026-01-01", periods=len(closes)),
                         "symbol": "AAA", "close": closes})
    assert summarize_inputs(bars)[0].volatility_annualized == pytest.approx(0.0, abs=1e-12)


def test_demo_snapshot_summarizes_every_predicted_symbol(demo_run):
    snapshot = demo_run.snapshot
    assert [row.symbol for row in snapshot.input_summary] == sorted(p.symbol for p in snapshot.predictions)
    assert {row.sessions for row in snapshot.input_summary} == {680}
    bars = pd.read_csv(demo_run.bars)
    first = snapshot.input_summary[0]
    closes = bars.loc[bars["symbol"] == first.symbol].sort_values("date")["close"].to_list()
    assert first.last_close == pytest.approx(closes[-1])
    assert first.return_21_sessions == pytest.approx(closes[-1] / closes[-22] - 1)
    assert "input_summary" in Snapshot.model_json_schema()["properties"]


def test_snapshot_published_before_input_summary_still_validates(demo_run, tmp_path):
    document = json.loads(demo_run.path.read_text())
    del document["input_summary"]
    body = {key: value for key, value in document.items() if key != "run_id"}
    raw = json.dumps(body, sort_keys=True, allow_nan=False, separators=(",", ":"))
    document["run_id"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps(document))
    snapshot = read_snapshot(legacy)
    assert snapshot.input_summary is None
    assert snapshot.run_id == document["run_id"]


def test_input_summary_must_cover_exactly_the_predicted_symbols(demo_run):
    document = json.loads(demo_run.path.read_text())
    document["input_summary"] = document["input_summary"][1:]
    with pytest.raises(ValueError, match="resumen de entrada"):
        Snapshot.model_validate(document)
