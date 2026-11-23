# DSIA · Proyectos I, II y III

| Entrega | Alcance y evidencia |
| --- | --- |
| [I · Programación avanzada](proyectos/proyecto_i/README.md) | Parte A de ventas y Parte B de acciones. Dos CLI, reglas de calidad, métricas y pytest con cobertura mínima del 60 %. Ventas pasa el checkpoint 140 válidas y 10 inválidas |
| [II · Automatización e IA](proyectos/proyecto_ii/README.md) | Entrenamiento e inferencia sklearn a 21 sesiones. Dummy, Ridge y Swarm, validación temporal con purga, artefacto persistido y cliente Hugging Face tipado con mock |
| [III · Desarrollo E2E](proyectos/proyecto_iii/README.md) | Informe versionado, API, dashboard y Playwright contra el backend real. Incluye despliegue reproducible y guion de defensa |

## Demo y evidencias

La [guía del III](proyectos/proyecto_iii/README.md) reproduce la demo en un clon limpio con Python 3.12, datos sintéticos y el proveedor `mock`. El [diagrama](docs/ARQUITECTURA_DSIA.md) sigue los flujos de datos, control y negocio. El [workflow](.github/workflows/ci.yml) ejecuta las tres suites y publica una captura sintética del dashboard como artefacto.

- **Proyecto I.** Los módulos loader, validador, métricas y CLI se comprueban en A y B. El conjunto preserva el historial de la entrega publicada. El extractor documentado permite obtener las barras con autorización. La suite usa fixtures inventadas. [Verificación previa del I](proyectos/proyecto_i/VERIFICACION.md)
- **Proyecto II.** Se congela el candidato elegido por validation antes de evaluar el holdout. La llamada Hugging Face autenticada y el paper externo quedan fuera de la evidencia verificada. El enunciado admite el mock con cliente tipado y configuración documentada. Se conserva la cronología disponible de la adaptación. [Decisión y evaluación](proyectos/proyecto_ii/README.md) · [Citación](proyectos/proyecto_ii/AI_USAGE.md)
- **Proyecto III.** El backend verifica y sirve un único informe. La pantalla expone modelo, baseline, último dato, cortes de evaluación e identidad del informe. El despliegue local corresponde a la opción de empaquetado del enunciado. [Contratos y prueba](proyectos/proyecto_iii/API.md)

[Índice de proyectos del profesor](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/proyectos/README.md)
