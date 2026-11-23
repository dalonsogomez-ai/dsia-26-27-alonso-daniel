# Verificación del Proyecto II

La suite de pytest valida datos, carga e inferencia sklearn, contrato del cliente de IA y lógica del adaptador paper con dobles. `marimo check` comprueba la estructura de los cuatro notebooks. En una réplica local pasaron 51 tests con 81 % de cobertura redondeada.

El histórico del proveedor se procesó en local. El despliegue de demostración y CI emplean datos sintéticos y el mock determinista. La evidencia del commit se verifica en la pestaña Actions del repositorio. [Workflow](../../.github/workflows/ci.yml)
