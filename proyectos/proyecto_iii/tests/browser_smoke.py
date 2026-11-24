"""Prueba reproducible contra la app en ejecución, con Chromium real."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright

ANALYZE_TIMEOUT_MS = 200_000


def simulated_error(status: int, body: str):
    """> Manejador de page.route con un solo parámetro: Playwright pasa (route, request) según la aridad."""
    return lambda route: route.fulfill(status=status, content_type="application/json",
                                       headers={"Retry-After": "42"}, body=body)


# Topología fija del grafo de Operación (misma que FLOW en dashboard.js): nodo -> etapas del journal.
FLOW = {"source": ("generate_bars", "download_bars"), "validate_input": ("validate_input",),
        "prepare": ("prepare",), "train": ("train",), "holdout": ("holdout",),
        "infer_snapshot": ("infer_snapshot",), "publish_snapshot": ("publish_snapshot",), "serve": ()}
RUN = "a" * 64
OTHER = "b" * 64


def ev(stage: str, status: str, **extra) -> dict:
    return {"timestamp": "2026-11-24T10:00:00+00:00", "stage": stage, "status": status, **extra}


def run(*stages: str, run_id: str = RUN, last: str = "succeeded") -> list[dict]:
    """Eventos started/succeeded de cada etapa; la última termina en ``last``."""
    events = []
    for position, stage in enumerate(stages):
        extra = {"run_id": run_id} if stage == "publish_snapshot" else {}
        events.append(ev(stage, "started", **extra))
        status = last if position == len(stages) - 1 else "succeeded"
        if status != "started":
            events.append(ev(stage, status, duration_ms=1.0, **extra))
    return events


DEMO = ("generate_bars", "prepare", "train", "holdout", "infer_snapshot", "publish_snapshot")
ALPACA = ("download_bars", "validate_input", "prepare", "train", "holdout", "infer_snapshot", "publish_snapshot")
REFRESH = ("validate_input", "infer_snapshot", "publish_snapshot")
# > Casos degradados del modelo del grafo: (nombre, entrada de pipelineModel, estados esperados de los 8 nodos,
#   fragmento obligatorio en las alertas o None si no debe haber ninguna).
FLOW_CASES = [
    ("demo completa", {"journal": "ok", "events": run(*DEMO), "servedRunId": RUN, "health": "ready"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "succeeded", "serving"], None),
    ("alpaca completa", {"journal": "ok", "events": run(*ALPACA), "servedRunId": RUN, "health": "ready"},
     ["succeeded"] * 7 + ["serving"], None),
    ("journal ausente", {"journal": "missing", "servedRunId": RUN, "health": "ready"},
     ["unknown"] * 7 + ["unverified"], "Journal no configurado"),
    ("journal ilegible", {"journal": "unavailable", "servedRunId": RUN, "health": "ready"},
     ["unknown"] * 7 + ["unverified"], "Journal ilegible"),
    ("líneas descartadas", {"journal": "ok", "events": run(*DEMO), "skipped": 2, "servedRunId": RUN,
                            "health": "ready"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "succeeded", "serving"],
     "2 líneas del journal"),
    ("journal truncado", {"journal": "ok", "events": run(*ALPACA)[5:], "servedRunId": RUN, "health": "ready"},
     ["truncated", "truncated", "succeeded", "succeeded", "succeeded", "succeeded", "succeeded", "serving"],
     "Lote truncado"),
    ("run_id discrepante", {"journal": "ok", "events": run(*DEMO, run_id=OTHER), "servedRunId": RUN,
                            "health": "ready"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "succeeded", "mismatch"],
     "run_id discrepante"),
    ("run_id desconocido", {"journal": "ok", "events": run(*DEMO[:-1]), "servedRunId": RUN, "health": "ready"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "pending", "unverified"],
     "run_id desconocido"),
    ("publicación sin cierre", {"journal": "ok", "events": run(*DEMO, last="started"), "servedRunId": RUN,
                                "health": "ready"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "started", "unverified"],
     "run_id desconocido"),
    ("refresco de modelo entrenado", {"journal": "ok", "events": run(*REFRESH), "servedRunId": RUN,
                                      "health": "ready"},
     ["skipped", "succeeded", "reused", "reused", "reused", "succeeded", "succeeded", "serving"], "Refresco"),
    ("fallo al entrenar", {"journal": "ok", "events": run(*DEMO[:3], last="failed"), "servedRunId": RUN,
                           "health": "degraded"},
     ["succeeded", "skipped", "succeeded", "failed", "unreached", "unreached", "unreached", "unverified"],
     "run_id desconocido"),
    ("lote interrumpido", {"journal": "ok", "events": run(*DEMO[:3], last="started"), "servedRunId": RUN,
                           "health": "ready"},
     ["succeeded", "skipped", "succeeded", "started", "pending", "pending", "pending", "unverified"],
     "run_id desconocido"),
    ("dos lotes en la ventana", {"journal": "ok", "events": run(*DEMO, run_id=OTHER) + run(*REFRESH),
                                 "servedRunId": RUN, "health": "degraded"},
     ["skipped", "succeeded", "reused", "reused", "reused", "succeeded", "succeeded", "degraded"],
     "lote anterior"),
    ("refresco fallido en validate_input", {"journal": "ok", "events": run(*REFRESH[:1], last="failed"),
                                            "servedRunId": RUN, "health": "ready"},
     ["skipped", "failed", "unreached", "unreached", "unreached", "unreached", "unreached", "unverified"],
     "run_id desconocido"),
    ("sin snapshot servido", {"journal": "ok", "events": run(*DEMO), "servedRunId": None, "health": "unavailable"},
     ["succeeded", "skipped", "succeeded", "succeeded", "succeeded", "succeeded", "succeeded", "down"], None),
]


def expected_states(events: list[dict], served_run_id: str, health_status: str) -> dict[str, str]:
    """Estado esperado de cada nodo observado según los eventos reales del backend (último evento de la etapa)."""
    states = {}
    for node, stages in FLOW.items():
        seen = [event for event in events if event["stage"] in stages]
        if seen:
            states[node] = seen[-1]["status"]
    published = [event["run_id"] for event in events if event["stage"] == "publish_snapshot"
                 and event["status"] == "succeeded" and "run_id" in event]
    serving = "degraded" if health_status == "degraded" else "serving"
    states["serve"] = ("unverified" if not published else serving if published[-1] == served_run_id
                       else "mismatch")
    return states


def check_real_states(page, url: str, run_id: str) -> None:
    """Cada nodo con el estado del último evento real de su etapa; Servir API según /health y el journal."""
    served = page.request.get(urljoin(url, "/api/v1/pipeline?limit=20")).json()
    health = page.request.get(urljoin(url, "/health")).json()
    nodes = page.locator("#ops-graph .flow-node")
    expect(nodes).to_have_count(len(FLOW))
    assert nodes.evaluate_all("nodes => nodes.map(n => n.dataset.node)") == list(FLOW)
    for node, state in expected_states(served["events"], run_id, health["status"]).items():
        expect(page.locator(f'#ops-graph [data-node="{node}"]')).to_have_attribute("data-state", state)


def check_flow_model(page) -> None:
    for name, payload, states, alert in FLOW_CASES:
        model = page.evaluate("input => pipelineModel(input)", payload)
        got = [node["state"] for node in model["nodes"]]
        assert [node["id"] for node in model["nodes"]] == list(FLOW), name
        assert got == states, (name, got)
        alerts = " ".join(model["alerts"])
        assert (alert in alerts) if alert else not alerts, (name, model["alerts"])
        # > El aviso de refresco solo aparece si de verdad hay etapas reutilizadas.
        assert ("Refresco" in alerts) == ("reused" in states), (name, model["alerts"])


def check_flow_ui(page, url: str, served_run_id: str) -> None:
    """Estados degradados pintados en el navegador con /api/v1/pipeline simulado (no toca el backend)."""
    graph = page.locator("#ops-graph .flow-node")
    simulated = [
        ("journal ausente", 404, {"error": "journal_not_configured"}, "unknown", "Journal no configurado",
         "unverified"),
        ("journal ilegible", 503, {"error": "journal_unavailable"}, "unknown", "Journal ilegible", "unverified"),
        ("truncado", 200, {"events": run(*ALPACA)[5:], "returned": 9, "skipped_lines": 1,
                           "last_run_id": served_run_id}, "truncated", "Lote truncado", None),
        ("discrepante", 200, {"events": run(*DEMO, run_id=OTHER), "returned": 12, "skipped_lines": 0,
                              "last_run_id": OTHER}, "succeeded", "run_id discrepante", "mismatch"),
        ("refresco", 200, {"events": run(*REFRESH, run_id=served_run_id), "returned": 6, "skipped_lines": 0,
                           "last_run_id": served_run_id}, "skipped", "Refresco", None),
    ]
    for name, status, body, first_state, alert, serve in simulated:
        page.route("**/api/v1/pipeline*", simulated_error(status, json.dumps(body)))
        page.locator("#ops-refresh").click()
        expect(page.locator("#ops-flow-alerts")).to_contain_text(alert)
        expect(graph).to_have_count(len(FLOW))
        expect(graph.first).to_have_attribute("data-state", first_state)
        if serve:
            expect(page.locator('#ops-graph [data-node="serve"]')).to_have_attribute("data-state", serve)
        page.unroute("**/api/v1/pipeline*")
    # > De vuelta al backend real: estados restaurados y sin avisos (el lote demo completo no tiene ninguno).
    page.locator("#ops-refresh").click()
    expect(page.locator("#ops-flow-alerts li")).to_have_count(0)
    check_real_states(page, url, served_run_id)


def check_flow_keyboard(page) -> None:
    graph = page.locator("#ops-graph .flow-node")
    # > Una sola parada de tabulación para el grafo (tabindex itinerante) y flechas dentro.
    assert graph.evaluate_all("nodes => nodes.filter(n => n.tabIndex === 0).length") == 1
    graph.first.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#ops-graph .flow-node:focus")).to_have_attribute("data-node", "validate_input")
    page.keyboard.press("End")
    expect(page.locator("#ops-graph .flow-node:focus")).to_have_attribute("data-node", "serve")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator('#ops-graph [data-node="prepare"]')).to_have_attribute("aria-current", "true")
    expect(page.locator("#ops-graph-detail")).to_contain_text("Preparar")
    page.keyboard.press("End")
    page.keyboard.press("Space")
    expect(page.locator("#ops-graph-detail")).to_contain_text("run_id servido")


def check_flow_canvas(page, url: str, served_run_id: str) -> None:
    """Vista «Lienzo interactivo» (React Flow): estados del backend real, igual que la lista, teclado y vuelta."""
    page.locator("#ops-view-canvas").click()
    nodes = page.locator("#ops-canvas .react-flow__node")
    expect(nodes).to_have_count(len(FLOW))
    expect(page.locator("#ops-graph")).to_be_hidden()
    expect(page.locator("#ops-view-canvas")).to_have_attribute("aria-pressed", "true")
    assert nodes.evaluate_all("nodes => nodes.map(n => n.dataset.node)") == list(FLOW)
    served = page.request.get(urljoin(url, "/api/v1/pipeline?limit=20")).json()
    health = page.request.get(urljoin(url, "/health")).json()
    for node, state in expected_states(served["events"], served_run_id, health["status"]).items():
        expect(page.locator(f'#ops-canvas [data-node="{node}"]')).to_have_attribute("data-state", state)
    # > Los 8 estados del lienzo son los de la lista: ambos salen del mismo pipelineModel.
    listed = page.locator("#ops-graph .flow-node").evaluate_all("nodes => nodes.map(n => n.dataset.state)")
    assert nodes.evaluate_all("nodes => nodes.map(n => n.dataset.state)") == listed
    # > Textos de accesibilidad de React Flow en español (por defecto, en inglés y sobre mover y borrar nodos).
    described = page.locator("#ops-canvas").evaluate("canvas => canvas.textContent")
    assert "Intro o Espacio abre los eventos" in described and "Press enter" not in described
    # Teclado: una sola parada de tabulación, flechas, Inicio y Fin; Intro y Espacio abren el detalle compartido.
    assert nodes.evaluate_all("nodes => nodes.filter(n => n.tabIndex === 0).length") == 1
    nodes.first.focus()
    for key in ("ArrowRight", "ArrowRight", "ArrowLeft"):
        page.keyboard.press(key)
    expect(page.locator("#ops-canvas .react-flow__node:focus")).to_have_attribute("data-node", "validate_input")
    page.keyboard.press("End")
    expect(page.locator("#ops-canvas .react-flow__node:focus")).to_have_attribute("data-node", "serve")
    page.keyboard.press("Home")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.locator('#ops-canvas [data-node="prepare"]')).to_have_attribute("aria-current", "true")
    expect(page.locator('#ops-graph [data-node="prepare"]')).to_have_attribute("aria-current", "true")
    expect(page.locator("#ops-graph-detail")).to_contain_text("Preparar")
    page.keyboard.press("End")
    scrolled = page.evaluate("window.scrollY")
    page.keyboard.press("Space")
    expect(page.locator("#ops-graph-detail")).to_contain_text("run_id servido")
    # > El nodo es un div: Espacio selecciona sin desplazar la página.
    assert page.evaluate("window.scrollY") == scrolled
    # > Escape no deselecciona ni quita el foco (React Flow lo haría); la lista tampoco hace nada con él.
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    expect(page.locator("#ops-canvas .react-flow__node:focus")).to_have_attribute("data-node", "serve")
    expect(page.locator('#ops-canvas [data-node="serve"]')).to_have_attribute("aria-current", "true")
    # > Flechas y luego clic en otra etapa: sigue habiendo una sola parada de tabulación.
    page.keyboard.press("Home")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    page.locator('#ops-canvas [data-node="train"]').click()
    expect(page.locator("#ops-graph-detail")).to_contain_text("Entrenar")
    assert nodes.evaluate_all("nodes => nodes.filter(n => n.tabIndex === 0).map(n => n.dataset.node)") == ["train"]
    # > Ningún texto de accesibilidad en inglés en las etapas.
    assert set(nodes.evaluate_all("nodes => nodes.map(n => n.getAttribute('aria-roledescription'))")) == {"etapa"}
    # > Un estado degradado simulado también llega al lienzo; de vuelta al backend real, se restaura.
    discrepant = {"events": run(*DEMO, run_id=OTHER), "returned": 12, "skipped_lines": 0, "last_run_id": OTHER}
    page.route("**/api/v1/pipeline*", simulated_error(200, json.dumps(discrepant)))
    page.locator("#ops-refresh").click()
    expect(page.locator('#ops-canvas [data-node="serve"]')).to_have_attribute("data-state", "mismatch")
    expect(page.locator("#ops-flow-alerts")).to_contain_text("run_id discrepante")
    page.unroute("**/api/v1/pipeline*")
    page.locator("#ops-refresh").click()
    expect(page.locator("#ops-flow-alerts li")).to_have_count(0)
    expect(page.locator('#ops-canvas [data-node="serve"]')).to_have_attribute(
        "data-state", expected_states(served["events"], served_run_id, health["status"])["serve"])
    page.locator("#ops-view-list").click()
    expect(page.locator("#ops-canvas")).to_be_hidden()
    expect(page.locator("#ops-graph")).to_be_visible()


def check_canvas_fallback(browser, url: str) -> None:
    """Si React Flow no carga (fichero ausente o bloqueado), el panel vuelve a la lista y lo dice."""
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.route("**/static/vendor/xyflow-react.umd.js", lambda route: route.fulfill(status=404, body=""))
    page.goto(url)
    expect(page.locator("#ops-graph .flow-node")).to_have_count(len(FLOW))
    page.locator("#ops-view-canvas").click()
    expect(page.locator("#ops-canvas-note")).to_have_text("No se pudo cargar el lienzo interactivo; se muestra la lista.")
    expect(page.locator("#ops-view-list")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#ops-graph")).to_be_visible()
    expect(page.locator("#ops-canvas")).to_be_hidden()
    page.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--chrome", help="Ruta a un navegador Chromium instalado")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--expect-pipeline", action="store_true",
                        help="Exigir que /api/v1/pipeline (DSIA_JOURNAL) sirva el journal indicado")
    parser.add_argument("--kind", default="Simulación sintética")
    parser.add_argument("--api-key", help="Valor de X-API-Key si el servicio define DSIA_API_KEY")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        # > Registro explícito de violaciones de CSP en Chromium, además de los errores de consola.
        page.add_init_script("window.__cspViolations = [];"
                             "document.addEventListener('securitypolicyviolation',"
                             " e => window.__cspViolations.push(e.violatedDirective + ' ' + e.blockedURI));")
        errors = []
        page.on("pageerror", lambda error: errors.append((str(error), "")))
        # > Las violaciones de CSP llegan como errores de consola, no como pageerror.
        page.on("console", lambda message: errors.append((message.text, message.location.get("url", "")))
                if message.type == "error" else None)
        with page.expect_response(lambda response: response.url.endswith("/api/v1/snapshot")) as pending:
            page.goto(args.url)
        response = pending.value
        assert response.ok
        assert response.headers["content-security-policy"] == "default-src 'self'; frame-ancestors 'none'"
        payload = response.json()
        expect(page.get_by_role("status")).to_have_text(args.kind)
        expect(page.locator("#predictions tr")).to_have_count(len(payload["predictions"]))
        assert payload["run_id"] == page.locator("#run").text_content()
        final = None
        if args.journal:
            events = [json.loads(line) for line in args.journal.read_text().splitlines()]
            final = events[-1]
            assert (final["stage"], final["status"]) == ("publish_snapshot", "succeeded")
            assert final["run_id"] == payload["run_id"]
        ranked = sorted(payload["predictions"], key=lambda row: -row["predicted_return"])
        assert page.locator("#predictions th").all_text_contents() == [row["symbol"] for row in ranked]
        health = page.request.get(urljoin(args.url, "/health"))
        assert health.ok and health.json()["run_id"] == payload["run_id"]
        schema = page.request.get(urljoin(args.url, "/api/v1/snapshot/schema"))
        assert schema.ok and schema.json()["title"] == "Snapshot"

        # Operación: salud, métricas y journal servidos por la API real.
        # > «Degradado (200)» si la última llamada al proveedor falló o su configuración no es válida (R9).
        expect(page.locator("#ops-status")).to_have_text(re.compile(r"^(Operativo|Degradado) \(200\)$"))
        expect(page.locator("#ops-run")).to_have_text(payload["run_id"])
        expect(page.locator("#ops-as-of")).to_have_text(payload["as_of"])
        expect(page.locator("#ops-requests")).not_to_have_text("—")
        build = health.json()
        expect(page.locator("#ops-version")).to_have_text(f"v{build['version']} · commit {build['commit']}")
        expect(page.locator("#ops-ai")).to_contain_text(f"IA {build['checks']['ai_provider']} · configuración")
        # > Mismo limit que el panel: caben los 14 eventos del lote con Alpaca, download_bars incluido.
        pipeline = page.request.get(urljoin(args.url, "/api/v1/pipeline?limit=20"))
        if args.expect_pipeline or pipeline.ok:
            assert pipeline.ok, "El journal no se sirve por /api/v1/pipeline (DSIA_JOURNAL)"
            served = pipeline.json()
            expect(page.locator("#ops-events tr")).to_have_count(served["returned"])
            expect(page.locator("#ops-pipeline-note")).to_have_attribute("data-run-id", payload["run_id"])
            if final is not None:
                assert served["events"][-1] == {key: final[key] for key in served["events"][-1]}
            # Grafo: topología fija y estado de cada nodo igual al último evento real de su etapa.
            check_real_states(page, args.url, payload["run_id"])
            for node, stages in FLOW.items():
                if stages:
                    page.locator(f'#ops-graph [data-node="{node}"]').click()
                    count = sum(event["stage"] in stages for event in served["events"])
                    expect(page.locator("#ops-graph-detail .flow-events li")).to_have_count(max(count, 1))
            check_flow_keyboard(page)
            check_flow_ui(page, args.url, payload["run_id"])
            check_flow_canvas(page, args.url, payload["run_id"])
            check_canvas_fallback(browser, args.url)
        check_flow_model(page)
        # > Rama «Degradado (200)» (R9) con /health simulado en el navegador: en CI la salud real siempre
        #   está en «ready» (mock), así que sin esto nadie comprobaría cómo se ve la IA en fallo.
        degraded = {**build, "status": "degraded",
                    "checks": {**build["checks"], "ai_config": "ok", "ai_last_call": "failing:timeout"}}
        page.route("**/health", lambda route: route.fulfill(status=200, content_type="application/json",
                                                             body=json.dumps(degraded)))
        page.locator("#ops-refresh").click()
        expect(page.locator("#ops-status")).to_have_text("Degradado (200)")
        expect(page.locator("#ops-ai")).to_contain_text("configuración válida · última llamada fallida (timeout)")
        page.unroute("**/health")
        page.locator("#ops-refresh").click()
        expect(page.locator("#ops-status")).to_have_text(re.compile(r"^(Operativo|Degradado) \(200\)$"))

        # Producto: datos de entrada y análisis bajo demanda.
        expect(page.locator("#inputs tr")).to_have_count(len(payload.get("input_summary") or []))
        symbol = ranked[0]["symbol"]
        page.get_by_role("combobox", name="Símbolo").select_option(symbol)
        if args.api_key:
            page.locator("#analyze-key").fill(args.api_key)
        # > Con un LLM real el análisis tarda decenas de segundos; con mock, milisegundos.
        with page.expect_response(lambda r: r.url.endswith("/api/v1/analyze"), timeout=ANALYZE_TIMEOUT_MS) as analyzed:
            page.get_by_role("button", name="Explicar símbolo").click()
        answer = analyzed.value
        assert answer.ok, answer.status
        result = answer.json()
        assert result["symbol"] == symbol and result["run_id"] == payload["run_id"]
        expect(page.locator("#analyze-summary")).to_have_text(result["summary"])
        expect(page.locator("#analyze-meta")).to_contain_text(answer.headers["x-request-id"])
        expect(page.locator("#analyze-error")).to_be_hidden()
        # > Errores simulados en el navegador (no llegan al backend ni gastan cupo): proveedor caído y
        #   límite de uso (429 con Retry-After); el panel los muestra igual, con mensaje y request_id.
        for status, code, message in ((503, "ai_unavailable", "Proveedor caído"),
                                      (429, "rate_limited", "Demasiados análisis seguidos desde tu conexión: "
                                                            "máximo 5 por minuto. Reintenta en 42 s.")):
            body = json.dumps({"error": code, "request_id": f"simulado-{status}",
                               "detail": {"code": code, "message": message}})
            page.route("**/api/v1/analyze", simulated_error(status, body))
            page.get_by_role("button", name="Explicar símbolo").click()
            expect(page.get_by_role("alert")).to_have_text(f"Error {status}: {message} · request_id simulado-{status}")
            expect(page.locator("#analyze-result")).to_be_hidden()
            page.unroute("**/api/v1/analyze")
        # Se repite contra el backend real para que la captura muestre el análisis correcto.
        # > Un LLM real no repite el texto exacto: se compara con la respuesta de esta segunda llamada.
        with page.expect_response(lambda r: r.url.endswith("/api/v1/analyze"), timeout=ANALYZE_TIMEOUT_MS) as again:
            page.get_by_role("button", name="Explicar símbolo").click()
        assert again.value.ok, again.value.status
        expect(page.locator("#analyze-summary")).to_have_text(again.value.json()["summary"])
        expect(page.locator("#analyze-error")).to_be_hidden()
        # > Tras una llamada real correcta, /health vuelve a «ready» y el panel lo refleja (los errores de
        #   arriba eran simulados en el navegador y no llegaron al backend).
        expect(page.locator("#ops-status")).to_have_text("Operativo (200)")
        expect(page.locator("#ops-ai")).to_contain_text("última llamada correcta")

        page.get_by_role("searchbox", name="Filtrar símbolo").fill(symbol)
        expect(page.locator("#predictions tr")).to_have_count(1)
        expect(page.locator("#predictions tr")).to_contain_text(symbol)
        page.get_by_role("searchbox", name="Filtrar símbolo").fill("")
        page.get_by_text("Cortes temporales y purga de etiquetas").click()
        expect(page.locator("#splits tr")).to_have_count(3)
        if args.screenshot:
            page.screenshot(path=str(args.screenshot), full_page=True)
        # Tableta: 4 columnas, con el conector del final de cada fila oculto.
        page.set_viewport_size({"width": 900, "height": 900})
        columns = {round(node.bounding_box()["x"]) for node in page.locator("#ops-graph .flow-node").all()}
        assert len(columns) == 4, columns
        assert page.locator("#ops-graph li:nth-child(4) .edge").is_hidden()
        page.set_viewport_size({"width": 390, "height": 840})
        assert page.locator("body").evaluate("(body) => body.scrollWidth") <= 390
        # Móvil: el grafo pasa a una columna, cada nodo cabe en pantalla y sigue navegable con teclado.
        boxes = [box for box in (node.bounding_box() for node in page.locator("#ops-graph .flow-node").all())
                 if box is not None]
        assert len(boxes) == len(FLOW)
        assert len({round(box["x"]) for box in boxes}) == 1, "El grafo no está en una columna a 390 px"
        assert all(box["x"] >= 0 and box["x"] + box["width"] <= 390 for box in boxes)
        assert all(earlier["y"] < later["y"] for earlier, later in zip(boxes, boxes[1:]))
        check_flow_keyboard(page)
        if args.screenshot:
            page.locator("#ops").screenshot(path=str(args.screenshot.with_name("operacion-390.png")))
        # Móvil, lienzo: una columna dentro de la pantalla, sin scroll horizontal y sin atrapar el desplazamiento.
        page.locator("#ops-view-canvas").click()
        canvas = page.locator("#ops-canvas .react-flow__node")
        expect(canvas).to_have_count(len(FLOW))
        expect(page.locator("#ops-canvas .rf-wrap")).to_have_attribute("data-mode", "column")
        # > Se mide cuando termina el encuadre (fitView): durante el primer fotograma los nodos aún no escalan juntos.
        page.wait_for_function("() => { const view = document.querySelector('#ops-canvas .react-flow__viewport')"
                               ".style.transform; const xs = [...document.querySelectorAll('#ops-canvas"
                               " .react-flow__node')].map(n => Math.round(n.getBoundingClientRect().x));"
                               " const stable = window.__rfView === view; window.__rfView = view;"
                               " return stable && xs.length === 8 && new Set(xs).size === 1; }",
                               polling=250, timeout=5000)
        boxes = [box for box in (node.bounding_box() for node in canvas.all()) if box is not None]
        assert len(boxes) == len(FLOW)
        assert len({round(box["x"]) for box in boxes}) == 1, ("El lienzo no está en una columna a 390 px", boxes)
        assert all(box["x"] >= 0 and box["x"] + box["width"] <= 390 for box in boxes)
        assert page.locator("body").evaluate("(body) => body.scrollWidth") <= 390
        # > Sin atrapar el desplazamiento: sobre el lienzo, el dedo mueve la página en vertical.
        assert page.locator("#ops-canvas .react-flow__pane").evaluate("pane => getComputedStyle(pane).touchAction") == "pan-y"
        if args.screenshot:
            page.locator("#ops-canvas").screenshot(path=str(args.screenshot.with_name("operacion-lienzo-390.png")))
        page.locator("#ops-view-list").click()
        assert page.evaluate("window.__cspViolations") == [], page.evaluate("window.__cspViolations")
        # Los errores simulados (503 y 429 del análisis; 404 y 503 del journal) registran un error de recurso
        # en consola; son los únicos admitidos.
        allowed = {"/api/v1/analyze": ("503", "429"), "/api/v1/pipeline?limit=20": ("404", "503")}
        unexpected = [text for text, url in errors
                      if not any(url.endswith(path) and any(code in text for code in codes)
                                 for path, codes in allowed.items())]
        assert unexpected == [], unexpected
        browser.close()
    print("OK · API, salud y operación, grafo del lote (estados reales, degradados, teclado y CSP), lienzo de"
          " React Flow (mismos estados, teclado, degradado, vuelta a la lista si no carga), datos de entrada,"
          " análisis y su error, ranking, filtro, cortes y móvil a 390 px")


if __name__ == "__main__":
    main()
