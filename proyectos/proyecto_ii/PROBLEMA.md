# Contrato predictivo aprobado el 12/11/2026

`->` Fijar antes de entrenar qué se predice, con qué información y cómo se evalúa, para que ningún resultado del test pueda cambiar el contrato después. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki).

| Elemento | Definición |
| --- | --- |
| Unidad | Símbolo y sesión de un universo fijo |
| Target | `close[t+21] / close[t] − 1`: retorno decimal a 21 sesiones, sin dividendos ni costes |
| Momento de la predicción | Después del cierre, con todas las barras de la sesión; no se supone ejecución al mismo cierre |
| Features | 14 factores causales de precio y volumen, normalizados entre los símbolos de cada fecha |
| Excluidos como features | Símbolo, target, `target_end` y cualquier respuesta de HF |
| Warmup | 252 sesiones |

`~>` Se reutilizan los 14 factores y cinco definiciones de especialistas de SwarmTrader **v1.4.0**, commit `5642dda71a1e50d55da3ad1206ec2ae1b891ac28`, verificado en GitHub el 12/11/2026, y se adapta la estimación a sklearn Ridge. Esta entrega predice el retorno absoluto, mientras que el ranking original usa rangos relativos: sus métricas no son intercambiables.

`>` **Información admisible.** Precios y volúmenes hasta `t`, con normalización *cross-section* dentro de cada fecha del mismo universo. Un panel incompleto se rechaza en lugar de rellenar precios.

`>` **Split.** 60/20/20 por fechas completas. Se purgan de train las filas cuyo `target_end` alcanza validation, y de validation las que alcanzan test. El preprocesamiento se ajusta solo con train dentro de un `Pipeline` de sklearn. Los símbolos reaparecen en periodos posteriores porque se evalúa el futuro del mismo universo, no empresas desconocidas.

`>` **Comparación prefijada.** `DummyRegressor(mean)`, `StandardScaler` + `Ridge(alpha=10)` y la media equiponderada de cinco especialistas `StandardScaler` + `Ridge(alpha=10)`, sin búsqueda adaptativa. Se selecciona el menor RMSE de validation, con preferencia por el modelo sencillo en caso de empate. MAE, R² y acierto de signo son descriptivos; no se afirma significación porque las etiquetas a 21 sesiones se solapan.

`>` **Holdout.** Las últimas fechas, congeladas por huella (*fingerprint*) y evaluadas una sola vez después de seleccionar en validation. No se reentrena con test ni se cambia el modelo por su resultado. Cada ejecución usa un directorio nuevo: repetir el mismo dataset no es evidencia independiente. Se persisten el ganador y su preprocesamiento, y se infiere desde el artefacto recargado.

`>` **IA.** `chat_completion` con `Qwen/Qwen2.5-7B-Instruct` para explicar un resumen agregado después de inferir. `mock` obligatorio en tests y CI. Modo real opcional: una llamada acotada, sin reintentos automáticos, sin datos crudos y sin alterar predicciones (modificado después; ver [Enmiendas posteriores](#enmiendas-posteriores)).

`~>` **Ampliación solicitada por el usuario.** Asignación por convicción sobre el símplex completo, sin mínimo de posiciones ni máximo por nombre: Kelly/CRRA decide concentración o combinación, y $\gamma = 0$ elige el mayor retorno esperado. Se usa el solver de v1.4 y se documenta la diferencia entre medias sklearn y mapa empírico original en [DECISION.md](DECISION.md). Los filtros de significación no vetan la elección. No se cambia el contrato del predictor ni se reabre su test.

`~>` **Adaptador Alpaca paper** (fuera del enunciado): plan separado, nocionales fraccionarios, redondeo a céntimos, `cash`/`buying_power` actualizado, rotación opcional y journal. No envía nada durante la inferencia (`paper-execute` es un comando aparte) y no acepta un endpoint live.

`=>` Objetivo académico: reproducibilidad e integración datos → sklearn → asignación → HF. SwarmTrader v1.4 sigue en investigación; su auditoría da «NO ACCIONABLE» (los primeros del ranking no superan de forma acreditada al universo). Esta adaptación no replica sus filtros G0–G4 y conserva la etiqueta de ventaja no demostrada. Los datos reales tienen sesgo de supervivencia, sin universo *point-in-time* con bajas. El paper trading externo no está validado y no hay trading real.

## Enmiendas posteriores

`~>` Lo anterior es lo aprobado el 12/11/2026, tal como entró en Git con [`e524ec0`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/e524ec0) (23/11), con otro formato y redacción pero el mismo contenido. Estas enmiendas no cambian el target, las features, el split ni el criterio de selección, y no se reabrió el holdout de ningún run para hacerlas:

| Fecha | Commit | Enmienda |
| --- | --- | --- |
| 23/11/2026 | [`3aa3352`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3aa3352) | El único toque del holdout calcula también el baseline Dummy (media del target en train) y lo guarda en `test_metrics.json`. Los runs anteriores, como el histórico del 12/11, no lo tienen y no se vuelve a tocar su test para calcularlo |
| 24/11/2026 | [`eefc6ed`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/eefc6ed) | En modo real se reintentan solo los fallos transitorios (429, 5xx, timeout o conexión), hasta dos veces con espera creciente; antes, una llamada sin reintentos. Cada llamada sigue acotada por timeout y tokens, sin datos crudos y sin alterar predicciones ni pesos |
| 24/11/2026 | [`eefc6ed`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/eefc6ed) (código) y [`1a0b306`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/1a0b306) (este documento) | Como cada factor es un z-score dentro de su fecha, la media diaria de las predicciones es constante e igual a la media del target en train: el modelo aporta el **orden relativo** entre símbolos, y por eso el resumen para la IA incluye la dispersión, el spread y la mejor señal |

`>>` `1a0b306` añadió estas enmiendas al texto aprobado sin marcarlas como tales; desde la segunda ronda de verificación de la RC2 (24/11/2026), el texto de arriba conserva lo aprobado y esta tabla recoge lo añadido después.
