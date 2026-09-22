# REG-006: Limitar agua y energía por horizonte o día civil

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 7.
User stories covered: HU-06.

## What to build

Permitir que una regla imponga un presupuesto sobre integrales de caudal o
potencia en el horizonte completo o en días civiles de una zona horaria elegida.
El analista ve ventanas, unidades y presupuesto efectivo antes de aplicar;
el solver recibe la suma afín ponderada por duración.

## Acceptance criteria

- [x] El SDK ofrece ventanas reproducibles sobre la grilla y sumas afines; la configuración guarda zona IANA y política de ventanas parciales.
- [x] La integración de MW por horas produce MWh; m³/s por segundos produce m³ y admite conversión explícita a hm³. No se suma potencia/caudal sin duración como si fuera energía/volumen.
- [x] Días de 23/25 horas usan sus intervalos reales; la zona local sirve para agrupar, manteniendo identidades UTC en el snapshot.
- [x] Bordes de ventana desalineados con intervalos bloquean en esta versión. Días parciales requieren aceptación explícita de la ventana parcial y no prorratean el presupuesto.
- [x] Preview muestra inicio/fin, duración, términos incluidos, unidad y presupuesto de cada fila; ausencia de períodos o unidades incorrectas produce error localizado.
- [x] La regla puede agregar uno o varios componentes ya soportados; se conserva la atribución de términos y la política temporal en lineage.
- [x] Julia aplica las sumas y la solución satisface el presupuesto dentro de tolerancias, sin alterar balances ni el objetivo.

## Demonstration and validation

Fronteras TDD: se reutilizan las interfaces confirmadas en REG-002/003 y
documentadas en REG-005: HTTP autenticado con SQLite/PostgreSQL, editor React,
runtime OCI real y carga/solve públicos de Julia.

Limitar un volumen diario de turbinado y una energía total; comparar contra un
caso sin esas reglas. Cubrir duración variable, cambio horario, ventana parcial
y límites de día que corten un intervalo. Comprobar conversiones con valores
calculables a mano, además del recorrido real desde UI hasta solver.

## Evidencia de implementación (2026-09-22)

Implementación mediante ciclos rojo → verde en las fronteras anteriores. El SDK
`reg-006.1` expone `ctx.ventanas()`, `ventana.integral(variable)` y conversión
explícita `.a("hm3")`/`.a("m3")`. La capacidad `affine_budget.v1` conserva
ventanas, coeficientes dimensionales e identidades de objetos/períodos; la política
queda fijada en publicación, aplicación, snapshot y lineage. Se añadieron energía,
MWh y m³ al catálogo canónico, sin reservar identificadores.

- **11 pruebas nuevas Python**: seis HTTP sobre SQLite/PostgreSQL y cinco de OCI
  real. Cubren persistencia, publicación, aplicación, snapshot inmutable, cambio
  de horizonte, motor sin capacidad, duraciones variables, dos componentes,
  conversiones, ventanas vacías, unidades incorrectas y potencia sin integrar.
  Los días de **23/25 horas** se verificaron en Nueva York y Santiago, incluidos
  cambios a medianoche. Se comprobaron aceptación parcial sin prorrateo y rechazo
  de intervalos que cruzan el día.
- **147 pruebas Python distintas verificadas**, sin omisiones: la tanda de 127
  pruebas de reglas pasó 124 y encontró tres expectativas del SDK anterior;
  se actualizaron y pasaron al repetirlas. Las 19 del catálogo encontraron dos
  expectativas de dimensiones/unidades antiguas, se actualizaron y se repitió
  la suite completa satisfactoriamente. Se añadió después la prueba de errores
  localizados: la tanda final de **17 pruebas** REG-006/runtime pasó con la imagen
  definitiva. El lineage se volvió a comprobar en ambos motores. La regresión
  anual existente compiló 8784 períodos en **4,610 s** y rechazó 8785 en **3,730 s**.
- **50 comprobaciones Julia/HiGHS** de reglas aprobadas: 11 nuevas comprueban
  reducción de 105 a **12 MWh**, presupuesto de **36.000 m³**, balance completo
  de almacenamiento/turbinado/vertimiento, roundtrip del snapshot y rechazo de
  políticas ausentes, días parciales no aceptados, ventanas o términos inválidos.
- **75 pruebas React distintas aprobadas**: 74 en la tanda de siete archivos y
  una nueva tras el recorrido real, repetida junto con las de ComponentRules.
  Cubren configuración, consentimiento, retorno contextual, preview de 25 horas,
  presupuesto completo y paginación de términos. Chromium detectó que comparar
  políticas por `JSON.stringify` dejaba cambios pendientes al reordenar claves;
  se reprodujo en rojo y se corrigió comparando sus valores.
- **Chromium, API, OCI y Julia reales**: `component-rules-budgets.spec.ts` pasó
  en **5,2 minutos**, con datos temporales. En intervalos de 0,5, 2 y 1 horas se
  aplicaron **12 MWh**, luego **0,036 hm³ diarios** con aceptación parcial, y se
  recuperó el caso libre de **105 MWh / 504.000 m³** al desactivar. Las versiones
  históricas permanecieron intactas. Preview revisada visualmente.
- **53 pruebas de corridas, resultados e indexación** aprobadas. Build,
  TypeScript, ESLint, Prettier de archivos modificados y OpenAPI regenerado/
  `api:check` aprobados.
- **532 comprobaciones generales Julia** aprobadas en `test/runtests.jl`,
  incluidos los modelos existentes y los recorridos CLI (7 min 43 s).

Workflow y [operación/reproducción](../runtime.md) incluyen REG-006. Para adoptar
el SDK se reconstruye la imagen OCI, se fija su digest y se reinicia el worker.
Las publicaciones previas requieren publicar, probar y aplicar con el nuevo SDK.
No se ejecutó CI remoto ni hubo despliegue o cambios en bases de proyectos reales.
La siguiente issue por orden es REG-007: publicar una serie calculada.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
