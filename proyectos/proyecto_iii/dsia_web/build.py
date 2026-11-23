"""Generar un informe público sintético o derivarlo de un run propio existente."""

from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
from contextlib import contextmanager, nullcontext
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter_ns
from typing import Iterator, TextIO

from swarmtrade_app.ai_client import AIClient, AIClientError, AnalysisRequest
from swarmtrade_app.data import DataError, generate_demo
from swarmtrade_app.pipeline import infer
from swarmtrade_app.preparation import prepare
from swarmtrade_app.training import evaluate_holdout, train_prepared

from .snapshot import Explanation, Metrics, Period, Prediction, Snapshot, create_snapshot

LOG = logging.getLogger(__name__)


class RunJournal:
    """Eventos de etapas del lote para diagnóstico y trazabilidad."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream

    @contextmanager
    def stage(self, stage: str, **fields: str) -> Iterator[None]:
        if self.stream is None:
            yield
            return

        def emit(status: str, **details: str | float) -> None:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": stage,
                "status": status,
                **fields,
                **details,
            }
            print(json.dumps(entry), file=self.stream, flush=True)

        emit("started")
        start = perf_counter_ns()
        try:
            yield
        except Exception as error:
            emit("failed", duration_ms=(perf_counter_ns() - start) / 1e6,
                 error_type=type(error).__name__)
            raise
        else:
            emit("succeeded", duration_ms=(perf_counter_ns() - start) / 1e6)


def from_run(data: Path, run: Path, provider: str = "mock") -> Snapshot:
    """Reutilizar un artefacto propio y el resultado del holdout que ya tiene guardado."""
    report, artifact, _ = infer(data, run / "model.joblib")
    validation = artifact["report"]
    holdout = json.loads((run / "test_metrics.json").read_text())
    summary = AnalysisRequest(**report["summary"])
    if holdout["touches"] != 1 or holdout["selected"] != summary.model:
        raise DataError("El holdout debe corresponder al modelo congelado y tener un toque")
    if report["input_sha256"] != validation["metadata"]["data_sha256"]:
        raise DataError("La entrada no coincide con el dataset evaluado")
    try:
        explanation = Explanation(**asdict(AIClient(provider=provider).analyze(summary)))
    except AIClientError:
        LOG.warning("Proveedor de explicación no disponible: %s", provider)
        explanation = None

    return create_snapshot({
        "generated_at": datetime.now(timezone.utc),
        "as_of": date.fromisoformat(summary.as_of),
        "data_kind": summary.data_kind,
        "input_sha256": report["input_sha256"],
        "artifact_sha256": report["artifact_sha256"],
        "sklearn_version": validation["sklearn_version"],
        "horizon_sessions": summary.horizon,
        "model": summary.model,
        "validation": {name: Metrics.model_validate(values)
                       for name, values in validation["validation"].items()},
        "splits": {name: Period.model_validate(period)
                   for name, period in validation["metadata"]["splits"].items()},
        "holdout": Metrics.model_validate({
            key: holdout[key] for key in Metrics.model_fields
        }),
        "predictions": [Prediction.model_validate(row) for row in report["predictions"]],
        "explanation": explanation,
    })


def demo(work: Path, journal: RunJournal | None = None) -> Snapshot:
    journal = journal or RunJournal()
    run = work / "model"
    with journal.stage("generate_bars"):
        work.mkdir(parents=True, exist_ok=False)
        data = generate_demo(work / "bars.csv", sessions=680, symbols=8, seed=42)
    with journal.stage("prepare"):
        prepare(data, run, data_kind="synthetic")
    with journal.stage("train"):
        train_prepared(run)
    with journal.stage("holdout"):
        evaluate_holdout(run)
    with journal.stage("infer_snapshot"):
        return from_run(data, run)


def write_snapshot(snapshot: Snapshot, output: Path) -> None:
    """Publicar un snapshot completo sin sobrescribir una salida anterior."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as staging:
        staged = Path(staging) / "snapshot.json"
        staged.write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.link(staged, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    demo_parser = modes.add_parser("demo")
    demo_parser.add_argument("--work", type=Path, required=True)
    existing_parser = modes.add_parser("from-run")
    existing_parser.add_argument("--data", type=Path, required=True)
    existing_parser.add_argument("--run", type=Path, required=True)
    existing_parser.add_argument("--provider", choices=("mock", "hf"), default="mock")
    for mode in (demo_parser, existing_parser):
        mode.add_argument("--output", type=Path, required=True)
        mode.add_argument("--journal", type=Path, help="Registro JSONL de etapas en un archivo nuevo")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.output.exists():
            raise FileExistsError("El informe de salida ya existe")
        stream = nullcontext(None)
        if args.journal is not None:
            journal_path = args.journal.resolve()
            output_path = args.output.resolve()
            if journal_path.is_relative_to(output_path) or output_path.is_relative_to(journal_path):
                raise ValueError("--journal y --output requieren rutas independientes")
            if args.mode == "demo":
                work_path = args.work.resolve()
                if journal_path.is_relative_to(work_path) or work_path.is_relative_to(journal_path):
                    raise ValueError("--journal debe estar fuera de --work")
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            stream = journal_path.open("x", encoding="utf-8")
        with stream as log:
            journal = RunJournal(log)
            if args.mode == "demo":
                snapshot = demo(args.work, journal)
            else:
                with journal.stage("infer_snapshot"):
                    snapshot = from_run(args.data, args.run, args.provider)
            with journal.stage("publish_snapshot", run_id=snapshot.run_id):
                write_snapshot(snapshot, args.output)
    except (DataError, OSError, ValueError, KeyError, RuntimeError) as exc:
        LOG.error("Generación del informe fallida: %s", exc)
        return 2
    print(json.dumps({"run_id": snapshot.run_id, "as_of": str(snapshot.as_of),
                      "data_kind": snapshot.data_kind, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
