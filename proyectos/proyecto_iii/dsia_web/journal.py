"""Lectura acotada y tolerante del journal JSONL del lote para la API de operación."""

from __future__ import annotations

import json
import os
from pathlib import Path

MAX_JOURNAL_BYTES = 64 * 1024
MAX_TEXT = 128
# > Lista blanca: solo campos de etapa conocidos; cualquier otro (p. ej. una ruta) se descarta.
EVENT_FIELDS = ("timestamp", "stage", "status", "duration_ms", "run_id", "error_type",
                "rows", "symbols", "input_sha256")


def _clean(entry: object) -> dict | None:
    if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in ("stage", "status")):
        return None
    event = {}
    for key in EVENT_FIELDS:
        value = entry.get(key)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)) or (isinstance(value, str) and len(value) <= MAX_TEXT):
            event[key] = value
    return event


def read_recent_events(path: Path, limit: int, max_bytes: int = MAX_JOURNAL_BYTES) -> tuple[list[dict], int]:
    """Últimos ``limit`` eventos válidos de los últimos ``max_bytes`` del archivo y nº de líneas descartadas."""
    with path.open("rb") as stream:
        size = stream.seek(0, os.SEEK_END)
        start = max(0, size - max_bytes)
        stream.seek(start)
        lines = stream.read(max_bytes).split(b"\n")
    if start > 0:
        lines = lines[1:]  # la primera línea puede estar cortada por la ventana
    events, skipped = [], 0
    for raw in lines:
        if not raw.strip():
            continue
        try:
            event = _clean(json.loads(raw))
        except ValueError:
            event = None
        if event is None:
            skipped += 1
        else:
            events.append(event)
    return events[-limit:], skipped
