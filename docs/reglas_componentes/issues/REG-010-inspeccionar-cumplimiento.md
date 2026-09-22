# REG-010: Inspeccionar cumplimiento y fallos de las reglas en resultados

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), sección 9.
User stories covered: HU-10.

## What to build

Agregar a los resultados internos una vista por regla que compare las filas
congeladas con la solución: valores de ambos lados, margen o residuo, unidad,
tolerancia y períodos afectados. Para corridas fallidas, distinguir errores
de código/datos, timeout e infactibilidad y permitir volver a la regla pertinente.
La explicación se reconstruye desde el snapshot y resultados de esa corrida.

## Acceptance criteria

- [ ] Cada fila evaluada se atribuye a definición/revisión, instancia, componentes y período/ventana; no usa el código o alias actuales para interpretar historia.
- [ ] Desigualdades muestran margen con convención documentada y las igualdades residuo; se registran tolerancias absolutas/relativas y unidades originales.
- [ ] La vista filtra reglas y períodos, pagina detalles y grafica muestras claramente identificadas, sin perder filas ni limitar la comprobación al gráfico.
- [ ] El estado distingue solución óptima, solución factible disponible y ausencia de solución primal; no inventa valores cuando el solver no los entrega.
- [ ] Contradicciones simples enlazan reglas/períodos identificados; una infactibilidad general muestra evidencia disponible sin afirmar causa única ni un IIS inexistente.
- [ ] Errores de compilación, capacidad, timeout, cancelación y solve mantienen categorías estables y acciones concretas; no se presentan todos como «modelo infactible».
- [ ] Los resultados derivados de cumplimiento se pueden reconstruir desde IR y resultados congelados, sin volver a ejecutar Python.
- [ ] El detalle técnico es solo interno; payloads de portal/consola no filtran código, IR, trazas ni identificadores internos por incorporar este informe.

## Demonstration and validation

Mostrar un máximo vinculante, otro con holgura y una igualdad. Resolver un caso
incompatible y comprobar la explicación limitada a la evidencia real. Editar
la regla actual y reconstruir el informe histórico con el mismo resultado.
Verificar tolerancias/escalas, ausencia de primal y paginación mediante API/UI.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
