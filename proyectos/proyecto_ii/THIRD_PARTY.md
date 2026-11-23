# -> Procedencia y decisiones de reutilización

> SwarmTrader se toma de [dalonsogomez-ai/swarmtrader](https://github.com/dalonsogomez-ai/swarmtrader/tree/5642dda71a1e50d55da3ad1206ec2ae1b891ac28), **v1.4.0**, commit `5642dda71a1e50d55da3ad1206ec2ae1b891ac28`. `git ls-remote` del GitHub indicado por el usuario confirmó ese HEAD el 12/11/2026. La carpeta adjunta se llama v1.3.0, pero su clon `repo-swarmtrader` tiene ese mismo commit v1.4.0. No se usa el árbol antiguo de la carpeta hermana.

~> `_vendor/features.py` y `_vendor/conviction.py` conservan íntegros los archivos upstream. `_vendor/specialists.py` extrae la dataclass y las cinco primeras definiciones del roster mediante AST. Se conserva [la licencia MIT](swarmtrade_app/_vendor/LICENSE), copyright 2026 dalonsogomez. [UPSTREAM.json](UPSTREAM.json) fija rutas y hashes SHA-256 de origen y copia.

> Adaptaciones propias: estimadores sklearn por especialista, validación de panel, split purgado, selección/persistencia, cliente HF, CLI y adaptador paper. La opción `mean-source=model` aplica el solver v1.4 a escenarios cuya media se alinea con la predicción sklearn. `mean-source=empirical` conserva la asignación empírica original. Las diferencias están en DECISION.md; no se atribuyen las métricas de esta adaptación al sistema original.

> No se importan torneos evolutivos, agentes profundos, señales externas, gates G0–G4, validación de brokers ni controles fiscales del original. El Proyecto II no pretende replicar la auditoría completa de SwarmTrader. La nueva característica de elección por convicción se conserva explícitamente; no se fuerza diversificación.

> `ml_pipeline/guard.py` fue copiado del helper de la skill ml-pipeline 0.4.0 suministrada en el entorno de desarrollo, por instrucción de esa herramienta. Autor según el manifiesto del plugin: Jananthan Paramsothy. Licencia **Apache-2.0**, comprobada en `.claude-plugin/plugin.json` y en el LICENSE del paquete el 12/11/2026; copia en `ml_pipeline/LICENSE.guard`. Hash fijado en UPSTREAM.json. No se atribuye MIT de SwarmTrader a ese helper.
