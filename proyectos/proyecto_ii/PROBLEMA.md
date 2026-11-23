# -> Contrato predictivo aprobado el 12/11/2026

> Unidad: símbolo y sesión del universo fijo suministrado. Target: `close[t+21]/close[t] - 1`, retorno decimal, sin dividendos ni costes. Predicción después del cierre y de disponer de todas las barras de la sesión. No se supone ejecución al mismo cierre.

~> Se reutilizan los 14 factores causales y cinco definiciones de especialistas de SwarmTrader **v1.4.0**, commit `5642dda71a1e50d55da3ad1206ec2ae1b891ac28`, verificado en GitHub el 12/11/2026. Se adapta la estimación a sklearn Ridge. Esta entrega predice retorno absoluto; el ranking original utiliza rangos relativos. Sus métricas no son intercambiables.

> Información admisible: precios y volúmenes hasta t; 252 sesiones de warmup y normalización cross-sectional dentro de cada fecha del mismo universo. Símbolo, target, target_end y resúmenes HF no son features. Se rechaza un panel incompleto en vez de rellenar precios.

> Split: 60/20/20 por fechas completas. Se purga train si target_end alcanza validation, y validation si alcanza test. Preprocesamiento ajustado solo con train mediante sklearn Pipeline. Los símbolos reaparecen en periodos posteriores porque se evalúa el futuro del universo fijo, no empresas desconocidas.

> Comparación prefijada: DummyRegressor(mean), StandardScaler + Ridge(alpha=10), y media equiponderada de cinco especialistas StandardScaler + Ridge(alpha=10). Sin búsqueda adaptativa. Selección por menor RMSE de validation, con preferencia por el modelo simple ante empate. MAE, R² y acierto de signo descriptivos. Sin afirmaciones de significación: las etiquetas a 21 sesiones se solapan.

> Holdout: últimas fechas, congelado por fingerprint, evaluado una sola vez después de seleccionar en validation. No se reentrena con test ni se cambia el modelo según su resultado. Cada ejecución utiliza un directorio nuevo; repetir el mismo dataset no es evidencia independiente. Persistencia del ganador y su preprocesamiento; inferencia desde el artefacto recargado.

> HF: chat_completion con Qwen/Qwen2.5-7B-Instruct para explicar un resumen agregado después de inferir. Mock obligatorio en tests/CI. Modo real opcional: una llamada acotada, sin reintentos automáticos, sin datos crudos y sin alterar predicciones.

~> Ampliación solicitada expresamente por el usuario: asignación por convicción sobre el símplex completo, sin mínimo de posiciones ni máximo por nombre. Kelly/CRRA decide concentración o combinación; gamma=0 elige el mayor retorno esperado. Se utiliza el solver v1.4 y se documenta la diferencia entre medias sklearn estimadas y mapa empírico original. Los filtros de significación no vetan esta elección. No se cambia el contrato del predictor ni se reabre su test.

> Adaptador Alpaca paper con plan separado, nocionales fraccionarios, redondeo a céntimos, cash/buying_power actualizado, rotación opt-in y journal. No hay envío durante la inferencia; paper-execute es un comando separado. Esta implementación no acepta un endpoint live.

=> Objetivo académico: reproducibilidad e integración datos → sklearn → asignación → HF. SwarmTrader v1.4 está en investigación/backtesting; su auditoría G4 da NO ACCIONABLE y no acredita que el top supere al universo. Esta adaptación no replica G0–G4: conserva la etiqueta de ventaja no demostrada y la elección relativa solicitada. Los datos reales tienen sesgo de supervivencia, sin universo point-in-time con bajas. Paper trading externo no validado; trading real no activado.
