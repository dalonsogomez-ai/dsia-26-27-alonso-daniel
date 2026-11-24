# Datos del Proyecto II y continuidad hacia el III

`->` Describir qué datos entran en el pipeline, de dónde salen, con qué licencia y qué limitaciones tienen. La leyenda de los marcadores está en el [README del II](../README.md#leyenda-utilizada-en-la-wiki).

## Contrato del CSV

| Columnas | Regla |
| --- | --- |
| `date` o `timestamp` | Fecha ISO 8601; panel de fechas comunes sin huecos |
| `symbol` | Al menos cinco símbolos |
| `close` | Número finito y positivo |
| `volume` | Número finito y no negativo |
| `open`, `high`, `low` (opcionales) | Positivos y coherentes con `close` |
| `(symbol, date)` | Clave única |

`>` Formato largo: una fila por símbolo y sesión. El código no consulta Alpaca ni rellena precios al cargar este CSV.

## Demo sintética

`>` Se genera con los mismos parámetros que la receta del [README](../README.md#reproducir-sin-claves-ni-datos-de-terceros) y el CI:

```bash
python -m swarmtrade_app demo-data --output data/demo.csv --sessions 680 --symbols 8 --seed 42
```

`>>` sha256 esperado: `c0574a8505d4329a8db523513d2f9f7bdbbb1599dd7568e4866d3b5ae1abf4c2`. Son caminatas lognormales correlacionadas generadas con NumPy, sin una señal añadida para asegurar un resultado favorable, con precios redondeados a 6 decimales para que el fichero sea idéntico entre arquitecturas. Los días laborables sintéticos no siguen el calendario de la NYSE.

`=>` **Licencia:** los datos los genera el propio proyecto y no proceden de ningún proveedor financiero, así que no tienen derechos de terceros. No se versionan porque se regeneran con el comando anterior.

## Histórico de Alpaca

`>` CSV local de barras diarias de 10 símbolos (AAPL, AMZN, GOOGL, JNJ, JPM, META, MSFT, NVDA, TSLA y XOM) del 2 de enero de 2018 al 28 de septiembre de 2026: 21.960 filas, feed SIP y ajuste por splits. La extracción, la cuenta necesaria y el formato están en el [Proyecto I](../../proyecto_i/ALPACA.md). Para usarlo, define `DSIA_BARS_CSV` con su ruta y sigue la [receta del histórico](../README.md#reproducir-el-histórico-autorizado).

`=>` **Licencia:** Alpaca [no permite redistribuir los datos obtenidos con su API](https://alpaca.markets/support/redistribute-alpaca-api). El CSV, los factores derivados, los modelos entrenados y los resultados detallados se quedan en carpetas ignoradas por Git. Solo se publica un [resumen agregado](../../proyecto_iii/evidencia/historico_alpaca.json) sin precios ni predicciones por símbolo. La licencia MIT del código vendorizado no autoriza a publicar estos datos.

## Limitaciones

`~>` Universo elegido de empresas supervivientes, sin bajas ni composición *point-in-time*: no representa el mercado completo. Los precios ajustados por splits no equivalen a rentabilidad total con dividendos. El CSV termina antes de la fecha de implementación, así que sus salidas son históricas y no órdenes vigentes. Noticias, fundamentales, opciones y otros productos de la extracción masiva del Proyecto I no se usan como features.
