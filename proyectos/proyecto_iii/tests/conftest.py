from collections import namedtuple

import pytest

from dsia_web.build import main
from dsia_web.snapshot import read_snapshot

Demo = namedtuple("Demo", "path snapshot journal bars run")


SERVICE_ENV = (
    "RENDER", "RENDER_GIT_COMMIT", "DSIA_COMMIT", "DSIA_REFRESH_TIMEOUT",
    "DSIA_ANALYZE_PER_MINUTE", "DSIA_ANALYZE_PER_DAY", "DSIA_ANALYZE_PER_IP_DAY", "DSIA_TRUSTED_PROXY_HOPS",
    "DSIA_ANALYZE_CONCURRENCY", "DSIA_ANALYZE_CONCURRENCY_PER_IP",
    # > La configuración de IA de la terminal (p. ej. AI_PROVIDER=nvidia) cambiaría /health y los análisis.
    "AI_PROVIDER", "AI_MOCK_MODE", "HF_TOKEN", "HF_MODEL", "HF_TIMEOUT", "HF_MAX_TOKENS", "HF_INFERENCE_PROVIDER",
    "NVIDIA_API_KEY", "NVIDIA_MODEL", "NVIDIA_TIMEOUT", "NVIDIA_MAX_TOKENS",
)


@pytest.fixture(autouse=True)
def isolate_service_env(monkeypatch):
    """>> Variables del despliegue (Render, límites, refresco e IA) fuera de la suite salvo que la prueba las fije."""
    for name in SERVICE_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope="session")
def demo_run(tmp_path_factory):
    """Lote demo completo una sola vez: snapshot, journal, CSV sintético y run congelado."""
    root = tmp_path_factory.mktemp("flow")
    path = root / "snapshot.json"
    journal = root / "pipeline.jsonl"
    assert main(["demo", "--work", str(root / "work"), "--output", str(path),
                 "--journal", str(journal)]) == 0
    return Demo(path, read_snapshot(path), journal, root / "work" / "bars.csv", root / "work" / "model")


@pytest.fixture(scope="session")
def report(demo_run):
    return demo_run.path, demo_run.snapshot
