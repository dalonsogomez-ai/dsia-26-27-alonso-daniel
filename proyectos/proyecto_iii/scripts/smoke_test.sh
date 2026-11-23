#!/usr/bin/env bash
# -> Smoke HTTP contra un servicio en marcha: salud, informe, predicción, análisis y métricas.
set -euo pipefail

base=${1:-http://127.0.0.1:8765}
base=${base%/}
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
fetch() { curl --fail --silent --show-error --max-time 10 "$@"; }

fetch "$base/health" > "$tmp_dir/health.json"
fetch "$base/api/v1/snapshot" > "$tmp_dir/snapshot.json"
# > El símbolo se toma del propio informe: vale para la demo sintética y para un histórico.
symbol=$("${PYTHON:-python3}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["predictions"][0]["symbol"])' \
  "$tmp_dir/snapshot.json")
fetch "$base/api/v1/predictions/$symbol" > "$tmp_dir/prediction.json"
analyze_headers=(-H "Content-Type: application/json" -H "X-Request-ID: smoke-analyze-0001")
if [[ -n "${DSIA_API_KEY:-}" ]]; then analyze_headers+=(-H "X-API-Key: $DSIA_API_KEY"); fi
fetch -X POST "${analyze_headers[@]}" --data "{\"symbol\": \"$symbol\"}" "$base/api/v1/analyze" > "$tmp_dir/analyze.json"
fetch "$base/api/v1/metrics" > "$tmp_dir/metrics.json"
"${PYTHON:-python3}" - "$tmp_dir" "$symbol" <<'PY'
import json
import sys
from pathlib import Path

root, symbol = Path(sys.argv[1]), sys.argv[2]
health, snapshot, prediction, analysis, metrics = (
    json.loads((root / f"{name}.json").read_text())
    for name in ("health", "snapshot", "prediction", "analyze", "metrics"))
run_id = snapshot.get("run_id")
checks = [
    (health.get("status") == "ready" and health.get("checks", {}).get("snapshot_loaded") is True,
     "salud no lista"),
    (bool(run_id) and health.get("run_id") == run_id and health.get("as_of") == snapshot.get("as_of"),
     "salud e informe incoherentes"),
    (bool(snapshot.get("predictions")), "informe sin predicciones"),
    (prediction.get("symbol") == symbol and prediction.get("run_id") == run_id, "predicción incoherente"),
    (analysis.get("symbol") == symbol and analysis.get("run_id") == run_id and analysis.get("summary")
     and analysis.get("request_id") == "smoke-analyze-0001", "análisis incoherente"),
    (metrics.get("run_id") == run_id and metrics.get("requests_total", 0) >= 4, "métricas incoherentes"),
]
failed = [message for ok, message in checks if not ok]
if failed:
    raise SystemExit("Smoke fallido: " + "; ".join(failed))
print(f"Smoke correcto · run_id={run_id} · símbolo={symbol} · proveedor={analysis['provider']}")
PY
