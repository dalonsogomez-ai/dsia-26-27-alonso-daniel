# Uso de IA en el Proyecto II

`->` Registro del uso de IA según la política del curso: herramienta y modelo, objetivo, resumen de prompts, lo aceptado y lo rechazado, verificación y commits. Las cifras proceden de comandos ejecutados y archivos generados, no del texto de los asistentes. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki). El registro común del repositorio está en [docs/AI_USAGE.md](../../docs/AI_USAGE.md).

## IA dentro del producto

| Proveedor | Tarea | Modelo | Uso |
| --- | --- | --- | --- |
| `mock` (por defecto) | `chat_completion` | `mock-determinista-v1` | Sin token ni red; siempre en tests y CI |
| Hugging Face Inference Providers | `chat_completion` | [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), pesos Apache-2.0 según su ficha | Explicar después de inferir un resumen agregado (fecha, modelo, horizonte, número de símbolos, media, dispersión, spread, mejor señal, RMSE de validation y tipo de datos) |
| NVIDIA ([build.nvidia.com](https://build.nvidia.com/models)), `AI_PROVIDER=nvidia` | `chat_completion` (API compatible con OpenAI) | `nvidia/nemotron-3.5-super-vl-120b-a12b` por defecto; `NVIDIA_MODEL` admite otro del catálogo | Mismo uso, mismo payload y mismo prompt que HF; alternativa añadida el 24/11/2026 porque la cuenta HF del autor no tenía saldo |

`>` SDK `huggingface_hub.InferenceClient` con proveedor de inferencia `auto` configurable, configurado con `AIClient.from_env()`. Timeout de 30 s y 256 tokens de salida por defecto, con límites de 120 s y 512 tokens. Solo los fallos transitorios (429, 5xx, timeout o conexión) se reintentan, hasta dos veces; 401, 403 y 404 fallan sin reintento. El proveedor no recibe barras, cuentas ni claves del broker, y no controla órdenes ni pesos. [Documentación oficial de HF](https://huggingface.co/docs/huggingface_hub/guides/inference) consultada el 12/11/2026.

`>` Con `nvidia`, el mismo `InferenceClient` apunta con `base_url` a `https://integrate.api.nvidia.com/v1` y envía `NVIDIA_API_KEY` como Bearer, con `reasoning_effort="low"`, 4096 tokens y 60 s por defecto (límites de 4096 tokens y 120 s). Errores y reintentos siguen la misma tabla que HF; una respuesta solo de razonamiento falla con un mensaje claro y sin reintento.

`=>` El 24/11/2026 el despliegue de Render (Proyecto III) hizo llamadas autenticadas a HF con el token del autor y fallaron porque la cuenta tenía 0 $ de crédito: `BadRequestError` con el proveedor `auto` y `Qwen/Qwen2.5-7B-Instruct`, y `HfHubHTTPError` con `deepinfra` y Qwen2.5-72B. El contrato y el cliente `hf` están probados con `mock` y con dobles del SDK, que es la alternativa explícita del enunciado (`mock` + cliente tipado + `HF_TOKEN=` en [.env.example](.env.example)). A NVIDIA se hicieron desde Render tres llamadas reales por modelo con cinco candidatos: dos agotaron el timeout (`ReadTimeout`) y Nemotron 3.5 Super respondió en las tres ([tabla](README.md#alternativa-nvidia)); con `nvidia/nemotron-3.5-super-vl-120b-a12b`, NVIDIA es el proveedor de «Explicar símbolo» en el despliegue. No se han enviado órdenes a un broker externo. El coste y la disponibilidad dependen del modelo, del proveedor, de los permisos y del saldo; no se presupone gratuidad.

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
- `~>` **Rechazado:** `httpx2==2.16.2`, que propuso el resolutor, porque llevaba 7 días publicado (se fijó 2.16.0); aplicar el filtro de pesos al modo `empirical`, para no alterar la salida upstream; una llamada HF autenticada ese día, por no validar el proveedor sin necesidad (el 24/11 se probó desde Render y falló por falta de crédito; ver «IA dentro del producto»).
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
- `>>` **Verificación:** receta del README en una copia temporal con métricas idénticas a las publicadas; media diaria de las predicciones constante en las 428 fechas de la demo; `pytest` del II → 128 passed, 85,40 % de cobertura.
- `>>` **Commits:** `e6b4129`, `eefc6ed`, `4bc67aa`, `d92fe7e` y `cf03bc3` (código); `18eae40`, `0d33781`, `1a0b306`, `d4f7e6c`, `6aaebe2`, `24bcaee` y `521a7f8` (documentación).

## 2026-11-24 — Proveedor alternativo NVIDIA

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** ofrecer un modelo real para la explicación cuando la cuenta de Hugging Face del autor tiene 0 $ de saldo y las llamadas autenticadas desde Render fallan (`BadRequestError` con `auto` y Qwen2.5-7B; `HfHubHTTPError` con `deepinfra` y Qwen2.5-72B), sin tocar el proveedor `hf` que exige el enunciado.
- `~>` **Prompts (resumen):** añadir el mejor modelo de build.nvidia.com → contrato N1–N9 (proveedor `nvidia`, transporte, límites, errores, configuración, payload, tests, docs y verificación) → tests en rojo → implementación → documentación.
- `=>` **Aceptado:** proveedor `nvidia` con `DEFAULT_NVIDIA_MODEL = nvidia/nemotron-3.5-super-vl-120b-a12b` y `NVIDIA_BASE_URL`; transporte con el `InferenceClient` ya fijado (comprobado en el código instalado de `huggingface_hub` 1.33.0: `base_url` usa el helper `hf-inference`, que añade `/chat/completions`, manda `Authorization: Bearer` y fusiona `extra_body`), así que no entra ninguna dependencia nueva; `reasoning_effort="low"`, 1024 tokens y 60 s por defecto, límite de 4096 tokens solo para `nvidia`; `NVIDIA_MODEL`, `NVIDIA_TIMEOUT` y `NVIDIA_MAX_TOKENS` en `AIClient.from_env`; misma clasificación de errores y reintentos que HF; error claro sin reintento si solo llega razonamiento; `--provider nvidia` en la CLI, con `--model` aplicado a `NVIDIA_MODEL`.
- `~>` **Rechazado:** usar `httpx` directamente, porque duplicaba el manejo de errores HTTP que ya da el SDK; reutilizar `HF_TIMEOUT` y `HF_MAX_TOKENS`, porque sus valores y límites por defecto no sirven a un modelo de razonamiento; sustituir `hf` por `nvidia` como proveedor por defecto o en el CI, que siguen en `mock`.
- `>>` **Verificación:** 34 tests nuevos en el II, 32 de ellos ejecutados en rojo antes de implementar; `pytest` del II → 162 passed, 85,97 % de cobertura (antes 128 y 85,40 %), `ai_client.py` al 100 %; `marimo check` sin avisos; pruebas del III → 134 passed, 97,20 %. Ninguna prueba sale a la red; en este commit no se hizo ninguna llamada autenticada a NVIDIA (las reales llegan con la entrada siguiente).
- `>>` **Commits:** `a86b9de`.

## 2026-11-24 — Elección del modelo de NVIDIA con la tarea real

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** elegir el mejor modelo del catálogo para *esta* tarea (explicar en español un resumen agregado, solo con sus cifras, sin sugerir órdenes y en un tiempo razonable para un botón web), no el más grande.
- `~>` **Prompts (resumen):** «el mejor modelo posible para nuestro proceso/tarea» → medir candidatos en el despliegue de Render cambiando solo `NVIDIA_MODEL` → comparar fidelidad, prudencia y latencia.
- `=>` **Aceptado:** `DEFAULT_NVIDIA_MODEL = nvidia/nemotron-3.5-super-vl-120b-a12b` (13–22 s, cifras exactas, separa error predictivo y rentabilidad, sin órdenes); `max_tokens` por defecto de 4096, porque con 1024 agotaba el presupuesto razonando; el prompt de sistema pide texto plano sin Markdown y como mucho 150 palabras. Tabla completa en el [README](README.md#alternativa-nvidia).
- `~>` **Rechazado:** `moonshotai/kimi-k3.1-pro`, el elegido al principio por tamaño, y `z-ai/glm-5.3-flash`: superan los 60 s; `mistralai/mistral-large-4-1t-a52b`: correcto pero 47–55 s y llama «rentabilidad esperada» a la media predicha; `nvidia/nemotron-3-ultra-550b-a55b`: inventa detalles no suministrados y menciona posiciones *long/short/flat*.
- `>>` **Verificación:** 3 llamadas reales por modelo (NVDA, AAPL, XOM) contra `https://dsia-swarmtrader.onrender.com/api/v1/analyze` con la clave guardada solo en Render; los fallos se diagnosticaron con los logs de Render (`ReadTimeout`, `_NoFinalAnswer`).
- `>>` **Commits:** `edb049c`.

## 2026-11-24 — Clase de fallo en `AIClientError` y símbolo enfocado

- `>` **Herramienta y modelo:** Claude Code · Claude Opus 5.5.
- `->` **Objetivo:** que quien consume el cliente distinga los fallos sin leer el mensaje (el III los traduce a 502, 503 o 504) y que la IA pueda situar el símbolo pedido respecto al resto del informe, porque el III enviaba solo ese símbolo como si fuera el universo.
- `~>` **Prompts (resumen):** auditoría del borde de IA con el tema de APIs y el uso real en Render → contrato C2 y C4 → tests en rojo → implementación → tabla de errores y párrafo de foco en el README.
- `=>` **Aceptado:** `AI_ERROR_KINDS` y `AIClientError(message, *, kind=...)` validado, con `config`, `auth`, `not_found`, `invalid_response`, `rate_limited`, `timeout` y `unavailable` en cada punto de fallo; mensaje propio para la respuesta vacía de HF; `focus_symbol`, `focus_prediction` y `focus_rank` opcionales y juntos en `AnalysisRequest`, con `_FOCUS_PROMPT` solo cuando existen y la frase del símbolo en el texto `mock`; `AnalysisRequest.to_dict()`, que `pipeline.py` usa para que el informe del lote no gane claves `focus_*` nulas.
- `~>` **Rechazado:** validar cada campo `focus_*` por separado, porque el texto `mock` necesita los tres; reescribir los mensajes de error existentes: se conservan todos salvo el de la respuesta vacía de HF.
- `>>` **Verificación:** cada test se escribió y se vio fallar antes de implementar (46 en rojo); `pytest` del II → 183 passed, 86,35 % de cobertura, `ai_client.py` al 100 %; `marimo check` sin avisos; smoke de la CLI con el sha256 `c0574a85…f4c2`, `ai_status=completed`, resumen sin `focus_*` y métricas dentro de 1e-6. Sin comprobar todavía: una llamada real a Nemotron con el prompt de foco.
- `>>` **Revisión adversarial (mismo día y herramienta):** la taxonomía mezclaba plazo vencido y conexión caída. Ahora `timeout` = `TimeoutError`, `httpx.TimeoutException` o HTTP 408/504 (el 504 tras los reintentos, como llega la cola de NVIDIA), y `ConnectionError` y el resto de `httpx.TransportError` pasan a `unavailable` sin dejar de reintentarse; el 408 sigue sin reintentarse. Nueva propiedad `AIClient.secret_env` (nombre de la variable de la clave, sin leer su valor) para que el III valide la configuración al arrancar; ninguna firma existente cambia. 13 tests nuevos o ajustados en rojo antes de implementar; `pytest` del II → 194 passed, 86,43 %, `ai_client.py` al 100 %; `marimo check` sin avisos y smoke de la CLI con las métricas dentro de 1e-6.
- `>>` **Revisión de la documentación (mismo día y herramienta):** el resultado de NVIDIA deja de generalizarse (de cinco candidatos, dos agotaron el timeout y Nemotron 3.5 Super respondió en las tres llamadas) en este registro, en el README y en la trazabilidad, y las cifras vigentes del README pasan a 194 passed y 86,43 %, comprobadas de nuevo con `pytest` tras los cambios.
- `>>` **Ronda de verificación (mismo día y herramienta):** las claves falsas de `test_ai.py` pasan a valores sin forma de clave real (`clave.falsa.nvidia.…`), para que salgan vacías las comprobaciones de secretos del curso (03_despliegue B13 y el prefijo de NVIDIA de E6 0.3); el smoke de la CLI del CI añade `inspect`, que la receta del README ya incluía; la verificación registra el reparto de 187 unitarios y 7 de integración. Se rechazó sustituir ya el marcador de commits por hashes: los commits los hace el lead. `pytest` del II → 194 passed y 86,43 %; `marimo check` sin avisos; smoke de la CLI con `inspect` y las métricas dentro de 1e-6.
- `>>` **Segunda ronda de verificación (mismo día y herramienta):** tres pruebas que faltaban, cada una en rojo con un sabotaje que la suite anterior no detectaba: las predicciones del informe son las de `estimator.predict` del artefacto recargado (con `np.linspace` en su lugar pasaban el II, el III y el smoke del CI), un artefacto de otra versión de sklearn se rechaza y una respuesta de HF con `choices=[]` es `invalid_response` sin reintentos. En el CI, el smoke de la CLI compara las 15 métricas de la tabla de referencia y la inferencia (media, spread, `top_symbol` DEMO06 y su predicción) con tolerancia 1e-6, en lugar de 3 RMSE. [`PROBLEMA.md`](PROBLEMA.md) vuelve al texto aprobado el 12/11 (incluida la llamada real sin reintentos) y recoge en [Enmiendas posteriores](PROBLEMA.md#enmiendas-posteriores) el baseline (`3aa3352`), los reintentos y la nota de los z-scores (`eefc6ed`, `1a0b306`). README, verificación y trazabilidad dejan de dar por comprobado en el CI lo que no lo estaba. Se rechazó sustituir ya el marcador de commits: lo hace el lead, y el CI falla mientras quede. `pytest` del II → 197 passed y 86,50 % (190 unitarios y 7 de integración); `marimo check` sin avisos; smoke de la CLI con las 15 métricas y la inferencia dentro de 1e-6.
- `>>` **Commits:** `<commit-arreglos-auditoria>`.

## Comandos de evidencia

`>` Desde la raíz del repositorio:

```bash
git log --format='%h %ad %s' --date=short -- proyectos/proyecto_ii
git show --stat e524ec0
cd proyectos/proyecto_ii
python -m pytest -q --cov=swarmtrade_app --cov-report=term-missing
grep -rn "HF_TOKEN" swarmtrade_app/ai_client.py
```
