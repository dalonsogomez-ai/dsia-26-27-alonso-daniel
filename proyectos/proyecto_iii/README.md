# Proyecto III · Aplicación de investigación SwarmTrader

El dashboard muestra retornos estimados a 21 sesiones, un baseline, los datos de entrada por símbolo y la procedencia de la inferencia. Consume el informe de la API con una petición HTTP real, lanza análisis bajo demanda con `POST /api/v1/analyze` y su panel **Operación** lee `/health`, `/api/v1/metrics` y `/api/v1/pipeline`. El [diagrama](../../docs/ARQUITECTURA_DSIA.md) explica por qué el cálculo se ejecuta por lotes. La explicación de la demo usa el cliente `mock` del Proyecto II.

-> **Tecnología.** Backend con **Starlette** (el núcleo ASGI de FastAPI) servido por Uvicorn, y dashboard con **HTML/JS propio** en `dsia_web/static/` sin dependencias externas ni CDN. Es la opción «FastAPI+HTML» del enunciado: Starlette aporta el enrutado y el middleware sin la capa de validación automática, que aquí hace pydantic de forma explícita.

~> **Cadena.** Ingesta (Proyecto I, Alpaca) → procesamiento y modelo sklearn (Proyecto II) → lote `dsia_web.build` que congela un snapshot validado → API → dashboard → contenedor o PaaS.

## Entrenar e inferir

