# Verificación del Proyecto I

Última actualización: **23 de noviembre de 2026**. Referencia: [enunciado del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_i/README.md) (versión fijada; copia en [INSTRUCTIONS.md](INSTRUCTIONS.md)). Las secciones del 13 de octubre se conservan como registro histórico.

| Requisito | Evidencia comprobada (23/11/2026) |
|---|---|
| Parte A con loader, validator, metrics y CLI | `ventas_app/`; ejecución real: 140 válidas y 10 inválidas |
| Parte B con el mismo patrón | `acciones_app/`; ejecución real sobre la muestra sintética versionada: 296 válidas y 5 inválidas. El 13/10 se procesó también el CSV descargado de Alpaca (21.960/0), que no se versiona |
| Dataset de internet documentado | Origen, condiciones, fecha, parámetros, prerrequisitos y descargador en README y ALPACA.md |
| Muestra + URL de origen | URL de Alpaca en el README; muestra **sintética** `data/sample/acciones_muestra.csv` (301 filas, sin datos de Alpaca) y su generador determinista `scripts/generar_muestra_acciones.py` |
| Parte B ejecutable sin red | `python -m acciones_app.cli --input data/sample/acciones_muestra.csv --output ...` con código 0, sin cuenta ni binario `alpaca` |
| Validación adaptada al dominio B | Fechas UTC, precios finitos positivos, OHLC, contadores, duplicados y aviso de `vwap` fuera de `[low, high]` |
| Tres métricas B | Rentabilidad del precio, volumen medio diario y volatilidad anualizada |
| Tests de los cuatro módulos en ambas partes | `tests/ventas/` y `tests/acciones/` |
| ≥8 tests en total | **177 tests en verde** |
| Cobertura ≥60 % | **99,31 % conjunta**; los módulos con menor cobertura (`cli.py` de A y B) alcanzan el 97 % |
| AAA, assert, raises, parametrize, fixture | Aplicados en la suite; AAA marcado en tests de A y de B; fixtures en memoria y `tmp_path` |
| ≥1 integración | **4 tests de integración**, sin red: checkpoint 140/10, muestra sintética de B (296/5 y las tres métricas) y ambas CLI con `python -m` |
| CI para ambas partes | `.github/workflows/ci.yml`, Python 3.12, push a main y pull_request, gate 60 % |
| GitHub Actions en verde | Último verde de `main`: run [45227267528](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45227267528) (commit `ab75ded`, anterior a las mejoras del 23/11) |
| Documentación de ejecución y tests | `proyectos/proyecto_i/README.md` |
| Uso de IA documentado | [AI_USAGE.md](AI_USAGE.md) |
| Datos grandes y secretos excluidos de Git | Descargas y resultados ignorados; los scripts usan el perfil local de Alpaca |
| Historial Git | Commits separados por parte y, desde el 23/11, uno por mejora; la cronología se explica en el README sin reescribir el historial |

## Verificación del 23 de noviembre de 2026

`>` Comandos en Python 3.12.13 con el entorno `.venv-i`, desde `proyectos/proyecto_i/`:

```bash
pytest -q
pytest -q -m "not integration"
pytest -q -m integration
pytest --cov=ventas_app --cov=acciones_app --cov-report=term-missing --cov-fail-under=60
python -m ventas_app.cli --input data/ventas.csv --output data/processed/ventas.csv
python -m acciones_app.cli --input data/sample/acciones_muestra.csv --output data/processed/acciones.csv
```

`=>` Resultados: **177 passed**; **173 passed, 4 deselected**; **4 passed, 173 deselected**; cobertura total **99,31 %** («Required test coverage of 60% reached»). Ventas: **140 válidas / 10 inválidas**, y la fila con `unidades = na` conserva ese valor en `ventas_invalidas.csv`. Muestra sintética de acciones: **296 válidas / 5 inválidas**, un aviso de `vwap` fuera de rango y las tres métricas para `FICT.A`–`FICT.D`. Desde la raíz del repositorio, `python -m pytest -q` ejecuta la misma suite.

`>>` Cada test nuevo se comprobó rompiendo temporalmente el código que cubre (se puso en rojo) y restaurándolo. Detalle de los cambios en [AI_USAGE.md](AI_USAGE.md).

`~>` Las cifras vigentes son locales: el último run verde de GitHub Actions ([45227267528](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45227267528)) corresponde a `main` en `ab75ded`, antes de estas mejoras. Quedan por confirmar en CI cuando se integren en `main`.

## Verificación del 13 de octubre de 2026 (histórica)

| Requisito | Evidencia de aquel día |
|---|---|
| ≥8 tests en total | 98 tests en verde |
| Cobertura ≥60 % | 99,25 % conjunta; el módulo con menor cobertura alcanzaba el 97 % |
| ≥1 integración | 3 tests de integración, sin red; checkpoint 140/10 y ambas CLI |
| GitHub Actions en verde | Run [38464158185](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/38464158185): 98 tests y 99,25 % de cobertura |

`>` Comandos de verificación en Python 3.12.13, desde `proyectos/proyecto_i/`:

