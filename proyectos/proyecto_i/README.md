# Desarrollo de Soluciones de IA — Proyecto I

**Daniel Alonso Gómez · Curso 2026–2027**

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.

![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)

`->` Construir las dos partes del [enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_i/README.md) (enlace fijado a la versión vigente; copia en [INSTRUCTIONS.md](INSTRUCTIONS.md)): pipeline de ventas (A) y pipeline de barras diarias de acciones de Alpaca (B), siguiendo carga → validación → métricas → CLI, con excepciones de dominio, pytest y un workflow común de CI. Repositorio de entrega: [dalonsogomez-ai/dsia-26-27-alonso-daniel](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel) (la cuenta se llamaba antes `dalonsoLabs`).

## Instalación

`>` Desde la raíz del repositorio, con **Python 3.12**. El entorno del Proyecto I se llama `.venv-i` (el `.gitignore` raíz excluye `.venv-*/`; los Proyectos II y III usan otro entorno):

```bash
python3.12 -m venv .venv-i
source .venv-i/bin/activate
python -m pip install -r requirements.txt
cd proyectos/proyecto_i
```

`>` En Windows, activar con `.venv-i\Scripts\activate` antes de cambiar de carpeta. Todos los comandos siguientes se ejecutan desde `proyectos/proyecto_i/`, con el entorno activo. Las versiones directas están fijadas en `requirements.txt`; pandas es la dependencia de runtime. `pytest` y `pytest-cov` verifican la entrega, e `ipykernel` conserva el soporte de los notebooks de clase. No es necesario tener Alpaca para ejecutar los tests.

## Estructura

```text
proyectos/proyecto_i/
  README.md
  INSTRUCTIONS.md             # >> Copia del enunciado
  ALPACA.md                   # >> Procedencia y extracción reproducible
  VERIFICACION.md             # >> Evidencia de la entrega
  AI_USAGE.md                 # >> Registro del uso de IA
  requirements.txt
  pytest.ini
  ventas_app/                 # -> Parte A: loader, validator, metrics, cli
  acciones_app/               # -> Parte B: loader, validator, metrics, cli
  scripts/
    generar_muestra_acciones.py  # > Genera la muestra sintética de B (sin red)
  tests/
    conftest.py               # >> Fixtures sintéticas en memoria
    ventas/                   # >> Tests de los cuatro módulos de A
    acciones/                 # >> Tests de los cuatro módulos de B y del generador
    test_extraccion_alpaca.py # >> Tests sin red de los scripts de extracción
  data/
    ventas.csv                # >> CSV del curso, versionado
    sample/
      acciones_muestra.csv    # >> Muestra SINTÉTICA de B, versionada (sin datos de Alpaca)
    raw/                      # >> Descargas locales, excluidas de Git
    processed/                # >> Resultados locales, excluidos de Git
  descargar_alpaca.py         # > Descarga paginada del dataset B (diez símbolos)
  alpaca_io.py                # > E/S común: CLI de solo lectura, paginación y checkpoints
  descargar_alpaca_completo.py  # > Extracción ampliada con checkpoints
  descargar_alpaca_masivo.py
  descargar_alpaca_eventos.py
  descargar_alpaca_actual.py  # > Capturas actuales (requiere data/raw/alpaca_activos.json)
  continuar_alpaca.py
  estado_alpaca.py
  auditar_alpaca.py           # > Comprueba manifiestos e integridad de las descargas
```

`~>` Los scripts de extracción de Alpaca son herramientas auxiliares: no forman parte del pipeline evaluado ni de la cobertura medida (`--cov=ventas_app --cov=acciones_app`), pero tienen sus propios tests sin red en `tests/test_extraccion_alpaca.py`.

`~>` Los paquetes, tests, datos y dependencias están agrupados en esta carpeta como muestra el enunciado. El material de prácticas se organiza en `1_programacion_avanzada_python/` y `2_pruebas_y_despliegue/`, en la raíz del repositorio. El workflow único está en la raíz, en `.github/workflows/ci.yml`, y ejecuta ambos paquetes desde esta carpeta. pytest descubre solo los tests de la entrega.

