"""-> E/S de extracción: CLI de solo lectura, paginación y recuperación por página.

~> JSONL gzip de respuestas completas: no se descartan campos desconocidos.
>> Un checkpoint confirma bytes persistidos; un manifiesto confirma fin de paginación.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: object) -> None:
    """> Publicar metadatos después de sincronizar su archivo temporal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8",
                                         delete=False) as sink:
            name = Path(sink.name)
            json.dump(value, sink, ensure_ascii=False, indent=2)
            sink.write("\n")
            sink.flush()
            os.fsync(sink.fileno())
        os.replace(name, path)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


@dataclass(frozen=True)
class Task:
    family: str
    name: str
    command: tuple[str, ...]
    key: str | None = None
    paginated: bool = False
    access: str = ""
    binary: bool = False

    @property
    def identity(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class DiskLimit(RuntimeError):
    pass


def call(command: tuple[str, ...], *, token: str | None = None,
         profile: str | None = None, delay: float = 0.4, binary: bool = False):
    """> Invocar únicamente los comandos de datos y referencia autorizados."""
    allowed = {"data", "asset", "calendar", "clock"}
    if not command or (command[0] not in allowed and command[:2] != ("option", "contracts")):
        raise ValueError("Solo se permiten comandos de datos, catálogos y calendario")
    if command[0] == "asset" and command[1:2] != ("list",):
        raise ValueError("Solo se permite asset list")
    args = ["alpaca", *command, "--timeout", "90"]
    if token:
        args += ["--page-token", token]
    if profile:
        args += ["--profile", profile]
    for attempt in range(5):
        try:
            result = subprocess.run(args, capture_output=True, timeout=110, check=False)
        except subprocess.TimeoutExpired:
            error = ApiError("Timeout de la CLI", 504)
        else:
            if result.returncode == 0:
                time.sleep(delay)
                return result.stdout if binary else json.loads(result.stdout)
            message = (result.stderr or result.stdout).decode("utf-8", errors="replace")
            try:
                detail = json.loads(message)
                error = ApiError(detail.get("error", message), int(detail.get("status", 0)))
            except (ValueError, TypeError, AttributeError):
                error = ApiError(message[:2000])
            time.sleep(delay)
        transient = error.status in (429, 500, 502, 503, 504) or any(
            term in str(error).lower() for term in
            ("no such host", "timed out", "timeout", "connection reset", "could not reach"))
        if not transient or attempt == 4:
            raise error
        time.sleep(max(delay, min(2 ** attempt, 30)))
    raise AssertionError("Reintentos agotados")


def record_count(response: object, key: str | None) -> int:
    """> Contar registros del payload; la unidad queda indicada en el manifiesto."""
    if key is None:
        return len(response) if isinstance(response, (list, dict)) else 1
    if not isinstance(response, dict) or key not in response:
        raise ValueError(f"Respuesta sin el campo esperado {key}")
    value = response[key]
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return sum(len(v) if isinstance(v, list) else 1 for v in value.values())
    raise ValueError(f"Formato inesperado en {key}")


class Storage:
    """-> Presupuesto global: incluye finales, parciales y archivos antiguos."""

    def __init__(self, root: Path, max_gb: float = 50, min_free_gb: float = 20):
        self.root = root
        self.max_bytes = int(max_gb * 1_000_000_000)
        self.min_free_bytes = int(min_free_gb * 1_000_000_000)
        self.used = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        self.checked_at = time.monotonic()

    def check(self, additional: int = 0) -> None:
        if time.monotonic() - self.checked_at > 30 or self.used > self.max_bytes * 0.99:
            # >> Incluir también el crecimiento de manifiestos, checkpoints y logs.
            self.used = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
            self.checked_at = time.monotonic()
        free = shutil.disk_usage(self.root).free
        if self.used + additional >= self.max_bytes or free - additional < self.min_free_bytes:
            raise DiskLimit(f"Límite global de disco: usados={self.used:,}, libres={free:,} bytes")

    def written(self, size: int) -> None:
        self.used += size


def paths(root: Path, task: Task) -> tuple[Path, Path, Path, Path]:
    folder = root / task.family
    stem = f"{re.sub(r'[^A-Za-z0-9_.-]', '_', task.name)}-{task.identity[:12]}"
    return (folder / f"{stem}.jsonl.gz", folder / f"{stem}.manifest.json",
            folder / f"{stem}.part.jsonl.gz", folder / f"{stem}.checkpoint.json")


def read_pages(path: Path, *, committed_bytes: int | None = None):
    """> Leer respuestas por streaming; los parciales solo hasta el checkpoint."""
    if committed_bytes is None:
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                yield json.loads(line)
    else:
        # > Los consumidores del catálogo leen solo archivos terminados.
        raise ValueError("No consumir un catálogo parcial como si estuviera completo")


def download(task: Task, root: Path, storage: Storage, *, page_budget: int = 25,
             profile: str | None = None, delay: float = 0.4) -> dict:
    """-> Avanzar una tarea hasta fin o presupuesto, sin confundir ambos estados."""
    final, manifest_path, partial, checkpoint = paths(root, task)
    final.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if (previous.get("identity") != task.identity or not final.exists()
                or final.stat().st_size != previous.get("bytes")):
            raise ValueError(f"Manifiesto incompatible o datos ausentes: {manifest_path}")
        return previous
    state = {"identity": task.identity, "task": json.loads(json.dumps(asdict(task))), "status": "partial",
             "rows": 0, "pages": 0, "bytes": 0, "next_page_token": None,
             "seen_token_hashes": [], "started_at_utc": utc_now(),
             "effective_command": list(task.command), "rejected_symbols": []}
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text())
        if state.get("identity") != task.identity:
            raise ValueError("Checkpoint de otra consulta")
    if state["bytes"] and not (partial.exists() or final.exists()):
        raise ValueError("Faltan los bytes confirmados por el checkpoint")
    if partial.exists():
        if partial.stat().st_size < state["bytes"]:
            raise ValueError("Archivo parcial truncado antes del checkpoint")
        # ~> Descartar solo bytes no confirmados de una escritura interrumpida.
        with partial.open("r+b") as sink:
            sink.truncate(state["bytes"])
    if state["status"] != "complete":
        for _ in range(page_budget):
            storage.check()
            while True:
                try:
                    response = call(tuple(state["effective_command"]), token=state["next_page_token"], profile=profile,
                                    delay=delay, binary=task.binary)
                except ApiError as exc:
                    # >> Un ticker inválido no debe impedir consultar los otros 49.
                    invalid = re.search(r"invalid symbol: ([A-Za-z0-9./_-]+)", str(exc))
                    command = state["effective_command"]
                    if state["next_page_token"] or not invalid or "--symbols" not in command:
                        raise
                    position = command.index("--symbols") + 1
                    symbols = command[position].split(",")
                    if invalid.group(1) not in symbols:
                        raise
                    symbols.remove(invalid.group(1))
                    state["rejected_symbols"].append({"symbol": invalid.group(1), "error": str(exc)})
                    if not symbols:
                        response = {task.key: {}, "next_page_token": None} if task.key else {}
                        break
                    command[position] = ",".join(symbols)
                    continue
                break
            if task.binary:
                # > Conservar el binario íntegro, sin pasarlo por un parser de JSON.
                import base64
                response = {"encoding": "base64", "content": base64.b64encode(response).decode()}
                count = 1
            else:
                count = record_count(response, task.key)
            if task.paginated and not isinstance(response, dict):
                raise ValueError("Respuesta paginada no es un objeto")
            token = response.get("next_page_token") if task.paginated else None
            token_hash = hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) and token else None
            if token and (not isinstance(token, str) or token_hash in state["seen_token_hashes"]):
                raise ValueError("Token de paginación repetido o inválido")
            packed = gzip.compress((json.dumps(response, ensure_ascii=False, separators=(",", ":"))
                                    + "\n").encode(), mtime=0)
            storage.check(len(packed))
            with partial.open("ab") as sink:
                sink.write(packed)
                sink.flush()
                os.fsync(sink.fileno())
            storage.written(len(packed))
            state.update(rows=state["rows"] + count, pages=state["pages"] + 1,
                         bytes=state["bytes"] + len(packed), next_page_token=token,
                         updated_at_utc=utc_now(), status="partial" if token else "complete")
            if token_hash:
                state["seen_token_hashes"].append(token_hash)
            atomic_json(checkpoint, state)
            if not token:
                break
    if state["status"] == "complete":
        if partial.exists():
            os.replace(partial, final)
        digest = hashlib.sha256()
        with final.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        manifest = {k: v for k, v in state.items() if k not in ("seen_token_hashes", "next_page_token")}
        manifest.update(data_file=final.name, sha256=digest.hexdigest(),
                        format="one_complete_api_response_per_jsonl_line",
                        completed_at_utc=utc_now(), count_key=task.key,
                        all_requested_symbols_accepted=not state["rejected_symbols"])
        atomic_json(manifest_path, manifest)
        checkpoint.unlink(missing_ok=True)
        return manifest
    return state
