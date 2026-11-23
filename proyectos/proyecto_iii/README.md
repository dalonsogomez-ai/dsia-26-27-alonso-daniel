# Proyecto III · Aplicación de investigación SwarmTrader

El dashboard muestra retornos estimados a 21 sesiones, un baseline y la procedencia de la inferencia. Consume el informe de la API con una petición HTTP real. El [diagrama](../../docs/ARQUITECTURA_DSIA.md) explica por qué el cálculo se ejecuta por lotes. La explicación de la demo usa el cliente `mock` del Proyecto II.

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

## Operación y verificación

- `--journal` escribe un JSONL por ejecución. Cada etapa tiene un inicio y un resultado con tiempo transcurrido. Un fallo incluye su tipo. El evento de publicación registra el `run_id`. En `from-run`, la etapa `validate_input` valida el CSV con el contrato del II y registra solo agregados (`rows`, `symbols`, `input_sha256`) antes de `infer_snapshot`. Usa un archivo nuevo fuera de `--work` para conservar la evidencia.
- `/health` confirma que el proceso tiene en memoria un snapshot válido. El timestamp del journal mide cuándo corrió el lote y `as_of` indica el cierre de los datos. Cada valor responde a una pregunta distinta durante la demo.
- Para un servicio gestionado, configura [`.env.example`](.env.example) en las variables del entorno y apunta a un snapshot persistente. Arranca Uvicorn con el host, puerto y política de acceso del entorno. El despliegue de referencia es local con el mismo proceso para API y dashboard.
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
