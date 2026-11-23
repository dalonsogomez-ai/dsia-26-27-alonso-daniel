"""Prueba reproducible contra la app en ejecución, con Chromium real."""

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--chrome", help="Ruta a un navegador Chromium instalado")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--kind", default="Simulación sintética")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        with page.expect_response(lambda response: response.url.endswith("/api/v1/snapshot")) as pending:
            page.goto(args.url)
        response = pending.value
        assert response.ok
        payload = response.json()
        expect(page.get_by_role("status")).to_have_text(args.kind)
        expect(page.locator("#predictions tr")).to_have_count(len(payload["predictions"]))
        assert payload["run_id"] == page.locator("#run").text_content()
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
        symbol = ranked[0]["symbol"]
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
        assert errors == [], errors
        browser.close()
    print("OK · API y salud, ranking, filtro, cortes y vista móvil")


if __name__ == "__main__":
    main()
