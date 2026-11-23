# -> Proyecto II — Automatización e integración de servicios

~> Dominio del Proyecto III: investigación de selección de acciones a 21 sesiones. Se adapta **SwarmTrader v1.4.0** a un pipeline didáctico con sklearn y un borde de IA/Hugging Face, siguiendo el [enunciado vigente del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_ii/README.md), cotejado el 23/11/2026.

> Flujo: **datos → factores SwarmTrader → train/validation/test con purga → sklearn persistido → inferencia → cartera por convicción → explicación HF/mock**. Alpaca paper es un adaptador separado; no participa en tests ni CI con credenciales reales.

=> Estado: implementación local y comprobaciones en [VERIFICACION.md](VERIFICACION.md). SwarmTrader sigue en investigación/backtesting; su auditoría G4 publicada da **NO ACCIONABLE**. Aquí se implementa la elección por convicción solicitada: elegir bajo incertidumbre no acredita ventaja. No hay trading real activado ni paper externo validado.

## > Reproducir sin claves ni datos de terceros

Desde esta carpeta, Python **3.12** y un entorno propio del Proyecto II:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m swarmtrade_app demo-data --output data/demo.csv --sessions 680 --symbols 8 --seed 42
python -m swarmtrade_app inspect --data data/demo.csv --output runs/demo-inspection
python -m swarmtrade_app train --data data/demo.csv --run runs/demo --data-kind synthetic
python -m swarmtrade_app evaluate --run runs/demo
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/report.json --provider mock
python -m pytest -q --cov=swarmtrade_app --cov-report=term-missing
```

>> La demo genera datos propios, no requiere Internet después de instalar dependencias y no lleva señal artificial diseñada para asegurar éxito. Los tests bloquean sockets y entrenan modelos pequeños sobre fixtures sintéticos. Un resultado de demo no demuestra desempeño financiero.

> No se sobrescriben datos, runs, modelos ni informes. Para otro experimento, usa nombres nuevos. `evaluate` rechaza una segunda evaluación del holdout. Repetir el mismo dataset con otra carpeta no lo convierte en un test nuevo: el flujo prohíbe utilizar sus resultados para afinar candidatos. `--prepared` permite continuar una preparación existente sin volver a dividir/congelar datos.

> Los logs van a stderr; el resultado JSON va a stdout y los informes al destino explícito. Cada etapa registra a INFO con su logger de módulo: carga (filas, símbolos, rango de fechas), preparación (tamaños del split y filas purgadas), inferencia (`as_of`, prefijo del sha256 del artefacto, media predicha), convicción (pesos, convergencia y brecha) e IA (proveedor, modelo, latencia y `ai_status`; nunca el token). `--log-level` va antes del subcomando, por ejemplo `python -m swarmtrade_app --log-level WARNING run ...`; matplotlib queda en WARNING. La CLI devuelve 0 en ejecución técnica correcta y 2 ante errores controlados. Una asignación con ventaja no demostrada no se convierte por ello en error técnico.

## > Datos, problema y evaluación

Origen, condiciones y limitaciones en [data/README.md](data/README.md). CSV diario con `date`/`timestamp`, `symbol`, `close`, `volume`; OHLC opcional. Se validan tipos, finitud, precios positivos, volumen, duplicados, coherencia OHLC y universo común sin huecos. Se requieren al menos cinco símbolos y suficiente historia para 252 sesiones de warmup y un split útil.

El [contrato aprobado](PROBLEMA.md) define `target=close[t+21]/close[t]-1`. Los 14 factores de precio/volumen proceden de la versión fijada en [UPSTREAM.json](UPSTREAM.json), con licencia y adaptación en [THIRD_PARTY.md](THIRD_PARTY.md). No se usan target, símbolo, fecha futura ni respuesta HF como features.

Se reservan 60/20/20 de fechas completas y se purgan etiquetas que cruzan fronteras. StandardScaler se ajusta solo en train dentro del Pipeline sklearn. Candidatos prefijados, alpha=10: DummyRegressor(mean), Ridge global y media de cinco Ridge especialistas (momentum, reversal, lowrisk, liquidity, seasonal). Se selecciona menor **RMSE validation**, con desempate estable a favor del modelo sencillo. No hay búsqueda de hiperparámetros ni selección por test. MAE, R² y acierto de signo completan el informe; retornos solapados no se tratan como observaciones independientes para inferencia estadística.

La ejecución sintética de referencia usa 680 sesiones, 8 símbolos y semilla 42. En validación, Ridge obtuvo RMSE 0,064383 frente a 0,065762 de Dummy y 0,065318 de Swarm. El holdout congelado de Ridge obtuvo RMSE 0,070995, MAE 0,055318 y R² −0,254941. Se genera con `dsia_web.build demo`, descrito en el Proyecto III. Para el histórico, el formato de entrada y las restricciones se documentan en [datos](data/README.md). Carga artefactos joblib propios y de procedencia conocida.

Los notebooks marimo leen el CSV sintético y el run generados por la receta anterior. Puedes seleccionar otro CSV con `DSIA_DATA_PATH`, otro directorio de EDA con `DSIA_EDA_DIR` y otra ejecución con `DSIA_RUN_DIR`. Abre los notebooks desde la carpeta del Proyecto II, por ejemplo con `marimo edit ml_pipeline/02_prep.py`.

### Reproducir el histórico autorizado

Desde el entorno del II, define `DSIA_BARS_CSV` con el CSV local descrito en [el contrato de datos](data/README.md). Usa un directorio nuevo para entrenar. Si ya tienes un run evaluado con ese CSV, reutiliza sus artefactos para inferir y para la [demo histórica del III](../proyecto_iii/README.md#informe-con-el-histórico-del-proyecto-ii).

```bash
python -m swarmtrade_app train --data "$DSIA_BARS_CSV" --run runs/historico --data-kind alpaca
python -m swarmtrade_app evaluate --run runs/historico
python -m swarmtrade_app run --data "$DSIA_BARS_CSV" --artifact runs/historico/model.joblib \
  --output runs/historico/report.json --provider mock
