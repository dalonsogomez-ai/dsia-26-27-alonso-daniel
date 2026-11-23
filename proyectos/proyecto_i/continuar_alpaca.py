"""-> Reanudar la extracción amplia con checkpoints y límite global de disco.

> python continuar_alpaca.py --end 2026-10-18
>> Reutiliza la misma carpeta e identidad; no cuenta manifiestos de otros intervalos.
"""

from datetime import datetime, timedelta, timezone
import sys

from descargar_alpaca_completo import main


if __name__ == "__main__":
    if "--end" not in sys.argv:
        sys.argv += ["--end", (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()]
    if "--max-rounds" not in sys.argv:
        sys.argv += ["--max-rounds", "0"]
    if "--run" not in sys.argv:
        sys.argv.append("--run")
    raise SystemExit(main())
