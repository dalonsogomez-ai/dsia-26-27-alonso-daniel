# Contrato HTTP de SwarmTrader DSIA

Servicio de lectura de un snapshot construido y validado fuera del servidor. El contrato del documento es la versión 1. Las predicciones son retornos decimales a 21 sesiones.

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | / | Dashboard. Carga el informe con una petición a la API |
| GET | /health | 200 con `status=ready`, `run_id` y `as_of`, o 503 con `status=unavailable` |
| GET | /api/v1/snapshot | 200 con procedencia, métricas, predicciones y explicación, o 503 con error tipado |
| GET | /api/v1/snapshot/schema | 200 con JSON Schema del documento |

## Cabeceras y trazabilidad

Todas las respuestas incluyen `X-Request-ID` (se reutiliza el valor entrante si cumple `^[A-Za-z0-9._-]{8,128}$`; si no, se genera un uuid4 en hexadecimal), `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` y `Referrer-Policy: no-referrer`. Cada petición deja una línea INFO `request request_id=… method=… route=… status=… latency_ms=…` y suma un contador en memoria por plantilla de ruta y estado. El dashboard no usa scripts ni estilos inline, por lo que la CSP no necesita excepciones.

El snapshot distingue datos sintéticos, Alpaca históricos y otra fuente local. Incluye el hash de entrada, del modelo y del propio informe, fecha del último dato, nombre y versión del modelo, baseline Dummy y comparativa en validation, holdout congelado y estado de IA. El campo opcional `input_summary` resume los datos de entrada por símbolo: sesiones, último cierre, retorno realizado de las últimas 21 sesiones y volatilidad anualizada de los últimos 63 retornos diarios. Un snapshot anterior sin ese campo conserva su `run_id` y sigue siendo válido. La aplicación carga una única ruta configurada por el operador. Los fallos devuelven códigos estables y los paths locales quedan en el proceso. El servidor arranca en loopback por defecto.