```bash
python -m pytest -q --cov=ventas_app --cov=acciones_app --cov-report=term-missing --cov-fail-under=60
python -m pytest -q -m "not integration"
python -m pip check
python -m ventas_app.cli --input data/ventas.csv --output data/processed/ventas.csv
python -m acciones_app.cli --input data/raw/alpaca_barras.csv --output data/processed/acciones.csv
```

`=>` Resultado de unitarios aquel día: 95 passed, 3 deselected. `pip check`: sin dependencias incompatibles. Los reports de las CLI se guardan en `data/processed/`, excluidos de Git.

## Evidencia remota

`>>` Repositorio de entrega: [dalonsogomez-ai/dsia-26-27-alonso-daniel](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel), **público**. La cuenta se llamaba `dalonsoLabs` cuando se escribieron las secciones del 13 de octubre; los enlaces se han actualizado al nombre actual.

Publicación completada en `main`. El run [38426844375](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/38426844375), correspondiente al commit `e00040894bf00a0ae6e31724ef5bbb372cad5013`, concluyó con **success** el 13 de octubre de 2026. El job ejecutó el comando de cobertura sobre ambos paquetes y confirmó 78 tests en verde y 99,20 % de cobertura, superando el gate del 60 %. Se comprobó también que las descargas y resultados de mercado no se incluyeron en el árbol remoto.

## Revisión posterior a la publicación pública (13 de octubre de 2026)

Se corrigieron y comprobaron valores infinitos e importes no representables en ventas, errores de codificación CSV/JSON, lectura de `.JSONL.GZ` y colisiones entre entrada y salidas de ambas CLI. Las pruebas verifican la conservación del archivo original, incluidos enlaces simbólicos y duros. La suite ampliada obtuvo 98 tests en verde y 99,25 % de cobertura. Los enlaces locales de la documentación se comprobaron y no se encontraron claves privadas ni tokens de GitHub o literales de credenciales Alpaca con los patrones revisados en archivos versionados. Las carpetas de datos publicadas contenían únicamente sus `.gitignore`.

La API de GitHub confirmó acceso público sin autenticación. Se descargó el archivo fuente público del commit `3c4d0621659aae8e136491620359ab540fcf125b` y se ejecutó la suite desde ese directorio limpio con el intérprete Python 3.12.13 del entorno local: 98 tests en verde y 99,25 % de cobertura. No dependió del enlace local `Datos` ni de archivos sin versionar. El mismo commit obtuvo **success** en Ubuntu / Python 3.12 en el run [38430807165](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/38430807165).

El descargador se ejecutó de nuevo contra la API el **13 de octubre de 2026**, con los diez símbolos y el intervalo documentados, usando un directorio temporal. Completó **3 páginas** y obtuvo **21.960 barras**, todas válidas. El manifiesto registró `2026-10-13T16:27:38.681713+00:00`, feed SIP y ajuste por splits. Esta comprobación adicional no sustituye la fecha de descarga del dataset original.

## Alcance de datos

La Parte B utiliza el CSV de diez símbolos descargado el 29 de septiembre, con corte histórico al 28 de septiembre de 2026. El script documentado sustituye a la publicación de datos reales, conforme a la alternativa del enunciado y a las condiciones de Alpaca. Desde el 23 de noviembre se versiona además una **muestra sintética** con el mismo esquema, para ejecutar B sin red; las fixtures y esa muestra son datos ficticios, no cotizaciones. Las descargas masivas adicionales de noticias y subastas siguen parciales y no forman parte del pipeline B evaluado.

## Reorganización del 13 de octubre de 2026

`->` Seguir la estructura orientativa del enunciado y conservar el README raíz de la primera sesión.

`~>` Los paquetes, tests, CSV de ventas, configuración de pytest y dependencias están dentro de `proyectos/proyecto_i/`. El material de clase se organiza por temas. El workflow permanece en `.github/workflows/ci.yml` en la raíz y ejecuta sus comandos desde la carpeta del proyecto.

`>>` La copia `data/ventas.csv` coincide con el CSV de la práctica. El checkpoint sigue siendo 140/10. La leyenda se aplica a los README y a los comentarios y docstrings de la entrega.

`=>` La estructura reorganizada pasó 98 tests y 99,25 % de cobertura, desde la raíz y desde esta carpeta. Las CLI mantuvieron 140/10 ventas y 21.960/0 barras. Los tres scripts de ventas de clase funcionaron con las rutas nuevas y los tests de ejemplo del Tema 2 obtuvieron 7 passed. Los enlaces locales de los cuatro README se comprobaron.

`>>` Se descargó y comprobó la copia pública del commit `c05c9d6839d0c80d3cdef51b21c1f376f3a6233a`: estructura, cuatro README, enlaces y exclusión de los datos de mercado correctos; 98 tests y 99,25 % de cobertura desde la carpeta de la entrega. El run [38464158185](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/38464158185) confirmó **success** en Ubuntu / Python 3.12 con el nuevo directorio de ejecución del workflow.