## Parte A — Ventas

`>` Ejecutar el pipeline con la copia del CSV del curso incluida en el proyecto:

```bash
python -m ventas_app.cli \
  --input data/ventas.csv \
  --output data/processed/ventas.csv
```

`~>` El loader admite CSV y una lista de objetos JSON. El validador requiere las columnas `region`, `producto`, `unidades`, `precio_unitario` y `cliente_id`, convierte los valores numéricos y rechaza unidades o precios nulos, no numéricos, no finitos o no positivos, y unidades no enteras. `region`, `producto` y `cliente_id` no pueden ser nulos ni quedar vacíos tras quitar espacios. Si existe la columna `fecha`, debe tener el formato `YYYY-MM-DD` y ser una fecha real del calendario. Calcula `importe = unidades × precio_unitario` y comprueba que el resultado sea finito y positivo.

`~>` Las filas rechazadas conservan los **valores originales** de cada columna (por ejemplo, `unidades = na`) y añaden en `motivo` todas las reglas incumplidas, separadas por `; `.

`=>` El CSV del curso produce **140 válidas y 10 inválidas**, comprobadas en un test de integración.

`~>` La CLI escribe `ventas.csv` y `ventas_invalidas.csv`, este último con el motivo de rechazo. Muestra las métricas de importe por región, top 3 productos por importe y clientes con más de una compra válida. Las rutas inexistentes, los formatos no soportados, los esquemas incorrectos y los errores de lectura o escritura terminan con código 1. Ambas CLI rechazan rutas de salida que sobrescribirían el archivo de entrada, también mediante enlaces simbólicos o duros.

`>>` Diseño OOP: [ventas_app/DESIGN.md](ventas_app/DESIGN.md). Los repositorios CSV y JSON implementan el contrato `SalesRepository`; las métricas reciben únicamente ventas validadas.

## Parte B — Acciones

`->` Adaptar la solución a datos de internet, con reglas OHLCV y tres métricas propias del dominio.

`>>` La elección son **barras diarias de diez símbolos**, con observaciones comparables y reglas OHLCV específicas del dominio. El dataset descargado el **29 de septiembre de 2026** contiene **21.960 filas**, del 2 de enero de 2018 al 28 de septiembre de 2026, con feed SIP y ajuste por splits. La API es públicamente documentada y requiere una cuenta y autenticación; sus datos no se presentan como open data.

