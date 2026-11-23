import socket

import pytest

from swarmtrade_app.data import generate_demo, load_bars


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    # >> Todo test falla si intenta alcanzar una red real.
    def forbidden(*args, **kwargs):
        raise AssertionError('La suite se ejecuta sin red')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


@pytest.fixture
def bars_file(tmp_path):
    return generate_demo(tmp_path / 'bars.csv', sessions=500, symbols=6, seed=17)


@pytest.fixture
def bars(bars_file):
    return load_bars(bars_file)
