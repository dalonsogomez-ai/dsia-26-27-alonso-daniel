# Arquitectura de investigación SwarmTrader

```mermaid
flowchart LR
    raw["Entrada batch<br/>CSV de barras diarias"] --> quality["Calidad<br/>Esquema, valores, duplicados y calendario"]
    quality --> factors["Transformación<br/>Factores disponibles al cierre"]
    quality -.-> rejected["Error de dominio<br/>Revisar entrada y ejecutar otro lote"]
    factors --> training["Entrenamiento<br/>Train, validation y holdout con purga"]
    training --> artifact["Artefacto sklearn<br/>Modelo congelado, huella de datos y métricas"]
    artifact --> inference["Inferencia batch<br/>Retorno estimado a 21 sesiones"]
    factors --> inference
    inference --> mock["Explicación<br/>Mock o cliente HF sobre resumen agregado"]
    inference --> snapshot["Snapshot versionado<br/>Predicciones, cortes y métricas"]
    mock --> snapshot
    snapshot --> api["API Starlette<br/>Informe JSON y health"]
    api --> web["Dashboard<br/>Ranking, filtro y evidencia"]
    web --> reader["Analista<br/>Contrasta el modelo y el baseline"]
    control["Control<br/>CLI y GitHub Actions"] -.-> training
    control -.-> inference
    monitor["Monitorización<br/>Logs, fecha de datos y run_id"] -.-> inference
    monitor -.-> api
```

**Datos.** La transformación produce factores causales por símbolo. Se selecciona por RMSE en validation y se conserva la evaluación de holdout. Inferencia utiliza el artefacto del Proyecto II. El informe incluye el tipo de fuente y los hashes necesarios para auditar el resultado.

**Control.** Con barras diarias y horizonte de 21 sesiones, el grueso del cálculo se ejecuta por lotes. El servidor responde lecturas HTTP contra un snapshot ya validado, con latencia y coste independientes de la llamada opcional de IA. La CLI publica cada resultado completo en un destino nuevo. El operador comprueba el `run_id` y conserva el informe anterior para recuperar el servicio.

**Negocio.** El analista usa el ranking para explorar resultados y compara el error con el baseline. El panel documenta cuándo se observó el último dato y qué limitaciones tiene la comparación. La evaluación sintética valida el funcionamiento del flujo.

[Prácticas E2E](https://github.com/dmartincc/dsia-26-27/tree/b76b9508acd7ecdf41da9890d35dfdefaa20847f/4_desarrollo_end_to_end/ejercicios) · [Contrato HTTP](../proyectos/proyecto_iii/API.md)
