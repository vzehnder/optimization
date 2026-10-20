# Tracker de implementación · Mesa de optimización

Fecha de creación: 2026-10-20.
Plan: [alcance y contratos](plan_implementacion.md).
Validación: [TDD y screenshots](validacion_tdd.md).

## Estado del trabajo

- Prototipo conceptual: aceptado por el usuario para avanzar a planificación.
- Desglose: aprobado por el usuario el 2026-10-20, manteniendo granularidad, dependencias y tipos.
- Implementación: no iniciada.
- Entregas: **14 planificadas · 0 en curso · 0 completadas**.
- Clasificación: **12 AFK y 2 HITL**.
- Capturas: dos referencias reales conservadas en [referencias](referencias/README.md).

Este es el tracker local solicitado; no se publicaron issues en GitHub ni otro
servicio externo. Se usa el formato de tickets del repositorio, con triage
ready-for-agent después de la aprobación explícita del desglose. Se conservan
las dependencias y las decisiones técnicas de MESA-001. Esto no asigna trabajo
ni inicia automáticamente la implementación.

## Registro de entregas

| Entrega | Tipo | Triage | Estado | Responsable | Dependencias directas | Historias |
| --- | --- | --- | --- | --- | --- | --- |
| [MESA-001 · Acordar el alcance de la mesa y sus contratos observables](issues/MESA-001-acordar-alcance-y-contratos.md) | HITL | ready-for-agent | Todo | — | Ninguna | HU-01, HU-05, HU-06, HU-11 |
| [MESA-002 · Abrir un caso real y consultar demanda en la mesa](issues/MESA-002-abrir-caso-y-demanda-real.md) | AFK | ready-for-agent | Todo | — | MESA-001 | HU-01, HU-03, HU-10, HU-11 |
| [MESA-003 · Guardar pestañas, paneles y distribución por caso](issues/MESA-003-persistir-pestanas-y-paneles.md) | AFK | ready-for-agent | Todo | — | MESA-002 | HU-02, HU-03, HU-10 |
| [MESA-004 · Consultar BESS, demanda y renovables por componente](issues/MESA-004-consultar-bess-y-renovables.md) | AFK | ready-for-agent | Todo | — | MESA-002 | HU-01, HU-03, HU-11 |
| [MESA-005 · Consultar centrales, embalses y otros objetos hidráulicos](issues/MESA-005-consultar-serie-hidraulica.md) | AFK | ready-for-agent | Todo | — | MESA-002 | HU-01, HU-03, HU-11 |
| [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](issues/MESA-006-editar-entradas-versionadas.md) | AFK | ready-for-agent | Todo | — | MESA-002 | HU-04, HU-10, HU-11 |
| [MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance](issues/MESA-007-ejecutar-caso-electrico-por-fechas.md) | AFK | ready-for-agent | Todo | — | MESA-004, MESA-006 | HU-05, HU-11 |
| [MESA-008 · Ejecutar una red hidráulica desde la misma mesa](issues/MESA-008-ejecutar-red-hidraulica.md) | AFK | ready-for-agent | Todo | — | MESA-005, MESA-006, MESA-007 | HU-05, HU-11 |
| [MESA-009 · Comparar entradas y resultados eléctricos con procedencia](issues/MESA-009-comparar-series-electricas.md) | AFK | ready-for-agent | Todo | — | MESA-007 | HU-03, HU-06 |
| [MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades](issues/MESA-010-comparar-series-hidraulicas.md) | AFK | ready-for-agent | Todo | — | MESA-008, MESA-009 | HU-03, HU-06 |
| [MESA-011 · Agregar y editar centrales y embalses ejecutables](issues/MESA-011-agregar-y-editar-activos-hidraulicos.md) | AFK | ready-for-agent | Todo | — | MESA-008, MESA-010 | HU-07, HU-05, HU-06 |
| [MESA-012 · Crear series manuales de apoyo y vincular entradas admitidas](issues/MESA-012-crear-series-manuales.md) | AFK | ready-for-agent | Todo | — | MESA-003, MESA-006 | HU-08, HU-04 |
| [MESA-013 · Recuperar ejecuciones y exportar la comparación](issues/MESA-013-historial-y-exportacion.md) | AFK | ready-for-agent | Todo | — | MESA-009, MESA-010 | HU-09, HU-06, HU-11 |
| [MESA-014 · Validar la mesa completa y habilitar su acceso en el producto](issues/MESA-014-aceptacion-visual-y-funcional.md) | HITL | ready-for-agent | Todo | — | MESA-003, MESA-011, MESA-012, MESA-013 | HU-01, HU-02, HU-03, HU-04, HU-05, HU-06, HU-07, HU-08, HU-09, HU-10, HU-11 |

