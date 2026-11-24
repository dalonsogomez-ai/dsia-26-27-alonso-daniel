# Registro histórico del pipeline (12/11/2026)

`->` Registro de las fases seguidas el 12/11/2026 para construir el modelo con el histórico de Alpaca, con la ayuda de la skill ml-pipeline (ver [AI_USAGE.md](../AI_USAGE.md)). Se conserva como evidencia de aquella ejecución; las cifras de la demo sintética actual están en el [README](../README.md#métricas-de-la-demo). Enunciado del profesor consultado en el commit `76d9d554697b6463bb379f03a605377a8c85d54a`. La leyenda de los marcadores está en el [README](../README.md#leyenda-utilizada-en-la-wiki).

`>` Los puntos de aprobación A, B y C de la skill son pausas en las que el usuario revisa el contrato, la preparación y la selección del modelo antes de seguir. Los tres se aprobaron el 12/11/2026, con la indicación del usuario de completar todas las fases sin más pausas.

## Fases

| Fase | Estado | Evidencia |
| --- | --- | --- |
| 1. Perfil de los datos | Hecho | 21.960 barras × 9 columnas; 10 símbolos, 2.196 fechas, de 2018-01-02 a 2026-09-28. Sin nulos de origen, sin claves duplicadas y sin sospechas automáticas de leakage. Sesgo de supervivencia conocido |
| 2. EDA | Hecho | Cinco figuras: colas de retornos asimétricas, OHLC colineales y 210 etiquetas finales no observables, que no se imputan |
| 3. Contrato | Hecho, punto A aprobado | Retorno a 21 sesiones por fecha y símbolo con evaluación temporal purgada ([PROBLEMA.md](../PROBLEMA.md)) |
| 4. Validación y limpieza | Hecho | [`data.py`](../swarmtrade_app/data.py): sin relleno de precios futuros |
| 5. Panel común | Hecho | [`data.py`](../swarmtrade_app/data.py): fechas comunes a todos los símbolos |
| 6. Split cronológico con purga | Hecho, punto B aprobado | [`preparation.py`](../swarmtrade_app/preparation.py): train 11.340, validation 3.630 y test congelado 3.840 filas |
| 7. Factores causales | Hecho | 14 factores de SwarmTrader normalizados por fecha ([`_vendor/features.py`](../swarmtrade_app/_vendor/features.py)) |
| 8. Preprocesamiento | Hecho | `StandardScaler` ajustado solo con train dentro del `Pipeline` |
| 9. Baselines | Hecho | `DummyRegressor` y Ridge ([`models.py`](../swarmtrade_app/models.py)) |
| 10. Especialistas | Hecho | Cinco Ridge de SwarmTrader con combinación fija |
| 11. Configuración | Hecho | `alpha=10` prefijado, sin búsqueda de hiperparámetros |
| 12. Comparación en validation | Hecho, punto C aprobado | RMSE principal y MAE secundaria ([`training.py`](../swarmtrade_app/training.py)) |
| 13. Errores por símbolo y fecha | Hecho | `validation_slices.csv` y figura 13 |
| 14. Evaluación única del holdout | Hecho | `guard.final_test`: RMSE 0,0919 en el primer y único toque |
| 15. Persistencia | Hecho | `model.joblib` para inferencia local; el despliegue lo hace el Proyecto III |
| 16. Monitorización y reentrenamiento | Hecho | [MONITORIZACION.md](../MONITORIZACION.md) |

## Figuras de la ejecución

- `>>` `01_missingness.png`: 1 de 10 columnas con ausentes; la peor es `return_21_sessions`, con un 1,0 % (las etiquetas finales no observables).
- `>>` `02_target_balance.png`: `return_21_sessions` va de −0,579 a 1,09 con mediana 0,0189; el baseline de la media es la referencia que hay que batir.
- `>>` `02_distributions.png`: histogramas de 7 variables numéricas, todas muy asimétricas (`open`, `high`, `low`, `close`, `volume`…), lo que importa para el escalado y los atípicos.
- `>>` `02_correlations.png`: la correlación más alta con `return_21_sessions` es la de `low` (0,09); por encima de 0,95 se sospecharía leakage.
- `>>` `02_temporal_coverage.png`: de 2018-01-02 a 2026-09-28, 105 meses; un split cronológico debe reservar el periodo más reciente.
- `>>` `04_preparation.png`: 21.960 barras válidas; 2.520 filas de warmup, 210 sin target futuro y 210 purgadas en cada frontera. Los huecos se rechazan y no se elimina ningún precio por su valor futuro.
- `>>` `06_temporal_split.png`: los tres bloques son cronológicos; el `target_end` de train precede a validation y el de validation precede a test.
- `>>` `12_validation.png`: ganador Swarm, RMSE 0,092665 frente a 0,093728 de Dummy. Son residuos de predicción, no rentabilidad.
- `>>` `13_error_slices.png`: error por símbolo; no se reajusta el modelo con estas diferencias.

## Elección del modelo

| Aspecto | Decisión |
| --- | --- |
| Tipo de problema | Regresión con 19.230 filas etiquetadas, temporal, universo fijo de 10 símbolos y retornos solapados |
| Baselines | `DummyRegressor(mean)` y `StandardScaler` + `Ridge(alpha=10)` |
| Candidato | Cinco Ridge especialistas de SwarmTrader equiponderados, `alpha=10` prefijado |
| Descartados | Redes profundas y LightGBM (complejidad sin necesidad académica); split aleatorio y ajuste con test (leakage) |
| Métrica | RMSE principal; MAE, R² y signo descriptivos |

`=>` Validation: Dummy 0,093728, Ridge 0,095000 y Swarm 0,092665. Se seleccionó Swarm sin búsqueda adicional, y el holdout dio RMSE 0,0919 en su único toque (12/11/2026). Las mismas cifras figuran en la [evidencia agregada del histórico](../../proyecto_iii/evidencia/historico_alpaca.json).
