# Tracker de implementación de la mejora de experiencia de usuario

Fecha de creación: 2026-09-12. Última actualización: 2026-09-12.
Referencia: [plan y orden recomendado](../README.md).

Este archivo registra el avance de los diez tickets del plan UX. Los tickets contienen los pasos y criterios de aceptación; el tracker centraliza estado, responsables, dependencias y evidencia de resolución. Crear los documentos no implica haber implementado los cambios: todos comienzan en `Todo`.

## Estados

| Estado | Significado |
| --- | --- |
| `Todo` | Pendiente de iniciar. Comprobar dependencias antes de tomarlo. |
| `In Progress` | Un responsable está implementando el alcance del ticket. |
| `Blocked` | Existe un impedimento concreto registrado, con acción para resolverlo. |
| `In Review` | Implementación y evidencia disponibles; pendiente de revisión y aceptación. |
| `Done` | Criterios de aceptación satisfechos y resolución aceptada con evidencia. |

Un ticket pendiente de su orden de ejecución puede permanecer en `Todo`; no hace falta marcarlo `Blocked` solo por tener dependencias. Si se descubre una regresión después de cerrar un ticket, reabrirlo y registrar el motivo.

## Registro de issues

| ID | Ticket | Prioridad | Estado | Responsable | Dependencias | PR o commit de resolución | Cierre |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UX-000 | [Acordar fronteras y registrar la línea base](UX-000-acordar-fronteras-y-linea-base.md) | P0 | Todo | Sin asignar | Ninguna | — | — |
| UX-001 | [Orientación y navegación por tareas](UX-001-orientacion-y-navegacion.md) | P0 | Todo | Sin asignar | UX-000 | — | — |
| UX-002 | [Editar el modelo con complejidad progresiva](UX-002-edicion-progresiva-del-modelo.md) | P1 | Todo | Sin asignar | UX-001 | — | — |
| UX-003 | [Importación guiada de series de tiempo](UX-003-importacion-guiada.md) | P1 | Todo | Sin asignar | UX-002 | — | — |
| UX-004 | [Encontrar y usar datos desde la necesidad del modelo](UX-004-catalogo-contextual.md) | P1 | Todo | Sin asignar | UX-001 | — | — |
| UX-005 | [Revisar la preparación y ejecutar con contexto](UX-005-revisar-y-ejecutar.md) | P0 | Todo | Sin asignar | UX-001 | — | — |
| UX-006 | [Mostrar primero resultados y facilitar la comparación](UX-006-resultados-y-comparacion.md) | P0 | Todo | Sin asignar | UX-001 | — | — |
| UX-007 | [Configurar y publicar informes con claridad](UX-007-configurar-y-publicar-informes.md) | P1 | Todo | Sin asignar | UX-006 | — | — |
| UX-008 | [Simplificar configuración y preparación de la consola](UX-008-consola-de-operador.md) | P1 | Todo | Sin asignar | UX-001 | — | — |
| UX-009 | [Administración y acciones sensibles comprensibles](UX-009-administracion-comprensible.md) | P2 | Todo | Sin asignar | UX-001 | — | — |

## Próximos tickets disponibles

Inicialmente solo UX-000 tiene sus dependencias satisfechas. Actualizar esta sección al cerrar o reabrir un ticket:

1. Resolver UX-000: línea base y fronteras de prueba confirmadas.
2. Resolver UX-001: navegación y contexto que usarán los demás cambios.
3. Priorizar UX-005 y UX-006 para la primera entrega útil.
4. Continuar con UX-002 → UX-003, UX-004, UX-007 y UX-008 según la prioridad de producto y sus dependencias.
5. Completar UX-009 y verificar la integración de los tickets incluidos en cada entrega.

Cuando se integren UX-003/004 con UX-005, volver a comprobar el recorrido desde datos hasta ejecución. La aceptación de cada ticket no reemplaza esta comprobación de integración.

## Cómo actualizar el avance

