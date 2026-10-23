# Tracker de implementación · Mesa de optimización

Fecha de creación: 2026-10-20.
Plan: [alcance y contratos](plan_implementacion.md).
Validación: [TDD y screenshots](validacion_tdd.md).

## Estado del trabajo

- Prototipo conceptual: aceptado por el usuario para avanzar a planificación.
- Desglose: aprobado por el usuario el 2026-10-20, manteniendo granularidad, dependencias y tipos.
- Implementación funcional: MESA-002 a MESA-011 Done, demanda real, vistas persistidas, consulta eléctrica/hidráulica, edición versionada, ejecución recuperable, comparación histórica y creación/edición de activos hidráulicos ejecutables con TDD; [contratos de MESA-001](decision_record_mesa001.md) aceptados por el usuario el 2026-10-20.
- Entregas: **14 planificadas · 0 Todo · 0 en curso · 1 en revisión · 13 completadas**.
- MESA-014 In Review: ayuda, recorrido completo, regresiones y capturas listas; conformidad humana y baseline pendientes. [Evidencia de aceptación](evidencia/MESA-014/validacion.md).
- MESA-013 Done: historial autorizado y CSV de vistas/rango con procedencia, recuperación y once ciclos TDD; [evidencia](evidencia/MESA-013/validacion.md).
- MESA-012 Done: series manuales canónicas de apoyo, edición versionada y vínculos explícitos compatibles; trece ciclos TDD, [capturas y límites](evidencia/MESA-012/validacion.md).
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
| [MESA-001 · Acordar el alcance de la mesa y sus contratos observables](issues/MESA-001-acordar-alcance-y-contratos.md) | HITL | ready-for-agent | Done | Codex | Ninguna | HU-01, HU-05, HU-06, HU-11 |
| [MESA-002 · Abrir un caso real y consultar demanda en la mesa](issues/MESA-002-abrir-caso-y-demanda-real.md) | AFK | ready-for-agent | Done | Codex | MESA-001 | HU-01, HU-03, HU-10, HU-11 |
| [MESA-003 · Guardar pestañas, paneles y distribución por caso](issues/MESA-003-persistir-pestanas-y-paneles.md) | AFK | ready-for-agent | Done | Codex | MESA-002 | HU-02, HU-03, HU-10 |
| [MESA-004 · Consultar BESS, demanda y renovables por componente](issues/MESA-004-consultar-bess-y-renovables.md) | AFK | ready-for-agent | Done | Codex | MESA-002 | HU-01, HU-03, HU-11 |
| [MESA-005 · Consultar centrales, embalses y otros objetos hidráulicos](issues/MESA-005-consultar-serie-hidraulica.md) | AFK | ready-for-agent | Done | Codex | MESA-002 | HU-01, HU-03, HU-11 |
| [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](issues/MESA-006-editar-entradas-versionadas.md) | AFK | ready-for-agent | Done | Codex | MESA-002 | HU-04, HU-10, HU-11 |
| [MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance](issues/MESA-007-ejecutar-caso-electrico-por-fechas.md) | AFK | ready-for-agent | Done | Codex | MESA-004, MESA-006 | HU-05, HU-11 |
| [MESA-008 · Ejecutar una red hidráulica desde la misma mesa](issues/MESA-008-ejecutar-red-hidraulica.md) | AFK | ready-for-agent | Done | Codex | MESA-005, MESA-006, MESA-007 | HU-05, HU-11 |
| [MESA-009 · Comparar entradas y resultados eléctricos con procedencia](issues/MESA-009-comparar-series-electricas.md) | AFK | ready-for-agent | Done | Codex | MESA-007 | HU-03, HU-06 |
| [MESA-010 · Comparar resultados hidráulicos sin mezclar objetos o unidades](issues/MESA-010-comparar-series-hidraulicas.md) | AFK | ready-for-agent | Done | Codex | MESA-008, MESA-009 | HU-03, HU-06 |
| [MESA-011 · Agregar y editar centrales y embalses ejecutables](issues/MESA-011-agregar-y-editar-activos-hidraulicos.md) | AFK | ready-for-agent | Done | Codex | MESA-008, MESA-010 | HU-07, HU-05, HU-06 |
| [MESA-012 · Crear series manuales de apoyo y vincular entradas admitidas](issues/MESA-012-crear-series-manuales.md) | AFK | ready-for-agent | Done | Codex | MESA-003, MESA-006 | HU-08, HU-04 |
| [MESA-013 · Recuperar ejecuciones y exportar la comparación](issues/MESA-013-historial-y-exportacion.md) | AFK | ready-for-agent | Done | Codex | MESA-009, MESA-010 | HU-09, HU-06, HU-11 |
| [MESA-014 · Validar la mesa completa y habilitar su acceso en el producto](issues/MESA-014-aceptacion-visual-y-funcional.md) | HITL | ready-for-agent | In Review | Codex | MESA-003, MESA-011, MESA-012, MESA-013 | HU-01, HU-02, HU-03, HU-04, HU-05, HU-06, HU-07, HU-08, HU-09, HU-10, HU-11 |

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
dependencias, tipos e interfaces S1/S2 y S3 condicional. Esa confirmación inicial
no resolvía las decisiones técnicas de MESA-001; quedaron aceptadas después,
con el «confirmo» del usuario al registro de contratos del mismo día.

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

