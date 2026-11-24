# Desarrollo de Soluciones de IA

**Daniel Alonso Gómez · Curso 2026–2027 · Repositorio propio de la asignatura**

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

`->` Repositorio de entrega de los Proyectos I, II y III de Desarrollo de Soluciones de IA (curso 2026-2027), según los [enunciados del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md).

`>>` URL canónica: <https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel>. Es el repositorio que ejecuta el CI y el que se evalúa; la cuenta `dalonsoLabs` se renombró a `dalonsogomez-ai` y sus enlaces antiguos redirigen aquí.

## Demo en vivo (Render)

| Enlace | Qué muestra |
| --- | --- |
| [**dsia-swarmtrader.onrender.com**](https://dsia-swarmtrader.onrender.com) | Dashboard del Proyecto III: ranking de retornos estimados, evidencia del modelo, «Explicar símbolo» y panel de operación |
| [`/health`](https://dsia-swarmtrader.onrender.com/health) | Estado del servicio y comprobaciones del snapshot |
| [`/api/v1/snapshot`](https://dsia-swarmtrader.onrender.com/api/v1/snapshot) · [`/api/v1/snapshot/schema`](https://dsia-swarmtrader.onrender.com/api/v1/snapshot/schema) | Informe publicado y su contrato JSON Schema |
| [`/api/v1/predictions/AAPL`](https://dsia-swarmtrader.onrender.com/api/v1/predictions/AAPL) | Predicción por símbolo |
| [`/api/v1/metrics`](https://dsia-swarmtrader.onrender.com/api/v1/metrics) · [`/api/v1/pipeline`](https://dsia-swarmtrader.onrender.com/api/v1/pipeline) | Contadores y latencias del servicio, y eventos del último lote |

`>>` Servicio Docker en Render (plan free, Frankfurt) que despliega `main` en cada commit. Al arrancar descarga barras diarias reales de Alpaca de 10 símbolos (AAPL, AMZN, GOOGL, JNJ, JPM, META, MSFT, NVDA, TSLA, XOM) hasta la última sesión cerrada, reentrena el modelo del II y publica **solo predicciones y métricas**: las condiciones de Alpaca no permiten redistribuir precios. Sin credenciales publica la demo sintética. La primera visita tras un rato sin tráfico tarda unos 50 s.

`=>` Comprobado el 23/11/2026: `data_kind: alpaca`, último dato 2026-11-20, smoke HTTP y prueba de navegador correctos contra la URL pública ([captura](proyectos/proyecto_iii/evidencia/dashboard_render.png)). Detalles en el [README del III](proyectos/proyecto_iii/README.md#despliegue-en-render).

## Proyectos

| Proyecto | Qué hace | Guía |
| --- | --- | --- |
| **I · Programación avanzada en Python** (10 %) | Dos pipelines con loader, validador, métricas y CLI: ventas del curso (checkpoint 140 válidas / 10 inválidas) y barras diarias de acciones (Alpaca o muestra sintética versionada). | [proyectos/proyecto_i/README.md](proyectos/proyecto_i/README.md) |
| **II · Automatización e integración** (20 %) | Pipeline sklearn que estima el retorno a 21 sesiones: split temporal con purga, Dummy, Ridge y Swarm, holdout de un solo toque, artefacto `joblib` y cliente de IA tipado (`mock`, Hugging Face o, como alternativa, NVIDIA). | [proyectos/proyecto_ii/README.md](proyectos/proyecto_ii/README.md) |
| **III · Desarrollo end-to-end** (40 %) | Lote que congela un snapshot del modelo del II, API Starlette (`/health`, snapshot, predicciones, análisis, pipeline y métricas), dashboard con panel de operación, Playwright, Docker y despliegue en Render con datos reales de Alpaca. | [proyectos/proyecto_iii/README.md](proyectos/proyecto_iii/README.md) |

`>>` [Índice de proyectos con diagramas](proyectos/README.md) · [Arquitectura en Excalidraw](docs/ARQUITECTURA_DSIA.md) · [Trazabilidad requisito → evidencia](docs/TRAZABILIDAD_DSIA.md) · [Guía de arranque](README_DSIA.md).

## Ejecución rápida

`->` Se usan **dos entornos** con Python 3.12. No son compatibles entre sí: el Proyecto I fija **pandas 3** y el II/III fijan **pandas 2** (además de versiones distintas de pytest), así que un único entorno no resuelve.

| Entorno | Instalación | Para qué |
| --- | --- | --- |
| `.venv-i` | `pip install -r requirements.txt` | Proyecto I y prácticas de los Temas 1 y 2 |
| `.venv-ii` | `pip install -r proyectos/proyecto_ii/requirements.txt` | Proyectos II y III (`proyectos/proyecto_iii/requirements-e2e.txt` añade Playwright) |

`>` Proyecto I y Tema 2 (desde la raíz):

```bash
python3.12 -m venv .venv-i
.venv-i/bin/python -m pip install -r requirements.txt
.venv-i/bin/python -m pytest -q                                  # suite del I (pytest.ini raíz)
.venv-i/bin/python -m pytest -q 2_pruebas_y_despliegue/ejemplos  # ejemplos del Tema 2
cd proyectos/proyecto_i
../../.venv-i/bin/python -m pytest -q --cov=ventas_app --cov=acciones_app --cov-report=term-missing --cov-fail-under=60
../../.venv-i/bin/python -m ventas_app.cli --input data/ventas.csv --output data/processed/ventas.csv
../../.venv-i/bin/python -m acciones_app.cli --input data/sample/acciones_muestra.csv --output data/processed/acciones.csv
```

`>` Proyectos II y III (desde la raíz, sin claves ni red):

```bash
python3.12 -m venv .venv-ii
.venv-ii/bin/python -m pip install -r proyectos/proyecto_iii/requirements-e2e.txt
export AI_PROVIDER=mock HF_TOKEN= MPLBACKEND=Agg PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii
(cd proyectos/proyecto_ii && ../../.venv-ii/bin/python -m pytest -q --cov=swarmtrade_app --cov-fail-under=80)
.venv-ii/bin/python -m pytest -q --cov=dsia_web --cov-fail-under=90 proyectos/proyecto_iii/tests
# Demo del lote: entrena, evalúa e infiere con datos sintéticos y publica el snapshot.
.venv-ii/bin/python -m dsia_web.build demo --work runs/demo/work \
  --output runs/demo/snapshot.json --journal runs/demo/pipeline.jsonl
# API y dashboard en el mismo proceso: http://127.0.0.1:8765/
DSIA_SNAPSHOT=runs/demo/snapshot.json DSIA_JOURNAL=runs/demo/pipeline.jsonl \
  .venv-ii/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765
# En otra terminal: smoke HTTP de /health, snapshot, predicción, análisis y métricas.
PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8765
```

`>` Empaquetado del III con Docker (contexto = raíz del repositorio):

```bash
docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
docker run --rm -p 8790:8000 -e DSIA_TRUSTED_PROXY_HOPS=0 dsia-iii   # sin proxy delante
PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
```

`=>` La receta completa del II (inspección, entrenamiento, evaluación, inferencia y Hugging Face) está en su [README](proyectos/proyecto_ii/README.md#reproducir-sin-claves-ni-datos-de-terceros); la del III (entrenar e inferir, arranque de API y dashboard, prueba de navegador, Render, Procfile y rollback), en el [suyo](proyectos/proyecto_iii/README.md).

## CI

`>>` [`.github/workflows/ci.yml`](.github/workflows/ci.yml) se ejecuta en cada `push` a `main`, en cada `pull_request` y bajo demanda (`workflow_dispatch`). Tiene tres jobs:

- `>` **proyecto-i**: `pip install -r requirements.txt`, pytest con `--cov=ventas_app --cov=acciones_app --cov-fail-under=60`, las dos CLI sin red y los ejemplos del Tema 2.
- `>` **proyectos-ii-y-iii**: pytest del II (umbral 80 %) y `marimo check`, receta de la CLI del II con el sha256 de la demo, pytest del III (umbral 90 %), lote demo, smoke HTTP y Playwright contra el backend real. Publica el artefacto `dsia-dashboard-sintetico` (captura y journal).
- `>` **proyecto-iii-docker**: construye la imagen, espera al `HEALTHCHECK` y pasa el smoke contra el contenedor.

`=>` Último run verde de `main`: [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693), sobre `bd3b0fa` el 24/11/2026, con los tres jobs en verde:

| Job | Resultado del run 45288524693 |
| --- | --- |
| `proyecto-i` | **178 tests** y **99,31 %** de cobertura; 7 tests de ejemplo del Tema 2 |
| `proyectos-ii-y-iii` | II: **74 tests** y **83,42 %**; III: **123 tests** y **97,22 %**; «Smoke correcto» y Playwright «OK» contra Uvicorn |
| `proyecto-iii-docker` | Imagen construida, `HEALTHCHECK` sano y «Smoke correcto» contra el contenedor |

## Uso de IA

`->` Política del curso: cuando el uso de IA está permitido **hay que indicar y citar la herramienta**; el uso sin referencia se considera plagio. Cada proyecto versiona su `AI_USAGE.md` (sin secretos) con herramienta, modelo, fecha, qué se aceptó, qué se rechazó, cómo se verificó y los commits.

- `>>` [Proyecto I · AI_USAGE.md](proyectos/proyecto_i/AI_USAGE.md)
- `>>` [Proyecto II · AI_USAGE.md](proyectos/proyecto_ii/AI_USAGE.md)
- `>>` [Proyecto III · AI_USAGE.md](proyectos/proyecto_iii/AI_USAGE.md)
- `>>` [Ficheros comunes (README, docs y CI) · docs/AI_USAGE.md](docs/AI_USAGE.md)

## Material y proyectos

- `>>` [Tema 1 — Programación avanzada en Python](1_programacion_avanzada_python/README.md).
- `>>` [Tema 2 — Pruebas y despliegue](2_pruebas_y_despliegue/README.md).
- `>>` [Proyecto I — Ventas y acciones](proyectos/proyecto_i/README.md).
- `>>` [Proyecto II — Automatización e integración](proyectos/proyecto_ii/README.md).
- `>>` [Proyecto III — Desarrollo end-to-end](proyectos/proyecto_iii/README.md) · [API](proyectos/proyecto_iii/API.md) · [Release Candidate](proyectos/proyecto_iii/RELEASE.md) · [Evidencia agregada del histórico Alpaca](proyectos/proyecto_iii/evidencia/historico_alpaca.json).
- `>>` [Documentación transversal en `docs/`](docs/ARQUITECTURA_DSIA.md): arquitectura, diagramas y [trazabilidad](docs/TRAZABILIDAD_DSIA.md).

## Desarrollo por fechas

- `->` **7 septiembre (sesión 1):** se crea el repositorio, con `.gitignore`, `requirements.txt` y la rama de la sesión `practica/sesion-01`.
- `~>` **21 septiembre – 13 octubre:** Proyecto I (arquitectura de `ventas_app`, extracción de Alpaca y reorganización de la entrega); cronología detallada en su [Desarrollo por fechas](proyectos/proyecto_i/README.md#desarrollo-por-fechas).
- `->` **11 noviembre:** se crea el repositorio de investigación [`dalonsogomez-ai/swarmtrader`](https://github.com/dalonsogomez-ai/swarmtrader); el II reutiliza su v1.4.0 (`5642dda`).
- `~>` **12 noviembre:** el Proyecto II se escribe con OpenAI Codex (gpt-6.1-sol).
- `>>` **19 noviembre:** auditoría de la extracción de Alpaca con Codex (gpt-6.1-sol).
- `~>` **23 noviembre:** integración del II y del III en este repositorio (`e524ec0` y `3d991d2`) con Codex (gpt-6.2-sol).
- `>` **23 noviembre:** auditoría de cumplimiento de los tres proyectos contra los enunciados (`dmartincc/dsia-26-27` @`b76b950`) con Claude Code (Claude Opus 5.5), en la rama `mejoras/cumplimiento-requisitos` con un commit por mejora.
- `=>` **23 noviembre:** [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) fusionado (`a5a5b9b`) con CI verde, tag [`v0.9.0-rc1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1) y despliegue en Render.
- `~>` **23-24 noviembre:** datos reales de Alpaca en Render ([PR #2](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/2), `bed8312`, y [PR #3](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/3), `033d134`).
- `=>` **24 noviembre:** `main` en `bd3b0fa` con el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) en verde; revisión de la documentación con la leyenda de la wiki.
- `>>` **Octubre:** no hay commits del II ni del III en octubre; se declara así y no se fabrican fechas.
