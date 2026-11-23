# -> Datos para Proyecto II y continuidad hacia el III

> Contrato CSV diario largo: `date` (o `timestamp` ISO 8601), `symbol`, `close`, `volume`. OHLC opcional; precios positivos, volumen no negativo, claves únicas, valores finitos y al menos cinco símbolos. Panel de fechas comunes sin huecos. El código no consulta Alpaca ni rellena precios al cargar este CSV.

~> Demo pública reproducible: `python -m swarmtrade_app demo-data --output data/demo.csv --sessions 680 --symbols 8 --seed 42` (los mismos parámetros que la receta del [README](../README.md) y el CI; sha256 `c0574a85…f4c2`). Caminatas lognormales correlacionadas generadas con NumPy, sin señal artificial añadida para asegurar un resultado favorable. Los días laborables sintéticos no son el calendario NYSE. Estos datos son generados por el proyecto y no proceden de un proveedor financiero; se puede regenerar la demo sin descargar ni redistribuir Alpaca.

> Entrada histórica local: CSV de barras diarias de Alpaca. El Proyecto I documenta extracción, feed y ajuste. El usuario puede referenciar el CSV correspondiente desde su entorno privado. [Fuente y extracción](../../proyecto_i/ALPACA.md)

>> No se ha otorgado una licencia abierta al CSV de Alpaca. Las [condiciones de Alpaca](https://alpaca.markets/disclosures) y los derechos del feed deben revisarse para cada redistribución. Datos crudos, features derivados, modelos entrenados y resultados detallados permanecen en carpetas ignoradas. No se presupone que MIT del código autorice publicar datos.

=> Limitaciones: universo escogido de empresas supervivientes, sin bajas ni composición point-in-time; no representa todo el mercado. Precios ajustados por split no equivalen a total return con dividendos. El CSV termina antes de la fecha de implementación: sus salidas son históricas y no son órdenes vigentes. Noticias, fundamentales, opciones y otros endpoints de la extracción masiva del Proyecto I no se utilizan como features de esta entrega.
