# Uso de IA en el Proyecto III

`->` Registro según la política de uso de IA de la asignatura y la plantilla de la sesión de IA asistida: una entrada por tarea relevante con herramienta y modelo, objetivo, resumen de la petición, lo aceptado, lo rechazado, la verificación y los commits. El código entregado es del autor, que revisó cada cambio antes de integrarlo.

`>>` El proveedor de IA **en ejecución** es otro asunto: la explicación de la demo y del despliegue la produce el cliente `mock` del Proyecto II (`mock-determinista-v1`), sin llamar a un modelo externo; el adaptador Hugging Face heredado está documentado en el [AI_USAGE del II](../proyecto_ii/AI_USAGE.md). Las métricas y las estimaciones proceden del pipeline sklearn y de sus artefactos, no del texto de un asistente. No se enviaron datos de Alpaca al proveedor de IA de la aplicación: a `AIClient` solo viajan agregados del informe.

`>>` Antecedentes del núcleo que amplía el III, registrados en el AI_USAGE del II: el repositorio de investigación [`dalonsogomez-ai/swarmtrader`](https://github.com/dalonsogomez-ai/swarmtrader) se crea el 11/11/2026 (código reutilizado: v1.4.0, commit `5642dda`); el II se escribe el 12/11/2026 con OpenAI Codex (modelo gpt-6.1-sol) y la extracción de Alpaca se audita el 19/11/2026 con el mismo modelo.

## 2026-11-23 — Integración del III en el repositorio de entrega

- **Herramienta:** OpenAI Codex · **modelo:** `gpt-6.2-sol`
- **Objetivo:** convertir el núcleo del II en una aplicación de extremo a extremo dentro del repositorio de entrega.
- **Prompts (resumen):** recuperar las fuentes y decisiones del II → diseñar el snapshot versionado → implementar lote, API, dashboard y tests → redactar el arranque → contrastar el resultado con los enunciados y ejemplos docentes (auditoría, diagramas y RC).
- **Aceptado:** esquema del snapshot con pydantic, paquete `dsia_web` (lote `build.py`, API Starlette, dashboard estático), journal por etapas, workflow de CI con Playwright, matriz de trazabilidad, diagramas Excalidraw y notas del RC.
- **Rechazado o aplazado:** la explicación con un proveedor externo quedó como integración opcional del lote (en ejecución se usa `mock`), y el empaquetado local como opción de despliegue, ampliada después con Docker y Render.
- **Verificación:** pytest del III, Uvicorn en local, smoke HTTP, prueba con Chromium y contraste de las métricas del snapshot con el artefacto del II.
- **Commit:** [`3d991d2`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3d991d2) (junto con [`e524ec0`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e524ec0) del II), seguidos de [`4da7058`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/4da7058) y [`ab75ded`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/ab75ded) (auditoría, diagramas e índice de proyectos).

## 2026-11-23 — Revisión arquitectónica no utilizada

- **Herramienta:** Claude Octopus Council · **modelo:** no registrado
- **Objetivo:** segunda opinión sobre la arquitectura con presupuesto limitado.
- **Aceptado:** nada.
- **Rechazado:** la revisión entera, que quedó parcial y sin quórum; no se usó como validación.
- **Verificación:** no aplica.
- **Commit:** ninguno.

## 2026-11-23 — Auditoría de cumplimiento y mejoras

- **Herramienta:** Claude Code · **modelo:** Claude Opus 5.5
- **Objetivo:** auditar el III frente al enunciado (requisitos mínimos y Entrega) y aplicar las mejoras en commits atómicos.
- **Prompts (resumen):** contrastar el enunciado y la rúbrica con el código → lista de huecos → un commit por mejora con su prueba → actualizar README, contrato y RC.
- **Aceptado:** middleware de `request_id`, `latency_ms`, contadores y cabeceras CSP, `nosniff` y `no-referrer`; `/health` con `checks`; `GET /api/v1/predictions/{symbol}`; `POST /api/v1/analyze` con el `AIClient` del II, límite de cuerpo, 503 tipado y `X-API-Key` opcional; `GET /api/v1/pipeline` y `GET /api/v1/metrics`; IA del lote configurada por `AI_PROVIDER` y `HF_*`; etapa `validate_input`; `input_summary` en el snapshot; paneles Operación, Datos de entrada y Explicar símbolo; smoke y prueba de navegador ampliados; Dockerfile, `.dockerignore`, `render.yaml`, `Procfile`, `.python-version` y `requirements-e2e.txt`; [evidencia agregada del histórico Alpaca](evidencia/historico_alpaca.json).
- **Rechazado:** campo `question` en `/api/v1/analyze` (`AnalysisRequest` del II no tiene pregunta libre y cambiarlo excede el III); estado `degraded` (el journal es informativo y no justifica un 503); normalizar símbolos en minúsculas (se prefiere un 422 explícito); publicar la URL y crear el tag sin la aprobación del autor; una captura del dashboard con cierres de Alpaca (la licencia no permite redistribuirlos).
- **Verificación:** 97 pruebas en verde con 98 % de cobertura de `dsia_web`; cada prueba nueva se puso en rojo rompiendo el código que cubre; `smoke_test.sh` y `browser_smoke.py --expect-pipeline` contra Uvicorn; `docker build` y `docker run` con `HEALTHCHECK` sano.
- **Commit:** [`7787286`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/7787286), [`8250055`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/8250055), [`830f150`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/830f150), [`9cf6d82`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/9cf6d82), [`85a2923`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/85a2923), [`d9693db`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/d9693db), [`f35d403`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/f35d403), [`e69bd3b`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e69bd3b), [`d9d9595`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/d9d9595), [`3a0304a`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3a0304a), [`8e8ee3b`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/8e8ee3b), [`f37f03b`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/f37f03b), [`d1d7b07`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/d1d7b07), [`dc75413`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/dc75413) y [`3207766`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3207766).

## 2026-11-23 (tarde) — Verificación final, despliegue en Render y RC

- **Herramienta:** Claude Code · **modelo:** Claude Opus 5.5
- **Objetivo:** repetir la verificación en un clon limpio, desplegar en Render desde `main` y preparar la RC.
- **Prompts (resumen):** verificación con revisores independientes y un crítico de completitud → corregir hallazgos → desplegar con la misma imagen del CI → integrar en `main` con CI verde.
- **Aceptado:** 404 y 405 del enrutador con el error JSON tipado; `browser_smoke.py` con `--api-key` y filtro del 503 limitado a `/api/v1/analyze`; README con `.venv-ii`, Procfile aclarado y nota sobre `run_id`; imagen con `requirements-runtime.txt` fijado a las versiones del II (1,17 → 0,88 GB); dashboard con tarjetas, «Mejor señal estimada», favicon y pie, sin código inline; `render.yaml` con `runtime: docker` y la URL pública. [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) fusionado y tag [`v0.9.0-rc1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1) sobre `0119c57`, ambos con la aprobación del autor.
- **Rechazado:** cabecera fija (aparecía a mitad de la captura de página completa del CI); fuentes web externas (la CSP `default-src 'self'` las bloquearía); el runtime Python de Render (la imagen Docker es la que prueba el CI).
- **Verificación:** 103 pruebas del III en verde (97,94 %); Playwright `--expect-pipeline` con y sin `DSIA_API_KEY`, móvil a 390 px y sin errores de consola; imagen `healthy` en 6 s; en Render, `/health` 200, `smoke_test.sh` correcto y análisis desde el dashboard. CI de `main` en verde en el run [45271274056](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45271274056).
- **Commit:** [`ca7aeb8`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/ca7aeb8), [`050c698`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/050c698), [`bb3942c`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/bb3942c), [`650970f`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/650970f), [`1156cfc`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/1156cfc), [`b983bcd`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/b983bcd), merge [`a5a5b9b`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/a5a5b9b), [`0119c57`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/0119c57) y [`b94a479`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/b94a479).

## 2026-11-23/24 — Datos reales de Alpaca en Render

- **Herramienta:** Claude Code · **modelo:** Claude Opus 5.5
- **Objetivo:** que el despliegue de Render muestre los símbolos reales en lugar de la demo sintética, respetando la licencia de Alpaca.
- **Prompts (resumen):** descargar barras reales en el lote → hornearlas en el build con un secret file → refrescar al arrancar con las claves como variables de entorno → adaptar el dashboard y la documentación.
- **Aceptado:** `alpaca_source.py` (descarga con `alpaca-py`, SIP con reintento en IEX, panel común `date, symbol, close, volume`, credenciales solo en memoria) y modos `alpaca` y `auto` del lote sin `input_summary`; secret mount en el Dockerfile y `alpaca-py` en el runtime; etiqueta «Datos reales · Alpaca» y aviso de licencia; `serve.py`, que refresca al arrancar; prueba de `/health` independiente de la hora; respuesta del análisis sin animación de entrada para que la captura de página completa no la apague.
- **Rechazado:** publicar cierres, retorno realizado o volatilidad con datos de Alpaca (sus condiciones prohíben redistribuirlos; el autor decidió publicar solo predicciones); leer las claves como `ARG` en el build (quedarían en el historial de la imagen); hornear en el repositorio un snapshot del histórico local (datos fijos y redistribución de derivados); que el asistente introdujese las claves en Render (las creó el autor en el panel).
- **Verificación:** 123 pruebas del III (97 %) con descarga simulada; build con claves falsas → Alpaca las rechaza y el build falla sin filtrar nada; contenedor con claves falsas → sirve el informe del build; en Render, `data_kind: alpaca`, 10 símbolos, último dato 2026-11-20, `download_bars` con 22 350 filas, smoke y Playwright `--kind "Datos reales · Alpaca"` correctos y ningún `last_close` en `/api/v1/snapshot`. CI de `main` en verde en el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693).
- **Commit:** [`507dba5`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/507dba5), [`35d85ee`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/35d85ee), [`31c3638`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/31c3638) ([PR #2](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/2), `bed8312`); [`5410155`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/5410155), [`6e45a4b`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/6e45a4b), [`87352b1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/87352b1) ([PR #3](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/3), `033d134`); [`e807373`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e807373) y [`bd3b0fa`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/bd3b0fa).

## 2026-11-24 — Documentación con el estilo de la wiki y contra la Entrega

- **Herramienta:** Claude Code · **modelo:** Claude Opus 5.5
- **Objetivo:** reescribir la documentación del III y de la raíz con la leyenda de la wiki del Proyecto I y ordenarla según la Entrega del enunciado.
- **Prompts (resumen):** leer el enunciado del III y la plantilla de AI_USAGE → tabla de requisitos mínimos con evidencia → arranque de API y dashboard por separado → despliegue con datos reales y licencia → cifras fechadas con el run 45288524693 → guion sobre la URL de Render → desarrollo por fechas.
- **Aceptado:** README, AI_USAGE, RELEASE y API del III; README raíz, `README_DSIA.md`, `proyectos/README.md` y `docs/` con la leyenda entre comillas invertidas, títulos limpios y cifras del último run.
- **Rechazado:** fechas de octubre para el II o el III (no hay commits; no se fabrican); la entrada «antes de octubre de 2026» de una versión anterior de este registro, que no casa con la cronología verificable (el repositorio de investigación se crea el 11/11/2026).
- **Verificación:** 123 pruebas del III en verde en local con `.venv-ii`; comprobador de enlaces relativos y anclas sobre los ficheros editados; cifras contrastadas con el log del run 45288524693.
- **Commit:** los de la revisión de documentación del 24/11/2026, sin cambios de código.

`>>` [Arquitectura](../../docs/ARQUITECTURA_DSIA.md) · [Uso de IA del Proyecto II](../proyecto_ii/AI_USAGE.md) · [Uso de IA en los ficheros comunes](../../docs/AI_USAGE.md) · [RC](RELEASE.md)
