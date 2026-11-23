# -> Uso de IA y aportaciones aceptadas

> Asistente de desarrollo: OpenAI Codex (familia GPT; el modelo exacto no quedó registrado; código integrado en `e524ec0`), utilizado el 12/11/2026 para leer el enunciado, analizar SwarmTrader v1.4.0, proponer el contrato temporal aprobado por el usuario, adaptar código, escribir tests y documentación y ejecutar comprobaciones. No se simula revisión humana ni se inventa historial de octubre.

~> Aportaciones aceptadas: reutilización de factores/especialistas/optimizador con procedencia MIT; implementación sklearn reproducible; aislamiento del test; cliente de borde y mock; selección de cartera en el símplex; adaptador de ejecución paper; pruebas offline. Las métricas se toman de comandos ejecutados y archivos generados, no de texto del asistente.

> Proveedor en ejecución por defecto: `mock`, tarea `chat_completion`, modelo `mock-determinista-v1`. No requiere token, no llama a Internet y se usa siempre en tests/CI.

> Proveedor real preparado: Hugging Face Inference Providers, tarea `chat_completion`, modelo Hub [Qwen/Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), licencia de pesos Apache-2.0 según su ficha. SDK `huggingface_hub.InferenceClient`, proveedor `auto` configurable. Uso: explicar después de inferir un resumen de fecha, modelo sklearn, horizonte, número de símbolos, media predicha, RMSE validation y tipo de datos. No recibe barras, símbolos individuales, cuentas ni claves del broker; no controla órdenes ni modifica pesos.

>> [Documentación oficial HF](https://huggingface.co/docs/huggingface_hub/guides/inference) consultada el 12/11/2026. El cliente tiene timeout 30 s, máximo 256 tokens de salida por defecto y límites configurables de 120 s/512 tokens. Una llamada, sin reintentos del código de aplicación. El coste y disponibilidad dependen del modelo/proveedor, permisos y saldo; no se presupone gratuidad ni disponibilidad permanente. La suite sustituye el SDK con dobles y verifica el contrato, límites y redacción de errores.

=> No se ha ejecutado una llamada HF autenticada ni órdenes contra un broker externo durante la implementación. Se cumple la alternativa explícita del enunciado: mock + cliente tipado listo + HF_TOKEN en .env.example. La conexión real y el paper trading externo siguen sin validarse. Las pruebas del broker son dobles locales; no se presentan como evidencia de fills reales.

## >> Propuestas rechazadas o no adoptadas

> De SwarmTrader no se incorporaron los torneos evolutivos, los agentes profundos, las señales externas, los gates G0–G4, la validación de brokers ni los controles fiscales (ver [THIRD_PARTY.md](THIRD_PARTY.md)): exceden el alcance del enunciado y no se podrían verificar con datos sintéticos y tests offline. Tampoco se adoptó la búsqueda de hiperparámetros ni la selección por test: los candidatos y alpha=10 quedan prefijados. No se fabricó historial de octubre ni se simuló una llamada HF real.

## >> 23/11/2026 · Auditoría de cumplimiento y mejoras

> Herramienta: **Claude Code (modelo Claude Opus 5.5)**. Se pidió auditar el Proyecto II frente al enunciado vigente y aplicar las mejoras de esa auditoría en commits pequeños, sin tocar las firmas públicas que usa el Proyecto III.

~> Aceptado: aislar los tests de un `.env` local; test de contrato contra la firma real de `InferenceClient`; logs por etapa con loggers de módulo, `--log-level` y matplotlib en WARNING, sin registrar el token; errores de dominio para `HF_TIMEOUT`/`HF_MAX_TOKENS`, alias `huggingface` → `hf` y comprobación de `HF_TOKEN` antes de inferir; cobertura de `inspection.py` e `inspect` con `--output` obligatorio; filtro de pesos < 1e-6 con renormalización; baseline Dummy en el único toque del holdout; dependencias directas del III (starlette, uvicorn, pydantic, httpx, httpx2) en `requirements.in` con los pins anteriores intactos; sección de motivación, proveedor `featherless-ai` según el Hub, modelo alternativo `Qwen/Qwen3-8B`, sha256 de la demo y entorno `.venv-ii` compartido con el III.

> Rechazado o no adoptado: `httpx2==2.16.2`, la versión que propuso el resolutor, porque llevaba 7 días publicada; se fijó 2.16.0. No se aplicó el filtro de pesos al modo `empirical` para no alterar la salida upstream. No se ejecutó una llamada HF autenticada: el proveedor de `auto` se documenta según el Hub, sin validarlo. El historial de octubre sigue sin subsanarse: no se reescriben fechas.

=> Verificación: cada test nuevo se puso en rojo rompiendo temporalmente el código que cubre y se restauró. `pytest` del II: 73 passed y 83 % de cobertura; `marimo check` de los cuatro notebooks sin errores; receta del README en una copia temporal con la red bloqueada; tests del III y `dsia_web.build demo`/`from-run` en verde con el nuevo `requirements.txt`. Las cifras proceden de esas ejecuciones, no del texto del asistente.

## >> 23/11/2026 (tarde) · Verificación final con Claude Code (modelo Claude Opus 5.5)

- `->` Se pidió repetir la verificación del II en un clon limpio y corregir los hallazgos.
- `~>` Aceptado: `evaluate` sin `model.joblib` da un error de dominio en español en lugar del `OSError` crudo, y un segundo `evaluate` traduce el aviso del guard vendorizado, que estaba pensado para un agente (`f9c9890`); el comando de la demo de `data/README.md` usa los mismos parámetros que la receta y el sha256 del CI (`dc7d11f`).
- `=>` No adoptado: convertir el aviso del guard en `DataError` dentro de la librería; se mantiene `TestSetAlreadyUsed` porque las pruebas del holdout dependen de él y la traducción pertenece al borde de la CLI.
- `>>` Verificación: los dos tests nuevos fallaron antes del cambio; `pytest` del II → 73 passed, 83 % de cobertura; `marimo check` de los cuatro notebooks sin avisos.
