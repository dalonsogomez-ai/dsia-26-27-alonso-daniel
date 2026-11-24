"""Prueba reproducible contra la app en ejecución, con Chromium real."""

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright

ANALYZE_TIMEOUT_MS = 200_000


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
        expect(page.locator("#ops-status")).to_have_text("Operativo (200)")
        expect(page.locator("#ops-run")).to_have_text(payload["run_id"])
        expect(page.locator("#ops-as-of")).to_have_text(payload["as_of"])
        expect(page.locator("#ops-requests")).not_to_have_text("—")
        pipeline = page.request.get(urljoin(args.url, "/api/v1/pipeline?limit=12"))
        if args.expect_pipeline or pipeline.ok:
            assert pipeline.ok, "El journal no se sirve por /api/v1/pipeline (DSIA_JOURNAL)"
            served = pipeline.json()
            expect(page.locator("#ops-events tr")).to_have_count(served["returned"])
            expect(page.locator("#ops-pipeline-note")).to_have_attribute("data-run-id", payload["run_id"])
            if final is not None:
                assert served["events"][-1] == {key: final[key] for key in served["events"][-1]}

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
        page.route("**/api/v1/analyze", lambda route: route.fulfill(
            status=503, content_type="application/json",
            body=json.dumps({"error": "ai_unavailable", "request_id": "simulado-503",
                             "detail": {"code": "ai_unavailable", "message": "Proveedor caído"}})))
        page.get_by_role("button", name="Explicar símbolo").click()
        expect(page.get_by_role("alert")).to_have_text("Error 503: Proveedor caído · request_id simulado-503")
        expect(page.locator("#analyze-result")).to_be_hidden()
        page.unroute("**/api/v1/analyze")
        # Se repite contra el backend real para que la captura muestre el análisis correcto.
        # > Un LLM real no repite el texto exacto: se compara con la respuesta de esta segunda llamada.
        with page.expect_response(lambda r: r.url.endswith("/api/v1/analyze"), timeout=ANALYZE_TIMEOUT_MS) as again:
            page.get_by_role("button", name="Explicar símbolo").click()
        assert again.value.ok, again.value.status
        expect(page.locator("#analyze-summary")).to_have_text(again.value.json()["summary"])
        expect(page.locator("#analyze-error")).to_be_hidden()

        page.get_by_role("searchbox", name="Filtrar símbolo").fill(symbol)
        expect(page.locator("#predictions tr")).to_have_count(1)
        expect(page.locator("#predictions tr")).to_contain_text(symbol)
        page.get_by_role("searchbox", name="Filtrar símbolo").fill("")
        page.get_by_text("Cortes temporales y purga de etiquetas").click()
        expect(page.locator("#splits tr")).to_have_count(3)
        if args.screenshot:
            page.screenshot(path=str(args.screenshot), full_page=True)
        page.set_viewport_size({"width": 390, "height": 840})
        assert page.locator("body").evaluate("(body) => body.scrollWidth") <= 390
        # El 503 simulado del análisis registra un error de recurso en consola; es el único admitido.
        unexpected = [text for text, url in errors if not ("503" in text and url.endswith("/api/v1/analyze"))]
        assert unexpected == [], unexpected
        browser.close()
    print("OK · API, salud y operación, datos de entrada, análisis y su error, ranking, filtro, cortes y móvil")


if __name__ == "__main__":
    main()
