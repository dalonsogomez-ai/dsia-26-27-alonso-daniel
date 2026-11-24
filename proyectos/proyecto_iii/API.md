# Contrato HTTP de SwarmTrader DSIA

`->` Servicio Starlette que lee un snapshot construido y validado fuera del servidor y expone análisis bajo demanda con el cliente de IA del Proyecto II. El contrato del documento es la versión 1. Las predicciones son retornos decimales a 21 sesiones, calculadas por lotes con el modelo sklearn congelado: el enunciado del II admite el endpoint de predicción «o integrado», y aquí van integradas en `/api/v1/snapshot` y además por símbolo en `/api/v1/predictions/{symbol}`.

`>>` Este contrato es el de `v0.9.0-rc2` (`dsia_web.__version__`). Lo que añade a `e433fae`, el despliegue anterior (posterior a la RC1, ver [Cambios en main después de la RC](RELEASE.md#cambios-en-main-después-de-la-rc)): límite de uso con `429 rate_limited`, `429 analyze_busy_client` y `503 analyze_busy`, `502` y `504` según el `kind` del fallo, `500` tipado, `degraded` y los campos de IA en `/health`, `version` y `commit`, el contexto del símbolo en el análisis y `AI_MOCK_MODE`. Todo eso responde en la URL pública desde el despliegue de `1ff1817` (24/11/2026). Cómo saber cuál sirve Render: [Versión desplegada](RELEASE.md#versión-desplegada).

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | / | Dashboard. Carga el informe, el panel Operación y el análisis con peticiones a la API |
| GET | /static/… | `index.html`, `dashboard.js` y `style.css` propios; 404 si no existen |
| GET | /health | 200 con `status=ready` o `status=degraded` (IA mal configurada o última llamada al proveedor fallida), `run_id`, `as_of`, `version`, `commit` y `checks`; o 503 con `status=unavailable`, `version`, `commit` y `checks` (ver [Salud](#salud)) |
| GET | /api/v1/snapshot | 200 con procedencia, métricas, predicciones y explicación, o 503 con error tipado |
| GET | /api/v1/snapshot/schema | 200 con JSON Schema del documento |
| POST | /api/v1/analyze | 200 con explicación de IA del símbolo, `provider`, `model`, `request_id` y `latency_ms`; 400, 401, 404, 413, 415, 422, 429, 500, 502, 503 o 504 tipados (ver abajo) |
| GET | /api/v1/pipeline?limit=N | 200 con los últimos N eventos (1–50, 20 por defecto) del journal de `DSIA_JOURNAL`; 422 `invalid_limit` si N no es un entero de 1 a 50 escrito con cifras ASCII (también «²», «٣» o miles de cifras); 404 `journal_not_configured`; 503 `journal_unavailable` |
| GET | /api/v1/metrics | 200 con `uptime_s`, `requests_total`, contadores por ruta y estado, latencia media y p95 aproximada de las últimas 1024 peticiones, `run_id` cargado (`null` sin snapshot), `version`, `commit` y `rate_limit` (límites, uso, análisis en curso, rechazos y procedencia de la IP de cliente) |
| GET | /api/v1/predictions/{symbol} | 200 con predicción, posición en el ranking y resumen de entrada del símbolo; 422 `invalid_symbol` si no cumple `^[A-Z0-9.]{1,32}$`; 404 `symbol_not_found`; 503 `snapshot_unavailable` |

`>>` Cualquier otra ruta responde 404 y un método no admitido, 405. Variables de entorno: `DSIA_SNAPSHOT`, `DSIA_JOURNAL`, `DSIA_API_KEY`, `DSIA_ANALYZE_PER_MINUTE`, `DSIA_ANALYZE_PER_DAY`, `DSIA_ANALYZE_PER_IP_DAY`, `DSIA_ANALYZE_CONCURRENCY`, `DSIA_ANALYZE_CONCURRENCY_PER_IP`, `DSIA_TRUSTED_PROXY_HOPS`, `DSIA_COMMIT`, `AI_PROVIDER` (`mock`, `hf` o `nvidia`), `AI_MOCK_MODE` (solo con `mock`), `HF_TOKEN`, `HF_MODEL`, `HF_TIMEOUT`, `HF_MAX_TOKENS`, `HF_INFERENCE_PROVIDER`, `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `NVIDIA_TIMEOUT` y `NVIDIA_MAX_TOKENS` (ver [`.env.example`](.env.example)). Render inyecta `RENDER_GIT_COMMIT` y `RENDER=true`. El arranque del contenedor ([`serve.py`](dsia_web/serve.py)) lee además `DSIA_REFRESH_TIMEOUT`.

`>` Ejemplos contra la demo local (símbolos `DEMO01`…) o contra el despliegue público, que sirve los 10 símbolos reales de Alpaca:

```bash
curl -s http://127.0.0.1:8765/api/v1/predictions/DEMO01
curl -s -X POST -H 'Content-Type: application/json' -d '{"symbol": "DEMO01"}' http://127.0.0.1:8765/api/v1/analyze
curl -s 'http://127.0.0.1:8765/api/v1/pipeline?limit=4'
curl -s http://127.0.0.1:8765/api/v1/metrics
curl -s https://dsia-swarmtrader.onrender.com/health
curl -s https://dsia-swarmtrader.onrender.com/api/v1/predictions/AAPL
```

`>>` Con datos reales de Alpaca (`data_kind: alpaca`) el snapshot no lleva `input_summary` y `/api/v1/predictions/{symbol}` devuelve `"input": null`: la licencia de Alpaca no permite redistribuir cierres, retornos realizados ni volatilidades.

## Análisis bajo demanda

`>` `POST /api/v1/analyze` recibe `application/json` con `{"symbol": "AAPL"}` (máximo 2048 bytes; campos extra rechazados). Construye un `AnalysisRequest` del Proyecto II con los agregados de **todo** el snapshot cargado (`symbols` = número de símbolos, `mean_prediction` = media de los retornos predichos, `prediction_std` = desviación típica poblacional, `prediction_spread` = máximo − mínimo, `top_symbol` = mejor señal, RMSE de validación del modelo seleccionado) y el símbolo pedido en `focus_symbol`, `focus_prediction` (su retorno estimado) y `focus_rank` (su puesto, el mismo de `GET /api/v1/predictions/{symbol}`); después llama a `AIClient`. Con `focus_symbol`, el prompt de sistema pide explicar la posición de ese símbolo respecto al resto, y el texto `mock` añade «símbolo analizado X: predicción Y, puesto R de N». El proveedor sale de `AI_PROVIDER` (`mock` por defecto, `hf` o `nvidia`). Con `hf`, el modelo, el timeout y el proveedor de inferencia salen de `HF_MODEL`, `HF_TIMEOUT` y `HF_INFERENCE_PROVIDER`; con `nvidia`, de `NVIDIA_MODEL` (por defecto `nvidia/nemotron-3.5-super-vl-120b-a12b`), `NVIDIA_TIMEOUT` y `NVIDIA_MAX_TOKENS`, igual que la CLI del II. El campo `provider` de la respuesta vale `mock`, `huggingface` o `nvidia`. Al proveedor solo viajan agregados y predicciones del modelo, con los tickers de la mejor señal y del símbolo pedido: nunca precios de Alpaca, el token ni la clave.

`>` **Modos de fallo del mock** (tema 4, B2 y B9). Con `AI_PROVIDER=mock`, `AI_MOCK_MODE` hace que cada análisis falle del modo pedido, sin red: `down` → `503 ai_unavailable`, `timeout` → `504 ai_timeout`, `invalid` → `502 ai_bad_response` y `bug` → `500 internal_error` (una excepción propia que recoge el handler central). Vacío, el mock responde normal; con `hf` o `nvidia` la variable se ignora; un valor desconocido deja `ai_config: invalid` al arrancar y los análisis en `503 ai_unavailable`. El motivo solo llega al log, nunca a la respuesta.

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
| 413 | `payload_too_large` | Cuerpo de más de 2048 bytes, declarado o recibido, o `Content-Length` que no es un entero en cifras ASCII |
| 415 | `unsupported_media_type` | `Content-Type` distinto de `application/json` |
| 422 | `validation_error` | Falta `symbol`, no cumple `^[A-Z0-9.]{1,32}$` o hay campos extra; `detail.fields` lista ubicación y tipo sin repetir el valor |
| 429 | `rate_limited` / `analyze_busy_client` | Límite de uso superado: por minuto o diario por conexión, o diario del servicio (ver [Límite de uso](#límite-de-uso)); cabecera `Retry-After` en segundos. `analyze_busy_client`: esa conexión ya tiene `DSIA_ANALYZE_CONCURRENCY_PER_IP` análisis en curso (`Retry-After: 10`) |
| 500 | `internal_error` | Error no controlado del servidor (se provoca con `AI_MOCK_MODE=bug`). Mensaje `Error interno.`, `request_id`, `X-Request-ID` y cabeceras de seguridad; la traza solo va al log (ERROR `unhandled_error request_id=… route=…`) |
| 502 | `ai_bad_response` | `AIClientError` con `kind=invalid_response`: el proveedor respondió vacío o solo con razonamiento |
| 503 | `snapshot_unavailable` / `analyze_busy` / `ai_unavailable` | Sin snapshot; cupo de análisis simultáneos lleno (`analyze_busy`, `Retry-After: 10`, ver [Límite de uso](#límite-de-uso)); o `AIClientError` con `kind` `unavailable` (conexión rechazada o cortada, 5xx agotados, otro 4xx, fallo desconocido), `rate_limited` (429 del proveedor agotado), `auth`, `not_found` o `config` (sin `HF_TOKEN` o `NVIDIA_API_KEY`, configuración inválida) |
| 504 | `ai_timeout` | `AIClientError` con `kind=timeout`: venció el timeout del cliente (`NVIDIA_TIMEOUT` o `HF_TIMEOUT`) o el proveedor respondió 408 o 504 (504 tras los reintentos del II; así llega la cola de NVIDIA agotada) |

`~>` `AnalysisRequest` del II no tiene campo de pregunta libre, así que la API no acepta `question`. Ni el token ni el texto del proveedor se escriben en los logs: la línea INFO `analyze` registra `request_id`, símbolo, proveedor, modelo y `latency_ms`. Un fallo del proveedor deja una línea **ERROR** `analyze_failed request_id=… provider=… kind=… status=… code=… latency_ms=…` (taxonomía del tema 4: fallo externo `=>` ERROR), sin el mensaje del proveedor ni claves. Durante una petición, las líneas del cliente del II (`IA provider=… attempt=…` de cada intento y `IA provider=… reintento=…`) terminan en ` request_id=…`: el middleware lo guarda en un `ContextVar`, anyio lo copia al hilo de `client.analyze` y un `logging.Filter` del logger `swarmtrade_app.ai_client` lo añade. El CLI de Uvicorn (el que lanzan `serve.py` y el `Procfile`) solo da handler a sus propios loggers y deja el root sin ninguno, así que al arrancar la app reenvía el logger `swarmtrade_app` al handler de Uvicorn: las líneas salen con su formato (`INFO:     IA provider=…`, `WARNING:  IA provider=…`) y su nivel mínimo. Si el root ya tiene handlers (lote, CLI del II, pruebas), no se toca. Así `grep request_id=<id>` reconstruye un 504 de unos 3 minutos intento a intento. Ningún mensaje de error incluye la clave.

## Límite de uso

`->` Con `AI_PROVIDER=nvidia` cada análisis gasta la clave del servicio y la URL es pública, así que `POST /api/v1/analyze` admite como mucho `DSIA_ANALYZE_PER_MINUTE` análisis por minuto (ventana deslizante de 60 s) y por conexión, 5 por defecto; `DSIA_ANALYZE_PER_IP_DAY` al día por conexión, 30 por defecto; y `DSIA_ANALYZE_PER_DAY` al día en todo el servicio, 200 por defecto. Los contadores diarios vuelven a 0 a las 00:00 UTC. Además, como mucho `DSIA_ANALYZE_CONCURRENCY` análisis corren a la vez (4 por defecto), y `DSIA_ANALYZE_CONCURRENCY_PER_IP` por conexión (2 por defecto).

- `>` **IP de cliente.** Solo se toma de lo que escribe un proxy de confianza, porque lo que manda el cliente en `X-Forwarded-For` se puede inventar:
  - En Render (`RENDER=true`, que Render define en todos sus servicios), `CF-Connecting-IP`. Según la [guía de Render para PocketBase](https://render.com/articles/host-pocketbase-on-render) (08/07/2026), Cloudflare, por el que pasa todo el tráfico de los servicios web de Render ([cómo gestiona Render los DDoS](https://render.com/articles/how-render-handles-ddos-attacks)), escribe esa cabecera y sobrescribe la que envíe el cliente; la misma guía avisa de que Cloudflare añade a `X-Forwarded-For` en lugar de reemplazarla, así que el primer salto lo controla quien llama.
  - Si falta o no es una IP, el salto `DSIA_TRUSTED_PROXY_HOPS` contando desde la derecha de `X-Forwarded-For` (1 por defecto: el último, que añade el proxy). La cabecera se lee en todas sus líneas y en orden, porque varias líneas con el mismo nombre equivalen a su lista separada por comas (RFC 9110, §5.3): si el proxy añade su propia línea, cuenta la suya. Con menos saltos que proxies de confianza no se fía de ninguno.
  - Con `DSIA_TRUSTED_PROXY_HOPS=0`, para un servicio sin proxy delante (`docker run -p` o Uvicorn expuesto directamente), `X-Forwarded-For` se ignora, porque entera la escribe el cliente.
  - Si tampoco, la IP del par TCP.
  - `>>` La clave agrupa IPv6 por su `/64` (un cliente suele tener el `/64` entero) e IPv4-mapped (`::ffff:a.b.c.d`) como IPv4. La aplicación nunca registra la IP, y `serve.py` (el `CMD` de la imagen) y el `Procfile` arrancan Uvicorn con `--no-access-log`, porque su access log escribiría la IP del par TCP en cada petición; al lanzar `uvicorn` a mano conviene añadirlo.
- `>` **Qué cuenta.** Solo las peticiones que llegarían al proveedor: después de la clave (`401`), la validación (`400`, `413`, `415`, `422`), el símbolo (`404`) y los cupos de simultáneos (`429 analyze_busy_client` y `503 analyze_busy`). Las rechazadas por el límite no se suman.
- `>` **Respuesta.** `429 rate_limited` con la forma común de error, mensaje en español y `Retry-After` en segundos. Se comprueba primero el tope del servicio, después el diario por conexión (ambos esperan hasta las 00:00 UTC) y por último la ventana de 60 s (hasta que caduque su petición más antigua). Deja una línea WARNING `analyze_rate_limited request_id=… scope=per_day|per_ip_day|per_minute retry_after_s=…`, sin la IP.
- `>` **Simultáneos.** Si esa conexión ya tiene `DSIA_ANALYZE_CONCURRENCY_PER_IP` análisis en curso, responde al momento `429 analyze_busy_client` («Tu conexión ya tiene N análisis en curso (máximo N a la vez). Reintenta en 10 s.») con `Retry-After: 10` y una línea WARNING `analyze_busy_client request_id=… concurrency_per_ip=N`: así una sola IP, sin salirse de sus 5 por minuto, no ocupa todos los huecos mientras NVIDIA tarda. Si ya hay `DSIA_ANALYZE_CONCURRENCY` análisis en curso en total, responde al momento `503 analyze_busy` («Hay demasiados análisis en curso (máximo N a la vez). Reintenta en 10 s.») con `Retry-After: 10` y una línea WARNING `analyze_busy request_id=… concurrency=N`. Ninguno encola. Los análisis admitidos corren en hilos con un `anyio.CapacityLimiter` propio, así que una cola lenta de NVIDIA no ocupa los hilos de `FileResponse` y `StaticFiles` y el dashboard sigue respondiendo.
- `>` **Métricas.** `GET /api/v1/metrics` cuenta los 429 y los 503 en `requests` (ruta `/api/v1/analyze`) y añade `rate_limit`: los límites, `trusted_proxy_hops`, `used_today`, `concurrency`, `concurrency_per_ip`, `in_flight`, los rechazos por tipo (`per_minute`, `per_day`, `per_ip_day`, `busy`, `busy_per_ip`), `xff_hops_seen` (cuántos análisis llegados a los cupos, es decir, `POST /api/v1/analyze` que pasan la clave, la validación y el símbolo, traían 0, 1, 2… saltos en `X-Forwarded-For`; `8` agrupa 8 o más) y `client_ip_source` (de esos mismos análisis, cuántas claves salieron de `cf-connecting-ip`, `x-forwarded-for` o `peer`). Los GET y los análisis rechazados antes (401, 400, 413, 415, 422, 404, 503 sin snapshot) no cuentan, así que tras desplegar y sin ningún análisis ambos valen `{}`. Solo enteros, nunca IPs: tras desplegar y hacer al menos un análisis (por ejemplo, el de `smoke_test.sh`), ahí se comprueba qué cabecera usa Render y cuántos saltos trae.
- `~>` **Configuración.** Vacío equivale al valor por defecto. Un valor `0`, negativo o no entero en `DSIA_ANALYZE_PER_MINUTE`, `DSIA_ANALYZE_PER_DAY`, `DSIA_ANALYZE_PER_IP_DAY`, `DSIA_ANALYZE_CONCURRENCY` o `DSIA_ANALYZE_CONCURRENCY_PER_IP` detiene el arranque con `<variable> debe ser un entero mayor que 0 (recibido un valor no válido de N caracteres)` y una línea ERROR `config_invalid`: no hay modo «sin límite», para que una errata no deje la clave sin protección. `DSIA_TRUSTED_PROXY_HOPS` admite `0` (sin proxy) y un negativo o no entero lo detiene con `DSIA_TRUSTED_PROXY_HOPS debe ser un entero mayor o igual que 0`. El mensaje da la longitud del valor y nunca el valor, ni en parte: si alguien pega una clave en el campo equivocado del panel, no llega al log (lo mismo hace `serve.py` con `DSIA_REFRESH_TIMEOUT`). El estado vive en memoria del proceso, como las métricas.
- `~>` **Riesgo residual.** Con al menos 7 IPs reales distintas (o 7 `/64` de IPv6) se puede gastar el tope de 200 diarios del servicio: «Explicar símbolo» respondería 429 hasta las 00:00 UTC, pero el informe y el resto de la API siguen. Es el precio de un tope global que protege la clave. Al revés, quienes salen a internet por la misma IP pública (la red de un campus o una sala) comparten los 5 por minuto y los 30 diarios; la mitigación para la exposición está en los [issues conocidos](RELEASE.md#issues-conocidos).
- `>>` `smoke_test.sh` (1 análisis) y `browser_smoke.py` (2 reales; el 503 y el 429 se simulan en el navegador) hacen 3 en el mismo minuto: quedan por debajo de 5 por minuto y de 30 al día.

## Journal del lote

`>` `GET /api/v1/pipeline` lee como máximo los últimos 64 KiB del JSONL y devuelve `{"events": [...], "returned": n, "skipped_lines": k, "last_run_id": "…"}`. Las líneas corruptas o sin `stage`/`status` se cuentan en `skipped_lines` y no rompen la respuesta. De cada evento solo salen `timestamp`, `stage`, `status`, `duration_ms`, `run_id`, `error_type`, `rows`, `symbols` e `input_sha256`; cualquier otro campo, como una ruta, se descarta.

## Métricas de servicio

`>` `GET /api/v1/metrics` devuelve contadores en memoria del proceso (se reinician con él y no se comparten entre workers). Las rutas se agrupan por plantilla (`/api/v1/predictions/{symbol}`, `/static`, `unmatched` para 404 sin ruta) para acotar la cardinalidad. La petición en curso no se cuenta porque se registra al terminar.

```json
{"uptime_s": 42.5, "requests_total": 4, "run_id": "…", "version": "0.9.0-rc2", "commit": "local",
 "requests": [{"route": "/health", "status": 200, "count": 2}],
 "latency_ms": {"samples": 4, "mean": 1.8, "p95": 3.2},
 "rate_limit": {"per_minute": 5, "per_day": 200, "per_ip_day": 30, "trusted_proxy_hops": 1, "used_today": 0,
                "concurrency": 4, "concurrency_per_ip": 2, "in_flight": 0,
                "rejected": {"per_minute": 0, "per_day": 0, "per_ip_day": 0, "busy": 0, "busy_per_ip": 0},
                "xff_hops_seen": {}, "client_ip_source": {}}}
```

## Salud

`>` `checks` contiene `snapshot_loaded`, `data_kind`, `as_of`, `snapshot_age_days` (días naturales UTC desde `generated_at`), `journal_available` (el JSONL de `DSIA_JOURNAL` existe y se puede leer) y tres campos de IA que no llaman al proveedor:

- `>` `ai_provider`: el valor de `AI_PROVIDER` normalizado como en el II (`mock` si falta, está vacío o solo tiene espacios, igual que `AIClient.from_env`; `huggingface` pasa a `hf`). Si no es `mock`, `hf` ni `nvidia`, vale `invalid` y el log solo registra su longitud (`config_invalid ai_provider=<no válido, N caracteres> …`): `/health` es público, y una clave pegada por error en ese campo del panel no debe salir.
- `>` `ai_config`: `ok` o `invalid`. Se valida al arrancar con la misma fábrica que usa `analyze` (`AIClient.from_env` del II: modelo, timeouts y tokens) y comprobando que existe la variable de la clave del proveedor (`HF_TOKEN` o `NVIDIA_API_KEY`), sin leer ni registrar su valor. Si no es válida, deja una línea ERROR `config_invalid ai_provider=… <motivo>` (el motivo solo nombra variables y rangos) y el servicio arranca igual: el informe no depende de la IA.
- `>` `ai_last_call`: `never`, `ok` o `failing:<kind>`, según la última llamada real de `POST /api/v1/analyze` (los 429 y los `analyze_busy` no llaman al proveedor y no lo cambian).

`>>` `status` vale `ready`; `degraded` (también 200) si `ai_config` es `invalid` o `ai_last_call` empieza por `failing`; o `unavailable` (503) sin snapshot. Es la opción A del tema 4: un proveedor en fallo no tumba el servicio, y el health check de Render y el `HEALTHCHECK` de la imagen, que solo miran el código HTTP, no lo reinician. La siguiente llamada correcta lo devuelve a `ready`. Ninguna respuesta incluye rutas del disco. El journal es informativo: su ausencia no cambia `status`.

`>` `version` es la versión del III (`dsia_web.__version__`, `0.9.0-rc2`, la RC2 de [RELEASE.md](RELEASE.md)) y `commit`, el commit servido: los 7 primeros caracteres de `RENDER_GIT_COMMIT` en Render; si no existe, `DSIA_COMMIT`; si tampoco, `local`. Solo se publica un hash hexadecimal de 7 a 40 caracteres: cualquier otro valor de esas variables (por ejemplo, una clave pegada por error) sale como `invalid` y el log deja un WARNING con su longitud, nunca el valor, como con `AI_PROVIDER`. Ambos aparecen también en `/api/v1/metrics` y en la tarjeta «Estado» del panel Operación, que muestra además el proveedor de IA, su configuración y la última llamada.

## Errores

`>` Los errores comparten la forma `{"error": "<código>", "detail": {"code": "<código>", "message": "…"}, "request_id": "…"}`. `detail` se mantiene por compatibilidad con la RC1. También los del enrutador: una ruta o estático inexistente devuelve `404 not_found` y un método no admitido `405 method_not_allowed` (con la cabecera `Allow`). Una excepción no controlada en cualquier ruta llega al handler central del middleware: `500 internal_error` con el mismo `request_id` que `X-Request-ID`, sin la traza ni el tipo de excepción, y una línea ERROR `unhandled_error request_id=… route=…` con la traza en el log. Si la respuesta ya había empezado, la excepción se relanza al servidor.

## Cabeceras y trazabilidad

`>` Todas las respuestas, también el `500 internal_error`, incluyen `X-Request-ID` (se reutiliza el valor entrante si cumple `^[A-Za-z0-9._-]{8,128}$`; si no, se genera un uuid4 en hexadecimal), `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`. Cada petición deja una línea `request request_id=… method=… route=… status=… latency_ms=…` y suma un contador en memoria por plantilla de ruta y estado. Su nivel sigue la taxonomía del tema 4 (A1): INFO si va bien, WARNING si es un 4xx (lo arregla el cliente) y ERROR si es un 5xx, de modo que cada 5xx deja exactamente una línea ERROR con su `request_id`. Los 5xx de un fallo ya tienen la suya (`analyze_failed`, `unhandled_error`) y entonces la línea `request` queda en INFO; los 503 de disponibilidad (`snapshot_unavailable`, el `/health` en `unavailable`, `journal_unavailable` y `analyze_busy`) no tienen línea ERROR propia, así que la pone la línea `request`, y `journal_unavailable` y `analyze_busy` dejan además un WARNING con su `request_id`. Un arranque sin snapshot válido deja también una línea ERROR `snapshot_unavailable error_type=…`. El dashboard no usa scripts ni estilos inline, por lo que la CSP no necesita excepciones.

`>>` El snapshot distingue datos sintéticos, Alpaca históricos y otra fuente local. Incluye el hash de entrada, del modelo y del propio informe, fecha del último dato, nombre y versión del modelo, baseline Dummy y comparativa en validation, holdout congelado y estado de IA. El campo opcional `input_summary` resume los datos de entrada por símbolo: sesiones, último cierre, retorno realizado de las últimas 21 sesiones y volatilidad anualizada de los últimos 63 retornos diarios. Un snapshot anterior sin ese campo conserva su `run_id` y sigue siendo válido. La aplicación carga una única ruta configurada por el operador. Los fallos devuelven códigos estables y los paths locales quedan en el proceso. El servidor arranca en loopback por defecto.
