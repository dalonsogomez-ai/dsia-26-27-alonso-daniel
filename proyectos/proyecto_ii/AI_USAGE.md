# Uso de IA en el Proyecto II

`->` Registro del uso de IA según la política del curso: herramienta y modelo, objetivo, resumen de prompts, lo aceptado y lo rechazado, verificación y commits. Las cifras proceden de comandos ejecutados y archivos generados, no del texto de los asistentes. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki). El registro común del repositorio está en [docs/AI_USAGE.md](../../docs/AI_USAGE.md).

## IA dentro del producto

| Proveedor | Tarea | Modelo | Uso |
| --- | --- | --- | --- |
| `mock` (por defecto) | `chat_completion` | `mock-determinista-v1` | Sin token ni red; siempre en tests y CI |
| Hugging Face Inference Providers | `chat_completion` | [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), pesos Apache-2.0 según su ficha | Explicar después de inferir un resumen agregado (fecha, modelo, horizonte, número de símbolos, media, dispersión, spread, mejor señal, RMSE de validation y tipo de datos) |

`>` SDK `huggingface_hub.InferenceClient` con proveedor de inferencia `auto` configurable, configurado con `AIClient.from_env()`. Timeout de 30 s y 256 tokens de salida por defecto, con límites de 120 s y 512 tokens. Solo los fallos transitorios (429, 5xx, timeout o conexión) se reintentan, hasta dos veces; 401, 403 y 404 fallan sin reintento. El proveedor no recibe barras, cuentas ni claves del broker, y no controla órdenes ni pesos. [Documentación oficial de HF](https://huggingface.co/docs/huggingface_hub/guides/inference) consultada el 12/11/2026.

`=>` No se ha hecho ninguna llamada autenticada a HF ni se han enviado órdenes a un broker externo. Se cumple la alternativa explícita del enunciado: `mock` + cliente tipado + `HF_TOKEN=` en [.env.example](.env.example). El coste y la disponibilidad dependen del modelo, del proveedor, de los permisos y del saldo; no se presupone gratuidad.

## 2026-11-12 — Primera versión del Proyecto II

- `>` **Herramienta y modelo:** OpenAI Codex · `gpt-6.1-sol`.
- `->` **Objetivo:** adaptar SwarmTrader v1.4.0 a un pipeline sklearn con borde de IA que cumpla el enunciado del II.
- `~>` **Prompts (resumen):** leer el enunciado y el código de SwarmTrader → proponer un contrato temporal → esperar la aprobación del usuario en los puntos A, B y C de la skill ml-pipeline → adaptar el código, escribir tests y documentación → ejecutar las fases y registrar la evidencia.
- `=>` **Aceptado:** el [contrato predictivo](PROBLEMA.md) aprobado por el usuario; reutilización de factores, especialistas y optimizador con procedencia MIT; implementación sklearn reproducible con holdout congelado; cliente de borde con `mock`; asignación en el símplex; adaptador paper; tests sin red.
- `~>` **Rechazado:** torneos evolutivos, agentes profundos, señales externas, filtros G0–G4, validación de brokers y controles fiscales de SwarmTrader, porque exceden el enunciado y no se podían verificar con datos sintéticos y tests sin red ([THIRD_PARTY.md](THIRD_PARTY.md)); búsqueda de hiperparámetros y selección por test; la sugerencia de la skill de crear commits y tags, porque el usuario había pedido no hacerlo ese día. No se simuló revisión humana, ni una llamada HF real, ni historial de octubre.
- `>>` **Verificación:** run local con el histórico de Alpaca, con validation y un único toque del holdout registrados en [ml_pipeline/PIPELINE.md](ml_pipeline/PIPELINE.md) (Swarm, RMSE de validation 0,092665 y de holdout 0,0919).
- `>>` **Commits:** trabajo local; el código entró en Git el 23/11 con [`e524ec0`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e524ec0).

## 2026-11-19 — Auditoría de la extracción de Alpaca

- `>` **Herramienta y modelo:** OpenAI Codex · `gpt-6.1-sol`.
- `->` **Objetivo:** revisar la extracción de barras del Proyecto I que alimenta el histórico del II.
- `~>` **Prompts (resumen):** auditar la extracción de barras de Alpaca.
- `=>` **Aceptado:** el CSV descargado el 29/09/2026 siguió siendo la entrada del histórico.
- `~>` **Rechazado:** no quedó un registro detallado de propuestas descartadas; no se atribuye a esta sesión ningún cambio que no esté en Git.
- `>>` **Verificación:** el `input_sha256` `2ebbd7d7…ce4b` es el mismo en el run del 12/11 y en la [evidencia agregada del histórico](../proyecto_iii/evidencia/historico_alpaca.json) del 23/11.
- `>>` **Commits:** ninguno; no hay commits en el repositorio entre el 13/10 y el 23/11.

## 2026-11-23 — Integración en el repositorio de entrega

- `>` **Herramienta y modelo:** OpenAI Codex · `gpt-6.2-sol`.
- `->` **Objetivo:** incorporar el Proyecto II y el Proyecto III al repositorio de la asignatura.
- `~>` **Prompts (resumen):** integrar el trabajo local del II y del III en el repositorio de entrega.
- `=>` **Aceptado:** la estructura `proyectos/proyecto_ii` y `proyectos/proyecto_iii`, con el III importando el núcleo del II.
- `~>` **Rechazado:** no quedó un registro detallado de propuestas descartadas.
- `>>` **Verificación:** la auditoría de Claude Code del mismo día partió de este estado y ejecutó la suite completa (entrada siguiente).
- `>>` **Commits:** [`e524ec0`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e524ec0) (II) y [`3d991d2`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3d991d2) (III).

## 2026-11-23 — Auditoría de cumplimiento y mejoras

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** auditar el II frente al enunciado vigente y aplicar las mejoras en commits pequeños, sin cambiar las firmas públicas que usa el III.
- `~>` **Prompts (resumen):** auditoría requisito a requisito → lista de mejoras → un commit por mejora, con un test que falle antes del cambio.
- `=>` **Aceptado:** aislar los tests de un `.env` local; test de contrato contra la firma real de `InferenceClient`; logs por etapa, `--log-level` y matplotlib en WARNING sin registrar el token; errores de dominio para `HF_TIMEOUT` y `HF_MAX_TOKENS`, alias `huggingface` → `hf` y comprobación de `HF_TOKEN` antes de inferir; cobertura de `inspection.py` e `inspect` con `--output` obligatorio; filtro de pesos residuales; baseline Dummy en el único toque del holdout; dependencias directas del III en `requirements.in`; motivación, proveedor `featherless-ai` según el Hub, modelo alternativo `Qwen/Qwen3-8B` y entorno `.venv-ii` compartido.
- `~>` **Rechazado:** `httpx2==2.16.2`, que propuso el resolutor, porque llevaba 7 días publicado (se fijó 2.16.0); aplicar el filtro de pesos al modo `empirical`, para no alterar la salida upstream; una llamada HF autenticada, por no validar el proveedor sin necesidad.
- `>>` **Verificación:** cada test nuevo se puso en rojo rompiendo temporalmente el código que cubre; `pytest` del II → 73 passed, 83 % de cobertura; `marimo check` sin errores; receta del README en una copia temporal con la red bloqueada; tests del III y `dsia_web.build` en verde.
- `>>` **Commits:** `0f3f419`, `d3c3d46`, `88b878b`, `284a065`, `4d2d141`, `3ee7340`, `3aa3352`, `5360e10`, `e33b6e1` y `823f3e7`.

## 2026-11-23 (tarde) — Verificación final en un clon limpio

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** repetir la verificación del II en un clon limpio y corregir los hallazgos antes de la RC.
- `~>` **Prompts (resumen):** clonar, ejecutar la receta y el CI en local → corregir cada hallazgo con su test.
- `=>` **Aceptado:** `evaluate` sin `model.joblib` da un error de dominio en español, y un segundo `evaluate` traduce el aviso del guard; el comando de la demo de `data/README.md` usa los parámetros de la receta; precios de la demo redondeados a 6 decimales para que el sha256 coincida en macOS y Linux (el primer run del CI en Linux daba `484397d2…`).
- `~>` **Rechazado:** convertir el aviso del guard en `DataError` dentro de la librería: las pruebas del holdout dependen de `TestSetAlreadyUsed` y la traducción pertenece al borde de la CLI.
- `>>` **Verificación:** los tests nuevos fallaron antes del cambio; `pytest` del II → 74 passed, 83 % de cobertura; `marimo check` sin avisos; CI verde en `main`.
- `>>` **Commits:** `f9c9890`, `dc7d11f`, `076d193` y `d3bff34`, integrados con el [PR #1](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/pull/1) (`a5a5b9b`).

## 2026-11-24 — Borde de IA, CI y documentación

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** reforzar el borde HF según el tema de APIs (validación, errores y reintentos), comprobar las métricas en el CI y reescribir la documentación del II con la leyenda de la wiki del Proyecto I.
- `~>` **Prompts (resumen):** contrastar el II con los enunciados del II y del III y con el material de APIs (B6 y A2) → contrato de cambios A1–A8 → implementación con tests → documentación que describe ese contrato.
- `=>` **Aceptado:** campos `prediction_std`, `prediction_spread` y `top_symbol` en el resumen, con validación de tipos y rangos en `AnalysisRequest`; errores HF clasificados y hasta 2 reintentos con backoff y jitter; `AIClient.from_env()` y `DEFAULT_HF_MODEL`, compartidos con el III; `inspect` sin sobrescribir; `MIN_WEIGHT` de `1e-4`; bloqueo de `connect_ex` y `getaddrinfo` en los tests; métricas del smoke comparadas en el CI; `prog` de la CLI y errores de dominio en `analyze-summary`; documentación con fórmulas renderizables, tablas de métricas y cronología real.
- `~>` **Rechazado:** afirmar una licencia MIT para todo el código, porque no hay LICENSE en la raíz; presentar el hash del artefacto como reproducible, porque incluye `created_utc`; mantener cifras antiguas de tests sin fecha.
- `>>` **Verificación:** receta del README en una copia temporal con métricas idénticas a las publicadas; media diaria de las predicciones constante en las 428 fechas de la demo; tests del II: <cifras de tests>.
- `>>` **Commits:** <commits del 24/11>.

## Comandos de evidencia

`>` Desde la raíz del repositorio:

```bash
git log --format='%h %ad %s' --date=short -- proyectos/proyecto_ii
git show --stat e524ec0
cd proyectos/proyecto_ii
python -m pytest -q --cov=swarmtrade_app --cov-report=term-missing
grep -rn "HF_TOKEN" swarmtrade_app/ai_client.py
```
