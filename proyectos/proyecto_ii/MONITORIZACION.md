# Evaluación continua y monitorización hacia el III

`->` Plan del Proyecto II para vigilar datos, modelo e IA cuando el núcleo se ejecute de forma recurrente. El Proyecto III implementa una parte; lo que sigue pendiente se indica al final. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki).

## Qué registrar en cada ejecución

`>` Hash de datos y de modelo, universo, fecha máxima, horizonte, versión de sklearn, fuente de medias, semilla, escenarios, brecha del solver y tipo de respuesta de IA. Del resumen para la IA, también la media, la dispersión (`prediction_std`), el spread (`prediction_spread`) y la mejor señal (`top_symbol`). No se registran tokens, cabeceras ni cuerpos de error del proveedor.

## Calidad de datos y deriva

`~>` Rechazar claves duplicadas, valores no finitos, OHLC incoherente y paneles con huecos. Comparar por símbolo la distribución de los 14 factores con la de train y la de predicciones con la de validation. No reajustar scalers durante la inferencia.

`~>` Como la media diaria de las predicciones es constante por construcción, no sirve como señal de deriva. Las señales útiles son la dispersión y el spread de las predicciones de cada fecha: si colapsan hacia cero, el modelo deja de distinguir símbolos; si se disparan, conviene revisar los factores de entrada. Una deriva no implica por sí sola pérdida de rentabilidad: requiere diagnóstico.

## Error del modelo y reentrenamiento

`>` Cuando maduren las etiquetas a 21 sesiones, evaluar bloques temporales sin solapamiento. Umbral propuesto para revisar o reentrenar: RMSE de dos bloques consecutivos superior a 1,25 × el RMSE de validation, con al menos seis fechas no solapadas. Es una regla propuesta, no calibrada. Comparar siempre con Dummy, medir el MAE por símbolo y no reutilizar el holdout de esta entrega para elegir variantes nuevas.

`>` Reentrenar significa una nueva versión de datos y repetir inspección → contrato → split purgado → train/validation → un periodo futuro nuevo de test. Se conserva el registro de todos los intentos y no se cambia la semilla por resultados favorables. Cambiar target, universo o criterio exige documentar un contrato nuevo.

## IA y broker paper

`>` HF: vigilar latencia, `error_type`, errores de autorización (401/403) o de disponibilidad (404) y el número de reintentos por 429, 5xx o timeout. Una explicación nunca altera predicciones ni pesos. `mock` es la vía reproducible del CI; la conectividad real se prueba aparte y se describe como tal.

`>` Broker paper (fuera del enunciado): reconciliar `accepted`, `new`, `partially_filled`, `filled`, `rejected` y `canceled` contra el journal y los `client_order_id`, y comprobar saldo y posiciones tras las ejecuciones. Ante un timeout de envío, consultar el broker antes de repetir.

## Estado

`=>` El Proyecto III cubre la parte operativa: [despliegue en Render](https://dsia-swarmtrader.onrender.com) que reentrena con datos reales de Alpaca en cada arranque, `/health`, `/api/v1/metrics` con latencia y contadores, y `/api/v1/pipeline` con el journal de etapas del lote ([README del III](../proyecto_iii/README.md#operación-y-verificación)). Siguen pendientes las alertas automáticas de deriva, la evaluación de bloques madurados y el seguimiento persistente de órdenes paper.
