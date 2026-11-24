# AGENTS.md · Contexto para asistentes de IA

`->` Fichero de contexto del repositorio para agentes de código (OpenCode, Aider, Codex CLI, Cline, Claude Code…), según la sesión de IA asistida del curso (tema 5, B1.2, B4 y B6). Es la única fuente de verdad: si una herramienta pide otro nombre, se enlaza (`ln -s AGENTS.md CLAUDE.md`) en vez de copiarlo.

`>` Leyenda de la wiki, usada en comentarios y documentos: `->` objetivo, `~>` cambio o ajuste, `>` paso técnico, `>>` evidencia, `=>` resultado.

## Propósito

`->` Repositorio de entrega de Desarrollo de Soluciones de IA (Comillas, curso 2026-2027): Proyectos I, II y III según los enunciados de `dmartincc/dsia-26-27` @`b76b950`. El III, SwarmTrader, está desplegado en <https://dsia-swarmtrader.onrender.com> con datos reales de Alpaca y «Explicar símbolo» con NVIDIA (`nvidia/nemotron-3.5-super-vl-120b-a12b`, activado en el panel de Render); el CI y la explicación del lote usan `mock`. Limitaciones del despliegue en `proyectos/proyecto_iii/RELEASE.md` («Issues conocidos»).

| Ruta | Qué es |
| --- | --- |
| `proyectos/proyecto_i/` | Proyecto I, **ya calificado**: `ventas_app` y `acciones_app`. Usa `.venv-i` (pandas 3); el `requirements.txt` y el `pytest.ini` de la raíz son suyos |
| `proyectos/proyecto_ii/` | Proyecto II: `swarmtrade_app` (pipeline sklearn, CLI, `ai_client.py` con `mock`, `hf` y `nvidia`) y notebooks marimo en `ml_pipeline/`. Usa `.venv-ii` (pandas 2) |
| `proyectos/proyecto_iii/` | Proyecto III: `dsia_web` (lote `build.py`, API Starlette `app.py`, límite de uso `ratelimit.py`, arranque `serve.py`, dashboard `static/`), `scripts/smoke_test.sh`, `tests/`, `Dockerfile`, `API.md` y `RELEASE.md`. Usa `.venv-ii` |
| `1_programacion_avanzada_python/`, `2_pruebas_y_despliegue/` | Prácticas de los temas 1 y 2 |
| `docs/` | Arquitectura, trazabilidad requisito → evidencia y `AI_USAGE.md` transversal |
| `.github/workflows/ci.yml`, `render.yaml`, `Procfile` | CI (jobs `proyecto-i`, `proyectos-ii-y-iii` y `proyecto-iii-docker`) y despliegue |

## Entornos y comandos

`>` Desde la raíz, con Python 3.12. Los comandos exactos y sus umbrales están en `.github/workflows/ci.yml`; si cambian allí, manda el workflow.

```bash
python3.12 -m venv .venv-i  && .venv-i/bin/python -m pip install -r requirements.txt
python3.12 -m venv .venv-ii && .venv-ii/bin/python -m pip install -r proyectos/proyecto_iii/requirements-e2e.txt
export AI_PROVIDER=mock HF_TOKEN= MPLBACKEND=Agg PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii

# I (umbral 60 %) y ejemplos del tema 2
(cd proyectos/proyecto_i && ../../.venv-i/bin/python -m pytest -q --cov=ventas_app --cov=acciones_app --cov-fail-under=60)
.venv-i/bin/python -m pytest -q 2_pruebas_y_despliegue/ejemplos
# II (umbral 80 %) y revisión de notebooks
(cd proyectos/proyecto_ii && ../../.venv-ii/bin/python -m pytest -q --cov=swarmtrade_app --cov-fail-under=80 \
  && ../../.venv-ii/bin/python -m marimo check ml_pipeline/01_eda.py ml_pipeline/02_prep.py ml_pipeline/03_model.py ml_pipeline/04_eval.py)
# III (umbral 90 %)
.venv-ii/bin/python -m pytest -q --cov=dsia_web --cov-fail-under=90 proyectos/proyecto_iii/tests
# III de extremo a extremo: lote demo, API, smoke HTTP y navegador
.venv-ii/bin/python -m dsia_web.build demo --work runs/demo/work --output runs/demo/snapshot.json --journal runs/demo/pipeline.jsonl
DSIA_SNAPSHOT=runs/demo/snapshot.json DSIA_JOURNAL=runs/demo/pipeline.jsonl .venv-ii/bin/python -m uvicorn dsia_web.app:app --port 8765
PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8765
.venv-ii/bin/python proyectos/proyecto_iii/tests/browser_smoke.py http://127.0.0.1:8765/ --journal runs/demo/pipeline.jsonl --expect-pipeline
# Imagen del III
docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
```

`>>` La receta reproducible del II (demo de 680 sesiones, 8 símbolos, semilla 42, sha256, las 15 métricas publicadas y las cifras de la inferencia con tolerancia 1e-6) es el paso «Proyecto II · smoke de la CLI» del workflow: no se cambian las cifras sin regenerarlas y actualizar el README del II. El último paso del job `proyectos-ii-y-iii` falla si un `.md` conserva un marcador de commit sin sustituir por su hash.

