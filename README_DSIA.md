# DSIA · Proyectos I, II y III

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

`->` Guía corta de las tres entregas. La leyenda de los marcadores está en el [README raíz](README.md#leyenda-utilizada-en-la-wiki).

| Entrega | Alcance y evidencia |
| --- | --- |
| [I · Programación avanzada](proyectos/proyecto_i/README.md) | Parte A de ventas y Parte B de acciones. Dos CLI, reglas de calidad, métricas y pytest con cobertura mínima del 60 %. Ventas pasa el checkpoint 140 válidas y 10 inválidas; acciones se ejecuta sin red con una muestra sintética versionada |
| [II · Automatización e IA](proyectos/proyecto_ii/README.md) | Entrenamiento e inferencia sklearn a 21 sesiones. Dummy, Ridge y Swarm, validación temporal con purga, baseline en el holdout, artefacto persistido, logs por etapa y cliente Hugging Face tipado con mock |
| [III · Desarrollo E2E](proyectos/proyecto_iii/README.md) | Lote que publica un snapshot, API (salud, snapshot, predicción por símbolo, análisis con IA, pipeline y métricas), dashboard con panel de operación y Playwright contra el backend real. Docker, Render y Procfile; despliegue público con datos reales de Alpaca |

## Demo y evidencias

`=>` Despliegue público: [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com), con datos reales de Alpaca (último dato 2026-11-20) y solo predicciones y métricas en la respuesta pública.

`>` La [guía del III](proyectos/proyecto_iii/README.md) reproduce la demo en un clon limpio con Python 3.12, datos sintéticos y el proveedor `mock`, y explica cómo entrenar e inferir, arrancar la API y el dashboard, y desplegar.

`>>` El [workflow](.github/workflows/ci.yml) ejecuta las tres suites con umbral de cobertura, construye la imagen Docker del III y publica una captura sintética del dashboard junto al journal del lote. Último run verde de `main`: [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) (I 178 tests / 99,31 %, II 74 / 83,42 %, III 123 / 97,22 %, Docker correcto). La [matriz de trazabilidad](docs/TRAZABILIDAD_DSIA.md) enlaza cada requisito de los tres enunciados con su evidencia, y los [diagramas de Excalidraw](docs/ARQUITECTURA_DSIA.md) muestran las dependencias entre entregas.

- `>>` **Proyecto I.** Los módulos loader, validador, métricas y CLI se comprueban en A y B. El extractor documentado obtiene las barras con autorización; sin cuenta, la Parte B se demuestra con la muestra sintética `data/sample/acciones_muestra.csv`. [Verificación del I](proyectos/proyecto_i/VERIFICACION.md) · [Citación](proyectos/proyecto_i/AI_USAGE.md)
- `>>` **Proyecto II.** Se congela el candidato elegido por validation antes de evaluar el holdout. La llamada autenticada a Hugging Face queda fuera de la evidencia verificada; el enunciado admite el mock con cliente tipado y configuración documentada. No hay commits de octubre y no se fabrican fechas. [Guía del II](proyectos/proyecto_ii/README.md) · [Citación](proyectos/proyecto_ii/AI_USAGE.md)
- `>>` **Proyecto III.** El backend verifica y sirve un único informe. La pantalla expone modelo, baseline, último dato, cortes de evaluación, identidad del informe y estado de operación. Empaquetado verificado en CI y desplegado en Render. [Contrato HTTP](proyectos/proyecto_iii/API.md) · [Release Candidate](proyectos/proyecto_iii/RELEASE.md) · [Citación](proyectos/proyecto_iii/AI_USAGE.md)

`>>` [Índice de proyectos del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md)