**MESA-001 a MESA-011 están Done**. Los [contratos aceptados](decision_record_mesa001.md)
se concretan en la [consulta de demanda real](evidencia/MESA-002/validacion.md)
y la [persistencia de vistas](evidencia/MESA-003/validacion.md), ampliadas con
[consulta eléctrica por componente](evidencia/MESA-004/validacion.md) y
[consulta hidráulica por identidad](evidencia/MESA-005/validacion.md) y
[edición de entradas versionadas](evidencia/MESA-006/validacion.md) y
[ejecución eléctrica recuperable](evidencia/MESA-007/validacion.md) y
[ejecución de red hidráulica desde versión promovida](evidencia/MESA-008/validacion.md) y
[comparación eléctrica con procedencia congelada](evidencia/MESA-009/validacion.md) y
[comparación hidráulica por entidad y topología](evidencia/MESA-010/validacion.md) y
[creación y edición de activos hidráulicos ejecutables](evidencia/MESA-011/validacion.md).
**MESA-013 también está Done**, con [historial y exportación](evidencia/MESA-013/validacion.md).
**MESA-012 también está Done**, con [series manuales y vínculos explícitos](evidencia/MESA-012/validacion.md).
**MESA-014 está In Review**: sus cuatro dependencias están Done y la evidencia
funcional/visual está preparada. La suite MESA pasó 53/53, incluido el recorrido
hidráulico con espera ajustada; se conserva su aceptación humana HITL antes de
fijar baselines y cerrar Done. No hay otra entrega Todo en este corte.

Orden de recorrido recomendado: 001 → 002 → (003, 004, 005, 006) → 007 → 008 →
009 → 010 → 011 → 013 → 012 → 014. MESA-012 podía tomarse desde que estuvieran
completas 003 y 006. Este orden es orientativo; mandan las dependencias directas del registro.

