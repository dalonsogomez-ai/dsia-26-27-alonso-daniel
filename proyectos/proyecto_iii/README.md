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

`=>` **Despliegue público:** [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com), con datos reales de Alpaca descargados al arrancar (el 24/11/2026 servía `as_of` 2026-11-23), solo predicciones y métricas en la respuesta pública y «Explicar símbolo» con `nvidia/nemotron-3.5-super-vl-120b-a12b`. La primera visita tras un rato sin tráfico tarda unos 50 s, más el refresco de Alpaca (unos 40 s; ver [Issues conocidos](RELEASE.md#issues-conocidos)), porque el plan gratuito duerme la instancia y la imagen lleva la demo.

## Requisitos mínimos y evidencia

`>>` Cada requisito del enunciado del III con el fichero, el endpoint o la prueba que lo demuestra. Las cifras de pruebas se verificaron en local el 24/11/2026 con `.venv-ii`. El estado del CI está en el [historial de `main`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions?query=branch%3Amain); último run comprobado: [45306204500](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45306204500) (`e433fae`, 24/11/2026), en verde.

| Requisito del III | Evidencia (fichero, endpoint, prueba) |
| --- | --- |
| 1. Arquitectura modular y README claro | Paquete [`dsia_web/`](dsia_web) con un módulo por responsabilidad (ver [Arquitectura](#arquitectura)); el III importa preparación, entrenamiento, inferencia y `AIClient` del II sin reescribirlos. [Diagrama Excalidraw](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http) |
| 2. Procesamiento de datos real (dataset del II) | [`alpaca_source.py`](dsia_web/alpaca_source.py) descarga las barras diarias de los 10 símbolos del I y del II; [`serve.py`](dsia_web/serve.py) reentrena y publica al arrancar. En Render el 24/11/2026: `data_kind: alpaca` y `as_of` 2026-11-23. Histórico del II reproducido con `from-run`: [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json). Pruebas: `tests/test_alpaca.py`, `tests/test_serve.py` |
| 3. Integración con sklearn e IA generativa | [`build.py`](dsia_web/build.py) ejecuta la cadena del II (preparar → entrenar → holdout → inferir); [`ai.py`](dsia_web/ai.py) configura el `AIClient` del II desde `AI_PROVIDER`, `HF_*` y `NVIDIA_*`. Endpoints `GET /api/v1/predictions/{symbol}` y `POST /api/v1/analyze`. `mock` en CI y en la explicación del lote; en Render, «Explicar símbolo» usa NVIDIA (`nvidia/nemotron-3.5-super-vl-120b-a12b`). Hugging Face está implementado y probado con dobles; sus llamadas autenticadas del 24/11 fallaron por falta de crédito ([Issues conocidos](RELEASE.md#issues-conocidos)). Pruebas: `tests/test_build.py`, `tests/test_analyze.py` |
| 4. Pruebas automatizadas y CI | [`tests/`](tests): **298 tests y 98,25 % de cobertura** de `dsia_web`, verificado en local el 24/11/2026 con `v0.9.0-rc2` tras la tercera ronda de verificación (umbral 90 %), más [`smoke_test.sh`](scripts/smoke_test.sh), [`browser_smoke.py`](tests/browser_smoke.py) con Chromium y el job Docker del [workflow](../../.github/workflows/ci.yml) |
| 5. Dashboard web o de monitorización | [`dsia_web/static/`](dsia_web/static): **Producto** (ranking, filtro, evidencia del modelo, cortes temporales, «Explicar símbolo») y **Operación** (`/health`, `/api/v1/metrics`, `/api/v1/pipeline`, con el [grafo del lote](#grafo-del-lote) y la tabla de eventos). Prueba: `tests/test_web.py` y `browser_smoke.py` |
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
| API | [`app.py`](dsia_web/app.py), [`ratelimit.py`](dsia_web/ratelimit.py), [`observability.py`](dsia_web/observability.py), [`journal.py`](dsia_web/journal.py) | Starlette sirve salud (con versión y commit), snapshot, predicción por símbolo, análisis con límite de uso, journal y métricas, con `X-Request-ID`, latencia en logs y cabeceras de seguridad. Contrato en [API.md](API.md) |
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

`>` **Con un fichero `.env`.** La API no carga ningún `.env` por su cuenta (solo el arranque del contenedor lee el secret file de Alpaca): las variables de [`.env.example`](.env.example) se exportan o se pasan a Uvicorn con `--env-file`, que usa `python-dotenv` (fijado en el `requirements.txt` del II). Para usar `hf` o `nvidia` en local sin escribir la clave en la shell:

```bash
cp proyectos/proyecto_iii/.env.example proyectos/proyecto_iii/.env   # ignorado por git: la clave, solo aquí
.venv-ii/bin/python -m uvicorn dsia_web.app:app --env-file proyectos/proyecto_iii/.env --host 127.0.0.1 --port 8765
```

`~>` Las variables ya exportadas en la shell mandan sobre las del fichero (Uvicorn no las sobrescribe): con el `export AI_PROVIDER=mock` de [Instalación](#instalación), el `AI_PROVIDER` del `.env` no se aplica hasta hacer `unset AI_PROVIDER`. `DSIA_SNAPSHOT` y `DSIA_JOURNAL` de la plantilla apuntan a `runs/dsia-demo/`, las rutas del CI: se ajustan en el `.env` o se mantienen los `export` de arriba.

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

`>>` Esta sección describe `v0.9.0-rc2`, la versión de este árbol (`dsia_web.__version__`). Lo que añade a `e433fae`, el despliegue del 24/11/2026 (límite de uso y análisis simultáneos acotados, `version`, `commit` y `degraded` en `/health`, refresco en un proceso hijo, contexto del símbolo, modos de fallo del mock), solo está en la URL pública desde que se despliega esa versión; qué versión sirve Render se comprueba en [Versión desplegada](RELEASE.md#versión-desplegada).

`~>` Web Service de Render con la misma imagen que construye y prueba el job `proyecto-iii-docker` del CI, región Frankfurt y plan free, desplegado desde `main` en cada commit (`autoDeployTrigger: commit`). Pasos y comprobaciones:

1. `>` **URL.** Dashboard en [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com); la API cuelga del mismo origen (enlaces de arriba). La primera visita tras un rato sin tráfico tarda unos 50 s, más el refresco de Alpaca (unos 40 s; ver [Issues conocidos](RELEASE.md#issues-conocidos)): el plan gratuito duerme la instancia y, como la imagen lleva la demo (punto 3), cada arranque descarga y reentrena.
2. `>` **Versión y commit.** Desde `v0.9.0-rc2`, `curl -s https://dsia-swarmtrader.onrender.com/health` devuelve `version` (`0.9.0-rc2`) y `commit` (los 7 primeros caracteres de `RENDER_GIT_COMMIT`, que Render inyecta), y el panel Operación los muestra en la tarjeta «Estado». Sin esos campos, Render sirve una versión anterior (el 24/11/2026, `e433fae`). Ver [Versión desplegada](RELEASE.md#versión-desplegada).
3. `>` **Build.** Render construye el [`Dockerfile`](Dockerfile) con el contexto en la raíz (`dockerfilePath: ./proyectos/proyecto_iii/Dockerfile` y `dockerContext: .` en [`render.yaml`](../../render.yaml)). El build ejecuta `python -m dsia_web.build auto`: con el secret file opcional `alpaca.env` genera el informe con datos reales y, sin él, con la demo sintética.
4. `>` **Variables.** Se definen en el panel de Render (*Environment*); ninguna de las nuevas es obligatoria, porque los valores por defecto aplican:
   - `>` Secretos, con `sync: false` en `render.yaml`: `ALPACA_PAPER_API_KEY_ID` y `ALPACA_PAPER_API_SECRET_KEY` (las lee `serve.py` al arrancar), `NVIDIA_API_KEY`, `HF_TOKEN` y, opcional, `DSIA_API_KEY`.
   - `>` IA: `render.yaml` deja `AI_PROVIDER=mock`; en el panel, el servicio usa `AI_PROVIDER=nvidia` y `NVIDIA_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b`, con `NVIDIA_MAX_TOKENS` (4096) y `NVIDIA_TIMEOUT` (60 s) en sus valores por defecto.
   - `>` Límite de uso de `POST /api/v1/analyze`: `DSIA_ANALYZE_PER_MINUTE` (5 por conexión), `DSIA_ANALYZE_PER_IP_DAY` (30 al día por conexión), `DSIA_ANALYZE_PER_DAY` (200 en todo el servicio), `DSIA_ANALYZE_CONCURRENCY` (4 análisis a la vez) y `DSIA_ANALYZE_CONCURRENCY_PER_IP` (2 a la vez por conexión). `DSIA_TRUSTED_PROXY_HOPS` (1) solo se usa si falta `CF-Connecting-IP`, que en Render escribe Cloudflare ([IP de cliente](API.md#límite-de-uso)); `0` es para un servicio sin proxy delante. Un valor negativo o no entero, o `0` salvo en `DSIA_TRUSTED_PROXY_HOPS`, detiene el arranque.
   - `>` Refresco al arrancar: `DSIA_REFRESH_TIMEOUT` (180 s). Un valor no válido avisa en el log y usa 180.
   - `>` Render inyecta `PORT` y `RENDER_GIT_COMMIT`; `DSIA_COMMIT` solo se usa fuera de Render.
5. `>` **Start.** El `CMD` de la imagen es `python -m dsia_web.serve`: con claves de Alpaca y un informe de demo o de otro día, refresca el informe y después lanza `uvicorn dsia_web.app:app` en `$PORT`; desde `v0.9.0-rc2`, el refresco es `python -m dsia_web.build alpaca` en un proceso hijo con el tope de `DSIA_REFRESH_TIMEOUT` (antes corría en el mismo proceso y sin tope). Render da el servicio por sano cuando `/health` (`healthCheckPath`) responde 200: `ready` o, desde `v0.9.0-rc2`, `degraded` (IA en fallo o mal configurada: el informe sigue servido). También desde `v0.9.0-rc2`, una configuración de IA no válida deja al arrancar `config_invalid ai_provider=…` en el log y `ai_config: invalid` en `/health`.
6. `>` **Smoke.** `PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh https://dsia-swarmtrader.onrender.com`. Cada GET espera hasta `SMOKE_TIMEOUT` segundos (90 por defecto) y el primer `/health` se reintenta 6 veces cada 10 s (también con la conexión rechazada o un 5xx), para cubrir el arranque en frío (unos 50 s) más el refresco de Alpaca (hasta `DSIA_REFRESH_TIMEOUT`, 180 s). El análisis espera hasta `ANALYZE_TIMEOUT` (200, por la cola de NVIDIA con sus reintentos). Acepta `/health` en `ready` o `degraded`, pero el análisis tiene que salir bien. Después, `browser_smoke.py https://dsia-swarmtrader.onrender.com/ --kind "Datos reales · Alpaca" --expect-pipeline` (desde `v0.9.0-rc2`, porque exige `version` y `commit`; con `e433fae`, la de `git show e433fae:proyectos/proyecto_iii/tests/browser_smoke.py`). Para comprobar la IP de cliente sin registrarla (desde `v0.9.0-rc2`), tras hacer al menos un análisis (por ejemplo, el de `smoke_test.sh`; los GET no cuentan): `curl -s https://dsia-swarmtrader.onrender.com/api/v1/metrics` y mirar `rate_limit.client_ip_source` (se espera `cf-connecting-ip`) y `rate_limit.xff_hops_seen`.
7. `>` **Rollback.** *Rollback* al deploy anterior en la pestaña *Deploys* (desactivando antes el auto-deploy) o *Manual Deploy* del commit bueno (desde la RC2, `e433fae`); si falla solo el proveedor de IA, basta `AI_PROVIDER=mock` en el panel. Después, repetir el smoke y comprobar el commit servido: en `/health` desde la RC2; con `e433fae`, que no tiene ese campo, en *Deploys* (y la prueba de navegador, la de ese commit). No consta ningún rollback ensayado en Render. Detalle en el [RC](RELEASE.md#rollback).

`~>` Con `AI_PROVIDER=nvidia`, «Explicar símbolo» responde con un modelo real en 13–22 s (elección medida en el [README del II](../proyecto_ii/README.md#alternativa-nvidia)). Desde `v0.9.0-rc2`, el modelo recibe los agregados de todo el informe y el puesto del símbolo pedido; antes recibía solo ese símbolo como si fuera todo el universo (`symbols=1`). La «Explicación del informe» del lote sigue en `mock` para que el arranque no dependa de un proveedor externo.

`>` Como la URL es pública y cada análisis gasta la clave de NVIDIA, desde `v0.9.0-rc2` al superar el límite `POST /api/v1/analyze` responde `429 rate_limited` con `Retry-After`; con 2 análisis de la misma conexión en curso, `429 analyze_busy_client`, y con 4 en total, `503 analyze_busy`, ambos al momento ([Límite de uso](API.md#límite-de-uso)). Limitaciones conocidas del despliegue (cola de NVIDIA, arranque en frío, contador en memoria): [Issues conocidos](RELEASE.md#issues-conocidos).

### Datos reales de Alpaca

`->` El despliegue sirve barras diarias reales de AAPL, AMZN, GOOGL, JNJ, JPM, META, MSFT, NVDA, TSLA y XOM, el universo del Proyecto I.

`>` **Al arrancar el contenedor**, [`serve.py`](dsia_web/serve.py) (el `CMD` de la imagen) comprueba si hay credenciales en las variables `ALPACA_PAPER_API_KEY_ID` y `ALPACA_PAPER_API_SECRET_KEY` del servicio (si faltan, las busca en el secret file `/etc/secrets/alpaca.env`, donde Render monta los secret files). Si el informe de la imagen es la demo o es de otro día, descarga las barras desde 2018 hasta la última sesión cerrada, reentrena con la cadena del II (preparar → entrenar → un toque del holdout → inferir) y publica el snapshot con `data_kind: alpaca` antes de lanzar Uvicorn. Desde `v0.9.0-rc2`, el lote corre en un proceso hijo (`python -m dsia_web.build alpaca`) con un tope de `DSIA_REFRESH_TIMEOUT` segundos (180 por defecto): si la descarga falla o se cuelga, se mata el hijo, se registra el motivo y se sirve el informe de la imagen. Con 0,1 CPU y 512 MB el refresco tarda unos 40 s, que se suman al arranque en frío.

`>` **En el build de la imagen**, `python -m dsia_web.build auto` usa el secret file opcional `alpaca.env`, que BuildKit monta solo durante ese `RUN`. Sin él (CI, local, o claves solo como variables, que Render pasa al build como *build args* y por eso no se leen allí), la imagen lleva la demo sintética.

`~>` **Procedencia y licencia.** Fuente: [Alpaca Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api), mediante `alpaca-py`, con claves de paper trading que dan acceso a datos de mercado. Alpaca [no permite redistribuir los datos obtenidos con su API](https://alpaca.markets/support/redistribute-alpaca-api). Por eso el informe público con datos reales **solo publica símbolos, retornos predichos y métricas de evaluación**: no incluye `input_summary` (cierres, retorno realizado ni volatilidad). El CSV descargado se borra al terminar y las claves no quedan en ninguna capa de la imagen ni en los logs. Las claves las introdujo el autor en el panel de Render (`sync: false` en `render.yaml`).

`>>` Comprobado el 23/11/2026 contra la URL pública: `/health` → `200 ready` con `data_kind: alpaca`, 10 símbolos y último dato 2026-11-20; el journal registra `download_bars` con 22 350 filas; `scripts/smoke_test.sh https://dsia-swarmtrader.onrender.com` → «Smoke correcto»; `tests/browser_smoke.py https://dsia-swarmtrader.onrender.com/ --kind "Datos reales · Alpaca" --expect-pipeline` → «OK · API, salud y operación, datos de entrada, análisis y su error, ranking, filtro, cortes y móvil»; y `/api/v1/snapshot` sin ningún `last_close`. El 24/11/2026 el despliegue servía `as_of` 2026-11-23 y la prueba de navegador volvió a pasar con el análisis de Nemotron ([captura del despliegue](evidencia/dashboard_render.png)). Como el servicio reentrena en cada arranque, `as_of`, el `run_id` y las métricas cambian de un día a otro: el valor vigente es el de `/health`.

### Métricas del modelo desplegado

`>>` Valores que muestra la [captura del despliegue](evidencia/dashboard_render.png) del 24/11/2026 (lote de las 01:32 UTC, `as_of` 2026-11-23). El objetivo es el retorno del precio a 21 sesiones, en decimal; el error se expresa en puntos porcentuales de retorno.

| Métrica | Cálculo | Valor | Interpretación |
| --- | --- | --- | --- |
| RMSE de validation | `sqrt(media((y − ŷ)²))` sobre el bloque de validation | Dummy 9,97 % · Ridge 10,19 % · **Swarm 9,92 %** | Swarm se elige por menor RMSE, con una ventaja de 0,05 puntos sobre predecir la media |
| RMSE del holdout | Mismo cálculo en el holdout, evaluado una sola vez con el modelo congelado | 9,08 % | Error típico del retorno a 21 sesiones fuera de muestra |
| MAE del holdout | Media del valor absoluto de `y − ŷ` en el holdout | 6,83 % | Error absoluto medio, menos sensible a los meses extremos |
| R² del holdout | `1 − SSE / SST` respecto a la media del holdout | −0,0032 | Casi nulo: el modelo no explica mejor que la media. El panel muestra el aviso «Ventaja económica sin demostrar» |
| Evaluaciones del holdout | Contador del guard del II | 1 | El holdout no se usó para elegir modelo ni hiperparámetros |

`~>` Los cortes de esa ejecución son train 2019-01-03 → 2023-09-08 (11 580 filas), validation 2023-09-11 → 2025-04-02 (3 710) y holdout 2025-04-03 → 2026-11-23 (3 920), con la última etiqueta de cada bloque antes del inicio del siguiente. Las predicciones son señales de investigación, no recomendaciones de inversión, y no descuentan comisiones ni impuestos.

## Evidencia de que el dashboard consume el backend real

- `>>` [`browser_smoke.py`](tests/browser_smoke.py) abre Chromium, intercepta las respuestas reales de `/api/v1/snapshot` y `/api/v1/analyze` y comprueba que el DOM pinta lo mismo: número y orden de filas del ranking, `run_id` en la página, en `/health`, en el panel Operación y en el último evento del journal, y la respuesta de «Explicar símbolo». Un 503 y un 429 simulados de `/api/v1/analyze` (este con `Retry-After`) deben mostrarse como alerta; la versión y el commit, en la tarjeta «Estado», y un `/health` simulado en `degraded` con la última llamada fallida, como «Degradado (200)»; en el grafo del lote, cada nodo debe tener el estado del último evento real de su etapa y su detalle tantos eventos como devuelve la API; se simulan el journal ausente, ilegible y truncado, un `run_id` discrepante y un refresco, se recorren los 15 casos del modelo del grafo y se navega con teclado, también a 390 px en una columna; no admite otros errores de consola, ninguna violación de CSP (registradas con `securitypolicyviolation`) ni scroll horizontal a 390 px.
- `>>` El [workflow](../../.github/workflows/ci.yml) genera un snapshot desde cero en Linux, arranca Uvicorn y ejecuta `smoke_test.sh` y `browser_smoke.py --expect-pipeline`; ambos deben terminar con «Smoke correcto» y «OK · API, salud y operación, grafo del lote (estados reales, degradados, teclado y CSP), datos de entrada, análisis y su error, ranking, filtro, cortes y móvil a 390 px», y el artefacto `dsia-dashboard-sintetico` guarda la captura, la del panel Operación a 390 px (`operacion-390.png`) y el `pipeline.jsonl` del mismo run. Resultados en el [historial de `main`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions?query=branch%3Amain); último run comprobado: [45306204500](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45306204500) (`e433fae`, 24/11/2026). En local, el 24/11/2026, las dos pruebas pasaron también con `v0.9.0-rc2`.
- `>>` El 23 y el 24/11/2026, la prueba de entonces (el 24/11, la de `e433fae`) pasó contra la URL de Render con `--kind "Datos reales · Alpaca"`. La de `v0.9.0-rc2` exige además `version`, `commit` y el proveedor de IA en `/health` y en la tarjeta «Estado», así que contra Render solo pasa desde que sirve la RC2; mientras sirva `e433fae`, vale la de `git show e433fae:proyectos/proyecto_iii/tests/browser_smoke.py`. La [captura](evidencia/dashboard_render.png) del 24/11/2026 muestra el panel Operación con `run_id`, latencia media y p95 y los 12 eventos del lote, y el análisis de NVDA generado por `nvidia/nemotron-3.5-super-vl-120b-a12b` con su `request_id`. Con un LLM real el texto cambia en cada llamada, así que la prueba compara la segunda respuesta con su propio JSON y espera hasta 200 s (`ANALYZE_TIMEOUT` en `smoke_test.sh`). Los GET del smoke esperan hasta 90 s (`SMOKE_TIMEOUT`) y el primero se reintenta, para tolerar el arranque en frío de Render. El texto de esa captura es anterior al contexto por símbolo: `/api/v1/analyze` enviaba entonces `symbols=1`, y por eso el modelo dice que hay un solo símbolo. El panel pedía entonces 12 eventos y el lote con Alpaca registra 14; ahora pide 20, así que una captura nueva mostrará también `download_bars`.
- `=>` El panel **Operación** es la prueba en vivo durante la demo: los contadores de `/api/v1/metrics` crecen con cada petición del propio dashboard y el botón «Actualizar» los vuelve a pedir.

## Empaquetado

- `>` **Docker.** El contexto es la raíz del repositorio y [`.dockerignore`](../../.dockerignore) deja fuera `.git`, entornos, `runs`, `data/raw`, `.env*`, cualquier `*.env` (como el secret file `alpaca.env`, también dentro de un proyecto) y el resto de asignaturas; [`.gitignore`](../../.gitignore) ignora igualmente `alpaca.env` y `*.env` en cualquier carpeta (`tests/test_packaging.py` comprueba ambos). La imagen instala sin caché [`requirements-runtime.txt`](requirements-runtime.txt) (las versiones fijadas del II más `alpaca-py`, sin marimo ni pytest; `tests/test_packaging.py` impide que se desalineen), genera el snapshot en el build, corre con el uid 10001 y declara un `HEALTHCHECK` contra `/health`.

  ```bash
  docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
  docker run --rm -p 8790:8000 -e DSIA_TRUSTED_PROXY_HOPS=0 dsia-iii   # sin proxy delante; -e PORT=9000 cambia el puerto interno
  PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
  ```

- `>` **Render.** [`render.yaml`](../../render.yaml) describe el servicio desplegado (`runtime: docker`, rama `main`, Frankfurt, plan free, `healthCheckPath: /health`). `HF_TOKEN`, `NVIDIA_API_KEY`, `DSIA_API_KEY` y las claves `ALPACA_*` se introducen en el panel (`sync: false`); `NVIDIA_MODEL` va en el blueprint y `AI_PROVIDER` sigue en `mock`. Para explicar con NVIDIA basta con poner `AI_PROVIDER=nvidia` y la clave en el panel, como en el servicio desplegado. Si la llamada falla, el informe sigue disponible y `/api/v1/analyze` responde, desde `v0.9.0-rc2`, 504 (timeout), 502 (respuesta no válida) o 503 (resto); con `e433fae`, cualquier fallo es `503 ai_unavailable`. Para recrearlo: *New → Blueprint* con este repositorio, o *New → Web Service* con Language `Docker` y Dockerfile Path `./proyectos/proyecto_iii/Dockerfile`. Para forzar datos nuevos: *Manual Deploy → Restart service*. Con el secret file (en la raíz; `alpaca.env` está en `.gitignore` y `.dockerignore`, así que no se versiona ni entra en la imagen): `docker build --secret id=alpaca_env,src=alpaca.env -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .`
- `>` **Procfile.** [`Procfile`](../../Procfile) arranca sin contenedor en un runner con `proyectos/proyecto_ii/requirements.txt` instalado: genera la demo si falta y lanza Uvicorn en `$PORT` con `--no-access-log`, como `serve.py`. [`.python-version`](../../.python-version) fija Python 3.12. En Heroku el buildpack de Python instalaría el `requirements.txt` raíz (solo el I), así que allí se usa el contenedor.

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

`>>` Las pruebas cubren el resumen de entrada del snapshot y su compatibilidad (`test_snapshot.py`), la IA del lote y `from-run` con sus fallos (`test_build.py`), la descarga simulada de Alpaca (`test_alpaca.py`), el refresco al arrancar en un proceso hijo con timeout (`test_serve.py`), la API (`test_api.py`, con `/health` en `degraded` y un `AI_PROVIDER` desconocido o un commit que no es un hash que no se publican; `test_analyze.py`, con los análisis simultáneos en total y por conexión, los modos de fallo del mock, el `500` tipado, el `request_id` en las líneas del II, también con la configuración de logging del CLI de Uvicorn, y un `Content-Length` que no es un entero ASCII; `test_pipeline.py`, con `limit=²` o `limit=٣`), el límite de uso de `analyze` con la IP del proxy (también con `X-Forwarded-For` en varias líneas o sin proxy), el cupo por conexión, el tope del histograma de saltos e IPv6 por `/64` (`test_ratelimit.py`), los timeouts y reintentos de `smoke_test.sh` con un `curl` falso (`test_smoke_script.py`), el middleware, con el nivel del log por código (una sola línea ERROR por cada 5xx, también sin snapshot o con el journal ilegible) y el `ContextVar` comprobado en la misma tarea (`test_observability.py`), el arranque sin access log y un hijo que publica el informe pero termina con código 2, que no se da por bueno (`test_serve.py`), una clave pegada en una variable numérica que no llega al log (`test_ratelimit.py`, `test_serve.py`), el dashboard servido y el journal del lote (`test_web.py`), la evidencia agregada (`test_evidence.py`) y la imagen y el empaquetado: el `Procfile` sin access log, toda receta `docker run -p` con `DSIA_TRUSTED_PROXY_HOPS=0` y `alpaca.env` fuera de Git y de la imagen (`test_packaging.py`). No usan red ni claves.

`>>` [Workflow](../../.github/workflows/ci.yml) en `push` a `main`, `pull_request` y manual. El job `proyectos-ii-y-iii` ejecuta el pytest del III con umbral del 90 %, el lote demo, el smoke HTTP y Playwright, publica el artefacto y, desde los commits de la RC2, falla si algún `.md` conserva un marcador de commit sin sustituir; `proyecto-iii-docker` construye la imagen, la arranca sin proxy delante (`-e DSIA_TRUSTED_PROXY_HOPS=0`), espera al `HEALTHCHECK`, pasa el smoke contra el contenedor y, desde los commits de la RC2, comprueba que seis análisis con un `X-Forwarded-For` distinto cada vez terminan en 429.

`=>` Verificado en local el 24/11/2026 con `.venv-ii` y `v0.9.0-rc2`, tras la tercera ronda de verificación: **298 tests y 98,25 % de cobertura** de `dsia_web` (`ai.py`, `ratelimit.py` y `observability.py` al 100 %, `app.py` y `serve.py` al 99 %), lote demo, smoke y Playwright correctos contra Uvicorn, y contenedor `healthy` en 6 s con el smoke correcto, sin líneas de access log y con las líneas `INFO:     IA provider=mock … request_id=…` del cliente del II; con `AI_PROVIDER=nvidia` y `NVIDIA_MAX_TOKENS=99999`, el contenedor sigue `healthy` y `/health` responde 200 `degraded` con `ai_config: invalid` (el smoke falla en el análisis con 503, como debe). CI: [historial de `main`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions?query=branch%3Amain); último run comprobado: [45306204500](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45306204500) (`e433fae`, 24/11/2026), con los tres jobs en verde.

## Operación

`>>` Comportamiento de `v0.9.0-rc2`. Con `e433fae`, el despliegue del 24/11/2026, `/health` no tiene `version`, `commit` ni los campos de IA, el panel pide 12 eventos y `POST /api/v1/analyze` no tiene límite de uso y responde 503 a cualquier fallo del proveedor.

- `>` `/health` confirma que el proceso tiene en memoria un snapshot válido y devuelve `checks` (`data_kind`, `as_of`, antigüedad en días, disponibilidad del journal, `ai_provider`, que vale `invalid` si el proveedor no es `mock`, `hf` ni `nvidia`, `ai_config` y `ai_last_call`), `version` y `commit` desplegado. Responde 200 `ready`, 200 `degraded` si la IA está mal configurada o su última llamada falló (el informe sigue servido y la siguiente llamada correcta lo devuelve a `ready`), y 503 `unavailable` sin snapshot. La tarjeta «Estado» muestra «Operativo (200)», «Degradado (200)» o «Sin informe válido», con el proveedor, su configuración y la última llamada.
- `>` `as_of` es la fecha del último dato y el timestamp del journal, la hora a la que corrió el lote: responden a preguntas distintas durante la demo.
- `>` Cada petición deja una línea `request` con `request_id` y `latency_ms`, en INFO, en WARNING si es un 4xx (tema 4, A1: lo arregla el cliente) o en ERROR si es un 5xx sin línea ERROR propia (los 503 sin snapshot, de `journal_unavailable` y de `analyze_busy`), de modo que cada 5xx alerta exactamente una vez; un arranque sin snapshot válido deja además la línea ERROR `snapshot_unavailable`. Responde con `X-Request-ID`, CSP `default-src 'self'`, `nosniff` y `no-referrer`, también un error no controlado: el handler central del middleware lo convierte en `500 internal_error` con la forma común y deja la traza en una línea ERROR `unhandled_error request_id=…`.
- `>` `GET /api/v1/pipeline` solo expone campos agregados del journal (etapa, estado, duración, `run_id`, filas, símbolos y hash), nunca rutas. El panel pide los 20 últimos: caben los 14 eventos del lote con Alpaca, de `download_bars` a `publish_snapshot`.

### Grafo del lote

`->` Encima de la tabla de eventos, el panel Operación dibuja el lote como una secuencia fija de 8 nodos: Datos (`generate_bars` o `download_bars`), Validar entrada, Preparar, Entrenar, Holdout, Inferir, Publicar snapshot y Servir API. Los siete primeros toman su estado del último evento de su etapa en `/api/v1/pipeline` o, si no tienen eventos, de su posición en el lote (omitida, reutilizada, pendiente, no alcanzada o fuera de la ventana); el octavo compara el `run_id` de `/health` con el del último `publish_snapshot` en `succeeded`. No hay endpoint nuevo: reutiliza `/health`, `/api/v1/pipeline` y el snapshot cargado.

- `>` **Estados.** Completada, fallida, iniciada sin cierre, pendiente, omitida en este lote (la demo no registra `validate_input`), reutilizada (refresco `from-run` con un modelo ya entrenado), no alcanzada (tras un fallo), fuera de la ventana (journal truncado) y sin eventos; en Servir API, sirve el lote publicado, sirve el lote con la IA degradada, sirve otro `run_id`, `run_id` sin verificar o sin informe válido. Los avisos explican el caso: journal no configurado (404), ilegible (503), líneas descartadas, lote truncado, eventos de un lote anterior en la ventana, etapas desconocidas, refresco y `run_id` discrepante. Así, un rollback que cambie solo `DSIA_SNAPSHOT` deja de pasar inadvertido.
- `>` **Teclado y móvil.** Es una lista ordenada (`role="list"`, porque Safari retira la semántica de lista con `list-style: none`) de botones con una sola parada de tabulación: las flechas, Inicio y Fin mueven el foco, e Intro o Espacio abren el detalle con los eventos observados de la etapa. El nodo elegido lleva `aria-current`, y los avisos y el detalle solo se anuncian cuando cambian. A 900 px se reparte en 4 columnas y a 390 px pasa a una sola, sin scroll horizontal.
- `~>` **Por qué no React Flow.** Se evaluó `@xyflow/react` 13.0.3 con su documentación oficial (accesibilidad con `nodesFocusable` y `ariaLabelConfig`, CSS obligatorio y contenedor con tamaño). Aporta arrastre, zoom y edición de grafos grandes, pero aquí el grafo es una secuencia fija de 8 nodos cuyo uso real es ver estados y abrir detalles. React Flow añadiría React, un bundler, `package.json` con lockfile, una etapa de Node en el Dockerfile y una versión mayor recién publicada (13.0.0 el 16/11/2026 y 13.0.3 el 23/11/2026, según el registro de npm). SVG y HTML nativos dan la navegación por teclado de una lista ordenada, cumplen la CSP `default-src 'self'` y no cambian el Dockerfile, que ya copia `dsia_web/static/`.

- `>` **Robustez de `/api/v1/analyze`.** Cada fallo del proveedor llega como `AIClientError` con `kind` y se traduce sin leer el mensaje: `timeout` (timeout del cliente, o 408/504 del proveedor) → `504 ai_timeout`, `invalid_response` → `502 ai_bad_response` y el resto, incluida una conexión rechazada → `503 ai_unavailable`. Deja una línea ERROR `analyze_failed` con `request_id`, `provider`, `kind` y `latency_ms`, sin el mensaje del proveedor ni claves, y las líneas de cada intento y reintento del cliente del II llevan el mismo `request_id`. El CLI de Uvicorn deja el root sin handlers, así que la app reenvía esas líneas al handler de Uvicorn y salen con su nivel (`INFO:`, `WARNING:`) también en Render. El límite de uso responde `429 rate_limited` con `Retry-After` y una línea WARNING `analyze_rate_limited` sin la IP; con 2 análisis de la misma conexión en curso, `429 analyze_busy_client`, y con el cupo total lleno, `503 analyze_busy`, ambos al momento. Con `AI_PROVIDER=mock`, `AI_MOCK_MODE` provoca cada fallo sin red ([fallo controlado](#fallo-controlado)). `/api/v1/metrics` expone `rate_limit` con los límites, el uso, los análisis en curso, los rechazos y de dónde salió la IP de cliente.
- `>` **Arranque acotado.** El refresco con Alpaca corre en un proceso hijo: si supera `DSIA_REFRESH_TIMEOUT`, se mata, se registra «Refresco con Alpaca cancelado» y se sirve el informe de la imagen. Un límite de uso mal configurado detiene el arranque con `config_invalid` en el log, que da la longitud del valor recibido pero nunca el valor (por si es una clave pegada en el campo equivocado); una configuración de IA no válida no lo detiene, pero queda en el log y en `/health`. Es una desviación consciente de la regla de configuración del tema de despliegue (A2: «falla al arrancar si falta un secreto obligatorio»): `NVIDIA_API_KEY` no es obligatoria para el núcleo del servicio, porque el informe no depende de la IA, y el health check sigue la opción A del tema de robustez (`degraded` con 200). El precio es que un deploy con la clave mal puesta entra en tráfico en lugar de fallar y conservar el anterior; por eso, tras cambiar la IA en el panel, se mira `ai_config` en `/health` y la línea `config_invalid` del log.
- `>` **Access log.** `serve.py` y el `Procfile` arrancan Uvicorn con `--no-access-log`: su access log escribe la IP del par TCP en cada petición, y la línea `request` del middleware ya registra método, ruta, estado, latencia y `request_id`.

## Guion de la exposición

`->` Exposición de 5–7 minutos con la demo sobre **[https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com)**. Abrir la URL unos minutos antes para que el plan gratuito despierte la instancia (unos 50 s más el refresco de Alpaca).

| Tiempo | Qué mostrar |
| --- | --- |
| 0:00–1:00 | Problema y usuario: ranking de retorno a 21 sesiones de diez acciones. Fuente Alpaca, etiqueta «Datos reales · Alpaca» y por qué solo se publican predicciones (licencia) |
| 1:00–2:00 | [Diagrama](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http): Ingesta → Procesamiento → Modelo / IA → API → Dashboard → Despliegue, y por qué por lotes |
| 2:00–3:00 | Panel **Operación** en Render con `v0.9.0-rc2`: estado 200 (`ready`, o `degraded` si falló la última llamada a NVIDIA) con proveedor de IA, versión y commit, `run_id`, último dato del día (el 24/11/2026, 2026-11-23), contadores y los 14 eventos del lote, empezando por `download_bars` (el panel pide 20). Abrir [`/health`](https://dsia-swarmtrader.onrender.com/health) en otra pestaña y comparar el `run_id` y el `commit`. Si Render sirve todavía `e433fae`, el panel no muestra versión, commit ni proveedor y pide 12 eventos, así que `download_bars` se enseña en [`/api/v1/pipeline`](https://dsia-swarmtrader.onrender.com/api/v1/pipeline), que devuelve 20 por defecto |
| 3:00–4:30 | Ranking y filtro; en la pestaña Red del navegador, la respuesta de `/api/v1/snapshot`. **Explicar símbolo**: `POST /api/v1/analyze` con Nemotron (10–25 s), `request_id` y latencia. Los errores tipados, si `/health` trae `version` (desde `v0.9.0-rc2`): 429 por el límite de uso o por tener ya 2 análisis en curso, 503 `analyze_busy` con el cupo total lleno, 504 si NVIDIA no responde a tiempo y 503 si no está disponible; con `e433fae`, cualquier fallo es `503 ai_unavailable` y no hay 429. Si hay tiempo, uno provocado con la receta de [fallo controlado](#fallo-controlado) |
| 4:30–5:30 | Evidencia del modelo: Dummy frente a Ridge y Swarm en validation, holdout de un toque y R² casi nulo, explicado como límite del resultado |
| 5:30–6:30 | CI de `main` (último run comprobado 45306204500; 298 tests del III en local el 24/11), `Dockerfile` con `HEALTHCHECK`, rollback, [issues conocidos](RELEASE.md#issues-conocidos) y [registro de IA](AI_USAGE.md) para las preguntas |

`~>` **Contingencia.** Si Render no responde, arrancar la demo local de [Arranque local de API y dashboard](#arranque-local-de-api-y-dashboard), pasar `smoke_test.sh` y enseñar la [captura del despliegue](evidencia/dashboard_render.png) y el artefacto del CI como referencia visual.

`~>` **IP compartida.** Desde `v0.9.0-rc2`, si el público abre la URL desde la red del campus, comparte con el presentador los 5 análisis por minuto, los 30 diarios y los 2 simultáneos: antes de la exposición, subir `DSIA_ANALYZE_PER_MINUTE` (y, si se quiere, `DSIA_ANALYZE_CONCURRENCY_PER_IP` hasta 4) en el panel de Render manteniendo los topes diarios, o pedir a la sala que no pulse durante la demo ([issues conocidos](RELEASE.md#issues-conocidos)).

### Fallo controlado

`->` El tema de robustez pide poder demostrar un fallo controlado: un error limpio para el usuario y una línea en el log con su `request_id`.

`>` **En local** (válido con `v0.9.0-rc2`), con el entorno de [Instalación](#instalación), el snapshot de la demo y `AI_PROVIDER=nvidia` sin clave:

```bash
export DSIA_SNAPSHOT="$PWD/runs/demo/snapshot.json" DSIA_JOURNAL="$PWD/runs/demo/pipeline.jsonl"
AI_PROVIDER=nvidia NVIDIA_API_KEY= .venv-ii/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765
# En otra terminal:
curl -s http://127.0.0.1:8765/health
curl -s -X POST -H 'Content-Type: application/json' -H 'X-Request-ID: fallo-controlado' \
  -d '{"symbol": "DEMO01"}' http://127.0.0.1:8765/api/v1/analyze
```

`>>` Comprobado en local el 24/11/2026: al arrancar, la línea ERROR `config_invalid ai_provider=nvidia Falta NVIDIA_API_KEY en el entorno`; `/health` responde 200 con `"status": "degraded"` y `"ai_config": "invalid"`; el análisis responde `503 ai_unavailable` («El proveedor de IA no está disponible. Inténtalo más tarde.») con `request_id` y `X-Request-ID` `fallo-controlado`, y el log deja `analyze_failed request_id=fallo-controlado provider=nvidia kind=config status=503 code=ai_unavailable latency_ms=…`. Ni la respuesta ni el log nombran el valor de ninguna clave.

`>` **Cada rama, sin red ni clave** (desde `v0.9.0-rc2`, tema de robustez B2 y B9): con `AI_PROVIDER=mock`, la variable `AI_MOCK_MODE` hace que el mock falle siempre del modo pedido. Con un proveedor real se ignora, así que en Render no cambia nada; un valor desconocido deja `ai_config: invalid`.

```bash
AI_PROVIDER=mock AI_MOCK_MODE=timeout .venv-ii/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765
# down → 503 ai_unavailable · timeout → 504 ai_timeout · invalid → 502 ai_bad_response · bug → 500 internal_error
curl -s -i -X POST -H 'Content-Type: application/json' -H 'X-Request-ID: modo-timeout-0001' \
  -d '{"symbol": "DEMO01"}' http://127.0.0.1:8765/api/v1/analyze
```

`>>` Comprobado en local el 24/11/2026, un arranque por modo: `down` → `503 ai_unavailable`, `timeout` → `504 ai_timeout`, `invalid` → `502 ai_bad_response`, los tres con `/health` en `degraded` y `ai_last_call` `failing:unavailable`, `failing:timeout` y `failing:invalid_response`, y la línea ERROR `analyze_failed request_id=modo-…-0001 provider=mock kind=… status=… code=…`; `bug` → `500 internal_error` («Error interno.», sin traza en el cuerpo) con la línea ERROR `unhandled_error request_id=modo-bug-0001 route=/api/v1/analyze` y la traza en el log, y `/health` sigue en `ready`, porque un fallo propio no es un fallo del proveedor.

`>` **En Render** (desde `v0.9.0-rc2`): seis análisis en menos de un minuto desde la misma conexión. Como el botón espera cada respuesta (13–22 s con Nemotron), lo práctico es `curl`, de 2 en 2 para no recibir `429 analyze_busy_client` (máximo 2 a la vez por conexión). Vale en bash y en zsh:

```bash
url=https://dsia-swarmtrader.onrender.com/api/v1/analyze
analyze() { curl -s -o /dev/null -w "$1 %{http_code} retry-after=%header{retry-after}\n" -X POST \
  -H 'Content-Type: application/json' -d "{\"symbol\": \"$1\"}" "$url"; }
analyze NVDA & analyze AAPL & wait
analyze XOM & analyze MSFT & wait
analyze JPM & analyze TSLA & wait
```

`>>` El sexto en llegar (uno de los dos de la tercera tanda) responde `429 rate_limited` con `Retry-After` y el log de Render muestra la línea WARNING `analyze_rate_limited request_id=… scope=per_minute retry_after_s=…`, sin la IP. Gasta 5 llamadas reales a NVIDIA y 5 análisis del cupo diario de la conexión (30). Si las dos primeras tandas tardan más de un minuto, la ventana se desliza y no salta el 429: basta repetir. La misma secuencia contra la demo local con `mock` (`url=http://127.0.0.1:8765/api/v1/analyze` y símbolos `DEMO01`…`DEMO06`) dio el 24/11/2026 cinco 200 y un 429 con `Retry-After: 60`, y las líneas WARNING `analyze_rate_limited … scope=per_minute retry_after_s=60` y `request … status=429`.

## Uso de IA

`>>` [AI_USAGE.md](AI_USAGE.md): OpenAI Codex (modelo gpt-6.2-sol) en la integración del 23/11/2026 y Claude Code (modelo Claude Opus 5.5) en la auditoría de cumplimiento, el despliegue y los datos reales, con lo aceptado, lo rechazado, la verificación y los commits. En la demo local, en el CI y en la explicación del lote, el proveedor `mock` escribe el texto sin llamar a un modelo externo; en Render, «Explicar símbolo» llama a NVIDIA. Al proveedor solo viajan agregados del informe y, desde `v0.9.0-rc2`, el puesto del símbolo pedido; nunca precios ni claves.

## Desarrollo por fechas

- `->` **11 noviembre:** se crea el repositorio de investigación [`dalonsogomez-ai/swarmtrader`](https://github.com/dalonsogomez-ai/swarmtrader); el código que reutiliza el II es su v1.4.0 (commit `5642dda`, ver [UPSTREAM.json](../proyecto_ii/UPSTREAM.json)).
- `~>` **12 noviembre:** el Proyecto II se escribe con OpenAI Codex (gpt-6.1-sol): contrato temporal, gates y adaptación del código. Es el núcleo que amplía el III.
- `>>` **19 noviembre:** auditoría de la extracción de Alpaca con Codex (gpt-6.1-sol).
- `~>` **23 noviembre:** integración del II y del III en el repositorio de entrega (`e524ec0` y `3d991d2`) con Codex (gpt-6.2-sol): lote, snapshot, API, dashboard y CI.
- `>` **23 noviembre:** auditoría de cumplimiento con Claude Code (Claude Opus 5.5) y mejoras en commits atómicos: endpoints de predicción, análisis, pipeline y métricas, panel Operación, cabeceras de seguridad, Dockerfile y blueprint de Render.
- `=>` **23 noviembre:** [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) fusionado en `main` (`a5a5b9b`), tag [`v0.9.0-rc1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1) y despliegue en Render.
- `~>` **23-24 noviembre:** datos reales de Alpaca en Render: descarga en el build ([PR #2](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/2), `bed8312`) y refresco al arrancar ([PR #3](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/3), `033d134`).
- `=>` **24 noviembre:** `main` en `bd3b0fa` con el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) en verde y el despliegue sirviendo datos hasta el 2026-11-20.
- `~>` **24 noviembre:** proveedor alternativo NVIDIA (`a86b9de`), porque la cuenta de Hugging Face no tiene saldo y las llamadas autenticadas desde Render fallaban, y elección de Nemotron 3.5 Super tras medir cinco modelos en Render (`edb049c`). En el panel de Render se activa `AI_PROVIDER=nvidia`.
- `>>` **24 noviembre:** smoke y Playwright adaptados a un LLM real y captura con el análisis de Nemotron (`e433fae`), con el run [45306204500](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45306204500) en verde y el despliegue sirviendo `as_of` 2026-11-23.
- `~>` **24 noviembre:** arreglos de la auditoría con Claude Code (Claude Opus 5.5): límite de uso de `/analyze`, errores 502 y 504 por `kind`, refresco con timeout, contexto del símbolo para la IA, versión y commit en `/health`, timeouts del smoke y `AGENTS.md`; y, tras una revisión adversarial, IP de cliente desde el proxy (`CF-Connecting-IP` o el último salto de `X-Forwarded-For`), cupo diario por conexión, IPv6 por `/64`, análisis simultáneos acotados (`503 analyze_busy`), 408/504 como timeout y la conexión caída como 503, `500` tipado, `/health` en `degraded`, `request_id` en las líneas del II, smoke con reintentos, panel con los 20 últimos eventos y versión `0.9.0-rc2`; en la documentación, receta de fallo controlado, IP compartida de la sala, sección [RC2](RELEASE.md#v090-rc2) y Parte 0 de E6 declarada como no ejecutada; y, en la ronda de verificación, `X-Forwarded-For` leído en todas sus líneas, `DSIA_TRUSTED_PROXY_HOPS=0` sin proxy, 2 análisis a la vez por conexión (`429 analyze_busy_client`), `AI_PROVIDER` desconocido sin publicar, 4xx en WARNING, Uvicorn sin access log, `AI_MOCK_MODE`, claves falsas de los tests sin forma de clave real e `inspect` en el CI del II; y, en una segunda ronda de verificación, una línea ERROR por cada 5xx, valores no válidos de las variables sin repetir en el log, `AI_PROVIDER` en blanco tratado como `mock`, recetas `docker run` con `DSIA_TRUSTED_PROXY_HOPS=0`, `alpaca.env` en `.gitignore` y `.dockerignore`, el `.env` local con `uvicorn --env-file` y, en el CI, las 15 métricas de referencia y la inferencia del II, el límite con `X-Forwarded-For` rotado contra el contenedor y la comprobación de marcadores de commit; y, en una tercera ronda, las líneas del cliente del II también con el logging del CLI de Uvicorn, `limit` y `Content-Length` solo con cifras ASCII y `commit` publicado solo si es un hash ([441b51a](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/441b51a), [b7c6a39](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/b7c6a39), [be8c8e5](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/be8c8e5), [54a184d](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/54a184d), [6356bee](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/6356bee), [aba475c](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/aba475c), [382a6f5](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/382a6f5), [ddda032](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/ddda032), [17fbedd](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/17fbedd), [81838fc](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/81838fc), [08979c1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/08979c1), [b66a15b](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/b66a15b), [1bdba5f](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/1bdba5f), [f97b552](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/f97b552), [f38b879](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/f38b879), [c471d6a](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/c471d6a), [3e6beb5](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3e6beb5), [bf545c6](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/bf545c6)). Ese día la RC2 quedó verificada en local, con el despliegue y el tag a la espera de la aprobación del autor.
- `>>` **Octubre:** no hay commits del II ni del III en octubre. El trabajo entró en Git a partir del 23/11/2026 y no se fabrican fechas ni se reescribe el historial.

`>>` [Release Candidate](RELEASE.md) · [Contrato HTTP](API.md) · [Citación de IA](AI_USAGE.md) · [Rúbricas y trazabilidad](../../docs/TRAZABILIDAD_DSIA.md) · [Enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md)
