"""-> Arranque del contenedor: refresca el informe con datos reales de Alpaca y lanza Uvicorn.

Si hay credenciales en tiempo de ejecución (variables de entorno o el secret file
``/etc/secrets/alpaca.env``) y el informe del build es la demo o es de un día anterior, se
descargan las barras hasta ayer, se reentrena y se sirve el informe nuevo. En el plan free de
Render el servicio se duerme sin tráfico, así que cada arranque publica datos del día anterior.
Si el refresco falla, se sirve el informe del build: el servicio nunca se queda sin snapshot.

El lote corre en un proceso hijo (``python -m dsia_web.build alpaca``) con un tope de
``DSIA_REFRESH_TIMEOUT`` segundos (180 por defecto): una descarga colgada no bloquea el arranque;
al vencer se mata el hijo, se registra el motivo y se sirve el informe de la imagen.
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path

from .alpaca_source import load_credentials

LOG = logging.getLogger(__name__)
SECRET_FILE = Path("/etc/secrets/alpaca.env")
BUILD_MODULE = "dsia_web.build"
DEFAULT_REFRESH_TIMEOUT = 180.0


def needs_refresh(snapshot: Path, *, today: date | None = None) -> bool:
    """> Refrescar si el informe no existe, no es legible, no es real o no se generó hoy (UTC)."""
    today = today or datetime.now(timezone.utc).date()
    try:
        document = json.loads(Path(snapshot).read_text(encoding="utf-8"))
        generated = datetime.fromisoformat(document["generated_at"]).astimezone(timezone.utc).date()
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return document.get("data_kind") != "alpaca" or generated < today


def refresh_timeout(env: Mapping[str, str] | None = None) -> float:
    """> Segundos máximos del refresco; un valor no válido avisa y usa el de por defecto (nunca impide arrancar)."""
    env = os.environ if env is None else env
    raw = str(env.get("DSIA_REFRESH_TIMEOUT") or "").strip()
    if not raw:
        return DEFAULT_REFRESH_TIMEOUT
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        # > Solo la longitud: una clave pegada por error en la variable no debe llegar al log.
        LOG.warning("DSIA_REFRESH_TIMEOUT no válido (%d caracteres): debe ser un número de segundos mayor que 0; "
                    "se usan %g s", len(raw), DEFAULT_REFRESH_TIMEOUT)
        return DEFAULT_REFRESH_TIMEOUT
    return value


def refresh(timeout: float = DEFAULT_REFRESH_TIMEOUT) -> tuple[Path, Path] | None:
    """> Generar un informe real en un directorio temporal; devuelve (snapshot, journal) o ``None``."""
    target = Path(tempfile.mkdtemp(prefix="dsia-live-"))
    snapshot, journal = target / "snapshot.json", target / "evidence" / "pipeline.jsonl"
    command = [sys.executable, "-m", BUILD_MODULE, "alpaca", "--work", str(target / "work"),
               "--output", str(snapshot), "--journal", str(journal)]
    if SECRET_FILE.is_file():
        command += ["--secrets-file", str(SECRET_FILE)]
    try:
        # > El hijo hereda el entorno (claves de Alpaca, PYTHONPATH) y escribe sus logs en la misma salida.
        code = subprocess.run(command, timeout=timeout, check=False).returncode
    except subprocess.TimeoutExpired:
        # > subprocess.run mata al hijo (SIGKILL) y lo espera antes de lanzar TimeoutExpired.
        LOG.warning("Refresco con Alpaca cancelado: superó DSIA_REFRESH_TIMEOUT=%g s y se detuvo el proceso", timeout)
        return None
    except OSError as error:
        LOG.warning("Refresco con Alpaca no se pudo lanzar: %s", type(error).__name__)
        return None
    finally:
        # -> Las barras descargadas no se conservan: el informe público no lleva precios.
        shutil.rmtree(target / "work", ignore_errors=True)
    if code != 0:
        LOG.warning("Refresco con Alpaca terminó con código %d", code)
    return (snapshot, journal) if code == 0 and snapshot.is_file() else None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    baked = Path(os.environ.get("DSIA_SNAPSHOT", "runs/dsia/snapshot.json"))
    if load_credentials(SECRET_FILE) is not None and needs_refresh(baked):
        LOG.info("Credenciales de Alpaca disponibles: se refresca el informe antes de arrancar")
        fresh = refresh(refresh_timeout())
        if fresh is None:
            LOG.warning("Refresco con Alpaca fallido; se sirve el informe del build")
        else:
            os.environ["DSIA_SNAPSHOT"], os.environ["DSIA_JOURNAL"] = map(str, fresh)
    port = os.environ.get("PORT", "8000")
    # > --no-access-log: el access log de Uvicorn escribe la IP del par TCP (en local o Docker, la del
    #   cliente); la línea «request request_id=…» del middleware ya da método, ruta, estado y latencia.
    os.execvp("uvicorn", ["uvicorn", "dsia_web.app:app", "--host", "0.0.0.0", "--port", port, "--no-access-log"])


if __name__ == "__main__":
    main()
