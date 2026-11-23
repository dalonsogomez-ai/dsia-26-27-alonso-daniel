# Auditoría de los Proyectos II y III

Revisión del 23 de noviembre de 2026. La fuente oficial es `main` del profesor en `b76b9508acd7ecdf41da9890d35dfdefaa20847f`. Hay once README en ese árbol. Los directorios de II y III contienen un README cada uno. El registro de abajo incluye los índices y la plantilla que desarrollan esos enunciados. [Árbol verificado del profesor](https://github.com/dmartincc/dsia-26-27/tree/b76b9508acd7ecdf41da9890d35dfdefaa20847f)

## Proyecto II · Automatización e integración

El Proyecto II pesa el 20 % de la asignatura. El trabajo de octubre es la base del III. Se aplicó al retorno a 21 sesiones y al pipeline diario de acciones. [Enunciado y rúbrica](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_ii/README.md)

| Mínimo docente | Implementación y evidencia |
| --- | --- |
| 1. Dominio, procedencia, licencia y motivación | El [contrato](../proyectos/proyecto_ii/PROBLEMA.md) fija target y unidad. [Datos](../proyectos/proyecto_ii/data/README.md) diferencia sintético, histórico Alpaca, restricciones del feed y sesgo del universo |
| 2. Pipeline repetible y logs | [CLI y receta](../proyectos/proyecto_ii/README.md) para generar, inspeccionar, preparar, entrenar, evaluar e inferir. Los errores salen por stderr. Las etapas que generan informes usan rutas explícitas |
| 3. Entrenamiento sklearn, persistencia, métricas e inferencia | [Entrenamiento](../proyectos/proyecto_ii/swarmtrade_app/training.py) y [pipeline](../proyectos/proyecto_ii/swarmtrade_app/pipeline.py) conectan `fit`, `joblib`, métricas e inferencia. El split temporal purga etiquetas y la selección usa RMSE de validation |
| 4. Tests unitarios e integración sklearn | [Suite](../proyectos/proyecto_ii/tests) cubre validación, splits, artefacto, recarga e inferencia por CLI. [CI](../.github/workflows/ci.yml) ejecuta pytest y valida notebooks |
| 5. Cliente de IA tipado, mock y proveedor real documentado | [AIClient](../proyectos/proyecto_ii/swarmtrade_app/ai_client.py) usa mock en CI y admite `chat_completion` con Qwen en Hugging Face. La respuesta explica un resumen del modelo |
| 6. Configuración y dependencias | [`.env.example`](../proyectos/proyecto_ii/.env.example) incluye `HF_TOKEN=`. [Dependencias fijadas](../proyectos/proyecto_ii/requirements.txt) incluyen sklearn y `huggingface_hub` |
| 7. Citación de IA | [AI_USAGE](../proyectos/proyecto_ii/AI_USAGE.md) recoge proveedor, tarea, modelo, aportaciones y límites de las pruebas |
| 8. Núcleo ampliable | El [generador del III](../proyectos/proyecto_iii/dsia_web/build.py) importa preparación, entrenamiento, inferencia y cliente del II |
| Entrega y continuidad | II y III están en el mismo repositorio. El README ofrece comandos para reentrenar y reutilizar un artefacto existente. El historial verificable de esta adaptación no cubre el trabajo de octubre |

La rúbrica reparte 20 % a pipeline, 20 % a sklearn, 20 % a API/HF, 15 % a tests y calidad, 10 % a robustez y 15 % a documentación, citación y continuidad. El [registro de pruebas](../proyectos/proyecto_ii/VERIFICACION.md) y el [README de ejecución](../proyectos/proyecto_ii/README.md) permiten localizar evidencias para cada criterio. Se reprodujo la referencia de 680 sesiones y se comprobó que Ridge obtiene RMSE de validation 0,064383 y RMSE de holdout 0,070995. El holdout se abrió una vez en ese run.

## Proyecto III · Desarrollo End-to-End

El Proyecto III pesa el 40 % de la asignatura. El enunciado fija Release Candidate el **23 de noviembre** y exposición el **30 de noviembre**, con demo de 5–7 minutos y preguntas. [Enunciado y rúbrica](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_iii/README.md)

| Mínimo docente | Implementación y evidencia |
| --- | --- |
| 1. Arquitectura modular y continuidad | [Escenas Excalidraw](ARQUITECTURA_DSIA.md) y [guía del III](../proyectos/proyecto_iii/README.md). CLI batch, snapshot tipado y servicio HTTP con responsabilidades separadas |
| 2. Procesamiento del dataset del II | El histórico autorizado se reproduce con el CSV Alpaca y el artefacto congelado del II. Se verificó en local `from-run`, snapshot válido, HTTP 200 y la coherencia del `run_id`. El repositorio usa datos sintéticos para reproducción pública |
| 3. Modelo o IA integrados | [Generador](../proyectos/proyecto_iii/dsia_web/build.py) reutiliza inferencia sklearn y métricas congeladas. La explicación mock comparte interfaz con HF. El snapshot vincula fuente, modelo y predicción |
| 4. Pruebas y evidencia de CI | [pytest](../proyectos/proyecto_iii/tests/test_web.py), [smoke HTTP](../proyectos/proyecto_iii/scripts/smoke_test.sh) y [Playwright](../proyectos/proyecto_iii/tests/browser_smoke.py). [Actions en main](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml?query=branch%3Amain) conserva la evidencia por commit |
| 5. Web usable y conectada al backend | El dashboard solicita resultados por HTTP. Permite filtrar símbolos y ver ranking, baseline y cortes temporales. `/health` expresa la disponibilidad. Chromium contrasta contenido, salud, run y journal |
| 6. Despliegue o paquete verificable | [Build → configuración → arranque → smoke → rollback](../proyectos/proyecto_iii/README.md#despliegue-reproducible). Python 3.12, Uvicorn y dependencias fijadas. La opción elegida es empaquetado verificable local |
| 7. Defensa de 5–7 minutos | [Guion y contingencia](../proyectos/proyecto_iii/RELEASE.md) con diagrama, navegación, métricas, degradación y evidencia de ejecución |
| 8. Uso de IA citado | [AI_USAGE](../proyectos/proyecto_iii/AI_USAGE.md) y [registro del II](../proyectos/proyecto_ii/AI_USAGE.md) |

La rúbrica reparte 20 % a complejidad y valor, 15 % a arquitectura, 20 % a integración, 15 % a web y monitorización, 15 % a tests, robustez y despliegue y 15 % a exposición y documentación. El dashboard y el artefacto sintético sostienen una defensa repetible. El espacio de investigación conserva sus límites de cobertura de activos e incertidumbre.

## Índices y prácticas revisados

| Fuente oficial | Aplicación |
| --- | --- |
| [README general](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/README.md) y [README de proyectos](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md) | Ponderación y continuidad II → III. Las fechas de RC y defensa se toman del enunciado del III |
| [Python](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/1_programacion_avanzada_python/README.md), [Proyecto I](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/proyecto_i/README.md) y [Pruebas y despliegue](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/2_pruebas_y_despliegue/README.md) | Reglas de datos, módulos Python, tests por frontera y gate de CI. El I mantiene su implementación. La Parte B proporciona el contrato de barras |
| [Automatización e IA](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/3_automatizacion_e_ia/README.md) y [E5 APIs](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/3_automatizacion_e_ia/ejercicios/E5_apis_ia.md) | Contratos tipados, configuración por entorno, timeouts y pruebas del cliente con dobles. Los ejemplos de APIs abiertas, batch de prompts y retry pertenecen al ejercicio. El uso del II requiere una explicación por lote |
| [Desarrollo E2E](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/4_desarrollo_end_to_end/README.md) y [plantilla](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/4_desarrollo_end_to_end/plantilla_proyecto/README.md) | E8 conecta datos, borde de IA, backend y prueba. E8b inspira la correlación por snapshot, las duraciones por etapa y el 503 de readiness. E9 aporta el smoke y el rollback. El servicio publica el contrato de análisis como una lectura del resultado ya calculado |
| [Entornos de IA generativa](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/5_entornos_ia_generativa/README.md) y [E7 RC](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/5_entornos_ia_generativa/ejercicios/E7_refactor_tests_docs.md) | Uso de asistentes con revisión de diffs, pruebas y citas, tres hallazgos corregidos y documentación del RC. El soporte de Nemotron y la etiqueta de ejemplo corresponden al taller |
