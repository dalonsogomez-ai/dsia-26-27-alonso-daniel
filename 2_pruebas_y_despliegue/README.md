# Tema 2 — Pruebas y despliegue

## **Leyenda utilizada en la wiki**

`->` Inicio, objetivo o tarea planteada.

`~>` Desarrollo, cambio o ajuste realizado.

`>` Paso técnico llevado a cabo.

`>>` Evidencia, archivo o comprobación del paso.

`=>` Resultado obtenido o estado final de la fecha.

`->` Organizar el material y las prácticas del Tema 2.

| Sesión | Material | Ejercicio |
| --- | --- | --- |
| **28 sep** | [pytest](01_pytest_intro.md), [CI](02_ci_github.md), [ejemplos](ejemplos/) | [E3 — pytest](ejercicios/E3_pytest.md), [E4 — CI](ejercicios/E4_ci_github.md) |

`>>` CI del repo: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).


`>` Ejecutar los tests de ejemplo desde la raíz:

```bash
python -m pytest -q 2_pruebas_y_despliegue/ejemplos/test_calculator.py
```

`>>` Los tests y la cobertura del [Proyecto I](../proyectos/proyecto_i/README.md) se ejecutan con el workflow común del repositorio, que también lanza `python -m pytest -q 2_pruebas_y_despliegue/ejemplos` en el job `proyecto-i`.

## Procedencia del material

`>>` Material docente copiado de [dmartincc/dsia-26-27 @b76b950](https://github.com/dmartincc/dsia-26-27/tree/b76b9508acd7ecdf41da9890d35dfdefaa20847f/2_pruebas_y_despliegue): `ejemplos/` (`calculator.py`, `test_calculator.py`, `ci_proyecto_i.yml`) y `ejercicios/E3_pytest.md` sin cambios; `02_ci_github.md` y `ejercicios/E4_ci_github.md` solo difieren en espacios al final de línea (comprobado el 23/11/2026).

`~>` Versión anterior: [`01_pytest_intro.md`](01_pytest_intro.md) es la copia del 14/09/2026 ([`3c9ff18`](https://github.com/dmartincc/dsia-26-27/blob/3c9ff182e1dd24c154c758208e3b8ff9fd8f072f/2_pruebas_y_despliegue/01_pytest_intro.md), 49 líneas). La versión vigente, ampliada el 28/09/2026, es [`01_pytest_intro.md` @b76b950](https://github.com/dmartincc/dsia-26-27/blob/b76b9508acd7ecdf41da9890d35dfdefaa20847f/2_pruebas_y_despliegue/01_pytest_intro.md) (605 líneas).

`=>` Soluciones propias: este README; los ejercicios E3 y E4 se resuelven en los tests del [Proyecto I](../proyectos/proyecto_i/README.md#tests-y-cobertura) y en el [workflow](../.github/workflows/ci.yml) del repositorio.
