"""-> Capturas actuales y códigos de referencia de acciones de EE. UU. con Alpaca CLI.

Una captura es una observación puntual, no un histórico. Solo se consultan
activos vigentes no OTC, pues los inactivos no tienen cotización actual.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time


RAW = Path(__file__).parent / "data" / "raw"
ASSETS_NAME = "alpaca_activos.json"


def call(*parts: str) -> dict:
    command = ["alpaca", "data", *parts, "--timeout", "90"]
    for attempt in range(5):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                raise ValueError("Respuesta inesperada de Alpaca")
            return value
        error = result.stderr.strip()
        if not any(term in error.lower() for term in (
            "no such host", "timeout", "timed out", "connection reset", "429", "500", "502", "503", "504",
        )) or attempt == 4:
            raise RuntimeError(error)
        time.sleep(min(2 ** attempt, 16))
    raise AssertionError("bucle de reintentos sin resultado")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """> Lee la carpeta de descargas; `--help` termina sin llamar a Alpaca."""
    parser = argparse.ArgumentParser(
        description="Descarga capturas actuales de acciones de EE. UU. con la CLI de Alpaca.",
    )
    parser.add_argument(
        "--raw", type=Path, default=RAW,
        help=f"carpeta con {ASSETS_NAME}; las capturas van a <raw>/masivo/estado_actual",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """> Comprueba el catálogo de activos antes de crear carpetas o llamar a la API."""
    args = parse_arguments(argv)
    assets_path = args.raw / ASSETS_NAME
    if not assets_path.is_file():
        print(
            f"ERROR: no existe {assets_path}. Genera antes el catálogo con "
            f"'alpaca asset list --asset-class us_equity > {assets_path}' (ver ALPACA.md).",
            file=sys.stderr,
        )
        return 1
    out = args.raw / "masivo" / "estado_actual"
    out.mkdir(parents=True, exist_ok=True)
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    symbols = sorted({item["symbol"] for item in assets
                      if item.get("class") == "us_equity" and item.get("status") == "active"
                      and item.get("exchange") != "OTC"
                      and re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", item.get("symbol", ""))})
    failures = []
    for index in range(0, len(symbols), 50):
        batch = symbols[index:index + 50]
        path = out / f"captura_{index // 50:04d}.json"
        if path.exists():
            continue
        try:
            response = call("multi-snapshots", "--symbols", ",".join(batch), "--feed", "iex")
        except (OSError, RuntimeError, ValueError) as exc:
            failures.append({"batch": index // 50, "error": str(exc)})
            print(f"captura {index // 50}: {exc}", flush=True)
            if len(failures) >= 3:
                break
            continue
        path.write_text(json.dumps({"downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                                    "feed": "iex", "requested_symbols": batch,
                                    "snapshots": response}, ensure_ascii=False) + "\n", encoding="utf-8")
        if index % 500 == 0:
            print(f"capturas: {index + len(batch)}/{len(symbols)}", flush=True)
        time.sleep(0.35)
    references = [("exchanges", ("meta", "exchanges"))]
    references.extend(
        (f"{ticktype}_conditions_{tape}",
         ("meta", "conditions", "--ticktype", ticktype, "--tape", tape))
        for ticktype in ("trade", "quote") for tape in ("A", "B", "C")
    )
    for name, parts in references:
        path = out / f"{name}.json"
        if not path.exists():
            try:
                path.write_text(json.dumps(call(*parts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except (OSError, RuntimeError, ValueError) as exc:
                failures.append({"reference": name, "error": str(exc)})
    (out / "fallos.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    snapshots = [json.loads(path.read_text(encoding="utf-8"))
                 for path in sorted(out.glob("captura_*.json"))]
    returned = {symbol for item in snapshots for symbol in item["snapshots"]}
    summary = {"requested_symbols": len(symbols), "returned_snapshots": len(returned),
               "without_snapshot": sorted(set(symbols) - returned),
               "completed_batches": len(snapshots), "expected_batches": (len(symbols) + 49) // 50,
               "failed_requests": len(failures)}
    (out / "resumen.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Solicitados: {len(symbols)}; capturas: {len(returned)}; fallos: {len(failures)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
