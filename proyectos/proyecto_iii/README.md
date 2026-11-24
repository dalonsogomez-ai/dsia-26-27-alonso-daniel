# Desarrollo de Soluciones de IA — Proyecto III

**Daniel Alonso Gómez · Curso 2026–2027 · Aplicación de investigación SwarmTrader**

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

`->` Llevar a producción el núcleo del [Proyecto II](../proyecto_ii/README.md) siguiendo el [enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md): mismos datos de Alpaca, mismo modelo sklearn y mismo cliente de IA, ampliados con una API, un dashboard web con panel de operación, pruebas de extremo a extremo y un despliegue público. El dashboard ordena los retornos estimados a 21 sesiones de diez acciones, los compara con un baseline y explica cada símbolo bajo demanda.

`=>` **Despliegue público:** [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com), con datos reales de Alpaca descargados al arrancar (último dato 2026-11-20) y solo predicciones y métricas en la respuesta pública. La primera visita tras un rato sin tráfico tarda unos 50 s, porque el plan gratuito duerme la instancia.

## Requisitos mínimos y evidencia

`>>` Cada requisito del enunciado del III con el fichero, el endpoint o la prueba que lo demuestra. Las cifras de pruebas proceden del run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) de `main` (commit `bd3b0fa`, 24/11/2026).

