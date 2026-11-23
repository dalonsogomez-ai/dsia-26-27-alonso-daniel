"""Backend de lectura. El worker sirve un snapshot validado y estable."""

from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .observability import ObservabilityMiddleware, RequestMetrics, request_id
from .snapshot import Snapshot, read_snapshot

LOG = logging.getLogger("uvicorn.error").getChild("dsia")
STATIC = Path(__file__).with_name("static")
SYMBOL = re.compile(r"^[A-Z0-9.]{1,32}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    """Error tipado y estable: código, mensaje genérico y request_id; nunca rutas ni trazas."""
    return JSONResponse({"error": code, "detail": {"code": code, "message": message},
                         "request_id": request_id(request.scope)}, status_code=status)


def is_readable_file(path: Path | None) -> bool:
    try:
        return path is not None and path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def create_app(snapshot_path: Path | None = None, *, journal_path: Path | None = None,
               clock: Callable[[], datetime] = utc_now) -> Starlette:
    @asynccontextmanager
    async def lifespan(app: Starlette):
        path = snapshot_path or Path(os.getenv("DSIA_SNAPSHOT", "runs/dsia-demo/snapshot.json"))
        journal = journal_path or (Path(os.environ["DSIA_JOURNAL"]) if os.getenv("DSIA_JOURNAL") else None)
        app.state.journal_path = journal
        app.state.snapshot = None
        try:
            snapshot = read_snapshot(path)
        except (OSError, ValueError) as error:
            LOG.warning("snapshot_unavailable error_type=%s", type(error).__name__)
        else:
            app.state.snapshot = snapshot
            LOG.info("snapshot_ready run_id=%s as_of=%s kind=%s symbols=%s",
                     snapshot.run_id, snapshot.as_of, snapshot.data_kind, len(snapshot.predictions))
        yield

    async def dashboard(request: Request) -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    async def health(request: Request) -> JSONResponse:
        snapshot: Snapshot | None = request.app.state.snapshot
        checks = {
            "snapshot_loaded": snapshot is not None,
            "data_kind": snapshot.data_kind if snapshot else None,
            "as_of": str(snapshot.as_of) if snapshot else None,
            "snapshot_age_days": ((clock().astimezone(timezone.utc).date()
                                   - snapshot.generated_at.astimezone(timezone.utc).date()).days
                                  if snapshot else None),
            "journal_available": is_readable_file(request.app.state.journal_path),
        }
        headers = {"Cache-Control": "no-store"}
        if snapshot is None:
            return JSONResponse({"status": "unavailable", "checks": checks}, status_code=503, headers=headers)
        return JSONResponse({"status": "ready", "run_id": snapshot.run_id, "as_of": str(snapshot.as_of),
                             "checks": checks}, headers=headers)

    async def report(request: Request) -> JSONResponse:
        snapshot = request.app.state.snapshot
        if snapshot is None:
            return error_response(request, 503, "snapshot_unavailable", "No hay un informe válido cargado.")
        return JSONResponse(snapshot.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    async def schema(request: Request) -> JSONResponse:
        return JSONResponse(Snapshot.model_json_schema())

    async def prediction(request: Request) -> JSONResponse:
        symbol = request.path_params["symbol"]
        if not SYMBOL.fullmatch(symbol):
            return error_response(request, 422, "invalid_symbol",
                                  "El símbolo debe cumplir ^[A-Z0-9.]{1,32}$.")
        snapshot: Snapshot | None = request.app.state.snapshot
        if snapshot is None:
            return error_response(request, 503, "snapshot_unavailable", "No hay un informe válido cargado.")
        ranked = sorted(snapshot.predictions, key=lambda row: -row.predicted_return)
        position = next((index for index, row in enumerate(ranked, 1) if row.symbol == symbol), None)
        if position is None:
            return error_response(request, 404, "symbol_not_found", "El símbolo no está en el informe cargado.")
        inputs = {row.symbol: row.model_dump(mode="json") for row in snapshot.input_summary or ()}
        return JSONResponse({
            "run_id": snapshot.run_id, "as_of": str(snapshot.as_of), "model": snapshot.model,
            "horizon_sessions": snapshot.horizon_sessions, "symbol": symbol,
            "predicted_return": ranked[position - 1].predicted_return, "rank": position,
            "universe": len(ranked), "input": inputs.get(symbol),
        }, headers={"Cache-Control": "no-store"})

    metrics = RequestMetrics()
    application = Starlette(lifespan=lifespan, routes=[
        Route("/", dashboard), Route("/health", health),
        Route("/api/v1/snapshot", report), Route("/api/v1/snapshot/schema", schema),
        Route("/api/v1/predictions/{symbol}", prediction),
        Mount("/static", app=StaticFiles(directory=STATIC)),
    ], middleware=[Middleware(ObservabilityMiddleware, metrics=metrics)])
    application.state.metrics = metrics
    return application


app = create_app()
