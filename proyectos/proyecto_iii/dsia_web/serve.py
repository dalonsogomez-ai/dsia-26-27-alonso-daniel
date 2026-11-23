"""-> Arranque del contenedor: refresca el informe con datos reales de Alpaca y lanza Uvicorn.

Si hay credenciales en tiempo de ejecución (variables de entorno o el secret file
``/etc/secrets/alpaca.env``) y el informe del build es la demo o es de un día anterior, se
descargan las barras hasta ayer, se reentrena y se sirve el informe nuevo. En el plan free de
Render el servicio se duerme sin tráfico, así que cada arranque publica datos del día anterior.
Si el refresco falla, se sirve el informe del build: el servicio nunca se queda sin snapshot.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from .alpaca_source import load_credentials
from .build import main as build_main

LOG = logging.getLogger(__name__)
SECRET_FILE = Path("/etc/secrets/alpaca.env")


def needs_refresh(snapshot: Path, *, today: date | None = None) -> bool:
    """> Refrescar si el informe no existe, no es legible, no es real o no se generó hoy (UTC)."""
    today = today or datetime.now(timezone.utc).date()
    try:
        document = json.loads(Path(snapshot).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(document["generated_at"]).astimezone(timezone.utc).date()
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return document.get("data_kind") != "alpaca" or generated < today


def refresh() -> tuple[Path, Path] | None:
    """> Generar un informe real en un directorio temporal; devuelve (snapshot, journal) o ``None``."""
    target = Path(tempfile.mkdtemp(prefix="dsia-live-"))
    snapshot, journal = target / "snapshot.json", target / "evidence" / "pipeline.jsonl"
    args = ["alpaca", "--work", str(target / "work"), "--output", str(snapshot), "--journal", str(journal)]
    if SECRET_FILE.is_file():
        args += ["--secrets-file", str(SECRET_FILE)]
    try:
        code = build_main(args)
    finally:
        # -> Las barras descargadas no se conservan: el informe público no lleva precios.
        shutil.rmtree(target / "work", ignore_errors=True)
    return (snapshot, journal) if code == 0 and snapshot.is_file() else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    baked = Path(os.environ.get("DSIA_SNAPSHOT", "runs/dsia/snapshot.json"))
    if load_credentials(SECRET_FILE) is not None and needs_refresh(baked):
        LOG.info("Credenciales de Alpaca disponibles: se refresca el informe antes de arrancar")
        fresh = refresh()
        if fresh is None:
            LOG.warning("Refresco con Alpaca fallido; se sirve el informe del build")
        else:
            os.environ["DSIA_SNAPSHOT"], os.environ["DSIA_JOURNAL"] = map(str, fresh)
    port = os.environ.get("PORT", "8000")
    os.execvp("uvicorn", ["uvicorn", "dsia_web.app:app", "--host", "0.0.0.0", "--port", port])


if __name__ == "__main__":
    main()
