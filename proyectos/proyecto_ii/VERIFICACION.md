# Verificación del Proyecto II

`->` Comprobaciones que respaldan las cifras del [README](README.md), con su fecha. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki).

## Qué se comprueba

| Comprobación | Cómo | Dónde |
| --- | --- | --- |
| Datos, preparación, entrenamiento, recarga del artefacto e inferencia | `python -m pytest -q --cov=swarmtrade_app` | Local y CI, umbral de cobertura del 80 % |
| Contrato del cliente de IA: validación del resumen, errores 401/403/404, reintentos ante 429/5xx/timeout, firma real de `InferenceClient` | Tests con dobles del SDK y espera simulada | Local y CI |
| Suite sin red | `tests/conftest.py` bloquea `connect`, `connect_ex`, `create_connection` y `getaddrinfo` | Local y CI |
| Notebooks | `python -m marimo check ml_pipeline/01_eda.py ml_pipeline/02_prep.py ml_pipeline/03_model.py ml_pipeline/04_eval.py` | Local y CI |
| Receta de la CLI | sha256 de la demo, `inspect` (en el CI desde los commits de la RC2), `train`, `evaluate`, `run --provider mock` y métricas con tolerancia 1e-6: en el CI, desde los commits de la RC2, los 15 valores de la tabla de referencia y la inferencia (media, spread, `top_symbol` y la predicción de DEMO06); hasta `e433fae`, 3 RMSE | CI y copia temporal local |
| Unitarios e integración | `python -m pytest -q -m integration` y `python -m pytest -q -m "not integration"` | Local |
| Núcleo reutilizado por el III | Tests del III, `dsia_web.build demo` y prueba de navegador | CI |

## 24/11/2026

`>>` Tests del II en local (`.venv-ii`, `pytest -q --cov=swarmtrade_app --cov-fail-under=80`): 128 passed y 85,40 % tras el borde de IA; 162 passed y 85,97 % tras añadir el proveedor `nvidia`; 183 passed y 86,35 % tras añadir `kind` a `AIClientError` y los campos `focus_*`; **194 passed y 86,43 %** tras separar en la taxonomía el plazo vencido (`timeout`, también 408 y 504) de la conexión caída (`unavailable`) y añadir `AIClient.secret_env`, con `ai_client.py` al 100 % y `marimo check` de los cuatro notebooks sin avisos; **197 passed y 86,50 %** tras la segunda ronda de verificación de la RC2 (pruebas de las predicciones del estimador guardado, de otra versión de sklearn y de `choices=[]` en HF).

`>>` Reparto de esos 197 tests, en local el 24/11/2026: **190 unitarios y 7 de integración** (`@pytest.mark.integration`). La carga e inferencia del modelo sklearn la prueban `test_load_inference_mock_and_conviction` (integración), `test_model_roundtrip_and_schema` y `test_inference_predictions_come_from_the_persisted_estimator`, que compara cada predicción del informe con `estimator.predict` del artefacto recargado (hasta la segunda ronda de verificación ninguna prueba lo comprobaba: un pipeline que ignorase el modelo habría pasado), en `tests/test_models_pipeline.py`.

```bash
python -m pytest -q -m integration        # 7 passed, 190 deselected
python -m pytest -q -m "not integration"  # 190 passed, 7 deselected
```

`>>` Ronda de verificación de la RC2, en local el 24/11/2026 con los pasos del workflow: 194 passed y 86,43 % (tras cambiar las claves falsas de `test_ai.py` por valores sin forma de clave real), `marimo check` sin avisos y el smoke de la CLI, ahora con `inspect --data … --output …` y `data_profile.json` no vacío, con el sha256 de la demo y las métricas dentro de 1e-6.

`>>` Llamadas reales desde el despliegue de Render (Proyecto III): a Hugging Face, fallidas por falta de crédito en la cuenta del autor (`BadRequestError` con `auto` y Qwen2.5-7B; `HfHubHTTPError` con `deepinfra` y Qwen2.5-72B); a NVIDIA, tres por modelo (NVDA, AAPL, XOM), correctas con `nvidia/nemotron-3.5-super-vl-120b-a12b` ([tabla](README.md#alternativa-nvidia)). Ninguna se hace desde los tests.

`>>` La receta del README, ejecutada en una copia temporal de esta carpeta con `AI_PROVIDER=mock` y sin `HF_TOKEN`, reprodujo el sha256 `c0574a85…f4c2` de `data/demo.csv`, las métricas de validation (Ridge 0,064383, Dummy 0,065762, Swarm 0,065318), las del holdout (Ridge 0,070995, MAE 0,055318, R² −0,254941) y el baseline (0,066148), con `ai_status=completed`.

`>>` Con el artefacto de esa ejecución, la media diaria de las predicciones fue la misma en las 428 fechas con factores completos (diferencia máxima de 1e-16) e igual a la predicción del baseline Dummy, 0,016455. Es la comprobación de que el modelo aporta el orden relativo entre símbolos y no el nivel.

## 23/11/2026

`>>` La receta se ejecutó en una copia temporal con la red de salida bloqueada (`sandbox-exec` en macOS) y en Linux x86_64 dentro del CI: ambos dieron el mismo sha256 de la demo después de fijar los precios a 6 decimales. `dsia_web.build demo` y `from-run` del III funcionaron con este núcleo. El histórico de Alpaca se procesó solo en local y se publicó su [resumen agregado](../proyecto_iii/evidencia/historico_alpaca.json).

## Evidencia remota

`=>` Las ejecuciones del CI se consultan en el [historial de `main`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions?query=branch%3Amain) y la definición en el [workflow](../../.github/workflows/ci.yml); último run comprobado: [45407490182](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45407490182) (`1ff1817`, 24/11/2026), con los jobs del I, del II y III y del contenedor Docker en verde. El CI usa la demo sintética y el `mock` determinista. El despliegue del III en Render usa datos reales de Alpaca y, para «Explicar símbolo», `AI_PROVIDER=nvidia`; la explicación del lote sigue en `mock`.
