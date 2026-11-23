# DSIA · Proyectos I, II y III

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

| Entrega | Alcance y evidencia |
| --- | --- |
| [I · Programación avanzada](proyectos/proyecto_i/README.md) | Parte A de ventas y Parte B de acciones. Dos CLI, reglas de calidad, métricas y pytest con cobertura mínima del 60 %. Ventas pasa el checkpoint 140 válidas y 10 inválidas; acciones se ejecuta sin red con una muestra sintética versionada |
| [II · Automatización e IA](proyectos/proyecto_ii/README.md) | Entrenamiento e inferencia sklearn a 21 sesiones. Dummy, Ridge y Swarm, validación temporal con purga, baseline en el holdout, artefacto persistido, logs por etapa y cliente Hugging Face tipado con mock |
| [III · Desarrollo E2E](proyectos/proyecto_iii/README.md) | Informe versionado, API (salud, snapshot, predicción por símbolo, análisis con IA, pipeline y métricas), dashboard con panel de operación y Playwright contra el backend real. Empaquetado Docker, Render y Procfile, y guion de defensa |

## Demo y evidencias

La [guía del III](proyectos/proyecto_iii/README.md) reproduce la demo en un clon limpio con Python 3.12, datos sintéticos y el proveedor `mock`. El [índice de proyectos](proyectos/README.md) resume las tres entregas con sus diagramas, y los [diagramas de Excalidraw](docs/ARQUITECTURA_DSIA.md) muestran las dependencias entre ellas. El [workflow](.github/workflows/ci.yml) ejecuta las tres suites con umbral de cobertura, construye la imagen Docker del III y publica una captura sintética del dashboard junto al journal del lote. La [matriz de trazabilidad](docs/TRAZABILIDAD_DSIA.md) enlaza cada requisito de los tres enunciados con su evidencia.

- **Proyecto I.** Los módulos loader, validador, métricas y CLI se comprueban en A y B. El conjunto preserva el historial de la entrega publicada. El extractor documentado permite obtener las barras con autorización; sin cuenta, la Parte B se demuestra con la muestra sintética `data/sample/acciones_muestra.csv`. [Verificación del I](proyectos/proyecto_i/VERIFICACION.md) · [Citación](proyectos/proyecto_i/AI_USAGE.md)
- **Proyecto II.** Se congela el candidato elegido por validation antes de evaluar el holdout. La llamada Hugging Face autenticada y el paper externo quedan fuera de la evidencia verificada. El enunciado admite el mock con cliente tipado y configuración documentada. Se conserva la cronología disponible de la adaptación. [Decisión y evaluación](proyectos/proyecto_ii/README.md) · [Citación](proyectos/proyecto_ii/AI_USAGE.md)
- **Proyecto III.** El backend verifica y sirve un único informe. La pantalla expone modelo, baseline, último dato, datos de entrada, cortes de evaluación, identidad del informe y el estado de operación. El empaquetado (Docker, Render y Procfile) está verificado en local; todavía no hay URL pública. [Contratos y prueba](proyectos/proyecto_iii/API.md) · [Citación](proyectos/proyecto_iii/AI_USAGE.md)

[Índice de proyectos del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md)
