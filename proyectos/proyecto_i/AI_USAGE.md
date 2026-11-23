# Uso de IA en el Proyecto I

**Daniel Alonso Gómez · Curso 2026–2027**

`->` Registro de cada intervención de asistentes de IA en la entrega del Proyecto I: qué se pidió, qué se aceptó, qué se rechazó y cómo se verificó. Leyenda: `->` objetivo, `~>` cambio, `>` paso técnico, `>>` evidencia, `=>` resultado. Que se documente el uso no implica que esté autorizado: eso depende de las normas de la actividad.

## 29/09/2026 y 13/10/2026 — OpenAI Codex

`>>` Texto original, publicado en la sección «Uso de IA» del README raíz en el commit `f2f61f0` (13/10/2026):

> Se ha utilizado **[OpenAI Codex](https://openai.com/codex/)** como asistente de desarrollo para revisar el enunciado, preparar los descargadores de Alpaca, implementar la Parte B, generar y ajustar tests y redactar documentación y CI. Intervenciones: 29 de septiembre y 13 de octubre de 2026; petición principal: «termina de completar los requisitos de proyecto_I». El código generado se ha contrastado con el material del profesor y comprobado mediante ejecución local y CI. Esta referencia documenta el uso de IA; la autorización de ese uso depende de las normas de la actividad.

- `->` **Qué se pidió:** revisar el enunciado, preparar los descargadores de Alpaca (29/09), implementar la Parte B y completar tests, documentación y CI (13/10).
- `~>` **Qué se aceptó:** los descargadores con paginación y manifiesto, el paquete `acciones_app` (loader, validator, metrics, cli), los tests de ambas partes, el workflow `.github/workflows/ci.yml` adaptado de la plantilla del profesor y la documentación (README, ALPACA.md, VERIFICACION.md).
- `~>` **Qué se rechazó o corrigió:** en la revisión del 13/10 se corrigieron casos límite (valores infinitos, importes no representables, errores de codificación, `.JSONL.GZ` en mayúsculas y colisiones entre entrada y salidas de las CLI; commit `3c4d062`). No se versionaron datos de Alpaca porque su licencia prohíbe redistribuirlos.
- `>>` **Cómo se verificó:** ejecución local de ambas CLI (140/10 ventas; 21.960/0 barras), suite de pytest con cobertura (98 tests, 99,25 %) y GitHub Actions en verde (runs `38426844375`, `38430807165` y `38464158185`).

## 23/11/2026 — Claude Code (modelo Claude Opus 5.5)

- `->` **Qué se pidió:** auditar el cumplimiento del enunciado del Proyecto I (requisitos, entrega, checklist y rúbrica) y aplicar las mejoras propuestas, en commits atómicos, sin reescribir el historial ni redistribuir datos de Alpaca.
- `~>` **Qué se aceptó** (un commit por cambio):
  - `>` muestra **sintética** de la Parte B (`data/sample/acciones_muestra.csv`) con su generador determinista `scripts/generar_muestra_acciones.py`, un test de integración que ejecuta la CLI de B sobre ella con recuentos exactos (296/5) y las tres métricas, y tests unitarios del determinismo;
  - `>` `acciones_app/loader.py`: `DataLoadError("No existe el fichero: ...")` en CSV y JSONL, igual que ventas, y líneas en blanco toleradas en JSONL;
  - `>` `ventas_app/validator.py`: `region`, `producto` y `cliente_id` no vacíos, unidades enteras y `fecha` `YYYY-MM-DD` real; los rechazos conservan los valores originales (`unidades = na` ya no sale vacío) y `motivo` acumula todas las reglas incumplidas. El checkpoint 140/10 se mantiene;
  - `>` `acciones_app/validator.py`: las barras rechazadas conservan los valores originales, y aviso (no rechazo) cuando el `vwap` queda fuera de `[low, high]`;
  - `>` docstrings de `CsvSalesRepository.load` y `JsonSalesRepository.load`, y exportación de `CsvSalesRepository`, `SalesRepository` y `load_from` en `ventas_app`;
  - `>` comentarios Arrange/Act/Assert explícitos en tests de la Parte B;
  - `>` `descargar_alpaca_actual.py` con argparse (`--help` no ejecuta nada) y comprobación previa de `data/raw/alpaca_activos.json`;
  - `>` este fichero y la actualización de README.md y VERIFICACION.md: cuenta `dalonsogomez-ai`, enlace fijo al enunciado, cifras vigentes fechadas, último run verde, estructura completa, prerrequisitos reales de la descarga y cronología del historial.
- `~>` **Qué se rechazó o no se adoptó:**
  - `>` **Reescribir el historial** para repartir los commits del 13/10 o del 23/11: no se hace; se explica la cronología en el README.
  - `>` **Mover los nueve scripts de extracción** a `scripts/` o a un subpaquete: obligaría a cambiar los imports de `tests/test_extraccion_alpaca.py` y las rutas documentadas en ALPACA.md sin mejorar el pipeline evaluado; se documentan en la estructura del README.
  - `>` **Convertir la regla de `vwap` en rechazo:** el vwap diario de Alpaca puede incluir operaciones fuera del horario regular y no se pudo contrastar con el CSV real (no versionado), así que queda como aviso.
  - `>` **Publicar en otro repositorio:** cualquier acción visible en GitHub queda para el autor. El CI sí se modificó, pero en un commit transversal aparte (`10f394d`: CLI A y B sin red y tests del Tema 2 en el job `proyecto-i`), registrado en [docs/AI_USAGE.md](../../docs/AI_USAGE.md).
- `>>` **Cómo se verificó:** cada test nuevo se comprobó rompiendo temporalmente el código que cubre (se puso en rojo) y restaurándolo. Desde `proyectos/proyecto_i/`, con Python 3.12.13 y `.venv-i`: `pytest -q` → **178 passed**; `pytest -q -m "not integration"` → **174 passed, 4 deselected**; `pytest -q -m integration` → **4 passed**; cobertura conjunta de `ventas_app` y `acciones_app` → **99,31 %** (gate 60 %). Ejecución real de ambas CLI: ventas **140/10**; muestra sintética de acciones **296/5**. El autor revisa los cambios antes de integrarlos en `main`.
