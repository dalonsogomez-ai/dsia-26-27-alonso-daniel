# Procedencia, licencias y reutilización

`->` Declarar de dónde procede cada pieza que no es código propio y con qué licencia se usa. La leyenda de los marcadores está en el [README](README.md#leyenda-utilizada-en-la-wiki).

| Pieza | Origen | Licencia | Cómo se usa |
| --- | --- | --- | --- |
| `swarmtrade_app/_vendor/` | [SwarmTrader v1.4.0](https://github.com/dalonsogomez-ai/swarmtrader/tree/5642dda71a1e50d55da3ad1206ec2ae1b891ac28), commit `5642dda` | **MIT** ([copia](swarmtrade_app/_vendor/LICENSE), copyright 2026 dalonsogomez) | Factores, especialistas y solver, con hashes en [UPSTREAM.json](UPSTREAM.json) |
| `ml_pipeline/guard.py` | Helper de la skill ml-pipeline 0.4.0 (autor según su manifiesto: Jananthan Paramsothy) | **Apache-2.0** ([copia](ml_pipeline/LICENSE.guard)) | Congela el holdout y limita su evaluación a una vez |
| Modelo `Qwen/Qwen2.5-7B-Instruct` | [Hub de Hugging Face](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | Apache-2.0 según su ficha | Solo vía Inference API; no se descargan ni redistribuyen pesos |
| Demo sintética `data/demo.csv` | La genera este proyecto con `demo-data` | Datos propios, sin derechos de terceros | Receta, tests y CI; no se versiona porque se regenera |
| Histórico de Alpaca | Market Data API, descargado en el [Proyecto I](../proyecto_i/ALPACA.md) | Alpaca [no permite redistribuirlo](https://alpaca.markets/support/redistribute-alpaca-api) | Solo en local; se publican agregados sin precios |

`=>` El repositorio **no incluye un LICENSE en la raíz**: la licencia MIT cubre únicamente el código vendorizado de `_vendor/`, y Apache-2.0, únicamente `ml_pipeline/guard.py`. El resto del código no se publica con licencia abierta, y ninguna de las dos licencias autoriza a publicar datos de Alpaca.

## SwarmTrader

`>>` `git ls-remote` del repositorio indicado por el usuario confirmó el HEAD `5642dda71a1e50d55da3ad1206ec2ae1b891ac28` (v1.4.0) el 12/11/2026. La carpeta descargada se llamaba v1.3.0, pero su clon contiene ese mismo commit; no se usa el árbol antiguo de la carpeta hermana.

`~>` `_vendor/features.py` y `_vendor/conviction.py` conservan íntegros los archivos upstream. `_vendor/specialists.py` extrae mediante AST la dataclass y las cinco primeras definiciones del roster. [UPSTREAM.json](UPSTREAM.json) fija rutas y hashes SHA-256 de origen y copia.

`~>` Adaptaciones propias: estimadores sklearn por especialista, validación del panel, split purgado, selección y persistencia, cliente HF, CLI y adaptador paper. `--mean-source model` aplica el solver de v1.4 a escenarios cuya media se alinea con la predicción sklearn; `--mean-source empirical` conserva la asignación empírica original. Las diferencias están en [DECISION.md](DECISION.md), y las métricas de esta adaptación no se atribuyen al sistema original.

`~>` No se importan los torneos evolutivos, los agentes profundos, las señales externas, los filtros estadísticos G0–G4, la validación de brokers ni los controles fiscales del original: el Proyecto II no pretende replicar la auditoría completa de SwarmTrader. La elección por convicción se conserva y no se fuerza la diversificación.

## Guard del holdout

`>>` `ml_pipeline/guard.py` se copió del helper de la skill ml-pipeline 0.4.0 disponible en el entorno de desarrollo, por indicación de esa herramienta. La licencia Apache-2.0 se comprobó en su `.claude-plugin/plugin.json` y en el LICENSE del paquete el 12/11/2026. Su hash está fijado en [UPSTREAM.json](UPSTREAM.json) (`guard_sha256`). No se le atribuye la licencia MIT de SwarmTrader.
