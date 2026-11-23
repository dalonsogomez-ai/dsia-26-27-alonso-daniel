# -> Progreso del modelo DSIA con SwarmTrader

~> Inicio: 12/11/2026. Enunciado del profesor consultado en GitHub en commit 76d9d554697b6463bb379f03a605377a8c85d54a.

1. done — 21.960 barras × 9 columnas; 10 símbolos, 2.196 fechas, 2018-01-02 a 2026-09-28. Sin nulos de origen ni claves duplicadas; sin sospechas automáticas de leakage. Sesgo de supervivencia conocido.
2. done — Cinco figuras reales; colas de retornos asimétricas, OHLC colineales y 210 etiquetas finales no observables que no se imputan.
3. done — Contrato aprobado: retorno a 21 sesiones por fecha/símbolo, evaluación temporal purgada. Definición en PROBLEMA.md.
4. todo — Validación y limpieza explícita; sin relleno de precios futuros.
5. todo — Panel común de barras diarias.
6. todo — Train/validation/test cronológicos por fechas completas y purga del horizonte.
7. todo — Factores causales de SwarmTrader, normalizados por fecha.
8. todo — Preprocesamiento sklearn ajustado solo con train.
9. todo — Baseline DummyRegressor y Ridge.
10. todo — Cinco especialistas Ridge de SwarmTrader; combinación fija.
11. todo — Configuración prefijada; sin búsqueda extensa de hiperparámetros.
12. todo — Comparación solo en validation; RMSE principal y MAE secundaria.
13. todo — Análisis de errores por símbolo y fecha.
14. todo — Evaluación única del holdout mediante guard.final_test.
15. todo — Persistencia para inferencia local; despliegue reservado al Proyecto III.
16. todo — Plan de monitorización y reentrenamiento.

=> Usuario: «Apruebo el contrato y completar todas las fases sin más pausas». Se conserva la ejecución ordenada y su evidencia; no se solicitan nuevas decisiones sobre este contrato.

- Gate A: approved 2026-11-12

~> El hook se inició con cwd del repositorio docente y no resolvía el tracker del proyecto del alumno. Se usa temporalmente un enlace al directorio real de evidencias; no se desactiva ningún control y se retira al terminar.

> Se respetará la petición vigente de no crear commits, tags ni publicaciones. Los checkpoints de la skill se guardan como archivos locales; no se aplica su sugerencia de git add/commit/tag.
- Figure 01_missingness.png: 1 of 10 columns have missing values; worst is return_21_sessions at 1.0%.
- Figure 02_target_balance.png: return_21_sessions ranges -0.579 to 1.09 with median 0.0189; a mean-predictor baseline is the number to beat.
- Figure 02_distributions.png: Histograms of 7 numeric features; 7 are strongly skewed (open, high, low, close, volume), which matters for scaling and outliers.
- Figure 02_correlations.png: Strongest correlation with return_21_sessions: low (0.09); anything above 0.95 is a leakage suspect.
- Figure 02_temporal_coverage.png: date spans 2018-01-02 to 2026-09-28 over 105 months; a chronological split must hold out the latest period.
- Figure 04_preparation.png: 21960 barras válidas; warmup=2520, sin target futuro=210, purga={'train': 210, 'validation': 210}. Los huecos se rechazan; no se elimina ningún precio por su valor futuro.
- Figure 06_temporal_split.png: Los tres bloques son cronológicos. target_end de train precede validation y el de validation precede test.

Model rationale:
- traits: regression, 19230 filas etiquetadas, temporal, universo fijo de 10 símbolos; retornos solapados.
- baseline: DummyRegressor(mean) y StandardScaler + Ridge(alpha=10).
- candidates: cinco Ridge especialistas de SwarmTrader equiponderados; alpha=10 prefijado; menor RMSE validation.
- ruled out: redes profundas y LightGBM (complejidad sin necesidad académica); random split y tuning con test (leakage).
- metric: RMSE principal; MAE, R2 y signo descriptivos.

>> Preparación comprobada: 21960 barras válidas; 2520 filas de warmup, 210 sin etiqueta futura y purga de 210 filas en cada frontera. Train 11340, validation 3630, test congelado 3840. Figuras 04_preparation y 06_temporal_split.

- Gate B: approved 2026-11-12
~> El usuario autorizó completar todas las fases sin nuevas pausas; se ha comprobado la preparación antes de entrenar.
- Figure 12_validation.png: Ganador por validation: swarm; RMSE=0.092665; Dummy=0.093728. Residuos predictivos, sin medir rentabilidad.
- Figure 13_error_slices.png: El error por símbolo muestra dónde falla más; no se reajusta el modelo usando estas diferencias.

>> Validation: Dummy RMSE 0.093728; Ridge 0.095000; Swarm 0.092665. Seleccionado Swarm, alpha=10 prefijado, sin búsqueda adicional. Residuo y error por símbolo guardados en figuras 12/13. No se interpretan como rentabilidad.
- Gate C: approved 2026-11-12
~> Autorización expresa del usuario para completar las fases sin más pausas, manteniendo el test único y la selección anterior.
- Step 14 final test: evaluate=0.0919 (touch 1, 2026-11-12)
