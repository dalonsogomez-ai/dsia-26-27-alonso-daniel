"""Exportar solo agregados de un snapshot y su journal: evidencia versionable sin redistribuir datos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .journal import read_recent_events
from .snapshot import Snapshot, read_snapshot

EXCLUDED = ("predictions", "input_summary", "explanation.text", "barras", "precios")


def aggregate_evidence(snapshot: Snapshot, events: list[dict]) -> dict:
    """Identidad, métricas y etapas del lote; sin precios, sin predicciones por símbolo y sin rutas."""
    stages = [{key: event[key] for key in ("stage", "status", "duration_ms", "rows", "symbols", "input_sha256",
                                            "run_id", "error_type") if key in event}
              for event in events if event.get("status") in {"succeeded", "failed"}]
    return {
        "schema_version": 1,
        "run_id": snapshot.run_id,
        "data_kind": snapshot.data_kind,
        "as_of": str(snapshot.as_of),
        "generated_at": snapshot.generated_at.isoformat(),
        "input_sha256": snapshot.input_sha256,
        "artifact_sha256": snapshot.artifact_sha256,
        "sklearn_version": snapshot.sklearn_version,
        "horizon_sessions": snapshot.horizon_sessions,
        "symbols": len(snapshot.predictions),
        "tickers": sorted(row.symbol for row in snapshot.predictions),
        "model": snapshot.model,
        "validation": {name: metrics.model_dump() for name, metrics in sorted(snapshot.validation.items())},
        "holdout": snapshot.holdout.model_dump(),
        "holdout_touches": snapshot.holdout_touches,
        "splits": {name: period.model_dump(mode="json") for name, period in snapshot.splits.items()},
        "explanation_provider": snapshot.explanation.provider if snapshot.explanation else None,
        "journal": stages,
        "excluded": list(EXCLUDED),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("La evidencia de salida ya existe")
    events, skipped = read_recent_events(args.journal, limit=200)
    if skipped:
        parser.error("El journal contiene líneas no válidas")
    document = aggregate_evidence(read_snapshot(args.snapshot), events)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": document["run_id"], "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