El entrenamiento, la evaluación única del holdout y la inferencia viven en el [Proyecto II](../proyecto_ii/README.md); el III no reentrena. `dsia_web.build demo` reproduce la cadena entera con datos sintéticos (`generate_bars → prepare → train → holdout → infer_snapshot → publish_snapshot`) y `dsia_web.build from-run` reutiliza un run congelado del II (ver [Informe con el histórico](#informe-con-el-histórico-del-proyecto-ii)). La predicción se calcula por lotes y la API la sirve integrada en el snapshot y por símbolo (`/api/v1/predictions/{symbol}`); la IA generativa se invoca bajo demanda con `POST /api/v1/analyze`.

## Arranque local de API y dashboard

Ejecuta desde la raíz del repositorio. El entorno de referencia es `.venv-ii` (Python 3.12 con las dependencias fijadas del II).

1. **Entorno.** `python3.12 -m venv .venv-ii` y `.venv-ii/bin/python -m pip install -r proyectos/proyecto_ii/requirements.txt`.
2. **Informe y configuración.** Genera la demo una vez en un destino nuevo.

   ```bash
   export PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii MPLBACKEND=Agg AI_PROVIDER=mock
   .venv-ii/bin/python -m dsia_web.build demo --work runs/demo/work \
     --output runs/demo/snapshot.json --journal runs/demo/pipeline.jsonl
   export DSIA_SNAPSHOT="$PWD/runs/demo/snapshot.json" DSIA_JOURNAL="$PWD/runs/demo/pipeline.jsonl"
   ```

3. **Arranque.** `.venv-ii/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765` y abre [el dashboard local](http://127.0.0.1:8765/). La misma orden sirve la API y el dashboard. En producción cambia a `--host 0.0.0.0 --port "$PORT"`.
4. **Smoke test.** En otra terminal: `PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8765`. Prueba `/health`, `/api/v1/snapshot`, `/api/v1/predictions/<primer símbolo del informe>`, `POST /api/v1/analyze` y `/api/v1/metrics`, y exige el mismo `run_id` en todos.
5. **Recuperación.** Conserva el snapshot anterior. Si el nuevo no supera las comprobaciones, apunta `DSIA_SNAPSHOT` a la versión previa y reinicia el servicio. Un snapshot ausente o inválido hace que `/health` responda 503. El rollback de código se describe en el [RC](RELEASE.md#rollback).

## Prueba de navegador en local

```bash
uv pip install -p .venv-ii -r proyectos/proyecto_iii/requirements-e2e.txt   # o pip install -r …
.venv-ii/bin/python -m playwright install chromium --only-shell
.venv-ii/bin/python proyectos/proyecto_iii/tests/browser_smoke.py http://127.0.0.1:8765/ \
  --journal runs/demo/pipeline.jsonl --expect-pipeline --screenshot runs/demo/dashboard.png
```

La prueba abre Chromium contra el servicio en marcha y comprueba que la respuesta de `/api/v1/snapshot`, el DOM, `/health`, el panel Operación y el journal comparten `run_id`; que la tabla de datos de entrada y el ranking cuadran con la API; que «Explicar símbolo» hace un `POST /api/v1/analyze` real y que un 503 simulado se muestra como alerta; y que no hay errores de consola (incluidas violaciones de CSP) ni scroll horizontal a 390 px.

## Evidencia de que el dashboard consume el backend real

- => `browser_smoke.py` intercepta las respuestas reales de `/api/v1/snapshot` y `/api/v1/analyze` y compara su contenido con lo que pinta la página.
- => El [workflow](../../.github/workflows/ci.yml) genera otro snapshot desde cero en Linux, arranca Uvicorn, ejecuta `smoke_test.sh` y `browser_smoke.py`, y publica el artefacto `dsia-dashboard-sintetico` con `dashboard.png` y `pipeline.jsonl` del mismo run.
- => El panel **Operación** muestra en vivo `/health`, los contadores de `/api/v1/metrics` (crecen con cada petición del propio dashboard) y los eventos del lote servidos por `/api/v1/pipeline`.

## Empaquetado y despliegue

`=>` **URL de despliegue:** [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com) (dashboard) · API en [`https://dsia-swarmtrader.onrender.com/health`](https://dsia-swarmtrader.onrender.com/health), [`/api/v1/metrics`](https://dsia-swarmtrader.onrender.com/api/v1/metrics), [`/api/v1/pipeline`](https://dsia-swarmtrader.onrender.com/api/v1/pipeline). Web Service de Render con la imagen [Dockerfile](Dockerfile) (región Frankfurt, plan free, `healthCheckPath: /health`, `AI_PROVIDER=mock`), desplegado el 23/11/2026 desde la rama `mejoras/cumplimiento-requisitos` (commit `8d11d94`) con auto-deploy en cada commit. En el plan free la instancia se duerme tras unos minutos sin tráfico y la primera petición tarda unos 50 s; para la exposición conviene abrir la URL antes. Comprobado el 23/11/2026: `/health` → `200 ready`, `scripts/smoke_test.sh https://dsia-swarmtrader.onrender.com` → «Smoke correcto», y el dashboard en Chrome pinta el panel Operación y responde a «Explicar símbolo» (`POST /api/v1/analyze`) sin errores de consola ni de CSP.

- **Modo producción sin contenedor.** Escucha en todas las interfaces y en el puerto que asigne la plataforma: `uvicorn dsia_web.app:app --host 0.0.0.0 --port "$PORT"`. En local usa siempre `--host 127.0.0.1`.
- **Docker.** El contexto es la raíz del repositorio y [`.dockerignore`](../../.dockerignore) deja fuera `.git`, entornos, `runs`, `data/raw`, `.env*` y el resto de asignaturas. La [imagen](Dockerfile) parte de `python:3.12-slim`, instala sin caché solo las dependencias de ejecución ([`requirements-runtime.txt`](requirements-runtime.txt): las mismas versiones fijadas del II, sin marimo, pytest ni alpaca-py; unos 0,9 GB frente a 1,2 GB con el entorno completo, y `tests/test_packaging.py` impide que se desalineen), genera el snapshot demo sintético durante el build, corre con un usuario sin privilegios (uid 10001) y declara un `HEALTHCHECK` contra `/health` hecho con Python.

  ```bash
  docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
  docker run --rm -p 8790:8000 dsia-iii        # -e PORT=9000 cambia el puerto interno
  PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
  ```

- **Render.** [`render.yaml`](../../render.yaml) describe el servicio desplegado: `runtime: docker` con el mismo [Dockerfile](Dockerfile) que el CI (el snapshot se genera en el build), contexto en la raíz, región Frankfurt, plan free, `healthCheckPath: /health` y `AI_PROVIDER=mock`; Render inyecta `$PORT` y el `CMD` escucha en él. `HF_TOKEN` y `DSIA_API_KEY` se introducen en el panel (`sync: false`). Para recrearlo: *New → Blueprint* con este repositorio, o *New → Web Service* con Language `Docker` y Dockerfile Path `./proyectos/proyecto_iii/Dockerfile`. Tras integrar la rama en `main`, cambia la rama del servicio a `main` en *Settings → Build & Deploy*. [`.python-version`](../../.python-version) fija Python 3.12 para el arranque sin contenedor.
- **Procfile.** [`Procfile`](../../Procfile) arranca sin contenedor en un runner que ya tenga instalado `proyectos/proyecto_ii/requirements.txt`: genera el snapshot demo si falta y lanza Uvicorn en `$PORT`. En Heroku no basta con el buildpack de Python, porque instalaría el `requirements.txt` raíz (solo el Proyecto I); allí usa el contenedor (`heroku stack:set container` con el mismo [Dockerfile](Dockerfile)), como en Render.
- **Clave opcional.** Con `DSIA_API_KEY` definida, `POST /api/v1/analyze` exige `X-API-Key`. El resto de endpoints son de lectura.

## Informe con el histórico del Proyecto II

Sigue la [receta de entrenamiento e inferencia del II](../proyecto_ii/README.md#reproducir-el-histórico-autorizado). Usa el mismo CSV y el directorio que contiene `model.joblib` y `test_metrics.json` de una ejecución propia. Define `DSIA_BARS_CSV` y `DSIA_FROZEN_RUN` en el entorno local. Con el `PYTHONPATH` anterior:

```bash
history_dir=$(mktemp -d)
.venv-ii/bin/python -m dsia_web.build from-run \
  --data "$DSIA_BARS_CSV" --run "$DSIA_FROZEN_RUN" --provider mock \
  --output "$history_dir/snapshot.json" --journal "$history_dir/pipeline.jsonl"
export DSIA_SNAPSHOT="$history_dir/snapshot.json"
```

Arranca Uvicorn con esa ruta. El generador comprueba el hash de los datos y reutiliza las métricas guardadas. La demo pública utiliza el snapshot sintético. Las barras, artefactos e informes del proveedor se manejan en local.

### Evidencia con datos reales sin redistribuirlos

La licencia de Alpaca no permite publicar las barras, así que se versiona solo un resumen agregado: [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json). Procede de `from-run` sobre el CSV del Proyecto I (`input_sha256` `2ebbd7d7…ce4b`, el mismo que registra `preparation.json` del run `alpaca-20261112`) con `--provider mock`, el 23/11/2026:

| Campo | Valor |
| --- | --- |
| `run_id` | `b2553cbc…6169211` |
| Datos | `alpaca`, 10 símbolos (AAPL, AMZN, GOOGL, JNJ, JPM, META, MSFT, NVDA, TSLA, XOM), 21 960 filas, `as_of` 2026-09-28 |
| Modelo | `swarm`; RMSE validación 0,0927 frente a 0,0937 de Dummy |
| Holdout (un toque) | RMSE 0,0919 · MAE 0,0705 · R² −0,0059 · acierto de signo 0,589 |
| Journal | `validate_input` 32,7 ms → `infer_snapshot` 132,4 ms → `publish_snapshot` 0,7 ms |

`run_id` incluye `generated_at`, así que cambia en cada ejecución aunque los datos y el modelo sean los mismos; para comparar una regeneración usa `input_sha256`, `artifact_sha256`, `validation`, `holdout` y `splits`, que sí se reproducen. El archivo no contiene precios, predicciones por símbolo, `input_summary` ni el texto de la explicación. Se regenera con `python -m dsia_web.evidence --snapshot <snapshot> --journal <pipeline.jsonl> --output <nuevo.json>`. En local, el mismo snapshot pasa `smoke_test.sh` y `browser_smoke.py --kind "Histórico Alpaca" --expect-pipeline`.

## Operación y verificación

- `--journal` escribe un JSONL por ejecución. Cada etapa tiene un inicio y un resultado con tiempo transcurrido. Un fallo incluye su tipo. El evento de publicación registra el `run_id`. En `from-run`, la etapa `validate_input` valida el CSV con el contrato del II y registra solo agregados (`rows`, `symbols`, `input_sha256`) antes de `infer_snapshot`. Usa un archivo nuevo fuera de `--work` para conservar la evidencia.
- `/health` confirma que el proceso tiene en memoria un snapshot válido. El timestamp del journal mide cuándo corrió el lote y `as_of` indica el cierre de los datos. Cada valor responde a una pregunta distinta durante la demo.
- Para un servicio gestionado, configura [`.env.example`](.env.example) en las variables del entorno y apunta a un snapshot persistente. API y dashboard comparten proceso; el empaquetado está en [Empaquetado y despliegue](#empaquetado-y-despliegue).
- Cada petición HTTP deja una línea INFO con `request_id` y `latency_ms`, y responde con `X-Request-ID` y cabeceras de seguridad (detalle en el [contrato](API.md)).
- Suite desde la raíz, con cobertura:

  ```bash
  AI_PROVIDER=mock HF_TOKEN= MPLBACKEND=Agg PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii \
    .venv-ii/bin/python -m pytest -q --cov=dsia_web --cov-report=term-missing proyectos/proyecto_iii/tests
  ```

## Guion de 5–7 minutos

| Tiempo | Qué mostrar |
| --- | --- |
| 1 min | Problema, fuente y horizonte de 21 sesiones. Carácter sintético de la demo y evidencia agregada del histórico Alpaca |
| 1 min | Diagrama con entrenamiento, artefacto e inferencia por lotes |
| 1 min | Panel **Operación**: estado 200, `run_id`, antigüedad, contadores y eventos del lote. Confirmar que el `run_id` coincide con `/health` y con el journal |
| 1,5 min | Ranking, filtro, tabla **Datos de entrada** y la respuesta HTTP en la red del navegador |
| 1 min | **Explicar símbolo**: `POST /api/v1/analyze` con `request_id` y latencia; explicar el 503 tipado si falla el proveedor |
| 1 min | Dummy frente a Ridge y Swarm en validación, holdout de un toque y R² negativo. Cerrar con CI, Docker y el rollback |

[Release Candidate](RELEASE.md) · [Rúbricas y trazabilidad](../../docs/TRAZABILIDAD_DSIA.md) · [Contrato HTTP](API.md) · [Citación de IA](AI_USAGE.md) · [Enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md)
