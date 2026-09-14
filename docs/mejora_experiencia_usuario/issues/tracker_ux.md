# Tracker de implementación de la mejora de experiencia de usuario

Fecha de creación: 2026-09-12. Última actualización: 2026-09-14.
Referencia: [plan y orden recomendado](../README.md).

Este archivo registra el avance de los diez tickets del plan UX. Los tickets contienen los pasos y criterios de aceptación; el tracker centraliza estado, responsables, dependencias y evidencia de resolución. UX-000 está aceptado tras confirmar las fronteras; UX-001 a UX-007 tienen implementación y evidencia para revisión.

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
| UX-000 | [Acordar fronteras y registrar la línea base](UX-000-acordar-fronteras-y-linea-base.md) | P0 | Done | Codex | Ninguna | Preparación `aeeb22e`; [línea base y acuerdo](../evidencia/ux-000/README.md) | 2026-09-12; usuario confirma fronteras |
| UX-001 | [Orientación y navegación por tareas](UX-001-orientacion-y-navegacion.md) | P0 | In Review | Codex | UX-000 | `feat(ux): implement task-oriented workspace navigation`, sobre `aeeb22e`; [evidencia](../evidencia/ux-001/README.md) | Pendiente de aceptación del resultado |
| UX-002 | [Editar el modelo con complejidad progresiva](UX-002-edicion-progresiva-del-modelo.md) | P1 | In Review | Codex | UX-001 | `feat(ux): add progressive model editing and protect unsaved changes`, sobre `9c24c1b`; [implementación, TDD y evidencia](../evidencia/ux-002/README.md) | Pendiente de aceptación del resultado |
| UX-003 | [Importación guiada de series de tiempo](UX-003-importacion-guiada.md) | P1 | In Review | Codex | UX-002 | Cambios locales sobre `19fc31c`; [implementación, TDD y evidencia](../evidencia/ux-003/README.md) | Pendiente de aceptación del resultado |
| UX-004 | [Encontrar y usar datos desde la necesidad del modelo](UX-004-catalogo-contextual.md) | P1 | In Review | Codex | UX-001 | `feat(ux): connect catalog sources to model needs`; [implementación, TDD y evidencia](../evidencia/ux-004/README.md) | Pendiente de aceptación del resultado |
| UX-005 | [Revisar la preparación y ejecutar con contexto](UX-005-revisar-y-ejecutar.md) | P0 | In Review | Codex | UX-001 | `feat(ux): guide variant preparation and execution`, sobre `e4eec65`; [evidencia](../evidencia/ux-005/README.md) | Pendiente de aceptación del resultado |
| UX-006 | [Mostrar primero resultados y facilitar la comparación](UX-006-resultados-y-comparacion.md) | P0 | In Review | Codex | UX-001 | `feat(ux): prioritize results and contextual run comparison`, sobre `61dc87a`; [implementación, TDD y evidencia](../evidencia/ux-006/README.md) | Pendiente de aceptación del resultado |
| UX-007 | [Configurar y publicar informes con claridad](UX-007-configurar-y-publicar-informes.md) | P1 | In Review | Codex | UX-006 | `feat(ux): guide report configuration and explicit publication`, sobre `cf64106`; [implementación, TDD y evidencia](../evidencia/ux-007/README.md) | Pendiente de aceptación del resultado |
| UX-008 | [Simplificar configuración y preparación de la consola](UX-008-consola-de-operador.md) | P1 | Todo | Sin asignar | UX-001 | — | — |
| UX-009 | [Administración y acciones sensibles comprensibles](UX-009-administracion-comprensible.md) | P2 | Todo | Sin asignar | UX-001 | — | — |

## Próximos tickets disponibles

