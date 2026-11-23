# Verificación del Proyecto II

La suite de pytest valida datos, carga e inferencia sklearn, contrato del cliente de IA y lógica del adaptador paper con dobles. `marimo check` comprueba la estructura de los cuatro notebooks. En una réplica local pasaron 51 tests con 81 % de cobertura redondeada.

El 23/11/2026, tras la auditoría de cumplimiento, pasaron 74 tests con 83 % de cobertura (`inspection.py` y `training.py` al 100 %), con un test de contrato contra la firma real de `InferenceClient` y los tests aislados de cualquier `.env` local. La receta del README, ejecutada en una copia temporal con la red de salida bloqueada (`sandbox-exec`), reprodujo el sha256 `c0574a85…f4c2` de `data/demo.csv`, las métricas de validación y holdout y el baseline del README, con `ai_status=completed` en mock. `dsia_web.build demo` y `from-run` del Proyecto III siguieron funcionando con este núcleo.

El histórico del proveedor se procesó en local. El despliegue de demostración y CI emplean datos sintéticos y el mock determinista. La evidencia remota es el run [45271274056](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45271274056) de `main`: pytest con umbral del 80 %, `marimo check` y la receta de la CLI con el sha256 de la demo. La evidencia del commit se verifica en la pestaña Actions del repositorio. [Workflow](../../.github/workflows/ci.yml)