```

## > Elegir una acción o combinación sin diversificación forzada

`run` usa `--decision conviction --mean-source model --risk-aversion 1` por defecto. Se utiliza el solver de v1.4 sobre el **símplex completo**: sin tope por nombre/sector, mínimo de posiciones o efectivo obligatorio. Puede asignar 100 % a un único activo. El [diseño, matemática, fuentes y ejecución](DECISION.md) explican el alcance del óptimo y el tratamiento de incertidumbre.

```bash
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/all-in.json --risk-aversion 0 --provider mock
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/empirical.json --mean-source empirical --provider mock
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/research.json --decision research --provider mock
```

> `risk-aversion=0` elige el mayor retorno esperado y asigna 100 %, incluso si todas las medias son negativas. `1` maximiza crecimiento logarítmico; una combinación solo aparece por el objetivo. El modo `empirical` conserva el mapa de medias original, que queda plano con universos pequeños. El modo `model` usa las medias sklearn estimadas, sin afirmar calibración; el banco de escenarios conserva la dependencia histórica. La fuente queda registrada y no cambia automáticamente según los resultados.

## > Hugging Face: una pieza diferente de sklearn

Se sigue el estilo del ejemplo de clase `ai_api_client.py`: dataclasses de entrada/salida, `AIClientError` y proveedores `mock`/`hf`. HF realiza **chat_completion**, modelo [Qwen/Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct). Explica un resumen agregado después de inferir; no decide carteras ni envía órdenes. [AI_USAGE.md](AI_USAGE.md) documenta proveedor, tarea, modelo, costes acotados y aportaciones de IA.

```bash
cp .env.example .env
# Completar HF_TOKEN localmente; no pegarlo en comandos ni versionarlo.
python -m swarmtrade_app run --data data/demo.csv --artifact runs/demo/model.joblib --output runs/demo/hf.json --provider hf
```

> El cliente usa InferenceClient, timeout 30 s y máximo 256 tokens de salida por defecto, sin reintentos de aplicación. Disponibilidad, autorización y saldo dependen del proveedor actual. Si falta HF_TOKEN, devuelve error claro; si falla HF, conserva el informe con predicciones y `ai_status=pending`, sin simular respuesta real. No carga credenciales del Proyecto I. En tests/CI siempre mock/dobles, sin Internet ni gasto.

## > Alpaca paper: plan y envío separados

> Añade solo las credenciales **paper** en `.env`: `ALPACA_PAPER_API_KEY_ID` y `ALPACA_PAPER_API_SECRET_KEY`. El adaptador construye TradingClient con `paper=True`. No se configura URL live. Nunca se envían órdenes con el comando `run`.

```bash
python -m swarmtrade_app paper-plan --report runs/actual/report.json --output runs/actual/paper-plan.json
# Tras revisar el plan y con datos de la última sesión cerrada:
python -m swarmtrade_app paper-execute --plan runs/actual/paper-plan.json --journal runs/actual/paper-journal.json
# Si se solicita rotar posiciones anteriores, añadir --liquidate.
```

> `runs/actual` representa un informe propio con datos vigentes; el CSV de septiembre de 2026 no cumple esa condición en noviembre. La demo sintética tampoco define activos operables. El plan consulta cuenta/activos/reloj, calcula `min(cash,buying_power)` sin préstamo y reparte nocionales a céntimos. Buffer técnico configurable con `--buffer-bps`, defecto 0; no hay recorte de concentración. Puede asignar todo el presupuesto a una sola acción.

> El envío comprueba última sesión cerrada, mercado abierto, activos fraccionables, cuenta, órdenes pendientes y rotación explícita. Espera cierres de posiciones antes de comprar y relee saldo. El journal y los client_order_id permiten reconciliar errores ambiguos y evitar reintentos ciegos. Una orden aceptada no es un fill; no se garantiza aceptación del 100 % por spread, reservas o cambios de saldo. No se han usado credenciales reales ni enviado órdenes externas para verificar esta entrega.

## > Módulos y continuidad al Proyecto III

| Ruta | Responsabilidad |
| --- | --- |
| `swarmtrade_app/data.py`, `preparation.py` | Esquema, factores causales, split y purga |
| `models.py`, `training.py` | Estimadores sklearn, selección, persistencia y test único |
| `pipeline.py` | Inferencia desde artefacto, convicción e informe |
| `ai_client.py`, `paper.py` | Bordes tipados de IA y ejecución paper |
| `cli.py`, `__main__.py` | Automatización y configuración; sin lógica de negocio duplicada |
| `_vendor/` | Factores, definiciones y solver v1.4 con MIT y hashes |
| `ml_pipeline/` | Tracker, helper y cuatro notebooks de inspección/evidencia |
| `tests/` | Unitarios e integración, sockets bloqueados por defecto |

Para revisar las figuras: `python -m marimo edit ml_pipeline/01_eda.py` (también 02_prep, 03_model, 04_eval). Ejecutar desde esta carpeta; `01_eda.py` lee `data/demo.csv` por defecto; para inspeccionar las barras autorizadas del Proyecto I, exporta `DSIA_DATA_PATH` con su ruta. Las demás fases muestran evidencias existentes y no vuelven a tocar el test al abrirse. Los perfiles/figuras reales y runs permanecen locales e ignorados.

El [Proyecto III](../proyecto_iii/README.md) reutiliza `infer` y `AIClient.analyze` para materializar un snapshot. La API de lectura y el dashboard muestran métricas y procedencia. El adaptador paper permanece separado del servicio web. [Plan de seguimiento](MONITORIZACION.md) · [Trazabilidad de requisitos](../../docs/TRAZABILIDAD_DSIA.md#proyecto-ii--automatización-e-integración) · [Diagrama Excalidraw del II](../../docs/ARQUITECTURA_DSIA.md#proyecto-ii--entrenamiento-e-inferencia)

## >> Cobertura del enunciado y entrega

| Requisito del profesor | Implementación o evidencia | Estado |
| --- | --- | --- |
| 1. Dominio/datos, origen/licencia/motivación | Investigación bursátil, contrato y data/README | Implementado; datos reales privados |
| 2. CLI/job y logs | train/evaluate/run/inspect; logging y códigos de salida | Comprobado localmente |
| 3. sklearn entrenado/persistido/inferencia/métricas | models, training, pipeline, joblib y tabla anterior | Comprobado localmente |
| 4. Pytest unitario + integración carga/inferencia | tests; fixtures pequeños, recarga de artefacto y CLI completa | Comprobado localmente |
| 5. Borde HF mock + diseño real documentado | AIClient tipado, Qwen, tests del SDK | Mock comprobado; real no validado, alternativa permitida |
| 6. Entorno, HF_TOKEN y dependencias | .env.example y requirements.txt fijado | Implementado e instalado |
| 7. Citar uso IA/proveedor/tarea/modelo | AI_USAGE.md | Documentado |
| 8. Núcleo modular reutilizable en III | Separación datos/modelos/pipeline/bordes/CLI | Implementado |
| Repo GitHub del III | Se trabaja en el mismo repositorio del alumno | II y III en el mismo árbol |
| Historial de octubre | No se alteran fechas ni se fabrican commits | No subsanable retroactivamente |
| Artefactos o instrucciones claras de reentrenamiento | Comandos sin claves y entorno fijado; modelos reales ignorados | Implementado |
| CI | [.github/workflows/ci.yml](../../.github/workflows/ci.yml), mock y bloqueo de red en tests | Consultar el run del commit en Actions |