UX-000 está cerrado. UX-001 está integrado en `e4eec65` y UX-005 en `61dc87a`.
UX-006 está integrado en `9c24c1b`; UX-002 está integrado en `19fc31c`.
UX-003 está integrado en `91bb561`; UX-004 está integrado en `cf64106`.
UX-007 tiene implementación completa y evidencia desde resultados hasta el
portal autorizado. La aceptación de producto de los siete sigue pendiente. Actualizar esta sección
al cerrar o reabrir un ticket:

1. Revisar y aceptar [UX-001](../evidencia/ux-001/README.md), [UX-002](../evidencia/ux-002/README.md), [UX-005](../evidencia/ux-005/README.md) y [UX-006](../evidencia/ux-006/README.md). El formato previo pendiente en 23 archivos no se cuenta como chequeo aprobado.
2. Revisar [UX-003](../evidencia/ux-003/README.md): 367 pruebas funcionales aprobadas; el formato global pendiente no se cuenta como chequeo aprobado.
3. Revisar [UX-004](../evidencia/ux-004/README.md): 491 pruebas aprobadas, 82 PostgreSQL omitidas y formato previo pendiente en 21 archivos.
4. Revisar [UX-007](../evidencia/ux-007/README.md): 12 ciclos TDD, 323 pruebas aprobadas y 14 capturas; formato previo pendiente en 21 archivos. Continuar con UX-008, siguiente ticket recomendado.
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
| 2026-09-12 | UX-000 | Todo → In Progress | Lectura completa del paquete, inspección de la base `428b6ad` y preparación de evidencia aislada. |
| 2026-09-12 | UX-000 | In Progress → In Review | [Servidor reproducible, siete recorridos, 17 capturas y 86 pruebas existentes aprobadas](../evidencia/ux-000/README.md). Sin cambios de producto; pendiente de confirmación de fronteras por el usuario. |
| 2026-09-12 | UX-000 | In Review → Done | El usuario responde «confirmo» al acuerdo F1/F2 y F3 condicional para UX-001, antes de escribir las pruebas nuevas. Preparación en `aeeb22e`. |
| 2026-09-12 | UX-001 | Todo → In Progress | Fronteras confirmadas, base limpia `aeeb22e` y regresión inicial de 62 pruebas aprobadas. |
| 2026-09-12 | UX-001 | In Progress → In Review | [Navegación por tareas, siete ciclos TDD, 197 pruebas funcionales aprobadas y siete capturas](../evidencia/ux-001/README.md). Diff local sin commit/PR; formato global pendiente por 25 archivos previos sin cambios. |
| 2026-09-12 | UX-001 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): implement task-oriented workspace navigation`. Se excluyen de Git las capturas, conservadas localmente y regenerables por Playwright. |
| 2026-09-12 | UX-005 | Todo → In Progress | Lectura del paquete sobre `e4eec65`; F1/F2/F3 confirmadas con «confirmo» antes de las pruebas nuevas. Primer ciclo: necesidad faltante, enlace de corrección y ejecución bloqueada. |
| 2026-09-12 | UX-005 | In Progress → In Review | [Preparación, fuentes, período y ejecución separados; ciclos TDD y 250 pruebas funcionales aprobadas](../evidencia/ux-005/README.md). 13 pruebas PostgreSQL omitidas; formato global pendiente en 24 archivos previos. Sin commit/PR nuevo. |
| 2026-09-12 | UX-005 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): guide variant preparation and execution`. Capturas excluidas de Git, conservadas localmente y regenerables por Playwright. |
| 2026-09-12 | UX-006 | Todo → In Progress | Lectura del paquete sobre `61dc87a`, 130 regresiones de base y F1/F2 confirmadas con «confirmo» antes de las pruebas nuevas. |
| 2026-09-12 | UX-006 | In Progress → In Review | [Resultado primero, diagnóstico, reintentos, tablas paginadas y comparación contextual](../evidencia/ux-006/README.md). 273 pruebas aprobadas; formato previo pendiente en 23 archivos. Capturas locales excluidas de Git. Sin commit/PR nuevo. |
| 2026-09-12 | UX-006 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): prioritize results and contextual run comparison`. Incluye implementación, pruebas, tutoriales y evidencia; capturas regenerables excluidas de Git. |
| 2026-09-12 | UX-002 | Todo → In Progress | Lectura del paquete sobre `9c24c1b`, 20 regresiones API de base y confirmación «Confirmo F1 y F2 para UX-002» antes de escribir la primera prueba. |
| 2026-09-12 | UX-002 | In Progress → In Review | [Edición por componente, conservación del documento, errores con foco y navegación protegida](../evidencia/ux-002/README.md). Ocho ciclos TDD y 243 pruebas aprobadas; formato previo pendiente en 23 archivos. Capturas locales regenerables excluidas de Git. Sin commit/PR nuevo. |
| 2026-09-12 | UX-002 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): add progressive model editing and protect unsaved changes`. Incluye implementación, pruebas, tutoriales y evidencia; capturas regenerables excluidas de Git. |
| 2026-09-14 | UX-004 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): connect catalog sources to model needs`. Incluye implementación, pruebas, tutoriales y evidencia; capturas regenerables excluidas de Git. |
| 2026-09-14 | UX-007 | Todo → In Progress | Lectura del paquete sobre `cf64106`, árbol limpio y F1/F2 confirmadas con «confirmo» antes de escribir pruebas nuevas; 70 regresiones de base aprobadas. |
| 2026-09-14 | UX-007 | In Progress → In Review | [Configuración conservada, flujo de informe y publicación explícita](../evidencia/ux-007/README.md). 12 ciclos TDD, 323 pruebas aprobadas y 14 capturas locales; formato previo pendiente en 21 archivos. Sin commit/PR nuevos. |
| 2026-09-14 | UX-007 | In Review → In Review | Commit solicitado por el usuario: `feat(ux): guide report configuration and explicit publication`. Incluye implementación, pruebas, tutoriales y evidencia; capturas regenerables excluidas de Git. |

## Control de entregas

El 2026-09-14, UX-004 pasó de Todo a In Progress tras confirmar F1/F2 y de
In Progress a In Review después de implementar el catálogo contextual y
comprobar la integración con preparación/ejecución. [Evidencia](../evidencia/ux-004/README.md):
234 frontend, 20 navegador y 237 Python aprobadas; 82 PostgreSQL omitidas.
El usuario solicitó el commit de UX-004; no se creó PR. TypeScript, ESLint y contrato generado pasan;
el fallo previo de formato global no se cuenta como aprobado.

| Entrega | Tickets previstos | Estado | Evidencia de integración |
| --- | --- | --- | --- |
| Primera mejora del flujo principal | UX-000, UX-001, UX-005, UX-006 | UX-000 Done; UX-001/005/006 In Review | [Línea base](../evidencia/ux-000/README.md), [UX-001](../evidencia/ux-001/README.md), [UX-005](../evidencia/ux-005/README.md) y [UX-006](../evidencia/ux-006/README.md); regresión conjunta del frontend y navegador aprobada, aceptación pendiente. |
| Modelo y datos | UX-002, UX-003, UX-004 | UX-002/003/004 In Review | [Importación](../evidencia/ux-003/README.md) y [catálogo contextual hasta ejecución](../evidencia/ux-004/README.md), con regresión conjunta del navegador; aceptación pendiente. |
| Informes y consola | UX-007, UX-008 | UX-007 In Review; UX-008 Todo | [Informe desde la ejecución elegida hasta el portal autorizado](../evidencia/ux-007/README.md), con regresión de navegador; aceptación pendiente. |
| Administración | UX-009 | Pendiente | — |

Estas agrupaciones orientan la entrega, no obligan a acumular todos los tickets en una sola PR. Cada entrega debe incluir la evidencia de integración correspondiente y conservar los criterios de reversión definidos en el plan.
