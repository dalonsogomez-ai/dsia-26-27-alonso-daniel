# DSIA · Proyectos I, II y III

[![CI](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/workflows/ci.yml)

`->` Guía corta de las tres entregas. La leyenda de los marcadores está en el [README raíz](README.md#leyenda-utilizada-en-la-wiki).

| Entrega | Alcance y evidencia |
| --- | --- |
| [I · Programación avanzada](proyectos/proyecto_i/README.md) | Parte A de ventas y Parte B de acciones. Dos CLI, reglas de calidad, métricas y pytest con cobertura mínima del 60 %. Ventas pasa el checkpoint 140 válidas y 10 inválidas; acciones se ejecuta sin red con una muestra sintética versionada |
| [II · Automatización e IA](proyectos/proyecto_ii/README.md) | Entrenamiento e inferencia sklearn a 21 sesiones. Dummy, Ridge y Swarm, validación temporal con purga, baseline en el holdout, artefacto persistido, logs por etapa y cliente de IA tipado (`mock`, Hugging Face y, como alternativa, NVIDIA) con la clase de cada fallo |
| [III · Desarrollo E2E](proyectos/proyecto_iii/README.md) | Lote que publica un snapshot, API (salud, snapshot, predicción por símbolo, análisis con IA, pipeline y métricas), dashboard con panel de operación y Playwright contra el backend real. Docker, Render y Procfile; despliegue público con datos reales de Alpaca |

## Demo y evidencias

`=>` Despliegue público: [https://dsia-swarmtrader.onrender.com](https://dsia-swarmtrader.onrender.com), con datos reales de Alpaca (el 24/11/2026 servía `as_of` 2026-11-23), solo predicciones y métricas en la respuesta pública y «Explicar símbolo» con `nvidia/nemotron-3.5-super-vl-120b-a12b`.

`>` La [guía del III](proyectos/proyecto_iii/README.md) reproduce la demo en un clon limpio con Python 3.12, datos sintéticos y el proveedor `mock`, y explica cómo entrenar e inferir, arrancar la API y el dashboard, y desplegar.

`>>` El [workflow](.github/workflows/ci.yml) ejecuta las tres suites con umbral de cobertura, construye la imagen Docker del III y publica una captura sintética del dashboard junto al journal del lote. Estado en el [historial de `main`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions?query=branch%3Amain); último run comprobado: [45407490182](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45407490182) (`1ff1817`, 24/11/2026), en verde. Verificado en local el 24/11/2026 sobre `v0.9.0-rc2`: I 178 tests / 99,31 %, II 197 / 86,50 %, III 298 / 98,25 %, Docker correcto. La [matriz de trazabilidad](docs/TRAZABILIDAD_DSIA.md) enlaza cada requisito de los tres enunciados con su evidencia, y los [diagramas de Excalidraw](docs/ARQUITECTURA_DSIA.md) muestran las dependencias entre entregas.

- `>>` **Proyecto I.** Los módulos loader, validador, métricas y CLI se comprueban en A y B. El extractor documentado obtiene las barras con autorización; sin cuenta, la Parte B se demuestra con la muestra sintética `data/sample/acciones_muestra.csv`. [Verificación del I](proyectos/proyecto_i/VERIFICACION.md) · [Citación](proyectos/proyecto_i/AI_USAGE.md)
- `>>` **Proyecto II.** Se congela el candidato elegido por validation antes de evaluar el holdout. Las llamadas autenticadas a Hugging Face desde Render del 24/11/2026 fallaron porque la cuenta del autor no tenía crédito, así que la evidencia de HF es el `mock` con cliente tipado, dobles del SDK y configuración documentada, que admite el enunciado. En el despliegue responde la alternativa NVIDIA con Nemotron 3.5 Super, elegido entre cinco modelos medidos en Render (dos agotaron el timeout). No hay commits de octubre y no se fabrican fechas. [Guía del II](proyectos/proyecto_ii/README.md) · [Citación](proyectos/proyecto_ii/AI_USAGE.md)
- `>>` **Proyecto III.** El backend verifica y sirve un único informe. La pantalla expone modelo, baseline, último dato, cortes de evaluación, identidad del informe y estado de operación. Empaquetado verificado en CI y desplegado en Render. [Contrato HTTP](proyectos/proyecto_iii/API.md) · [Release Candidate](proyectos/proyecto_iii/RELEASE.md) · [Citación](proyectos/proyecto_iii/AI_USAGE.md)

`>>` [Índice de proyectos del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md)
