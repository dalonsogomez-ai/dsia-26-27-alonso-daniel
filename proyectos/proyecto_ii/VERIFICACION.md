# Verificación del Proyecto II

`->` Comprobaciones que respaldan las cifras del [README](README.md), con su fecha. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki).

## Qué se comprueba

| Comprobación | Cómo | Dónde |
| --- | --- | --- |
| Datos, preparación, entrenamiento, recarga del artefacto e inferencia | `python -m pytest -q --cov=swarmtrade_app` | Local y CI, umbral de cobertura del 80 % |
| Contrato del cliente de IA: validación del resumen, errores 401/403/404, reintentos ante 429/5xx/timeout, firma real de `InferenceClient` | Tests con dobles del SDK y espera simulada | Local y CI |
| Suite sin red | `tests/conftest.py` bloquea `connect`, `connect_ex`, `create_connection` y `getaddrinfo` | Local y CI |
| Notebooks | `python -m marimo check ml_pipeline/01_eda.py ml_pipeline/02_prep.py ml_pipeline/03_model.py ml_pipeline/04_eval.py` | Local y CI |
| Receta de la CLI | sha256 de la demo, `train`, `evaluate`, `run --provider mock` y métricas con tolerancia 1e-6 | CI y copia temporal local |
| Núcleo reutilizado por el III | Tests del III, `dsia_web.build demo` y prueba de navegador | CI |

## 24/11/2026

`>>` Tests del II: <cifras de tests>.

`>>` La receta del README, ejecutada en una copia temporal de esta carpeta con `AI_PROVIDER=mock` y sin `HF_TOKEN`, reprodujo el sha256 `c0574a85…f4c2` de `data/demo.csv`, las métricas de validation (Ridge 0,064383, Dummy 0,065762, Swarm 0,065318), las del holdout (Ridge 0,070995, MAE 0,055318, R² −0,254941) y el baseline (0,066148), con `ai_status=completed`.

`>>` Con el artefacto de esa ejecución, la media diaria de las predicciones fue la misma en las 428 fechas con factores completos (diferencia máxima de 1e-16) e igual a la predicción del baseline Dummy, 0,016455. Es la comprobación de que el modelo aporta el orden relativo entre símbolos y no el nivel.

## 23/11/2026

`>>` La receta se ejecutó en una copia temporal con la red de salida bloqueada (`sandbox-exec` en macOS) y en Linux x86_64 dentro del CI: ambos dieron el mismo sha256 de la demo después de fijar los precios a 6 decimales. `dsia_web.build demo` y `from-run` del III funcionaron con este núcleo. El histórico de Alpaca se procesó solo en local y se publicó su [resumen agregado](../proyecto_iii/evidencia/historico_alpaca.json).

## Evidencia remota

`=>` Último run verde de `main`: [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693), con los jobs del I, del II y III y del contenedor Docker. Las ejecuciones se consultan en la [pestaña Actions](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml) y la definición en el [workflow](../../.github/workflows/ci.yml). El despliegue y el CI usan la demo sintética y el `mock` determinista, salvo el refresco con datos reales de Alpaca que hace el III en Render.
