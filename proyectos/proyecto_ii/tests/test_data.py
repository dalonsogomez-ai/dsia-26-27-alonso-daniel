import pandas as pd
import pytest

from swarmtrade_app.data import DataError, file_sha256, generate_demo, load_bars


def test_demo_is_reproducible_and_wont_overwrite(tmp_path):
    a = generate_demo(tmp_path / 'a.csv', sessions=450, symbols=5)
    b = generate_demo(tmp_path / 'b.csv', sessions=450, symbols=5)
    assert file_sha256(a) == file_sha256(b)
    with pytest.raises(DataError, match='existe'):
        generate_demo(a)


def test_load_timestamp_alias(bars_file):
    frame = pd.read_csv(bars_file).rename(columns={'date': 'timestamp'})
    frame.to_csv(bars_file, index=False)
    result = load_bars(bars_file)
    assert result['date'].dtype.kind == 'M'
    assert len(result) == 3000


@pytest.mark.parametrize('column,value', [('close', -1), ('close', float('inf')),
                                        ('volume', -2), ('symbol', ''), ('date', 'no-date')])
def test_reject_invalid_values(bars_file, column, value):
    frame = pd.read_csv(bars_file)
    frame.loc[0, column] = value
    frame.to_csv(bars_file, index=False)
    with pytest.raises(DataError):
        load_bars(bars_file)


def test_reject_duplicate_day(bars_file):
    frame = pd.read_csv(bars_file)
    pd.concat([frame, frame.iloc[:1]]).to_csv(bars_file, index=False)
    with pytest.raises(DataError, match='duplicadas'):
        load_bars(bars_file)


def test_reject_missing_columns(tmp_path):
    path = tmp_path / 'bad.csv'
    pd.DataFrame({'close': [1]}).to_csv(path, index=False)
    with pytest.raises(DataError, match='columnas'):
        load_bars(path)


def test_reject_small_universe(bars_file):
    frame = pd.read_csv(bars_file)
    frame[frame.symbol == frame.symbol.iloc[0]].to_csv(bars_file, index=False)
    with pytest.raises(DataError, match='cinco'):
        load_bars(bars_file)


def test_reject_ohlc_mismatch(bars_file):
    frame = pd.read_csv(bars_file).assign(open=1, high=2, low=1)
    frame.to_csv(bars_file, index=False)
    with pytest.raises(DataError, match='OHLC'):
        load_bars(bars_file)
