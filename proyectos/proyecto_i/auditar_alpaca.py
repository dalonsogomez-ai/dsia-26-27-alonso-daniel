"""-> Auditar los datos locales sin equiparar archivos presentes con cobertura total.

> --deep descomprime y cuenta cada registro; --output guarda evidencia reproducible.
>> Los recuentos de noticias son registros/versiones, no artículos únicos globales.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys

from alpaca_io import atomic_json, record_count, utc_now


RAW = Path(__file__).resolve().parent / "data" / "raw"


def inspect_manifest(path: Path, deep: bool = False) -> dict:
    result = {"manifest": str(path), "valid": False}
    try:
        meta = json.loads(path.read_text())
        name = meta.get("data_file")
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Nombre de archivo ausente o inseguro")
        data = path.parent / name
        result.update(rows=meta.get("rows", 0), pages=meta.get("pages", 0),
                      start=meta.get("start"), end=meta.get("end"), data_file=str(data),
                      format=meta.get("format", "records_jsonl"),
                      rejected_symbols=meta.get("rejected_symbols", []))
        if not data.is_file():
            raise ValueError("Manifiesto sin datos")
        size = data.stat().st_size
        result["bytes"] = size
        if "bytes" in meta and size != meta["bytes"]:
            raise ValueError("Tamaño distinto al confirmado")
        if deep:
            actual_rows = lines = 0
            fields = Counter()
            news_stats = Counter()
            news_ids = set()
            with gzip.open(data, "rt", encoding="utf-8") as source:
                for line in source:
                    item = json.loads(line)
                    lines += 1
                    if meta.get("format") == "one_complete_api_response_per_jsonl_line":
                        actual_rows += record_count(item, meta.get("count_key"))
                        records = item.get("news", []) if isinstance(item, dict) else []
                    else:
                        actual_rows += 1
                        fields.update(item.keys())
                        records = [item] if meta.get("mode") == "news" else []
                    for record in records:
                        news_stats["records"] += 1
                        news_stats["with_content"] += bool(record.get("content"))
                        news_stats["with_headline"] += bool(record.get("headline"))
                        news_stats["with_created_at"] += bool(record.get("created_at"))
                        news_stats["with_updated_at"] += bool(record.get("updated_at"))
                        identifier = record.get("id")
                        if identifier is not None:
                            news_stats["duplicate_ids_within_file"] += identifier in news_ids
                            news_ids.add(identifier)
            result.update(actual_rows=actual_rows, jsonl_lines=lines, fields=dict(fields),
                          news=dict(news_stats), unique_news_ids_within_file=len(news_ids))
            if actual_rows != meta.get("rows"):
                raise ValueError(f"Recuento real {actual_rows} != manifiesto {meta.get('rows')}")
            digest = hashlib.sha256()
            with data.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            result["sha256"] = digest.hexdigest()
            if meta.get("sha256") and meta["sha256"] != result["sha256"]:
                raise ValueError("SHA-256 distinto al manifiesto")
        result["valid"] = True
    except (OSError, ValueError, EOFError, TypeError) as exc:
        result["error"] = str(exc)
    return result


def audit(root: Path, deep: bool = False) -> dict:
    results = []
    families = defaultdict(Counter)
    for index, path in enumerate(sorted(root.rglob("*.manifest.json")), 1):
        result = inspect_manifest(path, deep)
        result["manifest"] = str(path.relative_to(root))
        family = str(path.parent.relative_to(root))
        families[family]["manifests"] += 1
        families[family]["valid"] += result["valid"]
        families[family]["rejected_symbols"] += len(result.get("rejected_symbols", []))
        if result["valid"]:
            families[family]["rows"] += result.get("rows", 0)
        else:
            families[family]["invalid"] += 1
        results.append(result)
        if deep and index % 20 == 0:
            print(f">> Auditados {index} manifiestos: {path.parent.name}/{path.name}", file=sys.stderr, flush=True)
    checkpoints = []
    for path in root.rglob("*.checkpoint.json"):
        state = json.loads(path.read_text())
        checkpoints.append({"path": str(path.relative_to(root)), "rows": state.get("rows", 0),
                            "pages": state.get("pages", 0), "status": state.get("status"),
                            "updated_at_utc": state.get("updated_at_utc")})
    errors = []
    for path in root.rglob("*.error.json"):
        errors.append({"path": str(path.relative_to(root)), **json.loads(path.read_text())})
    snapshots = []
    for path in (root / "estado_actual").glob("captura_*.json"):
        item = json.loads(path.read_text())
        snapshots.append({"file": str(path.relative_to(root)),
                          "requested_symbols": len(item.get("requested_symbols", [])),
                          "returned_symbols": len(item.get("snapshots", {})),
                          "downloaded_at_utc": item.get("downloaded_at_utc"), "feed": item.get("feed")})
    return {"audited_at_utc": utc_now(), "root": str(root), "deep": deep,
            "all_data_extracted": False, "families": {k: dict(v) for k, v in families.items()},
            "files": results, "checkpoints": checkpoints, "errors": errors,
            "legacy_snapshots": snapshots,
            "interpretation": ["valid means file integrity, not full API coverage",
                               "rows are records, not globally unique articles or trades",
                               "running files may advance after this snapshot"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=RAW / "masivo")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.root.resolve(), args.deep)
    if args.output:
        atomic_json(args.output, report)
    print(json.dumps({k: report[k] for k in ("audited_at_utc", "deep", "families")}, indent=2))
    return 1 if any(not item["valid"] for item in report["files"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
