# Proyectos de Desarrollo de Soluciones de IA

Esta carpeta reúne las tres entregas de DSIA. El Proyecto I desarrolla dos pipelines de calidad de datos, uno de ventas y otro de acciones. El II usa el contrato de barras de la Parte B para entrenar y evaluar un modelo de retornos. El III reutiliza el modelo y la inferencia del II para mostrar sus resultados en una aplicación web.

| Proyecto | Peso en la asignatura | Qué se entrega |
| --- | --- | --- |
| [I · Programación avanzada en Python](#proyecto-i) | 10 % | Dos CLI de validación y métricas, con pruebas por módulo |
| [II · Automatización e integración](#proyecto-ii) | 20 % | Un pipeline reproducible de scikit-learn y un cliente de IA tipado |
| [III · Desarrollo end-to-end](#proyecto-iii) | 40 % | Un pipeline batch, una API y un dashboard con pruebas de extremo a extremo |

## Proyecto I

Implementa dos flujos independientes que comparten el patrón de carga, validación, métricas y CLI.

![Diagrama del Proyecto I. Las ventas del curso y las barras de Alpaca siguen flujos independientes.](../docs/diagramas/proyecto-i.svg)

| Parte | Entrada y validación | Resultado |
| --- | --- | --- |
| **A · Ventas** | CSV del curso. Valida el esquema y comprueba que las unidades, los precios y los importes sean positivos y finitos | Exporta ventas válidas y rechazadas con su motivo. Calcula importe por región, top 3 de productos por importe y clientes con compras repetidas. El test de integración verifica **140 filas válidas y 10 inválidas** |
| **B · Acciones** | Barras diarias OHLCV de Alpaca. Valida tipos, coherencia de precios y clave única por símbolo y fecha | Calcula rentabilidad del precio, volumen medio diario y volatilidad anualizada por símbolo. Incluye un extractor documentado y fixtures sintéticas para probar el flujo |

Pytest cubre la carga, la validación, las métricas y la CLI de ambas partes. GitHub Actions ejecuta la suite conjunta y exige un mínimo del **60 %** de cobertura.

[Guía de ejecución y tests](proyecto_i/README.md) · [Origen y extracción de barras](proyecto_i/ALPACA.md) · [Diagrama editable en Excalidraw](../docs/diagramas/proyecto-i.excalidraw)

## Proyecto II

Automatiza una tarea de investigación de SwarmTrader. A partir de barras diarias, estima para cada símbolo el **retorno del precio a 21 sesiones**.

![Diagrama del Proyecto II. Las barras alimentan la preparación temporal, la selección del modelo, el holdout y la inferencia con explicación.](../docs/diagramas/proyecto-ii.svg)

1. **Preparación.** La CLI valida el CSV y construye factores con la información disponible al cierre de cada sesión. Separa train, validation y holdout por fecha y purga las etiquetas que cruzan sus fronteras.
2. **Entrenamiento y evaluación.** Compara Dummy, Ridge y Swarm por RMSE en validation. Persiste el candidato elegido en `model.joblib` y evalúa el holdout con el modelo ya congelado. La guía incluye la receta y las métricas de una demo sintética reproducible.
3. **Inferencia y explicación.** Recarga el artefacto para producir estimaciones por símbolo. Un cliente de IA tipado explica un resumen después de inferir. Los tests y CI usan `mock`; la integración opcional con Hugging Face está documentada en la guía.

[Guía de reproducción](proyecto_ii/README.md) · [Contrato de datos](proyecto_ii/data/README.md) · [Uso de IA](proyecto_ii/AI_USAGE.md) · [Diagrama editable en Excalidraw](../docs/diagramas/proyecto-ii.excalidraw)

## Proyecto III

Convierte el flujo del II en una aplicación end-to-end. El dashboard permite explorar el ranking de retornos estimados, filtrar símbolos y consultar su procedencia, el baseline y las métricas de evaluación.

![Diagrama del Proyecto III. El cálculo por lotes publica un snapshot que Starlette sirve al dashboard y que Playwright contrasta con el journal.](../docs/diagramas/proyecto-iii.svg)

1. **Lote e informe.** La demo entrena y evalúa con datos sintéticos. El modo `from-run` reutiliza un modelo del II y sus métricas de holdout con el histórico autorizado. Ambos publican un snapshot versionado antes de servir peticiones.
2. **API y dashboard.** Starlette sirve el informe en `/api/v1/snapshot` y comprueba su disponibilidad en `/health`. El dashboard carga el informe mediante una petición HTTP al backend.
3. **Operación y despliegue.** El journal JSONL registra el estado y la duración de las etapas. GitHub Actions genera la demo y Playwright verifica que el informe publicado, la API y la página muestran el mismo `run_id`. La guía documenta arranque local, smoke test y recuperación con un snapshot anterior.

[Arranque y demo](proyecto_iii/README.md) · [Contrato HTTP](proyecto_iii/API.md) · [Release Candidate y defensa](proyecto_iii/RELEASE.md) · [Diagrama editable en Excalidraw](../docs/diagramas/proyecto-iii.excalidraw)

## Verificación de las entregas

La matriz de trazabilidad enlaza los enunciados docentes de los Proyectos II y III con el código, las pruebas y la documentación correspondiente. La ejecución verificada de GitHub Actions incluye las tres suites y el artefacto del III con la captura del dashboard y el journal de la demo.

[Matriz de trazabilidad](../docs/TRAZABILIDAD_DSIA.md) · [Workflow](../.github/workflows/ci.yml) · [Ejecución verificada de GitHub Actions](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45225783712)
