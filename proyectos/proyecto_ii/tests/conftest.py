import os
import socket

import pytest

from swarmtrade_app.data import generate_demo, load_bars


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    # >> Todo test falla si intenta alcanzar una red real.
    def forbidden(*args, **kwargs):
        raise AssertionError('La suite se ejecuta sin red')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.fixture(autouse=True)
def isolate_local_env(monkeypatch):
    # >> Un .env local del desarrollador no debe cambiar proveedor, token, clave ni límites durante la suite.
    monkeypatch.setattr('swarmtrade_app.cli.load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setenv('AI_PROVIDER', 'mock')
    for name in ('HF_TOKEN', 'HF_MODEL', 'HF_INFERENCE_PROVIDER', 'HF_TIMEOUT', 'HF_MAX_TOKENS',
                 'NVIDIA_API_KEY', 'NVIDIA_MODEL', 'NVIDIA_TIMEOUT', 'NVIDIA_MAX_TOKENS'):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def offline_env():
    """>> Entorno para subprocesos: el bloqueo de red no cruza procesos; se fuerza mock sin HF_* ni NVIDIA_*."""
    def build() -> dict[str, str]:
        env = {name: value for name, value in os.environ.items() if not name.startswith(('HF_', 'NVIDIA_'))}
        return env | {'AI_PROVIDER': 'mock'}
    return build


@pytest.fixture
def bars_file(tmp_path):
    return generate_demo(tmp_path / 'bars.csv', sessions=500, symbols=6, seed=17)


@pytest.fixture
def bars(bars_file):
    return load_bars(bars_file)
