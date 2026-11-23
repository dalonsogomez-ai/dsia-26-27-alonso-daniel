"""Backend de lectura. El worker sirve un snapshot validado y estable."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .snapshot import Snapshot, read_snapshot

LOG = logging.getLogger("uvicorn.error").getChild("dsia")
STATIC = Path(__file__).with_name("static")


def create_app(snapshot_path: Path | None = None) -> Starlette:
    @asynccontextmanager
    async def lifespan(app: Starlette):
        path = snapshot_path or Path(os.getenv("DSIA_SNAPSHOT", "runs/dsia-demo/snapshot.json"))
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
        snapshot = request.app.state.snapshot
        if snapshot is None:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready", "run_id": snapshot.run_id, "as_of": str(snapshot.as_of)})

    async def report(request: Request) -> JSONResponse:
        snapshot = request.app.state.snapshot
        if snapshot is None:
            return JSONResponse({"detail": {"code": "snapshot_unavailable",
                                            "message": "No hay un informe válido cargado."}}, status_code=503)
        return JSONResponse(snapshot.model_dump(mode="json"), headers={"Cache-Control": "no-store"})

    async def schema(request: Request) -> JSONResponse:
        return JSONResponse(Snapshot.model_json_schema())

    return Starlette(lifespan=lifespan, routes=[
        Route("/", dashboard), Route("/health", health),
        Route("/api/v1/snapshot", report), Route("/api/v1/snapshot/schema", schema),
        Mount("/static", app=StaticFiles(directory=STATIC)),
    ])


app = create_app()
