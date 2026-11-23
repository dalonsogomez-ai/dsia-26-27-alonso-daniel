#!/usr/bin/env bash
set -euo pipefail

base=${1:-http://127.0.0.1:8765}
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

curl --fail --silent --show-error --max-time 5 "${base%/}/health" > "$tmp_dir/health.json"
curl --fail --silent --show-error --max-time 5 "${base%/}/api/v1/snapshot" > "$tmp_dir/snapshot.json"
"${PYTHON:-python3}" - "$tmp_dir" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
health = json.loads((root / "health.json").read_text())
snapshot = json.loads((root / "snapshot.json").read_text())
if (health.get("status") != "ready"
        or not snapshot.get("run_id")
        or health.get("run_id") != snapshot["run_id"]
        or health.get("as_of") != snapshot.get("as_of")
        or not snapshot.get("predictions")):
    raise SystemExit("Smoke fallido: salud e informe incoherentes")
print("Smoke correcto · run_id=" + snapshot["run_id"])
PY
