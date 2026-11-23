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


@pytest.mark.integration
def test_cli_inspect_writes_profile_and_summary(bars_file, tmp_path, capsys):
    import json
    from swarmtrade_app.cli import main
    output = tmp_path / 'inspection'
    assert main(['inspect', '--data', str(bars_file), '--output', str(output)]) == 0
    summary = json.loads((output / 'inspection_summary.json').read_text())
    profile = json.loads((output / 'data_profile.json').read_text())
    assert summary['raw_rows'] == 3000 and summary['symbols'] == 6 and summary['dates'] == 500
    assert summary['duplicate_keys'] == 0 and summary['horizon'] == 21
    # > Las 21 últimas sesiones de cada símbolo no tienen target observado.
    assert summary['labelled_rows'] == 3000 - 21 * 6
    assert summary['sha256'] == file_sha256(bars_file)
    assert 'return_21_sessions' in json.dumps(profile)
    assert json.loads(capsys.readouterr().out)['source_file'] == 'bars.csv'


def test_inspect_requires_symbol_and_close(tmp_path):
    from swarmtrade_app.inspection import inspect_dataset
    path = tmp_path / 'bad.csv'
    pd.DataFrame({'date': ['2026-01-02'], 'close': [1.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match='symbol y close'):
        inspect_dataset(path, tmp_path / 'out')


def test_cli_inspect_requires_explicit_output(bars_file):
    from swarmtrade_app.cli import main
    with pytest.raises(SystemExit):
        main(['inspect', '--data', str(bars_file)])


def test_reject_ohlc_mismatch(bars_file):
    frame = pd.read_csv(bars_file).assign(open=1, high=2, low=1)
    frame.to_csv(bars_file, index=False)
    with pytest.raises(DataError, match='OHLC'):
        load_bars(bars_file)


def test_demo_prices_have_fixed_precision_for_cross_platform_bytes(tmp_path):
    # Arrange/Act: np.exp puede diferir en el último ULP entre arquitecturas (SIMD de x86 y ARM).
    path = generate_demo(tmp_path / "demo.csv", sessions=450, symbols=5, seed=42)
    closes = pd.read_csv(path, dtype={"close": str})["close"]
    # Assert: con 6 decimales como máximo el CSV es idéntico byte a byte en macOS y Linux.
    assert closes.str.split(".").str[1].str.len().max() <= 6
