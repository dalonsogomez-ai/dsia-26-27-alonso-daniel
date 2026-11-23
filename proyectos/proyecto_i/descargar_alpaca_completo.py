"""-> Amplía la extracción a las familias de Market Data disponibles en la CLI.

> python descargar_alpaca_completo.py --end 2026-10-18 --run
>> Sin --run solo muestra el plan; --families permite priorizar colecciones.
=> El resultado separa completo, parcial, denegado y fallido; no promete todo Alpaca.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import sys
import subprocess

from alpaca_io import (ApiError, DiskLimit, Storage, Task, atomic_json, call,
                       download, paths, read_pages, utc_now)


HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
FAMILIES = ("referencias", "noticias", "acciones_corporativas", "acciones_actuales",
            "acciones_historicas", "crypto", "contratos_opciones", "cadenas_opciones",
            "opciones", "forex", "renta_fija", "logos", "feeds_adicionales")


def chunks(values: list[str], size: int = 50):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def end_timestamp(day: date) -> str:
    """> Final inclusivo que incluye todo el último día UTC, sin solapar el siguiente."""
    return day.isoformat() + "T23:59:59.999999Z"


def months(start: date, end: date):
    current = start.replace(day=1)
    while current <= end:
        following = (current.replace(year=current.year + 1, month=1) if current.month == 12
                     else current.replace(month=current.month + 1))
        yield current.strftime("%Y-%m"), max(current, start), min(following - timedelta(days=1), end)
        current = following


def news_tasks(end: date, legacy: Path):
    """~> Reutilizar solo meses antiguos con datos y cobertura temporal comprobables."""
    for name, start, last in reversed(list(months(date(2015, 1, 1), end))):
        manifest = legacy / "noticias" / f"{name}.manifest.json"
        if manifest.exists():
            from auditar_alpaca import inspect_manifest
            old = json.loads(manifest.read_text())
            data = manifest.parent / old.get("data_file", "missing")
            if (old.get("mode") == "news" and old.get("start") == start.isoformat() + "T00:00:00Z"
                    and old.get("end", "") >= end_timestamp(last) and data.is_file()
                    and inspect_manifest(manifest, deep=True)["valid"]):
                continue
        yield Task("noticias", name, ("data", "news", "--start", start.isoformat() + "T00:00:00Z",
                   "--end", end_timestamp(last), "--sort", "asc", "--limit", "50",
                   "--include-content"), "news", True, "news")


def reference_tasks(end: date):
    for name, command in [
        ("reloj", ("clock",)),
        ("relojes_mercados", ("clock", "markets", "--markets", "XNYS,XNAS")),
        ("calendario", ("calendar", "--start", "1970-01-01", "--end", "2029-12-31")),
        ("exchanges", ("data", "meta", "exchanges")),
        ("opciones_exchanges", ("data", "option", "exchanges")),
    ]:
        yield Task("referencias", name, command)
    for market in ("XNYS", "XNAS"):
        yield Task("referencias", f"calendario_{market}", ("calendar", "market", "--market", market,
                   "--start", "1970-01-01", "--end", "2029-12-31"))
    for tick in ("trade", "quote"):
        for tape in ("A", "B", "C"):
            yield Task("referencias", f"{tick}_{tape}", ("data", "meta", "conditions",
                       "--ticktype", tick, "--tape", tape))
        yield Task("referencias", f"opciones_{tick}", ("data", "option", "conditions", "--ticktype", tick))
    for by in ("volume", "trades"):
        yield Task("referencias", f"activos_{by}", ("data", "screener", "most-actives", "--by", by,
                   "--top", "100"))
    for market in ("stocks", "crypto"):
        yield Task("referencias", f"movers_{market}", ("data", "screener", "movers", "--market-type", market,
                   "--top", "50"))


def stock_tasks(assets: list[dict], end: date):
    """-> Mantener OTC como familia con permiso comprobado, sin borrarlo del universo."""
    symbols = sorted({a["symbol"] for a in assets if a.get("class") == "us_equity"
                      and a.get("exchange") != "OTC" and a.get("symbol")},
                     key=lambda s: (not bool(re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", s)), s))
    active = sorted({a["symbol"] for a in assets if a.get("class") == "us_equity"
                     and a.get("exchange") != "OTC" and a.get("status") == "active" and a.get("symbol")})
    for index, group in enumerate(chunks(active)):
        for product, key in (("multi-snapshots", None), ("latest-bars", "bars"),
                             ("latest-quotes", "quotes"), ("latest-trades", "trades")):
            yield Task("acciones_actuales", f"{product}_{index:04d}",
                       ("data", product, "--symbols", ",".join(group), "--feed", "iex"), key,
                       access=f"stocks_latest_{product}_iex")
    # > Barras diarias en sus cuatro ajustes y granularidad mínima agregada 1Min.
    products = [("multi-bars", "bars", "1Day", "split"), ("auctions", "auctions", None, None),
                ("multi-trades", "trades", None, None), ("multi-quotes", "quotes", None, None),
                ("multi-bars", "bars", "1Min", "raw")]
    products += [("multi-bars", "bars", "1Day", a) for a in ("raw", "dividend", "all")]
    for index, group in enumerate(chunks(symbols)):
        for product, key, timeframe, adjustment in products:
            # ~> El catálogo nuevo puede cambiar el reparto; los hashes evitan mezclar lotes.
            command = ("data", product, "--symbols", ",".join(group), "--start", "2016-01-01",
                       "--end", end_timestamp(end), "--feed", "sip", "--limit", "10000")
            if timeframe:
                command += ("--timeframe", timeframe, "--adjustment", adjustment)
            yield Task("acciones_historicas", f"{key}_{timeframe or 'tick'}_{adjustment or 'raw'}_{index:04d}",
                       command, key, True, f"stocks_{key}_sip")


def crypto_tasks(assets: list[dict], end: date):
    symbols = sorted({a["symbol"] for a in assets if a.get("symbol")})
    for location in ("us", "us-1", "eu-1"):
        for index, group in enumerate(chunks(symbols, 20)):
            for product, key in (("snapshots", "snapshots"), ("latest-bars", "bars"),
                                 ("latest-quotes", "quotes"), ("latest-trades", "trades"),
                                 ("orderbooks", "orderbooks")):
                prefix = ("data", "crypto-orderbook") if product == "orderbooks" else ("data", "crypto", product)
                yield Task("crypto", f"{location}_{product}_{index:03d}",
                           prefix + ("--symbols", ",".join(group), "--loc", location), key,
                           access=f"crypto_{location}_{product}")
            for product, timeframe in (("bars", "1Day"), ("bars", "1Min"), ("trades", None), ("quotes", None)):
                # > Las ubicaciones Kraken tienen su propia cobertura temporal.
                start = "2021-01-01" if location == "us" else "2025-10-14"
                command = ("data", "crypto", product, "--symbols", ",".join(group), "--loc", location,
                           "--start", start, "--end", end_timestamp(end), "--sort", "asc", "--limit", "10000")
                if timeframe:
                    command += ("--timeframe", timeframe)
                yield Task("crypto", f"{location}_{product}_{timeframe or 'tick'}_{index:03d}",
                           command, product, True, f"crypto_{location}_{product}")


def option_catalog_tasks():
    # >> Sin estas fechas explícitas la API devuelve solo vencimientos hasta el fin de semana.
    for status in ("active", "inactive"):
        yield Task("contratos_opciones", status, ("option", "contracts", "--status", status,
                   "--expiration-date-gte", "1970-01-01", "--expiration-date-lte", "2099-12-31",
                   "--show-deliverables", "--limit", "10000"), "option_contracts", True, "option_contracts")


def option_tasks(assets: list[dict], root: Path, end: date, catalog_names: set[str] | None = None):
    for asset in sorted(assets, key=lambda a: (a.get("status") != "active", a.get("symbol", ""))):
        if "has_options" in asset.get("attributes", []):
            for feed in ("indicative", "opra"):
                yield Task("cadenas_opciones", f"{asset['symbol']}_{feed}",
                           ("data", "option", "chain", "--underlying-symbol", asset["symbol"],
                            "--feed", feed, "--limit", "1000"), "snapshots", True, f"option_chain_{feed}")
    # > Procesar todos los contratos descubiertos, incluidos los inactivos, por streaming.
    for catalog in option_catalog_tasks():
        if catalog_names is not None and catalog.name not in catalog_names:
            continue
        data, manifest, _, _ = paths(root, catalog)
        if not manifest.exists() or not data.exists():
            continue
        for page_number, page in enumerate(read_pages(data)):
            contracts = page["option_contracts"]
            for index, group in enumerate(chunks([c["symbol"] for c in contracts])):
                tag = f"{catalog.name}_{page_number:05d}_{index:03d}"
                for product, key, timeframe in (("bars", "bars", "1Day"), ("bars", "bars", "1Min"),
                                                ("trades", "trades", None)):
                    command = ("data", "option", product, "--symbols", ",".join(group),
                               "--start", "2024-02-01", "--end", end_timestamp(end),
                               "--sort", "asc", "--limit", "10000")
                    if timeframe:
                        command += ("--timeframe", timeframe)
                    yield Task("opciones", f"{tag}_{product}_{timeframe or 'tick'}", command, key, True,
                               f"option_historical_{product}")
                if catalog.name == "active":
                    for product, key in (("snapshot", "snapshots"), ("latest-quotes", "quotes"),
                                         ("latest-trades", "trades")):
                        yield Task("opciones", f"{tag}_{product}",
                                   ("data", "option", product, "--symbols", ",".join(group),
                                    "--feed", "indicative"), key, product == "snapshot",
                                   f"option_{product}_indicative")


def options_after_catalogs(root: Path, end: date, denied: dict):
    """> Crear tareas conforme termina cada catálogo, sin esperar a toda la descarga."""
    handled = set()
    while len(handled) < 2:
        if "option_contracts" in denied:
            return
        for catalog in option_catalog_tasks():
            if catalog.name in handled:
                continue
            data, manifest, _, _ = paths(root, catalog)
            if manifest.exists() and data.exists():
                yield from option_tasks([], root, end, {catalog.name})
                handled.add(catalog.name)
            elif manifest.with_suffix(".error.json").exists():
                handled.add(catalog.name)
        if len(handled) < 2:
            yield None


def work_queue(source, root: Path, denied: dict):
    """~> Repartir turnos entre tareas nuevas y parciales sin esperar a una vuelta completa."""
    pending = deque()
    exhausted = False
    turn = 0
    while not exhausted or pending:
        if pending and (exhausted or turn % 4 == 3):
            task = pending.popleft()
        else:
            try:
                task = next(source)
            except StopIteration:
                exhausted = True
                continue
        turn += 1
        yield task
        if task is not None and task.access not in denied:
            _, manifest, _, checkpoint = paths(root, task)
            if checkpoint.exists() and not manifest.with_suffix(".error.json").exists():
                pending.append(task)


def other_tasks(assets: list[dict], end: date, currency_pairs: str, isins: str):
    for product in ("latest", "rates"):
        command = ("data", "forex", product, "--currency-pairs", currency_pairs)
        if product == "rates":
            command += ("--start", "2016-01-01", "--end", end_timestamp(end), "--timeframe", "1Min", "--limit", "10000")
        yield Task("forex", product, command, "rates", product == "rates", "forex")
    for product, key in (("latest-prices", "prices"), ("latest-quotes", "quotes")):
        yield Task("renta_fija", product, ("data", "fixed-income", product, "--isins", isins), key,
                   access="fixed_income")
    for asset in assets:
        if asset.get("symbol"):
            yield Task("logos", re.sub(r"[^A-Za-z0-9_.-]", "_", asset["symbol"]),
                       ("data", "logo", "--symbol", asset["symbol"], "--placeholder=false"),
                       access="logos", binary=True)
    # > Comprobar cada feed por endpoint antes de planificar el universo completo.
    for feed in ("otc", "boats", "overnight", "iex"):
        symbols = sorted({a["symbol"] for a in assets if a.get("symbol") and
                          (a.get("exchange") == "OTC" if feed == "otc" else a.get("exchange") != "OTC")})
        for product, key in (("multi-bars", "bars"), ("multi-trades", "trades"), ("multi-quotes", "quotes")):
            for index, group in enumerate(chunks(symbols)):
                command = ("data", product, "--symbols", ",".join(group), "--feed", feed,
                           "--start", "2016-01-01", "--end", end_timestamp(end), "--limit", "10000")
                if key == "bars":
                    command += ("--timeframe", "1Min", "--adjustment", "raw")
                yield Task("feeds_adicionales", f"{feed}_{key}_{index:04d}", command, key, True,
                           f"stocks_{key}_{feed}")


def task_sources(assets: list[dict], crypto: list[dict], args: argparse.Namespace, denied: dict):
    """-> Generar tareas bajo demanda para no cargar millones de contratos en RAM."""
    sources = {"referencias": reference_tasks(args.end), "noticias": news_tasks(args.end, RAW / "masivo")}
    sources["acciones_corporativas"] = iter([Task("acciones_corporativas", "ampliacion", ("data", "corporate-actions", "--start", "2026-09-29",
                   "--end", args.end.isoformat(), "--sort", "asc", "--limit", "1000", "--data-quality", "all"),
                   "corporate_actions", True, "corporate_actions")])
    def only(family, iterator):
        return (t for t in iterator if t.family == family)
    for family in ("acciones_actuales", "acciones_historicas"):
        sources[family] = only(family, stock_tasks(assets, args.end))
    sources["crypto"] = crypto_tasks(crypto, args.end)
    sources["contratos_opciones"] = option_catalog_tasks()
    sources["cadenas_opciones"] = only("cadenas_opciones", option_tasks(assets, args.output, args.end, set()))
    sources["opciones"] = (options_after_catalogs(args.output, args.end, denied)
                           if "contratos_opciones" in args.families else option_tasks([], args.output, args.end))
    for family in ("forex", "renta_fija", "logos", "feeds_adicionales"):
        sources[family] = only(family, other_tasks(assets + crypto, args.end, args.currency_pairs, args.isins))
    return {f: sources[f] for f in args.families}


@contextmanager
def lock(path: Path):
    """> Bloqueo del sistema operativo; se libera incluso si el proceso termina."""
    import fcntl
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Ya hay una extracción usando este directorio") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--profile", help="Omitir conserva la sesión ya activa en la CLI")
    parser.add_argument("--families", default=",".join(FAMILIES))
    parser.add_argument("--page-budget", type=int, default=25, help="Páginas por turno de una tarea")
    parser.add_argument("--max-rounds", type=int, default=1, help="0 repite mientras haya progreso")
    parser.add_argument("--max-tasks", type=int, help="Limitar una comprobación parcial")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--max-gb", type=float, default=50)
    parser.add_argument("--min-free-gb", type=float, default=20)
    parser.add_argument("--currency-pairs", default="EUR/USD,GBP/USD,USD/JPY,USD/CHF,AUD/USD,USD/CAD,NZD/USD")
    parser.add_argument("--isins", default="US912797KJ59", help="ISINs explícitos; no implica todo el universo de renta fija")
    args = parser.parse_args()
    args.families = args.families.split(",")
    if set(args.families) - set(FAMILIES):
        parser.error("Familia desconocida")
    if args.end >= datetime.now(timezone.utc).date():
        parser.error("--end debe ser un día UTC finalizado")
    if (args.page_budget < 1 or args.delay < 0.35 or args.max_gb <= 0 or args.min_free_gb <= 0
            or args.max_rounds < 0 or (args.max_tasks is not None and args.max_tasks < 1)):
        parser.error("Límites inválidos; delay mínimo 0.35 s")
    args.output = (args.output or RAW / "masivo" / f"ampliacion_{args.end}").expanduser().resolve()
    if not args.output.is_relative_to((RAW / "masivo").resolve()):
        parser.error("--output debe estar dentro de data/raw/masivo para aplicar el presupuesto global")
    return args


def catalog(root: Path, name: str, command: tuple[str, ...], args: argparse.Namespace, storage: Storage):
    task = Task("catalogos", name, command)
    download(task, root, storage, profile=args.profile, delay=args.delay)
    data, _, _, _ = paths(root, task)
    return next(read_pages(data))


def execute(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    storage = Storage(RAW / "masivo", args.max_gb, args.min_free_gb)
    storage.check()
    run_path = args.output / "ejecucion.json"
    if run_path.exists():
        previous = json.loads(run_path.read_text())
        if previous.get("profile") != (args.profile or "CLI active"):
            raise ValueError("Usar otra carpeta al cambiar de perfil; los permisos pertenecen a esa sesión")
    assets = catalog(args.output, "us_equity", ("asset", "list", "--asset-class", "us_equity"), args, storage)
    crypto = catalog(args.output, "crypto", ("asset", "list", "--asset-class", "crypto"), args, storage)
    atomic_json(run_path, {"started_at_utc": utc_now(), "pid": os.getpid(),
                "end": args.end.isoformat(), "families": args.families, "page_budget": args.page_budget,
                "max_gb": args.max_gb, "min_free_gb": args.min_free_gb, "profile": args.profile or "CLI active",
                "equity_assets": len(assets), "crypto_assets": len(crypto), "private_account_data": False,
                "python": sys.version, "cli_version": subprocess.run(["alpaca", "--version"],
                    capture_output=True, text=True, check=True).stdout.strip(),
                "code_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                for name in ("alpaca_io.py", "descargar_alpaca_completo.py")}})
    permissions_path = args.output / "permisos.json"
    denied = json.loads(permissions_path.read_text()) if permissions_path.exists() else {}
    attempts = 0
    for round_number in itertools.count(1):
        queues = {f: work_queue(source, args.output, denied)
                  for f, source in task_sources(assets, crypto, args, denied).items()}
        atomic_json(args.output / "plan_resumen.json", {"updated_at_utc": utc_now(),
                    "round": round_number, "tasks": "dynamic", "families": args.families,
                    "options_depend_on_completed_contract_catalog": True,
                    "limits": ["forex pairs and fixed income ISINs are explicit subsets",
                               "WebSocket/SSE future events cannot be backfilled through REST",
                               "no historical option quote endpoint in CLI/API reference"]})
        counts = Counter()
        progress = pending = failures = consecutive_transient_failures = 0
        stop = False
        # ~> Alternar familias para que los ticks no monopolicen todas las peticiones.
        for group in itertools.zip_longest(*(queues[f] for f in FAMILIES if f in queues)):
            for task in group:
                if task is None:
                    continue
                if task.access and task.access in denied:
                    counts["permission_blocked"] += 1
                    continue
                final, manifest, _, checkpoint = paths(args.output, task)
                if manifest.exists():
                    saved = json.loads(manifest.read_text())
                    if final.exists() and final.stat().st_size == saved.get("bytes"):
                        counts["complete_with_rejections" if saved.get("rejected_symbols") else "complete"] += 1
                        continue
                before = json.loads(checkpoint.read_text()).get("pages", 0) if checkpoint.exists() else 0
                attempts += 1
                try:
                    budget = min(args.page_budget, 2) if task.family == "contratos_opciones" else args.page_budget
                    state = download(task, args.output, storage, page_budget=budget,
                                     profile=args.profile, delay=args.delay)
                except DiskLimit:
                    raise
                except (ApiError, OSError, ValueError) as exc:
                    if isinstance(exc, ApiError) and exc.status == 401:
                        raise
                    status = "forbidden" if isinstance(exc, ApiError) and exc.status == 403 else "error"
                    detail = {"task": task.name, "family": task.family, "access": task.access,
                              "status": status, "http_status": getattr(exc, "status", 0),
                              "error": str(exc), "checked_at_utc": utc_now()}
                    atomic_json(manifest.with_suffix(".error.json"), detail)
                    if status == "forbidden" and task.access:
                        denied[task.access] = detail
                        atomic_json(permissions_path, denied)
                    counts[status] += 1
                    failures += 1
                    print(json.dumps(detail, ensure_ascii=False), flush=True)
                    transient = isinstance(exc, OSError) or (isinstance(exc, ApiError) and
                                (exc.status in (0, 429, 500, 502, 503, 504)))
                    consecutive_transient_failures = consecutive_transient_failures + 1 if transient else 0
                    if consecutive_transient_failures >= 3:
                        raise RuntimeError("Tres fallos de conectividad consecutivos; reanudar tras recuperar la conexión")
                else:
                    consecutive_transient_failures = 0
                    manifest.with_suffix(".error.json").unlink(missing_ok=True)
                    counts["complete_with_rejections" if state["status"] == "complete" and state.get("rejected_symbols")
                           else state["status"]] += 1
                    progress += state["pages"] - before
                    pending += state["status"] == "partial"
                    print(f"{utc_now()} {task.family}/{task.name}: {state['status']}; "
                          f"{state['rows']:,} registros; {state['pages']} páginas", flush=True)
                atomic_json(args.output / "estado.json", {"updated_at_utc": utc_now(), "pid": os.getpid(),
                            "round": round_number, "last_task": task.name, "counts_this_round": dict(counts),
                            "planned_tasks": "dynamic", "attempted_this_process": attempts,
                            "status": "running", "all_data_extracted": False})
                if args.max_tasks is not None and attempts >= args.max_tasks:
                    stop = True
                    break
            if stop:
                break
        pending = sum(1 for p in args.output.rglob("*.checkpoint.json") if p.parent.name in args.families)
        if stop or (args.max_rounds and round_number >= args.max_rounds) or not progress:
            status = "partial" if stop or pending else "finished_with_limits" if denied or failures else "planned_tasks_complete"
            atomic_json(args.output / "estado.json", {"updated_at_utc": utc_now(), "pid": os.getpid(),
                        "round": round_number, "counts_this_round": dict(counts), "planned_tasks": "dynamic",
                        "status": status, "all_data_extracted": False})
            return 1 if failures or pending or stop or denied else 0


def main() -> int:
    args = arguments()
    if not args.run:
        print(json.dumps({"end": args.end.isoformat(), "output": str(args.output), "families": args.families,
                          "page_budget": args.page_budget, "run": False}, indent=2))
        return 0
    try:
        args.output.mkdir(parents=True, exist_ok=True)
        with lock(RAW / "masivo" / "extraccion_global.lock"):
            return execute(args)
    except KeyboardInterrupt:
        atomic_json(args.output / "interrupcion.json", {"at_utc": utc_now(), "status": "interrupted",
                    "error": "Interrupción solicitada", "all_data_extracted": False})
        return 130
    except (ApiError, DiskLimit, OSError, ValueError, RuntimeError) as exc:
        atomic_json(args.output / "interrupcion.json", {"at_utc": utc_now(), "error": str(exc),
                    "status": "stopped", "all_data_extracted": False})
        print(f"Extracción detenida: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
