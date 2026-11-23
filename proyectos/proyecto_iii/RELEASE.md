# Release Candidate del Proyecto III

- Versión de la entrega **RC1 · 23 de noviembre de 2026**.
- Contrato del snapshot **1**. Se verifica el commit concreto en [GitHub Actions en main](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml?query=branch%3Amain).
- Preparación de la demo y recuperación en el [README](README.md#despliegue-reproducible).

## Hallazgos corregidos durante la revisión

| Hallazgo | Cambio y comprobación |
| --- | --- |
| La receta del II usaba el tamaño de demo por defecto, distinto al de sus métricas | Se fijaron 680 sesiones, 8 símbolos y semilla 42 en el comando publicado. La receta reproduce las métricas de referencia |
| Un exit code indicaba el fallo del lote sin señalar la etapa alcanzada | El journal guarda el inicio y resultado por etapa. pytest fuerza un fallo y verifica que se conserva la evidencia y no aparece un snapshot parcial |
| Había que comparar manualmente el resultado visible y el publicado | El smoke HTTP verifica salud, fecha e informe. La prueba Chromium comprueba además que el journal y la web corresponden al mismo `run_id` |

## Guion de defensa · 6 minutos

1. **0:00–1:00.** Explicar usuario, alcance del ranking y horizonte de 21 sesiones. Identificar el carácter sintético o histórico de los datos de la demo.
2. **1:00–2:00.** Abrir el [diagrama Excalidraw](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http). Señalar el artefacto congelado del II y la generación del snapshot antes de arrancar Uvicorn.
3. **2:00–4:00.** Abrir el dashboard, aplicar un filtro y enseñar en la red del navegador la petición a `/api/v1/snapshot`. Comparar la identidad del informe con el smoke y con el último evento del journal.
4. **4:00–5:00.** Comparar Dummy, Ridge y Swarm en validation. Explicar la purga temporal, por qué se abre una vez el holdout y por qué el R² de la demo puede ser negativo.
5. **5:00–6:00.** Enseñar CI y el artefacto. Explicar el 503 cuando falta un snapshot válido y el reinicio con el anterior. Abrir el [registro de IA](AI_USAGE.md) para preguntas.

Si el navegador de la exposición falla, ejecutar el smoke por terminal y usar la captura de la última ejecución verde como referencia visual. La evidencia de integración está en la prueba de navegador del mismo run de Actions.

## Alcance de esta versión

La demo de CI usa datos sintéticos y explicación mock. La integración con un histórico Alpaca se verificó en local con el run congelado y su resumen agregado, sin precios ni predicciones, está versionado en [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json) (`run_id` `b2553cbc…6169211`, holdout RMSE 0,0919). El servicio se entrega con empaquetado local reproducible. La llamada autenticada a HF y la exposición oral siguen pendientes de sus contextos de ejecución. La cronología verificable de la adaptación del II figura en [la auditoría](../../docs/TRAZABILIDAD_DSIA.md).