## Desglose aprobado

1. **Acordar el alcance de la mesa y sus contratos observables** — HITL. Bloqueado por: ninguno. Historias: HU-01, HU-05, HU-06, HU-11.
2. **Abrir un caso real y consultar demanda en la mesa** — AFK. Bloqueado por: MESA-001. Historias: HU-01, HU-03, HU-10, HU-11.
3. **Guardar pestañas, paneles y distribución por caso** — AFK. Bloqueado por: MESA-002. Historias: HU-02, HU-03, HU-10.
4. **Consultar BESS, demanda y renovables por componente** — AFK. Bloqueado por: MESA-002. Historias: HU-01, HU-03, HU-11.
5. **Consultar centrales, embalses y otros objetos hidráulicos** — AFK. Bloqueado por: MESA-002. Historias: HU-01, HU-03, HU-11.
6. **Editar entradas en tablas y guardar revisiones auditables** — AFK. Bloqueado por: MESA-002. Historias: HU-04, HU-10, HU-11.
7. **Ejecutar un caso eléctrico por fechas y recuperar su avance** — AFK. Bloqueado por: MESA-004, MESA-006. Historias: HU-05, HU-11.
8. **Ejecutar una red hidráulica desde la misma mesa** — AFK. Bloqueado por: MESA-005, MESA-006, MESA-007. Historias: HU-05, HU-11.
9. **Comparar entradas y resultados eléctricos con procedencia** — AFK. Bloqueado por: MESA-007. Historias: HU-03, HU-06.
10. **Comparar resultados hidráulicos sin mezclar objetos o unidades** — AFK. Bloqueado por: MESA-008, MESA-009. Historias: HU-03, HU-06.
11. **Agregar y editar centrales y embalses ejecutables** — AFK. Bloqueado por: MESA-008, MESA-010. Historias: HU-07, HU-05, HU-06.
12. **Crear series manuales de apoyo y vincular entradas admitidas** — AFK. Bloqueado por: MESA-003, MESA-006. Historias: HU-08, HU-04.
13. **Recuperar ejecuciones y exportar la comparación** — AFK. Bloqueado por: MESA-009, MESA-010. Historias: HU-09, HU-06, HU-11.
14. **Validar la mesa completa y habilitar su acceso en el producto** — HITL. Bloqueado por: MESA-003, MESA-011, MESA-012, MESA-013. Historias: HU-01, HU-02, HU-03, HU-04, HU-05, HU-06, HU-07, HU-08, HU-09, HU-10, HU-11.

Revisión del desglose: el usuario respondió «Mantener el desglose propuesto» y
«Confirmar las interfaces propuestas» el 2026-10-20. Quedan aceptadas granularidad,
dependencias, tipos e interfaces S1/S2 y S3 condicional. Las decisiones técnicas
restantes siguen en MESA-001; no se dan por resueltas con esta confirmación.

## Dependencias

~~~mermaid
flowchart TD
  M001["001 · Decisiones"]
  M002["002 · Primera serie real"]
  M003["003 · Vistas persistidas"]
  M004["004 · Familias eléctricas"]
  M005["005 · Familias hidráulicas"]
  M006["006 · Edición real"]
  M007["007 · Run eléctrico"]
  M008["008 · Run hidráulico"]
  M009["009 · Comparación eléctrica"]
  M010["010 · Comparación hidráulica"]
  M011["011 · Activos hidráulicos"]
  M012["012 · Series manuales"]
  M013["013 · Historial y CSV"]
  M014["014 · Aceptación final"]
  M001 --> M002
  M002 --> M003
  M002 --> M004
  M002 --> M005
  M002 --> M006
  M004 --> M007
  M006 --> M007
  M005 --> M008
  M006 --> M008
  M007 --> M008
  M007 --> M009
  M008 --> M010
  M009 --> M010
  M008 --> M011
  M010 --> M011
  M003 --> M012
  M006 --> M012
  M009 --> M013
  M010 --> M013
  M003 --> M014
  M011 --> M014
  M012 --> M014
  M013 --> M014
