# Proyecto III · Aplicación de investigación SwarmTrader

El dashboard muestra retornos estimados a 21 sesiones, un baseline, los datos de entrada por símbolo y la procedencia de la inferencia. Consume el informe de la API con una petición HTTP real, lanza análisis bajo demanda con `POST /api/v1/analyze` y su panel **Operación** lee `/health`, `/api/v1/metrics` y `/api/v1/pipeline`. El [diagrama](../../docs/ARQUITECTURA_DSIA.md) explica por qué el cálculo se ejecuta por lotes. La explicación de la demo usa el cliente `mock` del Proyecto II.

## Despliegue reproducible

Ejecuta desde la raíz del repositorio.

1. **Entorno e instalación.** Con Python 3.12, ejecuta `python3.12 -m venv .venv` y `.venv/bin/python -m pip install -r proyectos/proyecto_ii/requirements.txt`.
2. **Informe y configuración.** Genera la demo una vez en un destino nuevo.

   ```bash
   export PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii
   export MPLBACKEND=Agg
   .venv/bin/python -m dsia_web.build demo --work runs/demo/work \
     --output runs/demo/snapshot.json --journal runs/demo/pipeline.jsonl
   export DSIA_SNAPSHOT="$PWD/runs/demo/snapshot.json"
   ```

3. **Arranque.** Ejecuta `.venv/bin/python -m uvicorn dsia_web.app:app --host 127.0.0.1 --port 8765`. Abre [el dashboard local](http://127.0.0.1:8765/).
4. **Smoke test.** En otra terminal, verifica salud e informe con peticiones reales.

   ```bash
   curl -fsS http://127.0.0.1:8765/health
   curl -fsS http://127.0.0.1:8765/api/v1/snapshot
   PYTHON=.venv/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh
   ```

5. **Recuperación.** Conserva el snapshot anterior. Si el nuevo no supera las comprobaciones, apunta `DSIA_SNAPSHOT` a la versión previa y reinicia el servicio. Un snapshot ausente o inválido hace que `/health` responda 503.

El [workflow](../../.github/workflows/ci.yml) instala las dependencias en Linux, genera otro snapshot desde cero y verifica la API y el dashboard con Chromium. El artefacto `dsia-dashboard-sintetico` del run contiene `dashboard.png` y `pipeline.jsonl`. El navegador verifica que la publicación registrada, la API y la pantalla muestren el mismo `run_id`.

## Empaquetado y despliegue

> No hay URL pública desplegada todavía. El despliegue lo hace el autor con su propia cuenta; el repositorio deja listos la imagen y el blueprint, verificados en local.

- **Modo producción sin contenedor.** Escucha en todas las interfaces y en el puerto que asigne la plataforma: `uvicorn dsia_web.app:app --host 0.0.0.0 --port "$PORT"`. En local usa siempre `--host 127.0.0.1`.
- **Docker.** El contexto es la raíz del repositorio y [`.dockerignore`](../../.dockerignore) deja fuera `.git`, entornos, `runs`, `data/raw`, `.env*` y el resto de asignaturas. La [imagen](Dockerfile) parte de `python:3.12-slim`, instala `proyectos/proyecto_ii/requirements.txt` sin caché, genera el snapshot demo sintético durante el build, corre con un usuario sin privilegios (uid 10001) y declara un `HEALTHCHECK` contra `/health` hecho con Python.

  ```bash
  docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii .
  docker run --rm -p 8790:8000 dsia-iii        # -e PORT=9000 cambia el puerto interno
  PYTHON=.venv-ii/bin/python bash proyectos/proyecto_iii/scripts/smoke_test.sh http://127.0.0.1:8790
  ```

- **Render.** [`render.yaml`](../../render.yaml) instala dependencias y genera el snapshot en `buildCommand`, arranca Uvicorn con `$PORT` y usa `healthCheckPath: /health`. Fija `AI_PROVIDER=mock`, `PYTHONPATH`, `DSIA_SNAPSHOT` y `DSIA_JOURNAL`; `HF_TOKEN` y `DSIA_API_KEY` se introducen en el panel (`sync: false`). [`.python-version`](../../.python-version) fija Python 3.12.
- **Procfile.** [`Procfile`](../../Procfile) sirve para plataformas tipo Heroku: genera el snapshot demo si falta y arranca Uvicorn en `$PORT`.
- **Clave opcional.** Con `DSIA_API_KEY` definida, `POST /api/v1/analyze` exige `X-API-Key`. El resto de endpoints son de lectura.

## Informe con el histórico del Proyecto II

Sigue la [receta de entrenamiento e inferencia del II](../proyecto_ii/README.md#reproducir-el-histórico-autorizado). Usa el mismo CSV y el directorio que contiene `model.joblib` y `test_metrics.json` de una ejecución propia. Define `DSIA_BARS_CSV` y `DSIA_FROZEN_RUN` en el entorno local. Con el `PYTHONPATH` anterior:

```bash
history_dir=$(mktemp -d)
.venv/bin/python -m dsia_web.build from-run \
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

El archivo no contiene precios, predicciones por símbolo, `input_summary` ni el texto de la explicación. Se regenera con `python -m dsia_web.evidence --snapshot <snapshot> --journal <pipeline.jsonl> --output <nuevo.json>`. En local, el mismo snapshot pasa `smoke_test.sh` y `browser_smoke.py --kind "Histórico Alpaca" --expect-pipeline`.

## Operación y verificación

- `--journal` escribe un JSONL por ejecución. Cada etapa tiene un inicio y un resultado con tiempo transcurrido. Un fallo incluye su tipo. El evento de publicación registra el `run_id`. En `from-run`, la etapa `validate_input` valida el CSV con el contrato del II y registra solo agregados (`rows`, `symbols`, `input_sha256`) antes de `infer_snapshot`. Usa un archivo nuevo fuera de `--work` para conservar la evidencia.
- `/health` confirma que el proceso tiene en memoria un snapshot válido. El timestamp del journal mide cuándo corrió el lote y `as_of` indica el cierre de los datos. Cada valor responde a una pregunta distinta durante la demo.
- Para un servicio gestionado, configura [`.env.example`](.env.example) en las variables del entorno y apunta a un snapshot persistente. API y dashboard comparten proceso; el empaquetado está en [Empaquetado y despliegue](#empaquetado-y-despliegue).
- Suite desde la raíz:

  ```bash
  PYTHONPATH=proyectos/proyecto_ii:proyectos/proyecto_iii \
    .venv/bin/python -m pytest -q proyectos/proyecto_iii/tests
  ```

## Guion de 5–7 minutos

| Tiempo | Qué mostrar |
| --- | --- |
| 1 min | Problema, fuente y horizonte de 21 sesiones |
| 1 min | Diagrama con entrenamiento, artefacto e inferencia por lotes |
| 2 min | Ranking, filtro y respuesta HTTP. Confirmar que el `run_id` de la vista coincide con el de `/health` |
| 1 min | Comparar Dummy y Ridge por RMSE en validación. Abrir holdout y explicar el R² negativo |
| 1 min | Cortes temporales, purga, procedencia y alcance del mock. Mostrar el run de CI y el journal del lote |

[Release Candidate](RELEASE.md) · [Rúbricas y trazabilidad](../../docs/TRAZABILIDAD_DSIA.md) · [Contrato HTTP](API.md) · [Citación de IA](AI_USAGE.md) · [Enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md)
