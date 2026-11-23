# Uso de IA en el Proyecto III

| Herramienta | Contribución | Comprobación |
| --- | --- | --- |
| OpenAI Codex | Recuperó fuentes y decisiones, diseñó el esquema del snapshot, implementó el backend, el dashboard y sus tests, y redactó las instrucciones de arranque | pytest, ejecución de Uvicorn, Chromium y contraste con el artefacto y las métricas del II |
| Claude Code | Trabajo previo sobre SwarmTrader v1.8. Su razonamiento documentado orientó el control temporal y la trazabilidad del informe | Se contrastó la sesión indexada con el tracker de investigación y el contrato del II |
| Claude Octopus Council | Revisión arquitectónica intentada con presupuesto limitado | La revisión quedó parcial y sin quórum. El resultado no se usó como validación |

El proveedor `mock` produce la explicación de la demo sin llamar a un modelo externo. El adaptador Hugging Face heredado se documenta en el Proyecto II. Las métricas y las estimaciones provienen del pipeline sklearn y de sus artefactos. No se enviaron datos de Alpaca a proveedores externos durante estas comprobaciones.

[Arquitectura y trazabilidad](../../docs/ARQUITECTURA_DSIA.md) · [Uso de IA del Proyecto II](../proyecto_ii/AI_USAGE.md)

## 23 de noviembre de 2026 · Auditoría y RC

Se pidió contrastar los enunciados y ejemplos docentes con el flujo real, revisar los riesgos del arranque y documentar la ejecución. Codex y sus agentes de revisión aportaron la matriz de trazabilidad, el journal y las pruebas del camino crítico. Se aceptaron cambios comprobables con pytest, smoke HTTP e integración en Chromium. Se mantuvo la explicación externa como integración opcional de lote y el empaquetado local como opción de despliegue. El modelo de desarrollo concreto se registra como no disponible en el historial de esta entrega. Las fuentes y la evidencia están enlazadas en la [auditoría](../../docs/TRAZABILIDAD_DSIA.md) y el [RC](RELEASE.md).