~~~

## Frontera y orden sugerido

Hoy puede revisarse **MESA-001**. La primera implementación es **MESA-002** una vez
resueltas sus decisiones. Después de MESA-002, las entregas de vistas, familias
eléctricas, familias hidráulicas y edición tienen dependencias satisfechas entre
sí; deben coordinar los contratos que comparten.

Orden de recorrido recomendado: 001 → 002 → (003, 004, 005, 006) → 007 → 008 →
009 → 010 → 011 → 013 → 014. MESA-012 puede tomarse desde que estén completas
003 y 006. Este orden es orientativo; mandan las dependencias directas del registro.

MESA-001 puede añadir una entrega de motor si se requiere una cooptimización mixta
no soportada. Actualizar el grafo, el registro y los bloqueos de las corridas antes
de seguir; no ocultar esa extensión dentro de una tarea de interfaz.

## Cómo mantener el tracker

1. Antes de tomar una entrega, comprobar que sus dependencias están Done y que las
   interfaces de prueba necesarias fueron confirmadas. Asignar responsable y pasar
   a In Progress tanto aquí como en el ticket.
2. Trabajar por comportamiento: un test rojo, la implementación mínima y verde.
   Las tareas auxiliares de esquema/API/UI pertenecen a la misma entrega vertical.
3. Registrar comandos, evidencias, decisiones y resultados en el ticket. Capturas
   nuevas van a evidencia de implementación; las referencias originales se conservan.
4. Si falta una decisión o integración externa, usar Blocked con motivo concreto y
   condición de desbloqueo. No marcar Blocked solo porque existe una dependencia futura.
5. Pasar a In Review cuando se cumplan criterios y pruebas. Cerrar Done después de
   la revisión; HITL requiere su conformidad humana documentada.
6. Actualizar registro, contador y bitácora al cerrar. No marcar criterios ni tests
   como aprobados solo por existir en el plan.

## Estados y clasificación

- Todo: trabajo no iniciado; puede tener dependencias pendientes.
- In Progress: tiene responsable y trabajo activo.
- Blocked: existe un impedimento concreto documentado.
- In Review: implementación/evidencia lista para revisión.
- Done: criterios satisfechos y revisión aceptada.

AFK: implementable con los contratos ya acordados sin decisiones de producto
adicionales. HITL: requiere decisión o aceptación del usuario. El triage
ready-for-agent indica preparación del ticket, no que sus dependencias estén listas.

## Bitácora

| Fecha | Entrega | Cambio | Evidencia / nota |
| --- | --- | --- | --- |
| 2026-10-20 | Referencia | Prototipo conceptual aceptado | El usuario indicó «me parece bien» y pidió plan local con tracker. No equivale a aprobación del desglose posterior. |
| 2026-10-20 | Todas | Propuesta creada | 14 tickets verticales; implementación no iniciada. |
| 2026-10-20 | Validación | Referencias conservadas | Dos PNG, HTML congelado y estrategia TDD. |
| 2026-10-20 | Todas | Desglose aprobado | El usuario confirmó mantener granularidad, dependencias y tipos; triage actualizado a ready-for-agent. |
| 2026-10-20 | MESA-001 / TDD | Interfaces confirmadas | S1 navegador, S2 HTTP y S3 público de Julia solo si cambia el motor. No volver a pedir el mismo acuerdo. |
| 2026-10-20 | Documentación | Verificada | 14 tickets enlazados, 110 enlaces locales resueltos, dependencias sin ciclos y hashes de dos PNG 1440×900 y HTML comprobados. No son pruebas de la implementación. |
