# Contrato HTTP de SwarmTrader DSIA

Servicio de lectura de un snapshot construido y validado fuera del servidor. El contrato del documento es la versión 1. Las predicciones son retornos decimales a 21 sesiones.

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | / | Dashboard. Carga el informe con una petición a la API |
| GET | /health | 200 con `status=ready`, `run_id`, `as_of` y `checks`, o 503 con `status=unavailable` y `checks` |
| GET | /api/v1/snapshot | 200 con procedencia, métricas, predicciones y explicación, o 503 con error tipado |
| GET | /api/v1/snapshot/schema | 200 con JSON Schema del documento |
| POST | /api/v1/analyze | 200 con explicación de IA del símbolo, `provider`, `model`, `request_id` y `latency_ms`; 400, 401, 404, 413, 415, 422 o 503 tipados (ver abajo) |
| GET | /api/v1/pipeline?limit=N | 200 con los últimos N eventos (1–50, 20 por defecto) del journal de `DSIA_JOURNAL`; 422 `invalid_limit`; 404 `journal_not_configured`; 503 `journal_unavailable` |
| GET | /api/v1/metrics | 200 con `uptime_s`, `requests_total`, contadores por ruta y estado, latencia media y p95 aproximada de las últimas 1024 peticiones y `run_id` cargado (`null` sin snapshot) |
| GET | /api/v1/predictions/{symbol} | 200 con predicción, posición en el ranking y resumen de entrada del símbolo; 422 `invalid_symbol` si no cumple `^[A-Z0-9.]{1,32}$`; 404 `symbol_not_found`; 503 `snapshot_unavailable` |

## Análisis bajo demanda

`POST /api/v1/analyze` recibe `application/json` con `{"symbol": "AAPL"}` (máximo 2048 bytes; campos extra rechazados). Construye un `AnalysisRequest` del Proyecto II con la predicción del símbolo en el snapshot cargado (`symbols=1`, `mean_prediction` = retorno estimado, RMSE de validación del modelo seleccionado) y llama a `AIClient`. El proveedor sale de `AI_PROVIDER` (`mock` por defecto) y el modelo, el timeout y el proveedor de inferencia de `HF_MODEL`, `HF_TIMEOUT` y `HF_INFERENCE_PROVIDER`, igual que la CLI del II. Al proveedor solo viajan agregados, nunca el nombre del símbolo ni el token.

```json
{"symbol": "AAPL", "predicted_return": 0.0123, "run_id": "…", "as_of": "2026-09-28",
 "summary": "[mock] Modelo ridge; …", "provider": "mock", "model": "mock-determinista-v1",
 "request_id": "…", "latency_ms": 1.234}
```

| Código | `error` | Cuándo |
| --- | --- | --- |
| 400 | `invalid_json` | Cuerpo que no es JSON o no es un objeto |
| 401 | `unauthorized` | `DSIA_API_KEY` definida y `X-API-Key` ausente o distinta (comparación en tiempo constante) |
| 404 | `symbol_not_found` | Símbolo válido que no está en el snapshot |
| 413 | `payload_too_large` | Cuerpo de más de 2048 bytes, declarado o recibido |
| 415 | `unsupported_media_type` | `Content-Type` distinto de `application/json` |
| 422 | `validation_error` | Falta `symbol`, no cumple `^[A-Z0-9.]{1,32}$` o hay campos extra; `detail.fields` lista ubicación y tipo sin repetir el valor |
| 503 | `snapshot_unavailable` / `ai_unavailable` | Sin snapshot, o `AIClientError` (proveedor caído, sin `HF_TOKEN`, configuración inválida) |

`AnalysisRequest` del II no tiene campo de pregunta libre, así que la API no acepta `question`. Ni el token ni el texto del proveedor se escriben en los logs: la línea INFO `analyze` registra `request_id`, símbolo, proveedor, modelo y `latency_ms`.

## Journal del lote

`GET /api/v1/pipeline` lee como máximo los últimos 64 KiB del JSONL y devuelve `{"events": [...], "returned": n, "skipped_lines": k, "last_run_id": "…"}`. Las líneas corruptas o sin `stage`/`status` se cuentan en `skipped_lines` y no rompen la respuesta. De cada evento solo salen `timestamp`, `stage`, `status`, `duration_ms`, `run_id`, `error_type`, `rows`, `symbols` e `input_sha256`; cualquier otro campo, como una ruta, se descarta.

## Métricas de servicio

`GET /api/v1/metrics` devuelve contadores en memoria del proceso (se reinician con él y no se comparten entre workers). Las rutas se agrupan por plantilla (`/api/v1/predictions/{symbol}`, `/static`, `unmatched` para 404 sin ruta) para acotar la cardinalidad. La petición en curso no se cuenta porque se registra al terminar.

```json
{"uptime_s": 42.5, "requests_total": 4, "run_id": "…",
 "requests": [{"route": "/health", "status": 200, "count": 2}],
 "latency_ms": {"samples": 4, "mean": 1.8, "p95": 3.2}}
```

## Salud

`checks` contiene `snapshot_loaded`, `data_kind`, `as_of`, `snapshot_age_days` (días naturales UTC desde `generated_at`) y `journal_available` (el JSONL de `DSIA_JOURNAL` existe y se puede leer). Ninguna respuesta incluye rutas del disco. El journal es informativo: su ausencia no cambia `status`.

## Errores

Los errores comparten la forma `{"error": "<código>", "detail": {"code": "<código>", "message": "…"}, "request_id": "…"}`. `detail` se mantiene por compatibilidad con la RC1.

## Cabeceras y trazabilidad

Todas las respuestas incluyen `X-Request-ID` (se reutiliza el valor entrante si cumple `^[A-Za-z0-9._-]{8,128}$`; si no, se genera un uuid4 en hexadecimal), `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`. Cada petición deja una línea INFO `request request_id=… method=… route=… status=… latency_ms=…` y suma un contador en memoria por plantilla de ruta y estado. El dashboard no usa scripts ni estilos inline, por lo que la CSP no necesita excepciones.

El snapshot distingue datos sintéticos, Alpaca históricos y otra fuente local. Incluye el hash de entrada, del modelo y del propio informe, fecha del último dato, nombre y versión del modelo, baseline Dummy y comparativa en validation, holdout congelado y estado de IA. El campo opcional `input_summary` resume los datos de entrada por símbolo: sesiones, último cierre, retorno realizado de las últimas 21 sesiones y volatilidad anualizada de los últimos 63 retornos diarios. Un snapshot anterior sin ese campo conserva su `run_id` y sigue siendo válido. La aplicación carga una única ruta configurada por el operador. Los fallos devuelven códigos estables y los paths locales quedan en el proceso. El servidor arranca en loopback por defecto.
