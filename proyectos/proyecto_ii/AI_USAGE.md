# -> Uso de IA y aportaciones aceptadas

> Asistente de desarrollo: OpenAI Codex, utilizado el 12/11/2026 para leer el enunciado, analizar SwarmTrader v1.4.0, proponer el contrato temporal aprobado por el usuario, adaptar código, escribir tests y documentación y ejecutar comprobaciones. No se simula revisión humana ni se inventa historial de octubre.

~> Aportaciones aceptadas: reutilización de factores/especialistas/optimizador con procedencia MIT; implementación sklearn reproducible; aislamiento del test; cliente de borde y mock; selección de cartera en el símplex; adaptador de ejecución paper; pruebas offline. Las métricas se toman de comandos ejecutados y archivos generados, no de texto del asistente.

> Proveedor en ejecución por defecto: `mock`, tarea `chat_completion`, modelo `mock-determinista-v1`. No requiere token, no llama a Internet y se usa siempre en tests/CI.

> Proveedor real preparado: Hugging Face Inference Providers, tarea `chat_completion`, modelo Hub [Qwen/Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), licencia de pesos Apache-2.0 según su ficha. SDK `huggingface_hub.InferenceClient`, proveedor `auto` configurable. Uso: explicar después de inferir un resumen de fecha, modelo sklearn, horizonte, número de símbolos, media predicha, RMSE validation y tipo de datos. No recibe barras, símbolos individuales, cuentas ni claves del broker; no controla órdenes ni modifica pesos.

>> [Documentación oficial HF](https://huggingface.co/docs/huggingface_hub/guides/inference) consultada el 12/11/2026. El cliente tiene timeout 30 s, máximo 256 tokens de salida por defecto y límites configurables de 120 s/512 tokens. Una llamada, sin reintentos del código de aplicación. El coste y disponibilidad dependen del modelo/proveedor, permisos y saldo; no se presupone gratuidad ni disponibilidad permanente. La suite sustituye el SDK con dobles y verifica el contrato, límites y redacción de errores.

=> No se ha ejecutado una llamada HF autenticada ni órdenes contra un broker externo durante la implementación. Se cumple la alternativa explícita del enunciado: mock + cliente tipado listo + HF_TOKEN en .env.example. La conexión real y el paper trading externo siguen sin validarse. Las pruebas del broker son dobles locales; no se presentan como evidencia de fills reales.
