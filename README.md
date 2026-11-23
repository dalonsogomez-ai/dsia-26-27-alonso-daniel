# README Desarrollo Soluciones de IA

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

## Repositorio propio de la asignatura de DSIA.

### Daniel Alonso Gómez

`->` Repositorio de entrega de los Proyectos I, II y III de Desarrollo de Soluciones de IA (curso 2026-2027).

`>>` URL canónica: <https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel>. Es el repositorio que ejecuta el CI y el que se evalúa; la cuenta `dalonsoLabs` se renombró a `dalonsogomez-ai` y sus enlaces antiguos redirigen aquí.

## Proyectos

| Proyecto | Qué hace | Guía |
| --- | --- | --- |
| **I · Programación avanzada en Python** (10 %) | Dos pipelines con loader, validador, métricas y CLI: ventas del curso (checkpoint 140 válidas / 10 inválidas) y barras diarias de acciones (Alpaca o muestra sintética versionada). | [proyectos/proyecto_i/README.md](proyectos/proyecto_i/README.md) |
| **II · Automatización e integración** (20 %) | Pipeline sklearn que estima el retorno a 21 sesiones: split temporal con purga, Dummy, Ridge y Swarm, holdout de un solo toque, artefacto `joblib` y cliente de IA tipado (`mock` o Hugging Face). | [proyectos/proyecto_ii/README.md](proyectos/proyecto_ii/README.md) |
| **III · Desarrollo end-to-end** (40 %) | Lote que congela un snapshot del modelo del II, API Starlette (`/health`, snapshot, predicciones, análisis, pipeline y métricas), dashboard con panel de operación, Playwright y empaquetado Docker/Render. | [proyectos/proyecto_iii/README.md](proyectos/proyecto_iii/README.md) |

`>>` [Índice de proyectos con diagramas](proyectos/README.md) · [Arquitectura en Excalidraw](docs/ARQUITECTURA_DSIA.md) · [Trazabilidad requisito → evidencia](docs/TRAZABILIDAD_DSIA.md) · [Guía de arranque y rúbricas](README_DSIA.md).

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
docker run --rm -p 8790:8000 dsia-iii
PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
```

`=>` La receta completa del II (inspección, entrenamiento, evaluación, inferencia y Hugging Face) está en su [README](proyectos/proyecto_ii/README.md#-reproducir-sin-claves-ni-datos-de-terceros); la del III (prueba de navegador, Render, Procfile y rollback), en el suyo. Todavía no hay URL pública: el despliegue en Render lo hace el autor con su cuenta.

## CI

`>>` [`.github/workflows/ci.yml`](.github/workflows/ci.yml) se ejecuta en cada `push` a `main` y en cada `pull_request`. Tiene tres jobs:

- `>` **proyecto-i**: `pip install -r requirements.txt`, pytest con `--cov=ventas_app --cov=acciones_app --cov-fail-under=60`, las dos CLI sin red y los ejemplos del Tema 2.
- `>` **proyectos-ii-y-iii**: pytest del II (umbral 80 %) y `marimo check`, receta de la CLI del II con el sha256 de la demo, pytest del III (umbral 90 %), lote demo, smoke HTTP y Playwright contra el backend real. Publica el artefacto `dsia-dashboard-sintetico` (captura y journal).
- `>` **proyecto-iii-docker**: construye la imagen, espera al `HEALTHCHECK` y pasa el smoke contra el contenedor.

`=>` Último run verde de `main` antes de esta rama: [45227267528](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45227267528) (commit `ab75ded`).

## Uso de IA

`->` Política del curso: cuando el uso de IA está permitido **hay que indicar y citar la herramienta**; el uso sin referencia se considera plagio. Cada proyecto versiona su `AI_USAGE.md` (sin secretos) con herramienta, fecha, qué se aceptó, qué se rechazó y cómo se verificó.

- `>>` [Proyecto I · AI_USAGE.md](proyectos/proyecto_i/AI_USAGE.md)
- `>>` [Proyecto II · AI_USAGE.md](proyectos/proyecto_ii/AI_USAGE.md)
- `>>` [Proyecto III · AI_USAGE.md](proyectos/proyecto_iii/AI_USAGE.md)

## Material y proyectos

- `>>` [Tema 1 — Programación avanzada en Python](1_programacion_avanzada_python/README.md).
- `>>` [Tema 2 — Pruebas y despliegue](2_pruebas_y_despliegue/README.md).
- `>>` [Proyecto I — Ventas y acciones](proyectos/proyecto_i/README.md).
- `>>` [Proyecto II — Automatización e integración](proyectos/proyecto_ii/README.md).
- `>>` [Proyecto III — Desarrollo end-to-end](proyectos/proyecto_iii/README.md) · [API](proyectos/proyecto_iii/API.md) · [Release Candidate](proyectos/proyecto_iii/RELEASE.md) · [Evidencia agregada del histórico Alpaca](proyectos/proyecto_iii/evidencia/historico_alpaca.json).
- `>>` [Documentación transversal en `docs/`](docs/ARQUITECTURA_DSIA.md): arquitectura, diagramas y [trazabilidad](docs/TRAZABILIDAD_DSIA.md).

## Bitácora de sesiones

## 1 Sesión -> 07/09/2026

- `>` Creamos nuestro repositorio.
- `>` Creamos los archivos `.gitignore` y `requirements.txt`.
- `>` Añadimos rama de la sesión `practica/sesion-01`.

## 23/11/2026 -> Revisión de cumplimiento

- `->` Auditar los tres proyectos contra los enunciados del profesor (`dmartincc/dsia-26-27` @`b76b950`).
- `~>` Rama `mejoras/cumplimiento-requisitos` con commits atómicos por proyecto, hecha con Claude Code (modelo Claude Opus 5.5) y citada en cada `AI_USAGE.md`.
- `>` README raíz como índice, CI con tres jobs, trazabilidad del I y `.mailmap` para unificar la identidad del autor.
- `=>` Suites del I, II y III en verde en local; el CI remoto de la rama queda pendiente de push.

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.
