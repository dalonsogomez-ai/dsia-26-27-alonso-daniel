# Desarrollo de Soluciones de IA — Proyecto II

**Daniel Alonso Gómez · Curso 2026–2027**

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

`->` Automatizar un proceso de datos con las **dos piezas** que pide el [enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_ii/README.md) (cotejado el 23/11/2026): un modelo de **scikit-learn** entrenado sobre datos propios e integrado en el pipeline, y un modelo del **Hub de Hugging Face** vía Inference API con modo `mock`. El dominio es el del Proyecto III: elegir acciones para mantener **21 sesiones** a partir de barras diarias. El núcleo adapta factores y el optimizador de **SwarmTrader v1.4.0**, un repositorio de investigación propio.

`=>` Estado: pipeline reproducible sin claves, modelo sklearn persistido con inferencia desde el artefacto, borde HF tipado con `mock` en tests y CI, y el mismo núcleo reutilizado por la API, el dashboard y el despliegue del [Proyecto III](../proyecto_iii/README.md). Es un ejercicio académico: ninguna salida es una recomendación de inversión ni envía órdenes.

## Recorrido de la entrega

`>` El enunciado pide que el README deje claro este recorrido. Cada paso enlaza con su sección:

| Paso | Qué se hace | Sección |
| --- | --- | --- |
| 1. Datos | Barras diarias: demo sintética generada por el proyecto o histórico de Alpaca que no se redistribuye | [Datos: origen, licencia y contrato](#datos-origen-licencia-y-contrato) |
| 2. Entrenamiento sklearn | `train` compara Dummy, Ridge y cinco Ridge especialistas en validation y persiste el ganador con `joblib`; `evaluate` toca el holdout una vez | [Entrenamiento sklearn](#entrenamiento-sklearn) |
| 3. Pipeline con inferencia | `run` recarga el artefacto, predice el retorno a 21 sesiones por símbolo, asigna capital y escribe el informe | [Pipeline con inferencia](#pipeline-con-inferencia) |
| 4. Borde HF/API | `chat_completion` con `Qwen/Qwen2.5-7B-Instruct` explica el resumen agregado; en CI corre `mock` | [Borde Hugging Face](#borde-hugging-face) |
| 5. Ampliación en el III | API, dashboard, ingesta de Alpaca, despliegue en Render y monitorización | [Del Proyecto II al Proyecto III](#del-proyecto-ii-al-proyecto-iii) |

## Motivación

`->` El problema es elegir hoy, con la información cerrada de la última sesión, una acción o combinación de acciones para mantener 21 sesiones, sabiendo que el retorno futuro es incierto y que la mayoría de las señales de precio y volumen son débiles. Es una decisión repetida, con datos públicos diarios, que permite separar con rigor lo que se sabía al decidir de lo que se observa después.

`~>` sklearn resuelve la parte medible: una **regresión** del retorno a 21 sesiones con factores causales, split temporal purgado y comparación contra un `DummyRegressor`. Hugging Face resuelve otra pieza distinta: convertir un resumen agregado del experimento en una **explicación en lenguaje natural** para quien lee el informe, sin decidir pesos ni ver datos crudos.

`~>` Hay continuidad con el Proyecto I: el contrato de barras diarias (`date`/`timestamp`, `symbol`, `close`, `volume`) es el que produce su extracción de Alpaca, así que el histórico entra sin transformaciones nuevas. En el Proyecto III, este núcleo (datos → modelo persistido → inferencia → explicación) es el que ejecuta el lote y el que publican la API y el dashboard; por eso vive en módulos importables y no dentro de la CLI.

## Datos: origen, licencia y contrato

| Fuente | Origen | Licencia y uso | Para qué |
| --- | --- | --- | --- |
| Demo sintética `data/demo.csv` | La genera el proyecto con `demo-data` (caminatas lognormales correlacionadas con NumPy, semilla 42) | Datos propios del proyecto, sin derechos de terceros; se regeneran con un comando y no se versionan | Receta reproducible, tests y CI |
| Histórico de Alpaca | Barras diarias de 10 símbolos (2018-01-02 a 2026-09-28) descargadas en el [Proyecto I](../proyecto_i/ALPACA.md) desde la [Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api) | Alpaca [no permite redistribuir sus datos](https://alpaca.markets/support/redistribute-alpaca-api): el CSV no se versiona y solo se publican agregados | Entrenamiento real y [evidencia agregada](#métricas-del-histórico-real-sin-publicar-datos) |

`>` Esquema de entrada y reglas de validación ([`data.py`](swarmtrade_app/data.py)); el detalle, en [data/README.md](data/README.md):

| Columnas | Regla |
| --- | --- |
| `date` o `timestamp` | Fecha ISO 8601 válida; panel de fechas comunes sin huecos |
| `symbol` | Al menos cinco símbolos; el universo de inferencia debe coincidir con el de entrenamiento |
| `close` | Número finito y positivo |
| `volume` | Número finito y no negativo |
| `open`, `high`, `low` (opcionales) | Positivos y coherentes con `close` |
| `(symbol, date)` | Clave única; no se rellenan precios ausentes |

`~>` El [contrato predictivo](PROBLEMA.md), aprobado el 12/11/2026, define `target = close[t+21] / close[t] − 1`. Los 14 factores de precio y volumen proceden de la versión fijada en [UPSTREAM.json](UPSTREAM.json), con licencia y adaptación en [THIRD_PARTY.md](THIRD_PARTY.md). Se necesitan 252 sesiones de warmup. No se usan como features el target, el símbolo, fechas futuras ni la respuesta de HF.

## Reproducir sin claves ni datos de terceros

`>` Desde esta carpeta, con **Python 3.12**. El entorno `.venv-ii` vive en la raíz del repositorio y lo **comparten el II y el III**; el Proyecto I usa otro (`.venv-i`) porque fija pandas 3 y este requiere `pandas<3`. No instales ambos `requirements.txt` en el mismo entorno.

```bash
python3.12 -m venv ../../.venv-ii
source ../../.venv-ii/bin/activate
python -m pip install -r requirements.txt
python -m swarmtrade_app demo-data --output data/demo.csv --sessions 680 --symbols 8 --seed 42
python -m swarmtrade_app inspect --data data/demo.csv --output runs/demo-inspection
python -m swarmtrade_app train --data data/demo.csv --run runs/demo --data-kind synthetic
python -m swarmtrade_app evaluate --run runs/demo
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/report.json --provider mock
python -m pytest -q --cov=swarmtrade_app --cov-report=term-missing
```

`>>` `data/demo.csv` debe tener sha256 `c0574a8505d4329a8db523513d2f9f7bdbbb1599dd7568e4866d3b5ae1abf4c2`: los precios se redondean a 6 decimales para que el CSV sea idéntico en macOS arm64 y Linux x86_64. La demo no requiere Internet tras instalar dependencias y no lleva una señal artificial diseñada para que el modelo acierte. Un resultado de la demo no demuestra desempeño financiero.

`~>` Nada se sobrescribe: datos, runs, modelos e informes van a destinos nuevos. `evaluate` rechaza una segunda evaluación del mismo holdout, e `inspect` rechaza un `--output` que ya existe y no está vacío (`La salida de inspect ya existe; usa un directorio nuevo`). `inspect` registra a INFO un perfil con filas, símbolos, rango de fechas y sospechas de leakage. `--prepared` continúa una preparación existente sin volver a dividir los datos.

`~>` Los logs van a stderr; el resultado JSON, a stdout, y los informes, al destino indicado. Cada etapa registra a INFO con su logger de módulo: carga (filas, símbolos, fechas), preparación (tamaños del split y filas purgadas), inferencia (`as_of`, prefijo del sha256 del artefacto, media predicha), asignación (pesos, convergencia y brecha) e IA (proveedor, modelo, latencia y `ai_status`, nunca el token). `--log-level` va antes del subcomando: `python -m swarmtrade_app --log-level WARNING run ...`. La CLI, que se presenta como `python -m swarmtrade_app` en `--help`, devuelve 0 si la ejecución técnica es correcta y 2 ante errores controlados.

`>>` Los notebooks marimo de [`ml_pipeline/`](ml_pipeline/) muestran las figuras de cada fase a partir de lo que genera la receta: `python -m marimo edit ml_pipeline/01_eda.py` (también `02_prep`, `03_model` y `04_eval`). `DSIA_DATA_PATH`, `DSIA_EDA_DIR` y `DSIA_RUN_DIR` apuntan a otro CSV, otra inspección u otro run. Ninguno vuelve a tocar el test al abrirse. El registro del 12/11 está en [ml_pipeline/PIPELINE.md](ml_pipeline/PIPELINE.md).

## Entrenamiento sklearn

`>` `train` reserva el 60/20/20 de **fechas completas** para train, validation y test, y purga las etiquetas cuyo horizonte cruza una frontera. `StandardScaler` se ajusta solo con train dentro de un `Pipeline` de sklearn. Candidatos prefijados, con `alpha=10` y sin búsqueda de hiperparámetros:

| Candidato | Definición |
| --- | --- |
| `dummy` | `DummyRegressor(strategy="mean")`: predice siempre la media del target en train |
| `ridge` | `StandardScaler` + `Ridge(alpha=10)` con los 14 factores |
| `swarm` | Media equiponderada de cinco Ridge especialistas de SwarmTrader (momentum, reversal, lowrisk, liquidity, seasonal) |

`~>` Gana el menor **RMSE de validation**, con desempate a favor del modelo sencillo. El ganador y su preprocesamiento se guardan en `model.joblib` con las features, el universo, el horizonte y `validation.json`. `evaluate` puntúa el holdout congelado **una sola vez** (`test_metrics.json`) y guarda en el mismo toque el baseline Dummy; nada se reentrena ni se reselecciona con ese resultado.

`>>` Qué se reproduce y qué no: los datos, el split, las métricas y las predicciones se reproducen exactamente con la receta; el **sha256 de `model.joblib` no**, porque el artefacto incluye `created_utc`, la hora del entrenamiento. Para comparar dos ejecuciones se usan `input_sha256`, `validation.json` y `test_metrics.json`; `artifact_sha256` identifica un fichero concreto y solo coincide si se reutiliza el mismo artefacto.

### Métricas de la demo

| Métrica | Cálculo | Interpretación |
| --- | --- | --- |
| RMSE | `sqrt(media((ŷ − y)²))`, en retorno decimal a 21 sesiones | Error típico de la predicción; penaliza más los errores grandes. Es el criterio de selección. 0,064 ≈ 6,4 puntos porcentuales |
| MAE | `media(abs(ŷ − y))` | Error absoluto medio; menos sensible a colas |
| R² | `1 − SS_res / SS_tot`, con `SS_tot` respecto a la media del bloque evaluado | Negativo significa peor que predecir la media del propio bloque, que no se conoce al decidir |
| Acierto de signo | Proporción de casos con `(y > 0) == (ŷ > 0)` | Descriptiva; las etiquetas a 21 sesiones se solapan y no son observaciones independientes |
| Baseline Dummy | Media del target en train (0,016455 en la demo) | La referencia que el modelo debe batir |

`=>` Ejecución de referencia (680 sesiones, 8 símbolos, semilla 42), reproducida el 24/11/2026 con la receta anterior y comprobada en el CI con tolerancia 1e-6:

| Bloque | Modelo | RMSE | MAE | R² |
| --- | --- | --- | --- | --- |
| Validation | Dummy | 0,065762 | 0,054687 | −0,438352 |
| Validation | **Ridge (seleccionado)** | **0,064383** | 0,053232 | −0,378661 |
| Validation | Swarm | 0,065318 | 0,054426 | −0,419027 |
| Holdout | Ridge | 0,070995 | 0,055318 | −0,254941 |
| Holdout | Baseline Dummy | 0,066148 | 0,052328 | −0,089425 |

`=>` Ridge gana en validation por poco, pero en el holdout queda **peor que el baseline**: el modelo no acredita capacidad predictiva sobre estos datos sintéticos. Es el resultado esperable en una caminata aleatoria sin señal añadida, y se publica tal cual: el baseline no interviene en la selección y no se reentrena nada por ello. El R² de validation es negativo incluso para Dummy porque la media de ese bloque difiere de la de train.

### Métricas del histórico real (sin publicar datos)

`>>` Resumen agregado en [`../proyecto_iii/evidencia/historico_alpaca.json`](../proyecto_iii/evidencia/historico_alpaca.json), generado el 23/11/2026 con el run del 12/11 sobre el CSV del Proyecto I (`input_sha256` `2ebbd7d7…ce4b`, 10 símbolos, 21.960 filas, `as_of` 2026-09-28, sklearn 1.9.1). No contiene precios ni predicciones por símbolo.

| Bloque | Periodo y filas | Modelo | RMSE | MAE | R² | Signo |
| --- | --- | --- | --- | --- | --- | --- |
| Validation | 2023-08-07 a 2025-01-15 · 3.630 | Dummy | 0,093728 | 0,065623 | −0,000330 | 0,616 |
| Validation | | Ridge | 0,095000 | 0,067246 | −0,027669 | 0,606 |
| Validation | | **Swarm (seleccionado)** | **0,092665** | 0,064934 | 0,022242 | 0,616 |
| Holdout | 2025-02-18 a 2026-08-27 · 3.840 | Swarm | 0,091922 | 0,070540 | −0,005947 | 0,589 |

`=>` Con datos reales, Swarm mejora a Dummy en validation un 1,1 % de RMSE y en el holdout su R² es prácticamente cero: el modelo apenas explica la variación del retorno a 21 sesiones. Train abarca de 2019-01-03 a 2023-07-06 (11.340 filas). El baseline del holdout no figura en esta evidencia porque el run es anterior a ese cambio, y no se vuelve a tocar el test para calcularlo.

### Reproducir el histórico autorizado

`>` Con el entorno del II, define `DSIA_BARS_CSV` con la ruta del CSV local descrito en [el contrato de datos](data/README.md) y usa un directorio nuevo para entrenar. Si ya tienes un run evaluado con ese CSV, reutiliza sus artefactos para inferir y para la [demo histórica del III](../proyecto_iii/README.md#informe-con-el-histórico-del-proyecto-ii).

```bash
python -m swarmtrade_app train --data "$DSIA_BARS_CSV" --run runs/historico --data-kind alpaca
python -m swarmtrade_app evaluate --run runs/historico
python -m swarmtrade_app run --data "$DSIA_BARS_CSV" --artifact runs/historico/model.joblib \
  --output runs/historico/report.json --provider mock
```

## Pipeline con inferencia

`>` `run` es el job completo de inferencia ([`pipeline.py`](swarmtrade_app/pipeline.py)): valida el CSV, recarga `model.joblib` (rechaza otra versión de sklearn, otro universo o una fecha anterior al entrenamiento), calcula los factores de la última sesión cerrada, predice el retorno a 21 sesiones por símbolo, asigna capital y escribe el informe JSON. Si la IA falla después de inferir, el informe se conserva con `ai_status=pending`.

`~>` **Qué aporta el modelo.** Los 14 factores son z-scores *cross-section*: se normalizan entre los símbolos de cada fecha. Por eso la media diaria de las predicciones (`mean_prediction`) es constante e igual a la media del target en train: en la demo, 0,016455 en cualquier fecha, el mismo valor que predice el baseline Dummy. El modelo no anticipa el nivel del mercado; aporta el **orden relativo** entre símbolos. Por eso el resumen que recibe la IA incluye también la dispersión (`prediction_std`), el spread (`prediction_spread`, máximo menos mínimo de los retornos predichos de la fecha) y la mejor señal (`top_symbol`). En la demo, DEMO06 encabeza el orden con 4,58 % y el spread es de 5,67 puntos.

`~>` **Asignación.** `run` usa por defecto `--decision conviction --mean-source model --risk-aversion 1`: el optimizador de SwarmTrader v1.4 maximiza el crecimiento logarítmico sobre escenarios cuya media es la predicción sklearn, sin tope por nombre ni mínimo de posiciones, así que puede asignar el 100 % a un único activo. Con `--mean-source model`, los pesos por debajo de `1e-4` (menos de 1 USD sobre un nocional de 10.000 USD) se anulan como residuo numérico y el resto se renormaliza. Fórmulas, fuentes y límites en [DECISION.md](DECISION.md).

```bash
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/all-in.json --risk-aversion 0 --provider mock
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/empirical.json --mean-source empirical --provider mock
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/research.json --decision research --provider mock
```

`>>` `--risk-aversion 0` elige el mayor retorno esperado y le asigna el 100 %, aunque todas las medias sean negativas. `--mean-source empirical` conserva el mapa de medias original de SwarmTrader, que queda plano con universos pequeños. `--decision research` informa sin asignar. La opción elegida queda registrada en el informe y no cambia según los resultados.

`>>` **Etiqueta «NO ACCIONABLE».** El informe incluye siempre `research_status: "NO ACCIONABLE / ventaja no demostrada"`. En SwarmTrader, los *gates* G0–G4 son filtros estadísticos que deciden si una señal merece operarse; G4 comprueba si los primeros valores del ranking superan al universo, y la auditoría publicada de v1.4 lo da por no superado. Esta entrega no recalcula esos filtros: copia la etiqueta para que nadie lea la asignación como una recomendación. Elegir bajo incertidumbre no acredita ventaja.

`>>` El adaptador opcional de Alpaca **paper** (`paper-plan` y `paper-execute`) traduce un informe a órdenes en una cuenta de prácticas. No forma parte del enunciado, no participa en tests con credenciales reales ni en el CI, y nunca se ejecuta desde `run`. Su diseño está en [DECISION.md](DECISION.md#órdenes-alpaca-paper-fuera-del-enunciado).

## Borde Hugging Face

`->` Pieza distinta de sklearn, con el mismo estilo que el ejemplo de clase `ai_api_client.py`: dataclasses de entrada y salida, `AIClientError` y proveedores `mock` y `hf` en [`ai_client.py`](swarmtrade_app/ai_client.py).

| Elemento | Valor |
| --- | --- |
| Tarea Inference | `chat_completion` |
| Modelo del Hub | [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) (`DEFAULT_HF_MODEL`), pesos con licencia Apache-2.0 según su ficha |
| Para qué | Explicar en español, después de inferir, el resumen agregado del experimento (fecha, modelo, horizonte, número de símbolos, media, dispersión, spread, mejor señal, RMSE de validation y tipo de datos). No recibe barras, cuentas ni claves, y no decide pesos ni órdenes |
| En tests y CI | Siempre `mock` (`mock-determinista-v1`), sin red ni token. Su texto incluye la dispersión y la mejor señal |
| SDK | `huggingface_hub.InferenceClient`, proveedor de inferencia `auto` configurable |

`>` **Configuración con `AIClient.from_env()`.** La CLI y el III ([`dsia_web/ai.py`](../proyecto_iii/dsia_web/ai.py), cuyo `client_from_env` es un envoltorio fino) crean el cliente con la misma fábrica, que valida el entorno con mensajes de dominio. `--provider` y `--model` de la CLI prevalecen sobre el entorno.

| Variable | Valor por defecto | Validación |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | `mock` o `hf`; `huggingface` es alias de `hf`, sin distinguir mayúsculas |
| `HF_TOKEN` | vacío | Obligatorio con `hf`; la CLI lo comprueba antes de cargar datos |
| `HF_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | Formato `owner/name` |
| `HF_TIMEOUT` | 30 | Número entre 1 y 120 (`HF_TIMEOUT debe ser un número entre 1 y 120`) |
| `HF_MAX_TOKENS` | 256 | Entero entre 1 y 512 |
| `HF_INFERENCE_PROVIDER` | `auto` | `auto` o un identificador en minúsculas con guiones |

`~>` **Validación del resumen.** `AnalysisRequest` comprueba tipos y rangos al construirse: `horizon` y `symbols` enteros positivos, medias y dispersiones finitas, `validation_rmse` finito y no negativo, `as_of` en formato ISO y `data_kind` en {`synthetic`, `alpaca`, `local`}. Un resumen inválido lanza `AIClientError("Resumen para la IA no válido: <motivo>")` antes de llamar a nadie. Los campos nuevos son opcionales, de modo que los informes anteriores siguen siendo legibles. `analyze-summary` traduce las claves sobrantes o ausentes del JSON a un error de dominio.

`~>` **Errores y reintentos.** Se sigue la tabla del tema de APIs: se reintenta lo transitorio y no la configuración.

| Situación | Respuesta del cliente | Reintento |
| --- | --- | --- |
| 401 / 403 | `Token de Hugging Face inválido o sin permisos` | No |
| 404 | `Modelo o proveedor de inferencia no disponible` | No |
| 429, 5xx, timeout o error de conexión | `AIClientError` genérico al agotar los intentos | Hasta 2 (`MAX_RETRIES`), con esperas de 0,5 s y 1 s más jitter |

`>>` El token nunca aparece en mensajes ni logs; la espera entre intentos es inyectable para que los tests no duerman. Si el servicio falla tras inferir, el informe conserva las predicciones con `ai_status=pending` y no se simula una respuesta real.

```bash
cp .env.example .env
# Completar HF_TOKEN localmente; no pegarlo en comandos ni versionarlo.
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/hf.json --provider hf
```

`=>` Según el Hub el 23/11/2026, `Qwen2.5-7B-Instruct` tenía un único Inference Provider activo, **featherless-ai**, que es el que resuelve `HF_INFERENCE_PROVIDER=auto`. Si deja de estar disponible, `HF_MODEL=Qwen/Qwen3-8B` ofrece la misma tarea, licencia Apache-2.0 y el mismo proveedor en esa fecha. **No se ha hecho ninguna llamada autenticada**: se cumple la alternativa del enunciado (`mock` + cliente tipado + `HF_TOKEN=` en [.env.example](.env.example)). Proveedor, costes y aportaciones de IA en [AI_USAGE.md](AI_USAGE.md).

## Del Proyecto II al Proyecto III

`->` El enunciado define el II como la base del III. Correspondencia con los módulos reales de [`proyectos/proyecto_iii/dsia_web`](../proyecto_iii/dsia_web):

| Proyecto II (base) | Proyecto III (ampliación) | Módulos del III |
| --- | --- | --- |
| Datos + pipeline + logs: [`data.py`](swarmtrade_app/data.py), [`preparation.py`](swarmtrade_app/preparation.py), [`cli.py`](swarmtrade_app/cli.py) | Ingesta de Alpaca y lote que congela un snapshot validado | [`alpaca_source.py`](../proyecto_iii/dsia_web/alpaca_source.py), [`build.py`](../proyecto_iii/dsia_web/build.py), [`serve.py`](../proyecto_iii/dsia_web/serve.py) |
| Modelo sklearn + inferencia: [`training.py`](swarmtrade_app/training.py), `pipeline.infer` | Endpoints de predicción sobre un contrato versionado | [`app.py`](../proyecto_iii/dsia_web/app.py) (`/api/v1/snapshot`, `/api/v1/predictions/{symbol}`), [`snapshot.py`](../proyecto_iii/dsia_web/snapshot.py) |
| Cliente HF mock + real: [`ai_client.py`](swarmtrade_app/ai_client.py), `AIClient.from_env` | Contrato `/analyze` | [`ai.py`](../proyecto_iii/dsia_web/ai.py), `POST /api/v1/analyze` en [`app.py`](../proyecto_iii/dsia_web/app.py) |
| pytest + [.env.example](.env.example) con `HF_TOKEN=` | CI y robustez del servicio | [`tests/`](../proyecto_iii/tests), [`observability.py`](../proyecto_iii/dsia_web/observability.py), jobs `proyectos-ii-y-iii` y `proyecto-iii-docker` del [workflow](../../.github/workflows/ci.yml) |
| README, AI_USAGE y [plan de monitorización](MONITORIZACION.md) | Despliegue, monitorización y exposición | [`Dockerfile`](../proyecto_iii/Dockerfile), [`render.yaml`](../../render.yaml), `/health`, `/api/v1/metrics`, `/api/v1/pipeline` ([`journal.py`](../proyecto_iii/dsia_web/journal.py)), [`evidence.py`](../proyecto_iii/dsia_web/evidence.py), dashboard en [`static/`](../proyecto_iii/dsia_web/static) |

`=>` El III no reescribe el núcleo: importa `infer` y `AIClient` y añade lo que el II deja fuera. Despliegue en **[https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com)** (Render, imagen Docker): al arrancar descarga barras reales de Alpaca, reentrena con este pipeline y publica solo predicciones y métricas (último dato 2026-11-20).

`>` Módulos del II:

| Ruta | Responsabilidad |
| --- | --- |
| `swarmtrade_app/data.py`, `preparation.py` | Esquema, factores causales, split y purga |
| `inspection.py` | Perfil y figuras de EDA sin entrenar |
| `models.py`, `training.py` | Estimadores sklearn, selección, persistencia y test único |
| `pipeline.py` | Inferencia desde el artefacto, asignación e informe |
| `ai_client.py`, `paper.py` | Bordes tipados de IA y de Alpaca paper |
| `cli.py`, `__main__.py` | Automatización y configuración, sin lógica de negocio |
| `_vendor/` | Factores, especialistas y solver de SwarmTrader v1.4, con licencia MIT y hashes |
| `ml_pipeline/` | Guard del holdout, registro y cuatro notebooks marimo |
| `tests/` | Unitarios e integración, con la red bloqueada |

`>>` Más contexto: [trazabilidad de requisitos](../../docs/TRAZABILIDAD_DSIA.md#proyecto-ii--automatización-e-integración) · [diagrama del II](../../docs/ARQUITECTURA_DSIA.md#proyecto-ii--entrenamiento-e-inferencia) · [verificación](VERIFICACION.md).

## Tests y CI

`>` Desde esta carpeta, con el entorno activo:

```bash
python -m pytest -q --cov=swarmtrade_app --cov-report=term-missing
python -m pytest -q -m integration
```

`>>` Los tests cubren el esquema y la validación de datos, la preparación y la purga, el entrenamiento y la **recarga del artefacto con inferencia**, el contrato del cliente de IA (incluida la firma real de `InferenceClient`, la clasificación de errores y los reintentos con espera simulada), la asignación y el adaptador paper con dobles. Los de integración recorren la CLI completa con archivos temporales. `tests/conftest.py` bloquea `socket.connect`, `socket.connect_ex`, `socket.create_connection` y `socket.getaddrinfo`, y aísla la suite de un `.env` local; el subproceso del test de integración recibe `AI_PROVIDER=mock` sin variables `HF_*`.

`>>` Workflow: [.github/workflows/ci.yml](../../.github/workflows/ci.yml). El job `proyectos-ii-y-iii` ejecuta en Ubuntu con Python 3.12 los tests del II con `--cov-fail-under=80`, `marimo check` de los cuatro notebooks y un smoke de la CLI: genera la demo, comprueba su sha256, entrena, evalúa, ejecuta `run` con `mock` y compara `validation.json` (`ridge.rmse` 0,064383) y `test_metrics.json` (`rmse` 0,070995, `baseline.rmse` 0,066148) con tolerancia 1e-6.

`=>` Último run verde de `main`: [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693). Tests del II: <cifras de tests>. Detalle en [VERIFICACION.md](VERIFICACION.md).

## Cobertura del enunciado

| Requisito del profesor | Implementación o evidencia | Estado |
| --- | --- | --- |
| 1. Dominio y datos del III: origen, licencia, motivación | [Motivación](#motivación), [datos](#datos-origen-licencia-y-contrato), [contrato](PROBLEMA.md) y [data/README.md](data/README.md) | Cumple; el histórico de Alpaca no se redistribuye |
| 2. Pipeline reproducible con logs | CLI `inspect`/`train`/`evaluate`/`run`, logs por etapa y códigos de salida | Cumple |
| 3. Entrenamiento sklearn, persistencia, inferencia integrada y métricas | `training.py`, `model.joblib`, `run` y las tablas de métricas | Cumple |
| 4. pytest unitario + integración con carga e inferencia del modelo | `tests/`, recarga del artefacto y CLI completa | Cumple |
| 5. Borde HF con `mock` y proveedor real documentado | `AIClient`, `chat_completion` + `Qwen/Qwen2.5-7B-Instruct` | `mock` comprobado; llamada real no realizada (alternativa del enunciado) |
| 6. `.env.example` con `HF_TOKEN=` y `requirements.txt` | [.env.example](.env.example), [requirements.txt](requirements.txt) con `scikit-learn` y `huggingface_hub` | Cumple |
| 7. `AI_USAGE.md` con proveedor, tarea, modelo y lo aceptado | [AI_USAGE.md](AI_USAGE.md) | Cumple |
| 8. Estructura modular ampliable | [Del Proyecto II al Proyecto III](#del-proyecto-ii-al-proyecto-iii) | Cumple; el III la reutiliza |
| Entrega: repositorio del III | Este mismo repositorio | Cumple |
| Entrega: historial de commits en octubre | Ver [Desarrollo por fechas](#desarrollo-por-fechas) | No cumple; no se fabrican fechas |
| Entrega: artefactos o instrucciones de reentrenamiento | Receta sin claves y entorno fijado; los modelos se regeneran y no se versionan | Cumple |

## Desarrollo por fechas

- `->` **11 noviembre:** se crea el repositorio de investigación [`dalonsogomez-ai/swarmtrader`](https://github.com/dalonsogomez-ai/swarmtrader/tree/5642dda71a1e50d55da3ad1206ec2ae1b891ac28), del que se toman factores, especialistas y solver (v1.4.0, commit `5642dda`).
- `~>` **12 noviembre:** se escribe el Proyecto II con OpenAI Codex (modelo `gpt-6.1-sol`): contrato temporal, puntos de aprobación del pipeline, adaptación del código vendorizado, tests y primer run con el histórico de Alpaca. Trabajo local, sin commits.
- `>>` **19 noviembre:** auditoría de la extracción de Alpaca con Codex (`gpt-6.1-sol`).
- `~>` **23 noviembre:** integración del II ([`e524ec0`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e524ec0)) y del III ([`3d991d2`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3d991d2)) en el repositorio de entrega con Codex (`gpt-6.2-sol`); auditoría de cumplimiento y mejoras en commits pequeños con Claude Code (Claude Opus 5.5); [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) fusionado (`a5a5b9b`), tag [`v0.9.0-rc1`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1) y despliegue en Render.
- `>` **23 y 24 noviembre:** el despliegue pasa a datos reales de Alpaca ([PR #2](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/2), `bed8312`; [PR #3](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/3), `033d134`).
- `~>` **24 noviembre:** revisión del borde HF (validación del resumen, errores clasificados, reintentos y `from_env`), umbral de pesos `1e-4`, comprobación de métricas en el CI y esta documentación con la leyenda de la wiki.
- `=>` **Octubre:** no hay commits del Proyecto II en octubre, aunque el enunciado pide historial a lo largo de ese mes. El trabajo empezó el 11 y 12 de noviembre y entró en Git el 23. No se reescriben fechas ni se fabrican commits.
