""">> Generador de la muestra sintética de la Parte B: determinismo y filas sucias."""

from datetime import date
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from acciones_app.validator import validate_bars


PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "scripts" / "generar_muestra_acciones.py"


@pytest.fixture(scope="module")
def generator():
    """> Carga el script por ruta, sin depender de que `scripts/` sea un paquete."""
    spec = importlib.util.spec_from_file_location("generar_muestra_acciones", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_same_seed_produces_identical_bytes(tmp_path, generator):
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    assert generator.main(["--output", str(first)]) == 0
    assert generator.main(["--output", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()


def test_committed_sample_matches_generator(tmp_path, generator):
    regenerated = tmp_path / "muestra.csv"
    generator.main(["--output", str(regenerated)])
    assert regenerated.read_bytes() == (PROJECT / "data" / "sample" / "acciones_muestra.csv").read_bytes()


def test_different_seed_changes_prices(generator):
    assert generator.generate_bars(1) != generator.generate_bars(2)


def test_clean_bars_are_coherent_and_fictitious(generator):
    frame = pd.DataFrame(generator.generate_bars())
    assert len(frame) == 4 * generator.DEFAULT_SESSIONS
    assert set(frame["symbol"]) == set(generator.SYMBOLS)
    assert frame["symbol"].str.startswith("FICT.").all()
    valid, invalid = validate_bars(frame)
    assert len(valid) == len(frame) and invalid.empty
    assert valid["vwap"].between(valid["low"], valid["high"]).all()


def test_dirty_rows_are_injected_without_touching_input(generator):
    clean = generator.generate_bars(count=60)
    dirty = generator.inject_dirty_rows(clean)
    assert len(dirty) == len(clean) + 1
    assert clean == generator.generate_bars(count=60)
    _, invalid = validate_bars(pd.DataFrame(dirty))
    assert len(invalid) == 5


def test_sessions_skip_weekends(generator):
    days = generator.sessions(date(2026, 1, 2), 3)
    assert days == [date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)]


def test_too_few_sessions_is_rejected(generator):
    with pytest.raises(SystemExit) as stop:
        generator.parse_arguments(["--sessions", "50"])
    assert stop.value.code == 2
