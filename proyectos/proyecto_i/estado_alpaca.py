"""-> Mostrar archivos válidos, páginas parciales, permisos y procesos comprobados."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from auditar_alpaca import RAW, audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=RAW / "masivo")
    args = parser.parse_args()
    report = audit(args.root.resolve())
    processes = []
    for path in args.root.glob("ampliacion_*/ejecucion.json"):
        run = json.loads(path.read_text())
        pid = run.get("pid")
        result = subprocess.run(["ps", "-p", str(pid), "-o", "command="],
                                capture_output=True, text=True, check=False)
        active = result.returncode == 0 and any(name in result.stdout for name in
                    ("descargar_alpaca_completo.py", "continuar_alpaca.py"))
        processes.append({"directory": str(path.parent), "pid": pid, "active": active,
                          "end": run.get("end")})
    report["processes"] = processes
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f">> Estado local a {report['audited_at_utc']}")
    for family, counts in sorted(report["families"].items()):
        print(f"{family}: {counts['valid']}/{counts['manifests']} archivos válidos; "
              f"{counts.get('rows', 0):,} registros en archivos terminados; "
              f"{counts.get('rejected_symbols', 0)} rechazos de símbolos")
    snapshots = report["legacy_snapshots"]
    if snapshots:
        print(f">> Capturas antiguas: {len(snapshots)} lotes; "
              f"{sum(s['returned_symbols'] for s in snapshots):,} símbolos devueltos (captura puntual)")
    by_family = {}
    for item in report["checkpoints"]:
        family = str(Path(item["path"]).parent)
        total = by_family.setdefault(family, {"parts": 0, "rows": 0})
        total["parts"] += 1
        total["rows"] += item["rows"]
    for family, counts in sorted(by_family.items()):
        print(f"~> {family}: {counts['parts']} tareas parciales; {counts['rows']:,} registros confirmados")
    for item in processes:
        print(f"> Proceso {item['pid']}: {'ACTIVO' if item['active'] else 'inactivo'}; "
              f"corte histórico={item['end']}; {Path(item['directory']).name}")
    print(f">> {len(report['errors'])} errores de tareas registrados; consultar permisos.json y *.error.json")
    print("=> Integridad de archivos y fin de paginación no equivalen a todos los datos de Alpaca.")


if __name__ == "__main__":
    main()