1. Antes de empezar, comprobar dependencias y asignar responsable. Cambiar el estado a `In Progress` aquí y en el encabezado del ticket.
2. Registrar las fronteras TDD confirmadas en UX-000 o en la evidencia del ticket; no escribir pruebas nuevas en una frontera sin confirmar.
3. Implementar un ciclo RED → GREEN por comportamiento. Registrar la evidencia focalizada y ejecutar las regresiones aplicables, siguiendo la [estrategia TDD](../04_estrategia_tdd.md).
4. Si aparece un bloqueo, indicar su causa, quién puede resolverlo y cuál es la siguiente acción. Anotarlo en el registro de bloqueos y en el historial.
5. Para pasar a `In Review`, enlazar PR/commit, criterios comprobados, filas de paridad afectadas y evidencia de validación. La refactorización se evalúa en esta revisión posterior, conforme a la habilidad local.
6. Al aceptar la resolución, marcar `Done` tanto aquí como en el ticket, añadir fecha y completar la ficha de resolución. Actualizar próximos tickets disponibles.

No marcar un ticket `Done` si solo se completó un subconjunto de sus criterios. Cuando se entregue por varias PRs, registrar cada una y mantener el ticket abierto hasta completar su alcance, o acordar explícitamente una división de tickets y actualizar las dependencias.

## Criterios de cierre

- [ ] Se completaron los criterios de aceptación del ticket.
- [ ] Se conservaron las capacidades afectadas de la [matriz funcional](../03_matriz_funcional.md).
- [ ] Las pruebas aplicables pasan y se enlazan comandos y resultados reales.
- [ ] Se registró el ciclo TDD para los comportamientos nuevos y las fronteras estaban confirmadas.
- [ ] Se verificaron los estados relevantes: carga, vacío, error, cambios pendientes y conflicto.
- [ ] Se revisaron teclado, foco, navegación y presentación en los tamaños aplicables.
- [ ] Si corresponde, se verificaron permisos, revisión exacta, fail-closed y compatibilidad TS-7.
- [ ] Se documentaron limitaciones y se actualizó la guía afectada al comportamiento aceptado.
- [ ] Se registraron revisión/aceptación, PR o commit y fecha de cierre.

Para UX-000, usar sus criterios específicos de preparación: no requiere inventar pruebas RED → GREEN, pantallas ni cambios de producto. Marcar como «No aplica» los puntos de cierre que no correspondan y explicar por qué. Las pruebas omitidas no cuentan como aprobadas; aplicar el [protocolo de entrega](../05_validacion_y_entrega.md).

## Ficha de resolución por ticket

Copiar esta ficha al final del ticket cuando entre en revisión y enlazarla desde el historial si hace falta:

```markdown
## Resolución

- Responsable:
- Fecha de inicio:
- Fecha de revisión/aceptación:
- Estado final:
- PR o commits:
- Comportamiento implementado:
- Criterios de aceptación y evidencia:
- Fronteras confirmadas y referencia de confirmación:
- Evidencia RED → GREEN de los comportamientos nuevos:
- Pruebas/regresiones ejecutadas, comandos y resultados:
- Revisión visual y de accesibilidad:
- Filas de conservación funcional verificadas:
- Compatibilidad y permisos comprobados, si aplica:
- Limitaciones o puntos no aplicables:
- Persona que revisó/aceptó:
```

## Bloqueos activos

No hay bloqueos registrados al crear el tracker. Añadir una fila cuando exista un impedimento concreto; retirarla de esta tabla al resolverlo y conservar el evento en el historial.

| Ticket | Impedimento | Responsable de resolver | Próxima acción | Fecha |
| --- | --- | --- | --- | --- |

## Historial de cambios

| Fecha | Ticket | Cambio de estado | Evidencia o motivo |
| --- | --- | --- | --- |
| 2026-09-12 | UX-000 a UX-009 | Creación → Todo | Se registran los diez tickets del plan; implementación aún pendiente. |

## Control de entregas

| Entrega | Tickets previstos | Estado | Evidencia de integración |
| --- | --- | --- | --- |
| Primera mejora del flujo principal | UX-000, UX-001, UX-005, UX-006 | Pendiente | — |
| Modelo y datos | UX-002, UX-003, UX-004 | Pendiente | — |
| Informes y consola | UX-007, UX-008 | Pendiente | — |
| Administración | UX-009 | Pendiente | — |

Estas agrupaciones orientan la entrega, no obligan a acumular todos los tickets en una sola PR. Cada entrega debe incluir la evidencia de integración correspondiente y conservar los criterios de reversión definidos en el plan.
