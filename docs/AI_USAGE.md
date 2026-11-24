# Uso de IA en la parte transversal del repositorio

`->` Registro de las herramientas de IA usadas en los ficheros comunes a los tres proyectos: README raíz, `README_DSIA.md`, `proyectos/README.md`, `docs/`, el workflow de CI, `requirements.txt` raíz, `.mailmap` y los README de los Temas 1 y 2. Cada proyecto tiene además su propio registro: [I](../proyectos/proyecto_i/AI_USAGE.md), [II](../proyectos/proyecto_ii/AI_USAGE.md) y [III](../proyectos/proyecto_iii/AI_USAGE.md).

## 23/11/2026 · OpenAI Codex (modelo gpt-6.2-sol): integración, auditoría docente y diagramas

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Integrar el II y el III en el repositorio de entrega y contrastarlos con los enunciados y la rúbrica docente |
| Qué se aceptó | Workflow de CI del III, `README_DSIA.md`, arquitectura con los diagramas Excalidraw y sus SVG, primera matriz de trazabilidad e índice `proyectos/README.md` |
| Qué se rechazó o no se adoptó | La explicación con un proveedor externo quedó como integración opcional del lote; se usa `mock` en CI |
| Cómo se verificó | Pruebas del III, smoke y prueba de navegador en local; las cifras de esa sesión no quedaron registradas y la verificación con números es la de las entradas siguientes |
| Commits | [`3d991d2`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/3d991d2), [`4da7058`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/4da7058) y [`ab75ded`](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/commit/ab75ded) |

## 23/11/2026 · Claude Code (modelo Claude Opus 5.5)

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Auditoría de cumplimiento frente a los enunciados del profesor (`dmartincc/dsia-26-27` @`b76b950`) y aplicación de las mejoras transversales, en la rama `mejoras/cumplimiento-requisitos` y con un commit por cambio |
| Qué se aceptó | CI: quitar la rama `codex/proyecto-dsia` del trigger, smoke de las CLI A y B y tests de ejemplo del Tema 2 en el job del I, umbral del 80 % y receta de la CLI con sha256 en el II, `requirements-e2e.txt`, toda la carpeta de tests con umbral del 90 % y `--expect-pipeline` en el III, y un job nuevo que construye la imagen Docker y pasa el smoke contra el contenedor. README raíz como índice (URL canónica, badge, tabla de proyectos, dos entornos, comandos, CI y uso de IA). Enlaces a `proyectos/README.md` y a los `AI_USAGE.md`. Trazabilidad del Proyecto I y de la entrega del III, con lo no subsanable y lo que depende del autor. Endpoints y empaquetado en la arquitectura. `.mailmap`. Procedencia del material docente. Comentario de alcance en `requirements.txt` |
| Qué se rechazó o no se adoptó | `docker/build-push-action`: basta `docker build` en un `run:` y así no hay otra acción que fijar por SHA. Añadir la rama de trabajo al trigger `push`: el enunciado pide `main` y `pull_request`, y el PR ya dispara el CI. Refrescar las copias antiguas del material docente: se enlaza la versión vigente para no mezclar material del profesor con el propio. Editar los diagramas Excalidraw/SVG: el texto de la arquitectura recoge los cambios. Crear el tag `v0.9.0-rc1`, desplegar en Render, sincronizar el remoto antiguo o hacer push: son acciones externas que decide el autor |
| Cómo se verificó | `yaml.safe_load` del workflow y `actionlint` 1.7.12 con ShellCheck 0.11.0 sin avisos. Simulación local de los tres jobs sobre `git archive HEAD` con los mismos comandos: I `177 passed`, 99,31 %, CLI 140/10 y 296/5, Tema 2 `7 passed`; II `71 passed`, 83,32 %, sha256 de la demo `OK`; III `97 passed`, 97,91 %, smoke y Playwright `OK`; Docker `healthy` y smoke `OK` (también con `--no-cache`). Comprobador propio de enlaces relativos y anclas: 0 rotos en todos los `.md` versionados. Comparación byte a byte del material docente con el árbol del profesor. `git shortlog -sne` con el `.mailmap`: una sola identidad. El CI remoto de la rama no se ha ejecutado: depende del push del autor |