`>>` Origen: [Alpaca Market Data API](https://docs.alpaca.markets/us/docs/about-market-data-api), endpoint `https://data.alpaca.markets/v2/stocks/bars`. Alpaca [prohíbe redistribuir los datos obtenidos mediante su API](https://alpaca.markets/support/redistribute-alpaca-api). Se entrega el **script documentado**, alternativa permitida por el enunciado, y se excluyen de Git las descargas y los resultados derivados. Las fixtures de los tests y la [muestra versionada](data/sample/acciones_muestra.csv) son **sintéticas**, no cotizaciones redistribuidas.

`>` Prerrequisitos reales para reproducir la descarga (no hacen falta para los tests ni para la muestra sintética):

- `>` una **cuenta gratuita de Alpaca** y sesión iniciada con `alpaca profile login`;
- `>` el binario **`alpaca`** de la [CLI oficial](https://docs.alpaca.markets/us/docs/alpacas-cli), que **no se instala con pip** ni está en `requirements.txt`; los scripts lo invocan con `subprocess`;
- `>` **acceso a red**; con el plan Basic y feed SIP, `--end` debe ser un día de mercado ya cerrado (detalle en [ALPACA.md](ALPACA.md)).

`=>` Un revisor sin cuenta ni red puede validar la Parte B igualmente con la [muestra sintética](#ejecución-sin-red-con-la-muestra-sintética) versionada.

`>` Con esos prerrequisitos, ejecutar:

```bash
python descargar_alpaca.py \
  --symbols AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,JPM,JNJ,XOM \
  --start 2018-01-01 --end 2026-09-28 \
  --feed sip --adjustment split --min-rows 10000
```

`>>` El mínimo de 10.000 es una comprobación elegida para este descargador; **no es un requisito del enunciado**. La descarga sigue `next_page_token` hasta agotar las páginas y guarda CSV, JSONL y un manifiesto con fuente, parámetros, fecha y recuentos. Las credenciales se administran mediante el perfil de la CLI, sin incluir claves en el repositorio.

`>` Con el CSV descargado:

```bash
python -m acciones_app.cli \
  --input data/raw/alpaca_barras.csv \
  --output data/processed/acciones.csv
```

`~>` También se admite un lote `.jsonl` o `.jsonl.gz` de la extracción masiva; sus campos compactos se normalizan al mismo esquema y se ignoran las líneas en blanco. Se carga el archivo elegido en memoria: para la entrega se recomienda el CSV de diez símbolos y, para la colección masiva, procesar un lote cada vez.

### Ejecución sin red con la muestra sintética

`>>` [data/sample/acciones_muestra.csv](data/sample/acciones_muestra.csv) es una muestra **SINTÉTICA**: **no contiene cotizaciones de Alpaca** ni de ningún otro proveedor, así que se puede versionar sin infringir su licencia. Tiene el mismo esquema que el CSV descargado (`symbol,timestamp,open,high,low,close,volume,trade_count,vwap`), **301 filas** de cuatro símbolos ficticios (`FICT.A` a `FICT.D`, 75 sesiones laborables desde el 2 de enero de 2026) y filas sucias a propósito: un duplicado `symbol`/`timestamp`, un OHLC incoherente, un volumen negativo, una fecha inexistente y un `vwap` fuera de rango que solo genera aviso.

`>` La genera de forma determinista, con semilla fija y sin red, [scripts/generar_muestra_acciones.py](scripts/generar_muestra_acciones.py):

```bash
python scripts/generar_muestra_acciones.py            # >> reescribe data/sample/acciones_muestra.csv
python scripts/generar_muestra_acciones.py --help     # >> --output, --seed, --sessions
```

`>` Con ella cualquier revisor puede validar la Parte B **sin cuenta de Alpaca, sin el binario `alpaca` y sin red**:

```bash
python -m acciones_app.cli \
  --input data/sample/acciones_muestra.csv \
  --output data/processed/acciones.csv
```

`=>` Resultado esperado: **296 válidas y 5 inválidas** (las dos copias del duplicado, el OHLC incoherente, el volumen negativo y la fecha inválida), un `WARNING` por el `vwap` atípico y las tres métricas para los cuatro símbolos. Un test de integración ejecuta este mismo comando y comprueba los recuentos y los valores de las métricas; otro comprueba que el CSV versionado coincide byte a byte con el que produce el generador.

### Esquema y validación

| Columnas | Regla |
|---|---|
| `symbol` | Texto normalizado a mayúsculas, formato de ticker válido |
| `timestamp` | Fecha ISO 8601 válida, convertida a UTC |
| `open`, `high`, `low`, `close`, `vwap` | Números finitos y positivos |
| `volume`, `trade_count` | Números finitos, enteros y no negativos |
| OHLC | `low ≤ open, close ≤ high` y `low ≤ high` |
| `(symbol, timestamp)` | Clave única; se rechazan todos los miembros de un duplicado |
| `vwap` en `[low, high]` | **Solo aviso** en el log (`WARNING`), no rechazo: el vwap diario de Alpaca puede incluir operaciones fuera del horario regular |

`~>` El validador conserva el DataFrame de entrada, devuelve válidas ordenadas por símbolo y fecha y añade motivos a las inválidas, que conservan los valores originales recibidos (una fecha mal escrita no se convierte en `NaT`). Los campos adicionales recibidos de la API se conservan. Un esquema incompleto genera `ValidationError`; un fallo de carga genera `DataLoadError`.

### Tres métricas

| Métrica | Cálculo e interpretación |
|---|---|
| Rentabilidad del precio por símbolo | `100 × (último cierre / primer cierre − 1)` del intervalo observado |
| Volumen medio diario por símbolo | Media aritmética de `volume` sobre las barras válidas disponibles |
| Volatilidad anualizada por símbolo | Retornos simples entre cierres consecutivos; desviación muestral (`ddof=1`) × `sqrt(252)` × 100 |

`~>` Se calculan los retornos por símbolo y en orden temporal, sin mezclar empresas ni rellenar observaciones ausentes. Con menos de dos retornos la volatilidad queda vacía. La anualización supone sesiones diarias regulares; los huecos pueden convertir un retorno en uno de varios días. La rentabilidad ajustada por splits **no incluye dividendos, comisiones ni impuestos**. Las métricas son descriptivas del intervalo, no predicciones ni recomendaciones de inversión.

`~>` La CLI escribe `acciones.csv`, `acciones_invalidas.csv`, `acciones_rentabilidad.csv`, `acciones_volumen.csv` y `acciones_volatilidad.csv`. Para cada símbolo, la rentabilidad conserva fechas inicial/final y número de observaciones; la volatilidad informa del número de retornos utilizados.

`>>` Más información de extracción y cobertura de los productos de la API: [ALPACA.md](ALPACA.md). Las noticias y subastas masivas son una colección adicional, todavía parcial; no son entradas necesarias del pipeline B de esta entrega.

## Tests y cobertura

`>` Ejecutar desde esta carpeta:

```bash
pytest -q
pytest -q -m "not integration"
pytest -q -m integration
pytest --cov=ventas_app --cov=acciones_app --cov-report=term-missing --cov-fail-under=60
```

`>>` Hay tests de `loader`, `validator`, `metrics` y `cli` en ambas partes. Se usan fixtures en memoria y `tmp_path`, Arrange/Act/Assert (marcado explícitamente en tests de A y de B), `pytest.raises` y `parametrize`. Los cuatro tests de integración comprueban el CSV del curso (140/10), la CLI de B sobre la muestra sintética versionada (296/5 y las tres métricas) y los puntos de entrada `python -m ...` con archivos temporales; no acceden a la red ni usan rutas propias de una máquina.

`>` Desde la raíz se puede ejecutar también `python -m pytest -q`: el `pytest.ini` raíz apunta a los tests de esta carpeta. Los tests de ejemplo del Tema 2 se ejecutan por separado.

`=>` **Cifras vigentes, 23/11/2026** (Python 3.12.13, `.venv-i`, desde esta carpeta): **178 tests en verde**, de los cuales **174 unitarios** (`-m "not integration"`) y **4 de integración**, con **99,31 % de cobertura conjunta** de `ventas_app` y `acciones_app` (gate 60 %). Las CLI procesan el CSV del curso (140/10) y la muestra sintética de B (296/5).

`>>` Cifras históricas del **13/10/2026**, conservadas como referencia: 98 tests en verde, 3 de integración y 99,25 % de cobertura. Incluían regresiones para valores infinitos, importes no representables, errores de codificación, extensiones gzip en mayúsculas y protección del archivo de entrada. Aquel día las CLI procesaron también el CSV descargado de Alpaca (21.960 válidas, 0 inválidas), que no se versiona.

## CI

`>>` Workflow: [.github/workflows/ci.yml](../../.github/workflows/ci.yml), adaptado de la plantilla del profesor. Se ejecuta en `push` a `main`, `pull_request` y manualmente, sobre Ubuntu con **Python 3.12**, instala `requirements.txt` y comprueba ambos paquetes con `--cov-fail-under=60`. Después ejecuta sin red las dos CLI (A sobre `data/ventas.csv`, B sobre la muestra sintética `data/sample/acciones_muestra.csv`) y los tests de ejemplo del Tema 2. Un fallo de tests, de cobertura o de cualquier CLI hace fallar el job `proyecto-i`; el mismo workflow tiene jobs aparte para el II/III y la imagen Docker del III.

`>>` Ejecuciones y evidencia: [GitHub Actions](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml).

`=>` Último run verde de `main` (commit `ab75ded`, 23/11/2026): [45227267528](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45227267528), en Ubuntu / Python 3.12. Corresponde a `main` antes de las mejoras del 23/11 descritas en [AI_USAGE.md](AI_USAGE.md); las cifras vigentes de arriba son locales hasta que esas mejoras se integren y su run salga en verde.

`>>` Run histórico de la reorganización del **13/10/2026**: [38464158185](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/38464158185), con 98 tests y 99,25 % de cobertura. Checklist de comprobaciones: [VERIFICACION.md](VERIFICACION.md).

## Uso de IA

`>>` Registro completo en [AI_USAGE.md](AI_USAGE.md): OpenAI Codex (29/09 y 13/10/2026) y Claude Code con el modelo Claude Opus 5.5 (23/11/2026), con lo que se pidió, lo que se aceptó, lo que se rechazó y cómo se verificó.

## Desarrollo por fechas

- `->` **21 septiembre:** preparar la arquitectura modular de `ventas_app` y documentar su diseño.
- `~>` **29 septiembre:** selección y extracción del dataset de Alpaca.
- `~>` **13 octubre:** reorganización de la entrega dentro de `proyectos/proyecto_i/` y aplicación de la leyenda a README y comentarios.
- `>` **13 octubre:** ejecutar ambos pipelines y verificar los tests y la cobertura.
- `>>` **13 octubre:** comprobar los archivos generados y el workflow de GitHub Actions.
- `=>` **13 octubre:** pipelines ejecutables, tests en verde y documentación en la carpeta de la entrega.
- `~>` **23 noviembre:** auditoría de cumplimiento y mejoras, cada una en su propio commit: muestra sintética de B con su generador y test de integración, validadores más estrictos que conservan los valores originales en los rechazos, mensajes de fichero inexistente en el loader de B, `descargar_alpaca_actual.py` con argparse, AI_USAGE.md y cifras actualizadas (178 tests, 99,31 %).

`>>` Cronología del historial, explicada sin reescribirlo: el 21 de septiembre se creó la carpeta inicial (`8d974d2`). El código de las Partes A y B se **integró en Git el 13 de octubre**, sin commits intermedios del trabajo anterior (la extracción de Alpaca es del 29 de septiembre), en commits separados pero muy seguidos (`f3ec78e` y `e1a1a9a`, con 20 segundos de diferencia), seguidos de la documentación, el CI y las correcciones de la revisión pública. El 23 de noviembre se añadieron los Proyectos II y III y una ampliación del I en commits también consecutivos (`41b505c`, `e524ec0`, `3d991d2`). Esas fechas son las reales de los commits y no se han modificado; desde el 23 de noviembre cada mejora va en un commit atómico.

### Perfil estadístico reproducible de la Parte B

Después de la descarga autorizada, ejecuta desde esta carpeta. El perfil describe la entrada de la que parten la validación y las tres agregaciones.

```python
import pandas as pd

bars = pd.read_csv("data/raw/alpaca_barras.csv")
print("Dimensiones", bars.shape)
print("Tipos", bars.dtypes.to_dict())
print("Nulos por columna", bars.isna().sum().to_dict())
print("Duplicados símbolo/fecha", bars.duplicated(["symbol", "timestamp"]).sum())
print(bars[["open", "high", "low", "close", "volume"]].describe().round(3))
```

Las [fixtures OHLCV de las pruebas](tests/conftest.py) se generan localmente. El [extractor ampliado](descargar_alpaca_completo.py) gestiona checkpoints; se puede consultar su estado con `python estado_alpaca.py`. El flujo de la rúbrica usa el CSV de las barras diarias.
