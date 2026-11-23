""">> Modo Alpaca del lote: descarga simulada (sin red), panel común y snapshot sin precios."""

import json
from datetime import date

import pandas as pd
import pytest
from swarmtrade_app.data import DataError, generate_demo

from dsia_web import alpaca_source
from dsia_web.alpaca_source import (AlpacaCredentials, fetch_daily_bars, load_credentials,
                                    parse_symbols)
from dsia_web.build import main

SYMBOLS = ("AAPL", "MSFT", "NVDA", "JPM", "XOM")
CREDENTIALS = AlpacaCredentials("clave-falsa", "secreto-falso")


class FakeResponse:
    def __init__(self, frame):
        self.df = frame


class FakeClient:
    """Doble de StockHistoricalDataClient: devuelve barras con el índice (symbol, timestamp) del SDK."""

    def __init__(self, frame, fail_feeds=()):
        self.frame, self.fail_feeds, self.feeds = frame, set(fail_feeds), []

    def get_stock_bars(self, request):
        self.feeds.append(request.feed.value)
        if request.feed.value in self.fail_feeds:
            raise PermissionError("subscription does not permit querying recent SIP data")
        return FakeResponse(self.frame)


def sdk_frame(tmp_path, symbols=SYMBOLS, sessions=680):
    """Barras sintéticas con nombres reales, en el formato que devuelve alpaca-py."""
    demo = pd.read_csv(generate_demo(tmp_path / "base.csv", sessions=sessions, symbols=len(symbols), seed=7))
    names = dict(zip(sorted(demo["symbol"].unique()), symbols))
    frame = pd.DataFrame({
        "symbol": demo["symbol"].map(names),
        "timestamp": pd.to_datetime(demo["date"]).dt.tz_localize("America/New_York").dt.tz_convert("UTC"),
        "open": demo["close"], "high": demo["close"], "low": demo["close"], "close": demo["close"],
        "volume": demo["volume"].astype(float), "trade_count": 1.0, "vwap": demo["close"],
    })
    return frame.set_index(["symbol", "timestamp"])


def test_credentials_come_from_environment_or_secret_file_and_never_print(tmp_path):
    # Arrange
    secret = tmp_path / "alpaca.env"
    secret.write_text("ALPACA_PAPER_API_KEY_ID=desde-fichero\nALPACA_PAPER_API_SECRET_KEY=s3creto\n")
    # Act
    from_file = load_credentials(secret, environ={})
    from_env = load_credentials(secret, environ={"ALPACA_PAPER_API_KEY_ID": "env",
                                                 "ALPACA_PAPER_API_SECRET_KEY": "env-s"})
    # Assert: el entorno tiene prioridad, un par incompleto no cuenta y repr no filtra nada.
    assert (from_file.key, from_file.secret) == ("desde-fichero", "s3creto")
    assert (from_env.key, from_env.secret) == ("env", "env-s")
    assert load_credentials(None, environ={"ALPACA_PAPER_API_KEY_ID": "solo-clave"}) is None
    assert load_credentials(tmp_path / "no-existe.env", environ={}) is None
    assert "s3creto" not in repr(from_file) and "desde-fichero" not in repr(from_file)


@pytest.mark.parametrize("raw,expected", [
    (None, alpaca_source.DEFAULT_SYMBOLS), ("", alpaca_source.DEFAULT_SYMBOLS),
    (" aapl, MSFT ,aapl,", ("AAPL", "MSFT")),
])
def test_parse_symbols(raw, expected):
    assert parse_symbols(raw) == expected


def test_fetch_writes_common_panel_with_close_and_volume_only(tmp_path):
    # Arrange: a NVDA le falta una sesión, que debe desaparecer para todos.
    frame = sdk_frame(tmp_path)
    gap = frame.index[(frame.index.get_level_values("symbol") == "NVDA")][100]
    client = FakeClient(frame.drop(index=gap))
    # Act
    details = fetch_daily_bars(tmp_path / "bars.csv", CREDENTIALS, symbols=SYMBOLS,
                               today=date(2026, 11, 23), client_factory=lambda creds: client)
    bars = pd.read_csv(tmp_path / "bars.csv")
    # Assert
    assert list(bars.columns) == ["date", "symbol", "close", "volume"]
    assert bars.groupby("date")["symbol"].nunique().eq(len(SYMBOLS)).all()
    assert details["dropped_dates"] == 1 and details["dates"] == 679 and details["feed"] == "sip"
    assert details["rows"] == len(bars) and details["symbols"] == len(SYMBOLS)