## Convenciones

- `>` **Idioma.** Español en código, comentarios, mensajes de error, documentación y commits. Comentarios con la leyenda (`# >`, `# >>`, `# ~>`); en Markdown, la leyenda siempre entre comillas invertidas.
- `>` **Pruebas primero.** Cada cambio de comportamiento empieza por un test que falla. La cobertura no baja (CI: I 60 %, II 80 %, III 90 %). Las suites no usan red ni claves: `AI_PROVIDER=mock`, dobles del SDK y relojes o subprocesos inyectables. No se tocan tests para que pasen sin entender por qué fallan.
- `>` **Contratos.** El snapshot es la versión 1 (pydantic, solo cambios compatibles). La API mantiene la forma de error `{"error", "detail": {"code", "message"}, "request_id"}` documentada en `proyectos/proyecto_iii/API.md`, que se actualiza con cada cambio. `AnalysisRequest` del II no admite pregunta libre.
- `>` **Dependencias.** Ninguna nueva sin preguntar. Las versiones se fijan en `proyectos/proyecto_ii/requirements.txt`; `requirements-runtime.txt` del III es un subconjunto comprobado por `test_packaging.py`.
- `>` **Commits atómicos.** Un cambio por commit, con mensaje en español en infinitivo («Añadir…», «Limitar…»), cuerpo que explica el porqué y el trailer `Co-Authored-By:` de la herramienta de IA que participó. Solo se añaden los ficheros tocados (`git add <ficheros>`, nunca `git add .`). Sin push, merge, tags, deploy ni cambios en Render sin aprobación explícita del autor; nunca se reescribe el historial publicado.

## Secretos

- `>` **Nunca** se leen, escriben ni versionan `.env`, `alpaca.env`, `/etc/secrets/*` ni credenciales. En el repositorio solo hay `.env.example` con nombres y valores vacíos o por defecto.
- `>` Las claves (`HF_TOKEN`, `NVIDIA_API_KEY`, `ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY`, `DSIA_API_KEY`) viven solo en el panel de Render (`sync: false` en `render.yaml`) o en el entorno local del autor. No van en código, README, logs, prompts ni capturas. `render.yaml` mantiene `AI_PROVIDER=mock`: el panel decide el proveedor real.
- `>` Los tests usan valores falsos **sin** forma de clave real (`clave.falsa.nvidia.0123456789`), a la derecha de nombres que no son `token`, `secret` ni `api_key`. Antes de cada commit salen vacías, también con `--untracked` para los ficheros nuevos, las comprobaciones del curso: la de 03_despliegue B13 y 01_ia_asistida B12, `git grep -nI -E "(api[_-]?key|token|secret)\s*=\s*['\"]?[A-Za-z0-9_-]{12,}"`, y la del prefijo de NVIDIA de E6 0.3, que aquí se escribe `git grep -n "nvapi[-]"` (equivale a la del curso; con `[-]` esta línea no se encuentra a sí misma).

## Qué no debe hacer un agente

- `>` **Fabricar fechas, cifras o evidencias.** Las fechas salen de `git log`; las cifras de tests, cobertura y métricas, de ejecuciones reales citadas con su comando o run de CI. No hay commits del II ni del III en octubre y no se inventan.
- `>` **Publicar precios de Alpaca.** Sus condiciones no permiten redistribuirlos: el snapshot con `data_kind: alpaca` no lleva `input_summary`, los CSV descargados se borran y la evidencia versionada es agregada (`evidencia/historico_alpaca.json`). Al proveedor de IA solo viajan agregados y predicciones del modelo.
- `>` **Tocar el Proyecto I calificado** (`proyectos/proyecto_i/`, ni su `requirements.txt` ni su `pytest.ini` de la raíz) salvo petición expresa del autor.
- `>` Bajar umbrales de cobertura, saltarse el CI, cambiar `AI_PROVIDER` en `render.yaml`, llamar a proveedores reales desde los tests o enviar datos del repositorio a servicios externos.

## Cómo citar la IA en `AI_USAGE.md`

`->` La política de la asignatura obliga a indicar y citar la herramienta; usarla sin referencia se considera plagio. Cada proyecto tiene su registro (`proyectos/proyecto_*/AI_USAGE.md`) y lo transversal va en `docs/AI_USAGE.md`. Se distingue la IA que ayudó a escribir el código de la IA que usa la aplicación en ejecución (`AIClient`).

`>` Una entrada breve (5–8 líneas, sin pegar conversaciones ni secretos) por tarea relevante:

```markdown
## AAAA-MM-DD — Tarea
- **Herramienta:** … · **modelo:** …
- **Objetivo:** …
- **Prompts (resumen):** explicar → plan → paso 1 …
- **Aceptado:** …
- **Rechazado:** … (también las alucinaciones borradas)
- **Verificación:** comando → resultado (tests, cobertura, run de CI)
- **Commit:** `abc1234`
```
