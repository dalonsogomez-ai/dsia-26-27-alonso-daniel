"""Backend de lectura. El worker sirve un snapshot validado y estable."""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, perf_counter
from typing import Annotated, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from swarmtrade_app.ai_client import AIClient, AIClientError, AnalysisRequest

from .ai import client_from_env
from .journal import read_recent_events
from .observability import ObservabilityMiddleware, RequestMetrics, request_id
from .snapshot import Snapshot, read_snapshot

LOG = logging.getLogger("uvicorn.error").getChild("dsia")
STATIC = Path(__file__).with_name("static")
SYMBOL_PATTERN = r"^[A-Z0-9.]{1,32}$"
SYMBOL = re.compile(SYMBOL_PATTERN)
MAX_BODY_BYTES = 2048
DEFAULT_EVENTS, MAX_EVENTS = 20, 50


class AnalyzeBody(BaseModel):
    """Cuerpo de POST /api/v1/analyze. AnalysisRequest del II no admite pregunta libre."""

    model_config = ConfigDict(extra="forbid")
    symbol: Annotated[str, Field(pattern=SYMBOL_PATTERN)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def error_response(request: Request, status: int, code: str, message: str, **extra) -> JSONResponse:
    """Error tipado y estable: código, mensaje genérico y request_id; nunca rutas ni trazas."""
    return JSONResponse({"error": code, "detail": {"code": code, "message": message, **extra},
                         "request_id": request_id(request.scope)}, status_code=status)


async def read_limited_body(request: Request, limit: int = MAX_BODY_BYTES) -> bytes | None:
    """Leer el cuerpo sin pasar de ``limit`` bytes; ``None`` si lo supera (declarado o real)."""
    declared = request.headers.get("content-length")
    if declared is not None and (not declared.isdigit() or int(declared) > limit):
        return None
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > limit:
            return None
    return bytes(received)


def is_readable_file(path: Path | None) -> bool:
    try:
        return path is not None and path.is_file() and os.access(path, os.R_OK)
    except OSError:
        return False


def create_app(snapshot_path: Path | None = None, *, journal_path: Path | None = None,
               api_key: str | None = None, clock: Callable[[], datetime] = utc_now,
               ai_client_factory: Callable[[], AIClient] = client_from_env,
               metrics_clock: Callable[[], float] = monotonic) -> Starlette:
    @asynccontextmanager
    async def lifespan(app: Starlette):
        path = snapshot_path or Path(os.getenv("DSIA_SNAPSHOT", "runs/dsia-demo/snapshot.json"))
        journal = journal_path or (Path(os.environ["DSIA_JOURNAL"]) if os.getenv("DSIA_JOURNAL") else None)
        app.state.journal_path = journal
        app.state.api_key = api_key if api_key is not None else os.getenv("DSIA_API_KEY", "")
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

    async def analyze(request: Request) -> JSONResponse:
        started = perf_counter()
        expected = request.app.state.api_key
        if expected and not hmac.compare_digest(request.headers.get("x-api-key", "").encode("utf-8"),
                                                expected.encode("utf-8")):
            return error_response(request, 401, "unauthorized", "Falta la cabecera X-API-Key o no es válida.")
        media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if media_type != "application/json":
            return error_response(request, 415, "unsupported_media_type", "Envía el cuerpo como application/json.")
        body = await read_limited_body(request)
        if body is None:
            return error_response(request, 413, "payload_too_large",
                                  f"El cuerpo supera {MAX_BODY_BYTES} bytes.")
        try:
            payload = json.loads(body)
        except ValueError:
            return error_response(request, 400, "invalid_json", "El cuerpo no es JSON válido.")
        if not isinstance(payload, dict):
            return error_response(request, 400, "invalid_json", "El cuerpo debe ser un objeto JSON.")
        try:
            symbol = AnalyzeBody.model_validate(payload).symbol
        except ValidationError as exc:
            # > Solo ubicación y tipo: el valor recibido no se devuelve.
            fields = [{"loc": [str(part) for part in item["loc"]], "type": item["type"]} for item in exc.errors()]
            return error_response(request, 422, "validation_error",
                                  "Se espera {\"symbol\": \"AAPL\"} con ^[A-Z0-9.]{1,32}$.", fields=fields)
        snapshot: Snapshot | None = request.app.state.snapshot
        if snapshot is None:
            return error_response(request, 503, "snapshot_unavailable", "No hay un informe válido cargado.")
        row = next((item for item in snapshot.predictions if item.symbol == symbol), None)
        if row is None:
            return error_response(request, 404, "symbol_not_found", "El símbolo no está en el informe cargado.")
        summary = AnalysisRequest(as_of=str(snapshot.as_of), model=snapshot.model,
                                  horizon=snapshot.horizon_sessions, symbols=1,
                                  mean_prediction=row.predicted_return,
                                  validation_rmse=snapshot.validation[snapshot.model].rmse,
                                  data_kind=snapshot.data_kind)
        rid = request_id(request.scope)
        try:
            client = ai_client_factory()
            answer = await run_in_threadpool(client.analyze, summary)
        except AIClientError as exc:
            LOG.warning("analyze_unavailable request_id=%s error_type=%s", rid, type(exc).__name__)
            return error_response(request, 503, "ai_unavailable",
                                  "El proveedor de IA no está disponible. Inténtalo más tarde.")
        latency_ms = round((perf_counter() - started) * 1000, 3)
        LOG.info("analyze request_id=%s symbol=%s provider=%s model=%s latency_ms=%.2f",
                 rid, symbol, answer.provider, answer.model, latency_ms)
        return JSONResponse({
            "symbol": symbol, "predicted_return": row.predicted_return, "run_id": snapshot.run_id,
            "as_of": str(snapshot.as_of), "summary": answer.text, "provider": answer.provider,
            "model": answer.model, "request_id": rid, "latency_ms": latency_ms,
        }, headers={"Cache-Control": "no-store"})

    async def service_metrics(request: Request) -> JSONResponse:
        snapshot: Snapshot | None = request.app.state.snapshot
        return JSONResponse({**request.app.state.metrics.summary(),
                             "run_id": snapshot.run_id if snapshot else None},
                            headers={"Cache-Control": "no-store"})

    async def pipeline(request: Request) -> JSONResponse:
        raw = request.query_params.get("limit", str(DEFAULT_EVENTS))
        if not raw.isdigit() or not 1 <= int(raw) <= MAX_EVENTS:
            return error_response(request, 422, "invalid_limit", f"limit debe ser un entero entre 1 y {MAX_EVENTS}.")
        journal: Path | None = request.app.state.journal_path
        if journal is None:
            return error_response(request, 404, "journal_not_configured", "DSIA_JOURNAL no está configurado.")
        try:
            events, skipped = await run_in_threadpool(read_recent_events, journal, int(raw))
        except OSError as exc:
            LOG.warning("journal_unavailable error_type=%s", type(exc).__name__)
            return error_response(request, 503, "journal_unavailable", "No se puede leer el journal del lote.")
        return JSONResponse({
            "events": events, "returned": len(events), "skipped_lines": skipped,
            "last_run_id": next((event["run_id"] for event in reversed(events) if "run_id" in event), None),
        }, headers={"Cache-Control": "no-store"})

    metrics = RequestMetrics(clock=metrics_clock)
    application = Starlette(lifespan=lifespan, routes=[
        Route("/", dashboard), Route("/health", health),
        Route("/api/v1/snapshot", report), Route("/api/v1/snapshot/schema", schema),
        Route("/api/v1/predictions/{symbol}", prediction),
        Route("/api/v1/analyze", analyze, methods=["POST"]),
        Route("/api/v1/pipeline", pipeline),
        Route("/api/v1/metrics", service_metrics),
        Mount("/static", app=StaticFiles(directory=STATIC)),
    ], middleware=[Middleware(ObservabilityMiddleware, metrics=metrics)])
    application.state.metrics = metrics
    return application


app = create_app()
