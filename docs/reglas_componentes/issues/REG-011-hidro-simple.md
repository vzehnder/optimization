# REG-011: Usar reglas Python en componentes hidro del modelo v2

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 2, 5 y 6.
User stories covered: HU-11.

## What to build

Llevar el mismo recorrido de reglas al componente `hydro` del modelo de despacho
v2: caudal turbinado, vertimiento, potencia y volumen almacenado. El analista
reutiliza operadores y plantillas compatibles sin conocer la diferencia entre
adaptadores Julia. La integración respeta el balance eléctrico y las relaciones
hidráulicas que ese modelo ya impone.

## Acceptance criteria

- [x] La superficie contextual ofrece únicamente variables/unidades reales del componente v2; el contrato excluye altura/cota de la API inicial aunque el motor tenga detalles internos adicionales.
- [x] Los mismos puertos, parámetros, operadores, revisiones y permisos atraviesan editor, API, materialización, carga/normalización y solve v2.
- [x] Un pin registra tipo/esquema de objeto y capacidades requeridas; no se interpreta una identidad v3 como si fuera un componente v2.
- [x] Restricciones afines se agregan sobre variables existentes conservando curvas/modos y balances base; no amplían el soporte de curvas ni suprimen binarias internas.
- [x] Plantillas compatibles pueden aplicarse mediante remapeo explícito; una capacidad no soportada se rechaza antes del solve con explicación visible.
- [x] El snapshot y resultados identifican el adaptador/contrato usado; un motor antiguo no puede ignorar el bloque de reglas.
- [x] Casos v1/v2 sin reglas y casos hidráulicos v3 conservan su comportamiento; las pruebas cubren ambos caminos y sus lectores de contrato.

## Demonstration and validation

Aplicar una regla de caudal horario a un hidro v2 y comprobar potencia, volumen
y balance eléctrico de la solución. Reutilizar la intención de una plantilla
v3 con selección explícita del objeto v2; rechazar mezcla de referencias de
dos snapshots. Probar roundtrip/solve Julia y el recorrido contextual real.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).

## Implementación y fronteras TDD (2026-09-24)

Se reutilizan las fronteras confirmadas en REG-008/009: HTTP autenticado sobre
SQLite/PostgreSQL, runtime OCI real, React/navegador y contratos públicos Julia.
Los ciclos rojo → verde cubren el contexto v2, sus cuatro variables, entradas
horarias, pins, negociación de capacidades, remapeo de plantillas y alias,
clonación de variantes, selección independiente de snapshots v2/v3 y cumplimiento.

El editor del hidro simple ofrece el acceso contextual después de guardar.
`ctx.objeto` expone `caudal`, `vertimiento`, `potencia` y `almacenamiento`, con
unidades canónicas; cota/altura permanecen excluidas. Los puertos de afluente y
disponibilidad se añaden al catálogo canónico por claves, sin reasignar IDs.
Se conservan permisos, propiedad de entradas, revisiones selladas y obsolescencia.

Los pins v2 registran `hydro_v2.v1`, esquema, tipo/identidad del componente y
capacidades requeridas. Julia conserva el bloque al cargar, normalizar, resolver
y escribir el caso resuelto, y registra adaptador/contrato en el resumen.
Las restricciones se agregan a las variables físicas existentes. La negociación
se verifica al materializar y nuevamente en el worker antes de ejecutar el solve;
un motor antiguo falla con `RULE_CAPABILITY_UNSUPPORTED`.

Las plantillas de unidades v3 pueden reutilizarse con destinos elegidos
explícitamente; las revisiones existentes ganan compatibilidad con el adaptador
sin mover sus pins. Cada alias exige variables compatibles y pertenencia al
snapshot elegido. Cuando un escenario contiene ambos editores, el objeto de
origen determina el snapshot. Clonar conserva pins y exige revalidación.

No cambia el SDK ni la imagen OCI; se mantiene `reg-006.1`. No se añaden tablas
ni variables físicas, ni se habilitan consolas/programaciones (REG-014).

## Evidencia de entrega

- **26 pruebas nuevas aprobadas**, 13 por motor SQLite/PostgreSQL, con OCI real.
  Incluyen las cuatro variables y entradas horarias, permisos/proyecto, cota
  excluida, obsolescencia, snapshots separados, clonación, remapeo de plantillas
  y alias, negociación antes de encolar y rechazo de un worker antiguo.
- **610 comprobaciones Julia aprobadas**: 24 nuevas, 50 de reglas hidráulicas,
  4 de resultados primales y 532 generales. La curva no convexa conserva
  `[0,75; 0,65] MW` para caudales fijados en `[4; 6] m³/s`, además de
  vertimiento, volumen, balance eléctrico y el comportamiento base sin reglas.
- **130 pruebas React aprobadas**, además del build/TypeScript y ESLint completo.
- **Chromium real aprobado**, con API, OCI y Julia sobre una base temporal:
  el recorrido contextual aplica ocho restricciones; los máximos horarios de
  `[4; 6] m³/s` producen `[0,4; 0,6] MW`, almacenamiento
  `[2,5936; 2,68] hm³` y ocho filas cumplidas. La repetición final pasó en
  1,9 minutos. Capturas `frontend/test-results/reg011-applied.png` y
  `frontend/test-results/reg011-compliance.png` inspeccionadas visualmente.
- **95 pruebas de regresión de reglas** y **71 de corridas/resultados/catálogo**
  aprobadas. Se actualizaron dos expectativas afectadas: el catálogo ahora tiene
  tres compatibilidades adicionales y el motor simulado del test de timeout
  debe anunciar soporte de reglas. Ambas repeticiones pasaron. La regresión de
  reglas omitió 23 duplicados PostgreSQL y el catálogo omitió 2 pruebas de ese
  motor; las 13 nuevas de REG-011 sí se ejecutaron en PostgreSQL sin omisiones.
- OpenAPI regenerado y `api:check`, compilación Python, `git diff --check` y
  Prettier de archivos modificados aprobados. `npm run check` llega hasta el
  chequeo de formato y señala 17 archivos preexistentes ajenos a esta entrega,
  los mismos documentados en REG-007/008; no se reformatearon.

CI incluye las pruebas HTTP, Julia y navegador de esta entrega. No se ejecutó
CI remoto ni se modificaron proyectos reales. [Operación y reproducción](../runtime.md).
La siguiente issue por orden es **REG-012: baterías**.