def test_sip_rejection_falls_back_to_iex(tmp_path):
    client = FakeClient(sdk_frame(tmp_path), fail_feeds={"sip"})
    details = fetch_daily_bars(tmp_path / "bars.csv", CREDENTIALS, symbols=SYMBOLS,
                               client_factory=lambda creds: client)
    assert client.feeds == ["sip", "iex"] and details["feed"] == "iex"


def test_download_errors_are_domain_errors_without_the_response(tmp_path):
    client = FakeClient(sdk_frame(tmp_path), fail_feeds={"sip", "iex"})
    with pytest.raises(DataError, match=r"^No se pudieron descargar las barras de Alpaca \(PermissionError\)$"):
        fetch_daily_bars(tmp_path / "bars.csv", CREDENTIALS, symbols=SYMBOLS,
                         client_factory=lambda creds: client)


def test_missing_symbol_is_reported(tmp_path):
    frame = sdk_frame(tmp_path)
    client = FakeClient(frame[frame.index.get_level_values("symbol") != "XOM"])
    with pytest.raises(DataError, match="XOM"):
        fetch_daily_bars(tmp_path / "bars.csv", CREDENTIALS, symbols=SYMBOLS,
                         client_factory=lambda creds: client)


@pytest.fixture
def fake_alpaca(tmp_path, monkeypatch):
    (tmp_path / "sdk").mkdir()
    client = FakeClient(sdk_frame(tmp_path / "sdk"))
    monkeypatch.setattr(alpaca_source, "default_client", lambda creds: client)
    monkeypatch.setenv("DSIA_SYMBOLS", ",".join(SYMBOLS))
    return client


def test_alpaca_mode_publishes_real_symbols_without_prices(tmp_path, fake_alpaca, monkeypatch):
    # Arrange
    monkeypatch.setenv("ALPACA_PAPER_API_KEY_ID", "clave-falsa")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET_KEY", "secreto-falso")
    output, journal = tmp_path / "out" / "snapshot.json", tmp_path / "evidence" / "pipeline.jsonl"
    # Act
    assert main(["alpaca", "--work", str(tmp_path / "work"), "--output", str(output),
                 "--journal", str(journal)]) == 0
    document = json.loads(output.read_text())
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    # Assert: símbolos reales, origen alpaca y ningún precio ni estadística de precios publicados.
    assert document["data_kind"] == "alpaca"
    assert sorted(row["symbol"] for row in document["predictions"]) == sorted(SYMBOLS)
    assert document.get("input_summary") is None and "last_close" not in output.read_text()
    stages = [event["stage"] for event in events if event["status"] == "succeeded"]
    assert stages == ["download_bars", "validate_input", "prepare", "train", "holdout",
                      "infer_snapshot", "publish_snapshot"]
    download = next(e for e in events if e["stage"] == "download_bars" and e["status"] == "succeeded")
    assert download["symbols"] == len(SYMBOLS) and download["feed"] == "sip"
    # -> Ni las claves ni rutas del disco llegan al journal.
    assert "clave-falsa" not in journal.read_text() and "secreto-falso" not in journal.read_text()


def test_alpaca_mode_reads_the_secret_file(tmp_path, fake_alpaca, monkeypatch):
    monkeypatch.delenv("ALPACA_PAPER_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET_KEY", raising=False)
    secret = tmp_path / "alpaca.env"
    secret.write_text("ALPACA_PAPER_API_KEY_ID=k\nALPACA_PAPER_API_SECRET_KEY=s\n")
    output = tmp_path / "snapshot.json"
    assert main(["auto", "--secrets-file", str(secret), "--work", str(tmp_path / "work"),
                 "--output", str(output)]) == 0
    assert json.loads(output.read_text())["data_kind"] == "alpaca"


def test_alpaca_mode_without_credentials_fails_and_auto_falls_back_to_demo(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("ALPACA_PAPER_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET_KEY", raising=False)
    assert main(["alpaca", "--work", str(tmp_path / "a"), "--output", str(tmp_path / "a.json")]) == 2
    assert "Faltan las credenciales de Alpaca" in caplog.text
    assert not (tmp_path / "a.json").exists()
    output = tmp_path / "demo.json"
    assert main(["auto", "--work", str(tmp_path / "b"), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["data_kind"] == "synthetic"
    assert "se publica la demo sintética" in caplog.text
