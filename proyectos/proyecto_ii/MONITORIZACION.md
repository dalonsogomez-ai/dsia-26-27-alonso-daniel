# -> Continuidad de evaluación y monitorización hacia el III

> Registrar en cada ejecución: hash de datos/modelo, universo, fecha máxima, horizonte, versión sklearn, fuente de medias, semilla, escenarios, brecha del solver y tipo de respuesta IA. No registrar tokens, cabeceras ni cuerpos de error del proveedor.

~> Calidad: rechazar claves duplicadas, valores no finitos, OHLC incoherente y paneles con huecos. Comparar por símbolo la distribución de los 14 factores con train y la de predicciones con validation. No reajustar scalers durante inferencia. Una deriva no equivale automáticamente a pérdida de rentabilidad: requiere diagnóstico.

> Tras madurar las etiquetas a 21 sesiones, evaluar bloques temporales no solapados. Umbral operativo propuesto para revisar/reentrenar: RMSE de dos bloques consecutivos >1,25 × RMSE validation y soporte mínimo de seis fechas no solapadas. Es una regla propuesta, no calibrada ni desplegada. Comparar siempre Dummy y medir MAE por símbolo; no reutilizar el holdout de esta entrega para elegir nuevas variantes.

> Reentrenar significa nueva versión de datos y repetir inspección → contrato → split purgado → train/validation → nuevo periodo futuro de test. Mantener registro de todos los intentos, no cambiar semilla por resultados favorables. El usuario ya autorizó completar esta implementación; futuras decisiones que cambien target, universo o criterio requieren documentar el nuevo contrato.

> Broker paper: reconciliar accepted/new/partially_filled/filled/rejected/canceled contra el journal y client_order_id; comprobar saldo y posiciones después de fills. Ante timeout de envío, consultar el broker antes de repetir. El seguimiento persistente, recuperación de procesos interrumpidos y gestión de órdenes corporativas quedan para el III; actualmente se guardan estados parciales pero no hay un servicio desplegado.

> HF: vigilar latencia, errores de autorización/disponibilidad y presupuesto, sin permitir que una explicación altere predicciones o el plan. Mock es la vía reproducible de CI. Probar conectividad real aparte y describirla como tal.

=> No hay jobs programados, monitorización activa, endpoint público ni operaciones live. Se proporciona el plan de ampliación requerido, no una afirmación de despliegue.