## 23/11/2026 (tarde) · Claude Code (modelo Claude Opus 5.5): verificación final, despliegue y `main`

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Repetir la verificación de los tres proyectos en un clon limpio con revisores independientes y un crítico de completitud, desplegar el III en Render e integrar el trabajo en `main` con el CI en verde |
| Qué se aceptó | `render.yaml` con `runtime: docker`, región Frankfurt, plan free, `healthCheckPath: /health` y `autoDeployTrigger: commit`, que describe el servicio creado en Render (`b983bcd`); URL pública en el README raíz, `README_DSIA.md`, `proyectos/README.md`, la arquitectura y la matriz de trazabilidad; `workflow_dispatch` mencionado en el índice del CI |
| Qué se rechazó o no se adoptó | Desplegar con el runtime Python de Render: la imagen Docker es la misma que construye y prueba el job `proyecto-iii-docker`, así que el entorno desplegado coincide con el verificado. Tag `v0.9.0-rc1`: creado cuando el autor lo aprobó, sobre `0119c57` con CI verde; no se crea una release de GitHub aparte. Reescribir el historial de octubre del II: no se fabrica |
| Cómo se verificó | En Render: build de la imagen con el lote demo dentro, `/health` → `200 ready`, `scripts/smoke_test.sh https://dsia-swarmtrader.onrender.com` → «Smoke correcto», y dashboard en Chrome con el panel Operación y «Explicar símbolo» sin errores de consola; tras integrar, Render despliega `main` (`a5a5b9b`) y `browser_smoke.py --expect-pipeline` pasa contra la URL pública. CI: el primer run del PR falló por el sha256 de la demo en Linux (corregido en `d3bff34`); después, PR ([45270756811](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45270756811)) y `main` ([45271274056](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45271274056)) en verde con I 178 / 99,31 %, II 74 / 83,42 %, III 103 / 97,94 % y Docker. `render.yaml` validado con PyYAML y contrastado con la especificación de Blueprints de Render |

## 23-24/11/2026 · Claude Code (modelo Claude Opus 5.5): datos reales en Render

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Que el despliegue de Render muestre los símbolos reales y quede completamente funcional en `main`, con los enlaces de Render en el README |
| Qué se aceptó | PR #2 (descarga de Alpaca en el lote y en el build con secret file) y PR #3 (refresco al arrancar con las claves como variables de entorno, sección «Demo en vivo (Render)» del README raíz y `render.yaml` con `ALPACA_*` como `sync: false`), ambos con CI verde antes de fusionar |
| Qué se rechazó o no se adoptó | Mostrar precios de Alpaca en la web pública (sus condiciones lo prohíben; el autor eligió publicar solo predicciones). Pasar las claves como `ARG` al build de Docker. Introducir yo las claves en Render: las creó el autor en el panel |
| Cómo se verificó | https://dsia-swarmtrader.onrender.com/health → `ready`, `data_kind: alpaca`, último dato 2026-11-20; `smoke_test.sh` y `browser_smoke.py --kind "Datos reales · Alpaca" --expect-pipeline` correctos contra la URL pública; `/api/v1/snapshot` sin `last_close`; CI de `main` en verde en el run [45288524693](https://github.com/dalonsogomez-ai/dsia-26-27-alonso-daniel/actions/runs/45288524693) |

## 24/11/2026 · Claude Code (modelo Claude Opus 5.5): documentación con la leyenda de la wiki

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Reescribir la documentación del III y de la raíz con el estilo del README del Proyecto I (leyenda entre comillas invertidas, títulos limpios, cifras fechadas con su run y desarrollo por fechas) y ordenarla según la Entrega del enunciado del III |
| Qué se aceptó | README raíz con la leyenda al principio, CI fechado con el run 45288524693 y desarrollo por fechas; `README_DSIA.md` y `proyectos/README.md` con marcadores y despliegue con datos reales; arquitectura con la cadena completa y el arranque con `serve.py`; matriz de trazabilidad al día con `main` en `bd3b0fa`; anclas al README del II sin el guion inicial (por ejemplo `#motivación`); entrada de Codex (gpt-6.2-sol) para los ficheros comunes del 23/11 |
| Qué se rechazó o no se adoptó | Fechas de octubre para el II o el III: no hay commits y no se fabrican. Tocar código, los README del I y del II o los diagramas: fuera del alcance de esta revisión |
| Cómo se verificó | Pruebas del III en local con `.venv-ii`: 123 passed. Comprobador de enlaces relativos y anclas sobre los ficheros editados. Cifras contrastadas con el log del run 45288524693 (I 178 / 99,31 %, II 74 / 83,42 %, III 123 / 97,22 %, Docker correcto) |

## 24/11/2026 · Claude Code (modelo Claude Opus 5.5): proveedor alternativo NVIDIA

| Campo | Contenido |
| --- | --- |
| Qué se pidió | Añadir el mejor modelo de [build.nvidia.com](https://build.nvidia.com/models) como alternativa a Hugging Face, porque la cuenta HF del autor tenía 0 $ de saldo e Inference Providers rechazaba las llamadas |
| Qué se aceptó | En los ficheros comunes, `render.yaml` con `NVIDIA_API_KEY` (`sync: false`) y `NVIDIA_MODEL` (`moonshotai/kimi-k3.1-pro`), manteniendo `AI_PROVIDER=mock`. El código y su documentación se registran en el AI_USAGE del [II](../proyectos/proyecto_ii/AI_USAGE.md) y del [III](../proyectos/proyecto_iii/AI_USAGE.md) |
| Qué se rechazó o no se adoptó | Cambiar el proveedor del CI o de Render a `nvidia`: el CI sigue en `mock` y la clave la introduce el autor en el panel. Actualizar las cifras ligadas al run 45288524693, que describen ese run y no la verificación local |
| Cómo se verificó | Local con `.venv-ii`, sin red: II 162 passed y 85,97 % de cobertura, `marimo check` sin avisos; III 134 passed y 97,20 %. `render.yaml` cargado con PyYAML |