El alcance aceptado usa los modelos existentes: hidro simple v2 en el balance
eléctrico y red v3 por su camino propio. La cooptimización mixta de red v3 queda
fuera del primer corte; se mantienen las 14 entregas y sus dependencias.

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
| 2026-10-21 | MESA-014 | Todo → In Progress → In Review | Seis ciclos TDD de ayuda y disposición visible, recorrido eléctrico completo ampliado, acceso existente y rutas anteriores verificados. 139 Python distintas, 336 Vitest, 53 MESA y cinco regresiones generales; revisión visual final 4/4 y recorrido real adicional 1/1. Capturas y diferencias listas para conformidad HITL; baseline y Done pendientes de esa aceptación. [Evidencia](evidencia/MESA-014/validacion.md). |
| 2026-10-20 | Referencia | Prototipo conceptual aceptado | El usuario indicó «me parece bien» y pidió plan local con tracker. No equivale a aprobación del desglose posterior. |
| 2026-10-20 | Todas | Propuesta creada | 14 tickets verticales; implementación no iniciada. |
| 2026-10-20 | Validación | Referencias conservadas | Dos PNG, HTML congelado y estrategia TDD. |
| 2026-10-20 | Todas | Desglose aprobado | El usuario confirmó mantener granularidad, dependencias y tipos; triage actualizado a ready-for-agent. |
| 2026-10-20 | MESA-001 / TDD | Interfaces confirmadas | S1 navegador, S2 HTTP y S3 público de Julia solo si cambia el motor. No volver a pedir el mismo acuerdo. |
| 2026-10-20 | Documentación | Verificada | 14 tickets enlazados, 110 enlaces locales resueltos, dependencias sin ciclos y hashes de dos PNG 1440×900 y HTML comprobados. No son pruebas de la implementación. |
| 2026-10-20 | MESA-001 | In Progress → In Review | Codex tomó la siguiente issue por instrucción del usuario y preparó el registro de contratos. Revisión HITL pendiente; no se inicia MESA-002. |
| 2026-10-20 | MESA-001 | Capacidades e integración verificadas | v2 incluye hidro simple en el balance eléctrico; v3 es red hidráulica separada. Simulación/progreso ya integrados en `d206e78`. 29 pruebas Python verificadas entre ejecución inicial y reintento de 2 pruebas Julia; 6 regresiones React OK. Detalle en el ticket. |
| 2026-10-20 | MESA-001 | Demostración y documentos verificados | Casos CLI v1/v2 con Julia real: OPTIMAL. 20 Markdown, 14 tickets, 130 enlaces locales y grafo sin ciclos; hashes y dimensiones originales de referencias conservados. |
| 2026-10-20 | MESA-001 | In Review → Done | El usuario respondió «confirmo» a los contratos propuestos con los modelos actuales. Conformidad HITL registrada; no se exige cooptimización mixta de red v3 en este corte. MESA-002 queda con su dependencia satisfecha. |
| 2026-10-20 | MESA-002 | Todo → In Progress → In Review | Implementación solicitada por el usuario; S1/S2 ya confirmadas. Seis ciclos rojo → verde: consulta real, recorrido UI, cobertura HTTP/UI, fuente de variante anterior y panel visible. |
| 2026-10-20 | MESA-002 | In Review → Done | Revisión técnica AFK y capturas completadas. 7 tests HTTP nuevos, 3 de navegador, 336 Vitest, 37 Python OK y 4 regresiones de navegador. 5 PostgreSQL omitidos; formato global pendiente en 16 archivos ajenos, formato modificado/TypeScript/ESLint/OpenAPI OK. [Evidencia](evidencia/MESA-002/validacion.md). Siguiente: MESA-003. |
| 2026-10-20 | MESA-003 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario, con S1/S2 confirmadas. Nueve ciclos rojo → verde; cinco tests HTTP y siete de navegador nuevos. 42 Python OK, cinco PostgreSQL omitidos; 10 MESA y cuatro regresiones de navegador OK; 336 Vitest verificadas entre ejecución inicial y dos reintentos. Migración, capturas y revisión AFK en [evidencia](evidencia/MESA-003/validacion.md). Siguiente: MESA-004. |
| 2026-10-20 | MESA-004 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario con S1/S2 confirmadas. Doce ciclos rojo → verde; diez tests HTTP y tres de navegador nuevos. 93 Python OK, cinco PostgreSQL omitidos; 13 MESA, cuatro regresiones de navegador y 336 Vitest OK. Consulta por activo v1/v2, parámetros escalares, zona congelada y fallback a CSV. Fixture TS-4 reparada; capturas y revisión AFK en [evidencia](evidencia/MESA-004/validacion.md). Siguiente: MESA-005. |
| 2026-10-20 | MESA-005 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario con S1/S2 confirmadas. Dieciséis ciclos rojo → verde; diecisiete tests HTTP y dos de navegador nuevos. 172 Python distintos verificados entre ejecución amplia y focalizada, cinco PostgreSQL omitidos; 15 MESA y cinco regresiones de navegador OK. 336 Vitest verificadas entre suite y reintento de foco. Inventario, entradas y resultados hidráulicos por identidad; revisión AFK, capturas y límites en [evidencia](evidencia/MESA-005/validacion.md). Siguiente: MESA-006. |
| 2026-10-20 | MESA-006 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario con S1/S2 confirmadas. Quince ciclos rojo → verde; quince tests HTTP y cinco de navegador nuevos. 142 Python OK, 62 PostgreSQL omitidos; 20 MESA, cinco regresiones de navegador y 336 Vitest OK. Edición canónica atómica, copia local, conflictos recuperables y borrador protegido al navegar/reconectar. Revisión AFK, capturas y límites en [evidencia](evidencia/MESA-006/validacion.md). Siguiente: MESA-007. |
| 2026-10-20 | MESA-007 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario con S1/S2 confirmadas. Trece ciclos rojo → verde; dieciocho tests HTTP y tres de navegador nuevos. 151 Python OK y cinco PostgreSQL omitidos; 23 MESA y cinco regresiones de navegador OK. 336 Vitest verificadas entre suite 335/336 y reintento del archivo con foco intermitente 4/4. Preparación por fechas, snapshot atómico, idempotencia, recarga y ejecución de éxito/fallo con Julia/worker reales. Revisión AFK, capturas y límites en [evidencia](evidencia/MESA-007/validacion.md). Siguiente: MESA-008. |
| 2026-10-21 | MESA-008 | Todo → In Progress → In Review → Done | Implementada por instrucción del usuario con S1/S2 confirmadas. Nueve ciclos rojo → verde; once tests HTTP y tres de navegador nuevos. 145 Python, 26 MESA, cinco regresiones de navegador y 336 Vitest OK. Fuente v3 explícita, opciones económicas, remuestreo, snapshot/diagrama/run atómicos, idempotencia y recuperación; potencia y volumen con worker/Julia reales. Revisión AFK, cuatro capturas y límites en [evidencia](evidencia/MESA-008/validacion.md). Siguiente: MESA-009. |
| 2026-10-21 | MESA-009 | Todo → In Progress → In Review → Done | Nueve ciclos rojo → verde; diez tests HTTP y cuatro de navegador nuevos. Comparación eléctrica desde snapshot, referencia explícita, Δ compatible y lecturas concurrentes coordinadas. 145 Python distintas verificadas entre suite/reintentos, 30/30 MESA, cinco regresiones generales y 336/336 Vitest. Revisión AFK, capturas 1440/390, restricciones de Julia y formato previo en [evidencia](evidencia/MESA-009/validacion.md). Siguiente: MESA-010. |
| 2026-10-21 | MESA-010 | Todo → In Progress → In Review → Done | Trece ciclos rojo → verde; trece tests HTTP y dos de navegador nuevos. Comparación hidráulica con identidad/topología congeladas, parámetros escalares, Δ compatible y unidades separadas. 129 Python OK, incluyendo dos corridas reales en una prueba HTTP; 32 MESA y cinco regresiones generales OK, seis comparaciones revalidadas tras ajuste móvil. Vitest 335/336 y reintento con el fallo de foco previo de ReportExperience; formato global mantiene 16 archivos ajenos. Revisión AFK, capturas y límites en [evidencia](evidencia/MESA-010/validacion.md). Siguiente: MESA-011. |
| 2026-10-21 | MESA-011 | Todo → In Progress → In Review → Done | Diez ciclos rojo → verde; una prueba HTTP y nueve de navegador nuevas. Editor hidráulico integrado, identidad estable, borradores protegidos, vigencia de preparación y snapshots conservados. Embalse y central nuevos ejecutados con Julia real: 10 MW y 4,9352 hm³ finales. 188 Python, 41 MESA y cinco regresiones generales OK; Vitest 335/336 por fallo de foco previo y formato global pendiente en 16 archivos ajenos. Revisión técnica/visual AFK, capturas 1440/390 y límites en [evidencia](evidencia/MESA-011/validacion.md). Siguiente: MESA-013; MESA-012 también lista por dependencias. |
| 2026-10-21 | MESA-013 | Todo → In Progress → In Review → Done | Once ciclos rojo → verde; diez pruebas HTTP y seis de navegador nuevas. Historial autorizado, recuperación de entidades archivadas, rango común y CSV de vistas visibles con procedencia, ausencia explícita y protección de planillas. 135 Python distintas, 47 MESA, cinco regresiones generales y 336 Vitest verificadas; Julia revalidada fuera del sandbox. Revisión AFK, capturas y límites en [evidencia](evidencia/MESA-013/validacion.md). Siguiente: MESA-012. |
| 2026-10-21 | MESA-012 | Todo → In Progress → In Review → Done | Trece ciclos rojo → verde; once pruebas HTTP y cinco de navegador nuevas. Series manuales canónicas, apoyo persistido, revisiones y vínculo explícito con snapshots conservados. 129 Python distintas, 336 Vitest entre suite/reintento, cinco regresiones generales y 51/52 MESA; la prueba hidráulica de 120 s pasa en una copia temporal con mayor espera. Última revisión visual y funcional 9/9, build/contratos/lint OK; 33 PostgreSQL omitidas y formato previo en 16 archivos ajenos. Revisión AFK, capturas y límites en [evidencia](evidencia/MESA-012/validacion.md). Siguiente: MESA-014, HITL con dependencias satisfechas. |
