from collections import namedtuple

import pytest

from dsia_web.build import main
from dsia_web.snapshot import read_snapshot

Demo = namedtuple("Demo", "path snapshot journal bars run")


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
