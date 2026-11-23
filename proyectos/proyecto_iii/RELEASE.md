# Release Candidate del Proyecto III

- Versión de la entrega **RC1 · 23 de noviembre de 2026**, preparada para el tag **`v0.9.0-rc1`**.
- Contrato del snapshot **1**, con el campo opcional `input_summary` compatible hacia atrás. Se verifica el commit concreto en [GitHub Actions en main](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml?query=branch%3Amain).
- Preparación de la demo y recuperación en el [README](README.md#arranque-local-de-api-y-dashboard).

## v0.9.0-rc1

El tag anotado se crea en un paso aparte, sobre el commit con CI verde, y se enlazará aquí: `https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/releases/tag/v0.9.0-rc1`.

| Ámbito | Contenido |
| --- | --- |
| API | `/health` con `checks`; `GET /api/v1/predictions/{symbol}`; `POST /api/v1/analyze` con el `AIClient` del II, 503 tipado y `X-API-Key` opcional; `GET /api/v1/pipeline`; `GET /api/v1/metrics`; `X-Request-ID`, `latency_ms` en logs y cabeceras CSP, nosniff y no-referrer |
| Lote | IA configurada por `AI_PROVIDER` y `HF_*`; etapa `validate_input` en `from-run`; `input_summary` por símbolo en el snapshot |
| Dashboard | Paneles Operación, Datos de entrada y Explicar símbolo, sin código inline |
| Empaquetado | [`Dockerfile`](Dockerfile), [`render.yaml`](../../render.yaml), [`Procfile`](../../Procfile), [`.python-version`](../../.python-version) y [`requirements-e2e.txt`](requirements-e2e.txt). Sin URL pública: el despliegue lo hace el autor con su cuenta |
| Evidencia | [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json): agregados del `from-run` con el histórico Alpaca, sin precios ni predicciones por símbolo |

Comprobación antes de etiquetar: pytest del III con cobertura, `smoke_test.sh` contra Uvicorn local y contra el contenedor, y `browser_smoke.py --expect-pipeline`.

## Rollback

1. **Datos (snapshot).** Conserva el snapshot anterior. Si el nuevo no supera `smoke_test.sh`, apunta `DSIA_SNAPSHOT` al anterior y reinicia; un snapshot inválido deja `/health` en 503 y no se sirve.
2. **Código (tag).** Vuelve al tag anterior y redepliega ese commit: `git checkout <tag-anterior>` y `docker build -f proyectos/proyecto_iii/Dockerfile -t dsia-iii:<tag-anterior> .`, o en Render «Manual Deploy» del commit del tag (`autoDeploy` está desactivado). Antes del primer tag, la referencia es el commit `ab75ded` de la RC1 en main. Tras el rollback, repetir `smoke_test.sh` contra la URL o el contenedor.

## Hallazgos corregidos durante la revisión

| Hallazgo | Cambio y comprobación |
| --- | --- |
| La receta del II usaba el tamaño de demo por defecto, distinto al de sus métricas | Se fijaron 680 sesiones, 8 símbolos y semilla 42 en el comando publicado. La receta reproduce las métricas de referencia |
| Un exit code indicaba el fallo del lote sin señalar la etapa alcanzada | El journal guarda el inicio y resultado por etapa. pytest fuerza un fallo y verifica que se conserva la evidencia y no aparece un snapshot parcial |
| Había que comparar manualmente el resultado visible y el publicado | El smoke HTTP verifica salud, fecha e informe. La prueba Chromium comprueba además que el journal y la web corresponden al mismo `run_id` |
| Auditoría del 23/11: sin análisis desde la web, sin panel de operación, sin cabeceras de seguridad ni empaquetado | Endpoints `analyze`, `predictions`, `pipeline` y `metrics`, panel Operación, middleware de seguridad y trazas, Dockerfile y blueprint. Cada uno con pruebas que se pusieron en rojo al romper el código |

## Guion de defensa · 6 minutos

1. **0:00–1:00.** Explicar usuario, alcance del ranking y horizonte de 21 sesiones. Identificar el carácter sintético de la demo y enseñar la [evidencia agregada del histórico Alpaca](evidencia/historico_alpaca.json).
2. **1:00–2:00.** Abrir el [diagrama Excalidraw](../../docs/ARQUITECTURA_DSIA.md#proyecto-iii--lote-y-servicio-http). Señalar el artefacto congelado del II y la generación del snapshot antes de arrancar Uvicorn.
3. **2:00–3:00.** Panel **Operación**: estado, `run_id`, antigüedad, contadores de `/api/v1/metrics` y eventos de `/api/v1/pipeline`. Comparar el `run_id` con `/health` y con el último evento del journal.
4. **3:00–4:30.** Aplicar un filtro, recorrer **Datos de entrada** y enseñar en la red del navegador `/api/v1/snapshot`. Pulsar **Explicar símbolo** y mostrar el `POST /api/v1/analyze` con `request_id` y latencia.
5. **4:30–5:15.** Comparar Dummy, Ridge y Swarm en validation. Explicar la purga temporal, el holdout de un toque y el R² negativo.
6. **5:15–6:00.** Enseñar CI, el artefacto y `docker run` con su `HEALTHCHECK`. Explicar el 503 cuando falta el snapshot o cae la IA y los dos rollbacks. Abrir el [registro de IA](AI_USAGE.md) para preguntas.

Si el navegador de la exposición falla, ejecutar el smoke por terminal y usar la captura de la última ejecución verde como referencia visual. La evidencia de integración está en la prueba de navegador del mismo run de Actions.

## Alcance de esta versión

La demo de CI usa datos sintéticos y explicación mock. La integración con un histórico Alpaca se verificó en local con el run congelado y su resumen agregado, sin precios ni predicciones, está versionado en [`evidencia/historico_alpaca.json`](evidencia/historico_alpaca.json) (`run_id` `b2553cbc…6169211`, holdout RMSE 0,0919). El servicio se entrega empaquetado (imagen Docker verificada en local y blueprint de Render) sin URL pública todavía. La llamada autenticada a HF y la exposición oral siguen pendientes de sus contextos de ejecución. La cronología verificable de la adaptación del II figura en [la auditoría](../../docs/TRAZABILIDAD_DSIA.md).