| Requisito del III | Evidencia (fichero, endpoint, prueba) |
| --- | --- |
| 1. Arquitectura modular y README claro | Paquete [`dsia_web/`](dsia_web) con un módulo por responsabilidad (ver [Arquitectura](#arquitectura)); el III importa preparación, entrenamiento, inferencia y `AIClient` del II sin reescribirlos. [Diagrama Excalidraw](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http) |
| 2. Procesamiento de datos real (dataset del II) | [`alpaca_source.py`](dsia_web/alpaca_source.py) descarga las barras diarias de los 10 símbolos del I y del II; [`serve.py`](dsia_web/serve.py) reentrena y publica al arrancar. En Render: `data_kind: alpaca`, 22 350 filas, último dato 2026-11-20. Histórico del II reproducido con `from-run`: [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json). Pruebas: `tests/test_alpaca.py`, `tests/test_serve.py` |
| 3. Integración con sklearn e IA generativa | [`build.py`](dsia_web/build.py) ejecuta la cadena del II (preparar → entrenar → holdout → inferir); [`ai.py`](dsia_web/ai.py) configura el `AIClient` del II desde `AI_PROVIDER`, `HF_*` y `NVIDIA_*`. Endpoints `GET /api/v1/predictions/{symbol}` y `POST /api/v1/analyze`. Proveedor `mock` justificado en CI; Hugging Face listo con `HF_TOKEN` y NVIDIA (`nvidia/nemotron-3.5-super-vl-120b-a12b`) con `NVIDIA_API_KEY`. Pruebas: `tests/test_build.py`, `tests/test_analyze.py` |
| 4. Pruebas automatizadas y CI | [`tests/`](tests): **123 tests y 97,22 % de cobertura** de `dsia_web` en el run 45288524693 (umbral 90 %), más [`smoke_test.sh`](scripts/smoke_test.sh), [`browser_smoke.py`](tests/browser_smoke.py) con Chromium y el job Docker del [workflow](../../.github/workflows/ci.yml) |
| 5. Dashboard web o de monitorización | [`dsia_web/static/`](dsia_web/static): **Producto** (ranking, filtro, evidencia del modelo, cortes temporales, «Explicar símbolo») y **Operación** (`/health`, `/api/v1/metrics`, `/api/v1/pipeline`). Prueba: `tests/test_web.py` y `browser_smoke.py` |
| 6. Despliegue accesible y empaquetado | [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com) con el [`Dockerfile`](Dockerfile) y [`render.yaml`](../../render.yaml); también [`Procfile`](../../Procfile). Ver [Despliegue en Render](#despliegue-en-render) y [Empaquetado](#empaquetado). Prueba: `tests/test_packaging.py` y job `proyecto-iii-docker` |
| 7. Exposición de 5–7 minutos con demo | [Guion de la exposición](#guion-de-la-exposición) sobre la URL de Render, con plan de contingencia en local |
| 8. Política de uso de IA | [`AI_USAGE.md`](AI_USAGE.md) con herramienta, modelo, lo aceptado, lo rechazado, la verificación y los commits |

| Entrega del III | Dónde |
| --- | --- |
| Mismo repositorio del Proyecto II | `proyectos/proyecto_ii/` y `proyectos/proyecto_iii/` en el [repositorio de entrega](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel) |
| Cómo entrenar e inferir | [Entrenar e inferir](#entrenar-e-inferir) |
| Cómo arrancar la API | [Arrancar la API](#arrancar-la-api) |
| Cómo arrancar el dashboard | [Arrancar el dashboard](#arrancar-el-dashboard) |
| URL de despliegue | [Despliegue en Render](#despliegue-en-render) |
| Evidencia de que el dashboard consume el backend real | [Evidencia de que el dashboard consume el backend real](#evidencia-de-que-el-dashboard-consume-el-backend-real) |

## Arquitectura

`->` El enunciado pide la cadena Ingesta → Procesamiento → Modelo / IA → API → Dashboard → Despliegue. Con barras diarias y un horizonte de 21 sesiones, el cálculo se hace **por lotes**: el lote congela un snapshot validado y el servidor solo lo lee, así que las lecturas de la API no dependen del modelo ni del proveedor de IA; solo `POST /api/v1/analyze` llama al cliente de IA.

```text
Ingesta  ─────────►  Procesamiento  ─────►  Modelo / IA  ──────►  API  ─────────►  Dashboard  ─────►  Despliegue
alpaca_source.py     contrato del II        sklearn del II         app.py           static/            Dockerfile
(barras Alpaca o     (validar, factores,    + snapshot.py          (Starlette +     (HTML/JS/CSS       render.yaml
 demo sintética)      split purgado)        + ai.py (AIClient)      Uvicorn)         propios)          serve.py
```

| Etapa | Módulo | Qué hace |
| --- | --- | --- |
| Ingesta | [`alpaca_source.py`](dsia_web/alpaca_source.py) | Descarga con `alpaca-py` las barras diarias ajustadas por split (feed SIP, reintento en IEX), conserva las fechas comunes y escribe solo `date, symbol, close, volume`. Sin credenciales, `build demo` genera barras sintéticas reproducibles |
| Procesamiento | [`build.py`](dsia_web/build.py) con el paquete del II | Valida el CSV con el contrato del II (etapa `validate_input`), construye factores causales y separa train, validation y holdout con purga de etiquetas |
| Modelo / IA | [`build.py`](dsia_web/build.py), [`snapshot.py`](dsia_web/snapshot.py), [`ai.py`](dsia_web/ai.py) | Compara Dummy, Ridge y Swarm en validation, evalúa el holdout una vez, infiere y publica un snapshot tipado con pydantic. La IA explica el resultado en el lote y bajo demanda |
| API | [`app.py`](dsia_web/app.py), [`observability.py`](dsia_web/observability.py), [`journal.py`](dsia_web/journal.py) | Starlette sirve salud, snapshot, predicción por símbolo, análisis, journal y métricas, con `X-Request-ID`, latencia en logs y cabeceras de seguridad. Contrato en [API.md](API.md) |
| Dashboard | [`static/`](dsia_web/static) | `index.html`, `dashboard.js` y `style.css` propios, sin CDN ni código inline; todo llega por `fetch` a la API del mismo origen |
| Despliegue | [`Dockerfile`](Dockerfile), [`serve.py`](dsia_web/serve.py), [`render.yaml`](../../render.yaml) | Imagen `python:3.12-slim` con usuario sin privilegios y `HEALTHCHECK`; al arrancar refresca el informe con Alpaca y lanza Uvicorn en `$PORT` |

`~>` **Tecnología.** Backend con **Starlette**, el núcleo ASGI de FastAPI, servido por Uvicorn, y dashboard con HTML y JavaScript propios. Es la opción «FastAPI+HTML» del enunciado: Starlette aporta el enrutado y el middleware, y la validación la hace pydantic de forma explícita. [`evidence.py`](dsia_web/evidence.py) exporta un resumen agregado del snapshot sin precios.

## Instalación

`>` Desde la raíz del repositorio, con **Python 3.12**. El II y el III comparten el entorno `.venv-ii`, separado del I porque este fija pandas 3 y el II pandas 2:

```bash
python3.12 -m venv .venv-ii
.venv-ii/bin/python -m pip install -r proyectos/proyecto_ii/requirements.txt
export PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii MPLBACKEND=Agg AI_PROVIDER=mock
```

`>>` `proyectos/proyecto_ii/requirements.txt` fija también las dependencias directas del III (starlette, uvicorn, pydantic, httpx). [`requirements-e2e.txt`](requirements-e2e.txt) añade Playwright para la prueba de navegador y [`requirements-runtime.txt`](requirements-runtime.txt) es el subconjunto de ejecución de la imagen Docker. Las variables de configuración están en [`.env.example`](.env.example); no hace falta ninguna clave para la demo.

## Entrenar e inferir

`->` El entrenamiento, la evaluación única del holdout y la inferencia son los del II; el III los orquesta en un lote que termina publicando el snapshot que sirve la API.

`>` Demo completa con datos sintéticos (`generate_bars → prepare → train → holdout → infer_snapshot → publish_snapshot`), en un destino nuevo:

```bash
.venv-ii/bin/python -m dsia_web.build demo --work runs/demo/work \
  --output runs/demo/snapshot.json --journal runs/demo/pipeline.jsonl
```

`>` Con datos reales de Alpaca, si las variables `ALPACA_PAPER_API_KEY_ID` y `ALPACA_PAPER_API_SECRET_KEY` están en el entorno (`auto` cae en la demo si no lo están):

```bash
.venv-ii/bin/python -m dsia_web.build alpaca --work runs/alpaca/work \
  --output runs/alpaca/snapshot.json --journal runs/alpaca/pipeline.jsonl
```

`~>` `from-run` reutiliza un modelo ya entrenado y evaluado por el II, sin reentrenar (ver [Informe con el histórico del Proyecto II](#informe-con-el-histórico-del-proyecto-ii)). La receta paso a paso del II está en su [README](../proyecto_ii/README.md#reproducir-sin-claves-ni-datos-de-terceros).

`>>` `--journal` escribe un JSONL con el inicio, el resultado y la duración de cada etapa; un fallo registra su tipo y no deja un snapshot parcial. La predicción por lotes se consulta después en el snapshot completo o por símbolo con `GET /api/v1/predictions/{symbol}`; la IA generativa se invoca bajo demanda con `POST /api/v1/analyze`.

## Arranque local de API y dashboard

`>` Con el snapshot generado, un solo proceso Uvicorn sirve la API y el dashboard.

### Arrancar la API

```bash
export DSIA_SNAPSHOT="$PWD/runs/demo/snapshot.json" DSIA_JOURNAL="$PWD/runs/demo/pipeline.jsonl"
.venv-ii/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765
```

`>` En otra terminal, el smoke HTTP comprueba `/health`, `/api/v1/snapshot`, la predicción del primer símbolo, `POST /api/v1/analyze` y `/api/v1/metrics`, y exige el mismo `run_id` en todos:

```bash
PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8765
curl -s http://127.0.0.1:8765/api/v1/predictions/DEMO01
curl -s -X POST -H 'Content-Type: application/json' -d '{"symbol": "DEMO01"}' http://127.0.0.1:8765/api/v1/analyze
```

`>>` Endpoints, errores tipados y cabeceras: [API.md](API.md). Con `DSIA_API_KEY` definida, `POST /api/v1/analyze` exige `X-API-Key`; el resto son de lectura. En producción el host cambia a `--host 0.0.0.0 --port "$PORT"`.

### Arrancar el dashboard

`>` Con la API en marcha, abrir [http://127.0.0.1:8765/](http://127.0.0.1:8765/). La página carga `/api/v1/snapshot`, `/health`, `/api/v1/metrics` y `/api/v1/pipeline` por HTTP y lanza `POST /api/v1/analyze` desde el formulario «Explicar símbolo».

`>` Prueba de navegador con Chromium real contra el servicio local:

```bash
.venv-ii/bin/python -m pip install -r proyectos/proyecto_iii/requirements-e2e.txt
.venv-ii/bin/python -m playwright install chromium --only-shell
.venv-ii/bin/python proyectos/proyecto_iii/tests/browser_smoke.py http://127.0.0.1:8765/ \
  --journal runs/demo/pipeline.jsonl --expect-pipeline --screenshot runs/demo/dashboard.png
```

`~>` **Recuperación.** Conserva el snapshot anterior: si el nuevo no supera el smoke, apunta `DSIA_SNAPSHOT` a la versión previa y reinicia. Un snapshot ausente o inválido deja `/health` en 503 y no se sirve. El rollback de código está en el [RC](RELEASE.md#rollback).

## Despliegue en Render

`=>` **URL de despliegue:** [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com) (dashboard) · API en [`/health`](https://dsia-swarmtrader.onrender.com/health), [`/api/v1/snapshot`](https://dsia-swarmtrader.onrender.com/api/v1/snapshot), [`/api/v1/predictions/AAPL`](https://dsia-swarmtrader.onrender.com/api/v1/predictions/AAPL), [`/api/v1/metrics`](https://dsia-swarmtrader.onrender.com/api/v1/metrics) y [`/api/v1/pipeline`](https://dsia-swarmtrader.onrender.com/api/v1/pipeline).

`~>` Web Service de Render con la imagen del [`Dockerfile`](Dockerfile), región Frankfurt, plan free y `healthCheckPath: /health`, desplegado desde `main` en cada commit. `render.yaml` deja `AI_PROVIDER=mock`; en el panel de Render el servicio usa `AI_PROVIDER=nvidia` con `NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b` y `NVIDIA_API_KEY` guardada solo allí, así que «Explicar símbolo» responde con un modelo real en 12–22 s (elección medida en el [README del II](../proyecto_ii/README.md#alternativa-nvidia)). La «Explicación del informe» del lote sigue en `mock` para que el arranque no dependa de un proveedor externo. Es la misma imagen que construye y prueba el job `proyecto-iii-docker` del CI.

### Datos reales de Alpaca

`->` El despliegue sirve barras diarias reales de AAPL, AMZN, GOOGL, JNJ, JPM, META, MSFT, NVDA, TSLA y XOM, el universo del Proyecto I.

`>` **Al arrancar el contenedor**, [`serve.py`](dsia_web/serve.py) (el `CMD` de la imagen) comprueba si hay credenciales en las variables `ALPACA_PAPER_API_KEY_ID` y `ALPACA_PAPER_API_SECRET_KEY` del servicio. Si el informe de la imagen es la demo o es de otro día, descarga las barras desde 2018 hasta la última sesión cerrada, reentrena con la cadena del II (preparar → entrenar → un toque del holdout → inferir) y publica el snapshot con `data_kind: alpaca` antes de lanzar Uvicorn. Si la descarga falla, registra el aviso y sirve el informe de la imagen. Con 0,1 CPU y 512 MB el refresco tarda unos 40 s, que se suman al arranque en frío.

`>` **En el build de la imagen**, `python -m dsia_web.build auto` usa el secret file opcional `alpaca.env`, que BuildKit monta solo durante ese `RUN`. Sin él (CI, local, o claves solo como variables, que Render pasa al build como *build args* y por eso no se leen allí), la imagen lleva la demo sintética.

`~>` **Procedencia y licencia.** Fuente: [Alpaca Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api), mediante `alpaca-py`, con claves de paper trading que dan acceso a datos de mercado. Alpaca [no permite redistribuir los datos obtenidos con su API](https://alpaca.markets/support/redistribute-alpaca-api). Por eso el informe público con datos reales **solo publica símbolos, retornos predichos y métricas de evaluación**: no incluye `input_summary` (cierres, retorno realizado ni volatilidad). El CSV descargado se borra al terminar y las claves no quedan en ninguna capa de la imagen ni en los logs. Las claves las introdujo el autor en el panel de Render (`sync: false` en `render.yaml`).

`>>` Comprobado el 23/11/2026 contra la URL pública: `/health` → `200 ready` con `data_kind: alpaca`, 10 símbolos y último dato **2026-11-20**; el journal registra `download_bars` con **22 350 filas**; `scripts/smoke_test.sh https://dsia-swarmtrader.onrender.com` → «Smoke correcto»; `tests/browser_smoke.py https://dsia-swarmtrader.onrender.com/ --kind "Datos reales · Alpaca" --expect-pipeline` → «OK · API, salud y operación, datos de entrada, análisis y su error, ranking, filtro, cortes y móvil»; y `/api/v1/snapshot` sin ningún `last_close`. [Captura del despliegue](evidencia/dashboard_render.png).

### Métricas del modelo desplegado

`>>` Valores que muestra la [captura del despliegue](evidencia/dashboard_render.png) del 23/11/2026 (lote de las 23:23 UTC, último dato 2026-11-20). El objetivo es el retorno del precio a 21 sesiones, en decimal; el error se expresa en puntos porcentuales de retorno.

| Métrica | Cálculo | Valor | Interpretación |
| --- | --- | --- | --- |
| RMSE de validation | `sqrt(media((y − ŷ)²))` sobre el bloque de validation | Dummy 9,96 % · Ridge 10,19 % · **Swarm 9,92 %** | Swarm se elige por menor RMSE, con una ventaja de 0,04 puntos sobre predecir la media |
| RMSE del holdout | Mismo cálculo en el holdout, evaluado una sola vez con el modelo congelado | 9,07 % | Error típico del retorno a 21 sesiones fuera de muestra |
| MAE del holdout | Media del valor absoluto de `y − ŷ` en el holdout | 6,82 % | Error absoluto medio, menos sensible a los meses extremos |
| R² del holdout | `1 − SSE / SST` respecto a la media del holdout | −0,0032 | Casi nulo: el modelo no explica mejor que la media. El panel muestra el aviso «Ventaja económica sin demostrar» |
| Evaluaciones del holdout | Contador del guard del II | 1 | El holdout no se usó para elegir modelo ni hiperparámetros |

`~>` Los cortes de esa ejecución son train 2019-01-03 → 2023-09-07 (11 570 filas), validation 2023-09-08 → 2025-04-01 (3 710) y holdout 2025-04-02 → 2026-11-20 (3 920), con la última etiqueta de cada bloque antes del inicio del siguiente. Las predicciones son señales de investigación, no recomendaciones de inversión, y no descuentan comisiones ni impuestos.

## Evidencia de que el dashboard consume el backend real

- `>>` [`browser_smoke.py`](tests/browser_smoke.py) abre Chromium, intercepta las respuestas reales de `/api/v1/snapshot` y `/api/v1/analyze` y comprueba que el DOM pinta lo mismo: número y orden de filas del ranking, `run_id` en la página, en `/health`, en el panel Operación y en el último evento del journal, y la respuesta de «Explicar símbolo». Un 503 simulado de `/api/v1/analyze` debe mostrarse como alerta; no admite errores de consola (incluidas violaciones de CSP) ni scroll horizontal a 390 px.
- `>>` El [workflow](../../.github/workflows/ci.yml) genera un snapshot desde cero en Linux, arranca Uvicorn y ejecuta `smoke_test.sh` y `browser_smoke.py --expect-pipeline`. En el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) ambos pasan («Smoke correcto» y «OK · API, salud y operación, datos de entrada, análisis y su error, ranking, filtro, cortes y móvil») y el artefacto `dsia-dashboard-sintetico` guarda la captura y el `pipeline.jsonl` del mismo run.
- `>>` La misma prueba pasa contra la URL de Render con `--kind "Datos reales · Alpaca"`; la [captura](evidencia/dashboard_render.png) del 24/11/2026 muestra el panel Operación con `run_id`, latencia media y p95 y los 12 eventos del lote, y el análisis de NVDA generado por `nvidia/nemotron-3.5-super-vl-120b-a12b` con su `request_id`. Con un LLM real el texto cambia en cada llamada, así que la prueba compara la segunda respuesta con su propio JSON y espera hasta 200 s (`ANALYZE_TIMEOUT` en `smoke_test.sh`).
- `=>` El panel **Operación** es la prueba en vivo durante la demo: los contadores de `/api/v1/metrics` crecen con cada petición del propio dashboard y el botón «Actualizar» los vuelve a pedir.

## Empaquetado

- `>` **Docker.** El contexto es la raíz del repositorio y [`.dockerignore`](../../.dockerignore) deja fuera `.git`, entornos, `runs`, `data/raw`, `.env*` y el resto de asignaturas. La imagen instala sin caché [`requirements-runtime.txt`](requirements-runtime.txt) (las versiones fijadas del II más `alpaca-py`, sin marimo ni pytest; `tests/test_packaging.py` impide que se desalineen), genera el snapshot en el build, corre con el uid 10001 y declara un `HEALTHCHECK` contra `/health`.

  ```bash
  docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
  docker run --rm -p 8790:8000 dsia-iii        # -e PORT=9000 cambia el puerto interno
  PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
  ```

- `>` **Render.** [`render.yaml`](../../render.yaml) describe el servicio desplegado (`runtime: docker`, rama `main`, Frankfurt, plan free, `healthCheckPath: /health`). `HF_TOKEN`, `NVIDIA_API_KEY`, `DSIA_API_KEY` y las claves `ALPACA_*` se introducen en el panel (`sync: false`); `NVIDIA_MODEL` va en el blueprint y `AI_PROVIDER` sigue en `mock`. Para explicar con NVIDIA basta con poner `AI_PROVIDER=nvidia` y la clave en el panel; si la llamada falla, `/api/v1/analyze` responde 503 y el informe sigue disponible. Para recrearlo: *New → Blueprint* con este repositorio, o *New → Web Service* con Language `Docker` y Dockerfile Path `./proyectos/proyecto_iii/Dockerfile`. Para forzar datos nuevos: *Manual Deploy → Restart service*. Con el secret file: `docker build --secret id=alpaca_env,src=alpaca.env -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .`
- `>` **Procfile.** [`Procfile`](../../Procfile) arranca sin contenedor en un runner con `proyectos/proyecto_ii/requirements.txt` instalado: genera la demo si falta y lanza Uvicorn en `$PORT`. [`.python-version`](../../.python-version) fija Python 3.12. En Heroku el buildpack de Python instalaría el `requirements.txt` raíz (solo el I), así que allí se usa el contenedor.

## Informe con el histórico del Proyecto II

`->` Reproducir el run congelado del II con el CSV de Alpaca del Proyecto I, sin reentrenar. Sigue la [receta del II](../proyecto_ii/README.md#reproducir-el-histórico-autorizado) y define `DSIA_BARS_CSV` y `DSIA_FROZEN_RUN` (el directorio con `model.joblib` y `test_metrics.json`) en el entorno local:

```bash
history_dir=$(mktemp -d)
.venv-ii/bin/python -m dsia_web.build from-run \
  --data "$DSIA_BARS_CSV" --run "$DSIA_FROZEN_RUN" --provider mock \
  --output "$history_dir/snapshot.json" --journal "$history_dir/pipeline.jsonl"
export DSIA_SNAPSHOT="$history_dir/snapshot.json"
```

`>>` El generador comprueba el hash de los datos y reutiliza las métricas guardadas. Como la licencia de Alpaca no permite publicar las barras, se versiona solo un resumen agregado: [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json), generado el 23/11/2026 con `--provider mock` sobre el CSV del I (`input_sha256` `2ebbd7d7…ce4b`, el mismo que registra el run `alpaca-20261112` del II):

| Campo | Valor |
| --- | --- |
| `run_id` | `b2553cbc…6169211` |
| Datos | `alpaca`, 10 símbolos, 21 960 filas, `as_of` 2026-09-28 |
| Modelo | `swarm`; RMSE de validation 0,0927 frente a 0,0937 de Dummy |
| Holdout (un toque) | RMSE 0,0919 · MAE 0,0705 · R² −0,0059 · acierto de signo 0,589 |
| Journal | `validate_input` 32,7 ms → `infer_snapshot` 132,4 ms → `publish_snapshot` 0,7 ms |

`~>` `run_id` incluye `generated_at` y cambia en cada ejecución; para comparar una regeneración se usan `input_sha256`, `artifact_sha256`, `validation`, `holdout` y `splits`. El archivo no contiene precios, predicciones por símbolo ni el texto de la explicación. Se regenera con `python -m dsia_web.evidence --snapshot <snapshot> --journal <pipeline.jsonl> --output <nuevo.json>`.

## Pruebas y CI

`>` Suite del III desde la raíz, con cobertura:

```bash
AI_PROVIDER=mock HF_TOKEN= MPLBACKEND=Agg PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii \
  .venv-ii/bin/python -m pytest -q --cov=dsia_web --cov-report=term-missing --cov-fail-under=90 proyectos/proyecto_iii/tests
```

`>>` Las pruebas cubren el resumen de entrada del snapshot y su compatibilidad (`test_snapshot.py`), la IA del lote y `from-run` con sus fallos (`test_build.py`), la descarga simulada de Alpaca (`test_alpaca.py`), el refresco al arrancar (`test_serve.py`), la API (`test_api.py`, `test_analyze.py`, `test_pipeline.py`), el middleware (`test_observability.py`), el dashboard servido y el journal del lote (`test_web.py`), la evidencia agregada (`test_evidence.py`) y la imagen (`test_packaging.py`). No usan red ni claves.

`>>` [Workflow](../../.github/workflows/ci.yml) en `push` a `main`, `pull_request` y manual. El job `proyectos-ii-y-iii` ejecuta el pytest del III con umbral del 90 %, el lote demo, el smoke HTTP y Playwright, y publica el artefacto; `proyecto-iii-docker` construye la imagen, espera al `HEALTHCHECK` y pasa el smoke contra el contenedor.

`=>` Run verde [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) de `main` (commit `bd3b0fa`, 24/11/2026): **123 tests y 97,22 % de cobertura** de `dsia_web`, smoke y Playwright correctos contra Uvicorn, y smoke correcto contra el contenedor. La verificación local del 24/11/2026 con `.venv-ii`, tras añadir el proveedor NVIDIA, da 134 tests en verde y 97,20 % de cobertura.

## Operación

- `>` `/health` confirma que el proceso tiene en memoria un snapshot válido y devuelve `checks` (`data_kind`, `as_of`, antigüedad en días y disponibilidad del journal); sin snapshot responde 503.
- `>` `as_of` es la fecha del último dato y el timestamp del journal, la hora a la que corrió el lote: responden a preguntas distintas durante la demo.
- `>` Cada petición deja una línea INFO con `request_id` y `latency_ms` y responde con `X-Request-ID`, CSP `default-src 'self'`, `nosniff` y `no-referrer`.
- `>` `GET /api/v1/pipeline` solo expone campos agregados del journal (etapa, estado, duración, `run_id`, filas, símbolos y hash), nunca rutas.

## Guion de la exposición

`->` Exposición de 5–7 minutos con la demo sobre **[https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com)**. Abrir la URL unos minutos antes para que el plan gratuito despierte la instancia (unos 50 s más el refresco de Alpaca).

| Tiempo | Qué mostrar |
| --- | --- |
| 0:00–1:00 | Problema y usuario: ranking de retorno a 21 sesiones de diez acciones. Fuente Alpaca, etiqueta «Datos reales · Alpaca» y por qué solo se publican predicciones (licencia) |
| 1:00–2:00 | [Diagrama](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http): Ingesta → Procesamiento → Modelo / IA → API → Dashboard → Despliegue, y por qué por lotes |
| 2:00–3:00 | Panel **Operación** en Render: estado 200, `run_id`, último dato 2026-11-20, contadores y eventos del lote con `download_bars`. Abrir [`/health`](https://dsia-swarmtrader.onrender.com/health) en otra pestaña y comparar el `run_id` |
| 3:00–4:30 | Ranking y filtro; en la pestaña Red del navegador, la respuesta de `/api/v1/snapshot`. **Explicar símbolo**: `POST /api/v1/analyze` con `request_id` y latencia, y el 503 tipado si cae el proveedor |
| 4:30–5:30 | Evidencia del modelo: Dummy frente a Ridge y Swarm en validation, holdout de un toque y R² casi nulo, explicado como límite del resultado |
| 5:30–6:30 | CI del run 45288524693 (123 tests, Playwright, Docker), `Dockerfile` con `HEALTHCHECK`, rollback y [registro de IA](AI_USAGE.md) para las preguntas |

`~>` **Contingencia.** Si Render no responde, arrancar la demo local de [Arranque local de API y dashboard](#arranque-local-de-api-y-dashboard), pasar `smoke_test.sh` y enseñar la [captura del despliegue](evidencia/dashboard_render.png) y el artefacto del CI como referencia visual.

## Uso de IA

`>>` [AI_USAGE.md](AI_USAGE.md): OpenAI Codex (modelo gpt-6.2-sol) en la integración del 23/11/2026 y Claude Code (modelo Claude Opus 5.5) en la auditoría de cumplimiento, el despliegue y los datos reales, con lo aceptado, lo rechazado, la verificación y los commits. El proveedor `mock` produce la explicación de la demo sin llamar a un modelo externo; a él solo viajan agregados, nunca precios ni claves.

## Desarrollo por fechas

- `->` **11 noviembre:** se crea el repositorio de investigación [`dalonsogomez-ai/swarmtrader`](https://github.com/dalonsogomez-ai/swarmtrader); el código que reutiliza el II es su v1.4.0 (commit `5642dda`, ver [UPSTREAM.json](../proyecto_ii/UPSTREAM.json)).
- `~>` **12 noviembre:** el Proyecto II se escribe con OpenAI Codex (gpt-6.1-sol): contrato temporal, gates y adaptación del código. Es el núcleo que amplía el III.
- `>>` **19 noviembre:** auditoría de la extracción de Alpaca con Codex (gpt-6.1-sol).
- `~>` **23 noviembre:** integración del II y del III en el repositorio de entrega (`e524ec0` y `3d991d2`) con Codex (gpt-6.2-sol): lote, snapshot, API, dashboard y CI.
- `>` **23 noviembre:** auditoría de cumplimiento con Claude Code (Claude Opus 5.5) y mejoras en commits atómicos: endpoints de predicción, análisis, pipeline y métricas, panel Operación, cabeceras de seguridad, Dockerfile y blueprint de Render.
- `=>` **23 noviembre:** [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) fusionado en `main` (`a5a5b9b`), tag [`v0.9.0-rc1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1) y despliegue en Render.
- `~>` **23-24 noviembre:** datos reales de Alpaca en Render: descarga en el build ([PR #2](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/2), `bed8312`) y refresco al arrancar ([PR #3](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/3), `033d134`).
- `=>` **24 noviembre:** `main` en `bd3b0fa` con el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) en verde y el despliegue sirviendo datos hasta el 2026-11-20.
- `~>` **24 noviembre:** proveedor alternativo NVIDIA (`a86b9de`), porque la cuenta de Hugging Face no tiene saldo, y elección de Nemotron 3.5 Super tras medir cinco modelos en Render (`edb049c`).
- `>>` **Octubre:** no hay commits del II ni del III en octubre. El trabajo entró en Git a partir del 23/11/2026 y no se fabrican fechas ni se reescribe el historial.

`>>` [Release Candidate](RELEASE.md) · [Contrato HTTP](API.md) · [Citación de IA](AI_USAGE.md) · [Rúbricas y trazabilidad](../../docs/TRAZABILIDAD_DSIA.md) · [Enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md)
