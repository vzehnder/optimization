# REG-003: Calcular mínimos y máximos horarios desde series versionadas

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5, 6 y 7.
User stories covered: HU-03, HU-09.

## What to build

Permitir seleccionar entradas del catálogo o del objeto para una regla y escribir
límites horarios calculados. El analista vincula afluente/disponibilidad, define
parámetros y compara las curvas calculadas antes de aplicarlas a una corrida.
La selección usa revisiones canónicas exactas y conserva sus reglas de propiedad,
compatibilidad y obsolescencia. Esta entrega completa el MVP de límites horarios.

## Acceptance criteria

- [x] Cada puerto declara alias, dimensión/semántica y contexto de objeto; la selección persiste identidad, revisión sellada y hash mediante el contrato canónico.
- [x] La UI ofrece solo entradas autorizadas/compatibles y distingue series genéricas de específicas. La API vuelve a verificar pertenencia, revisión y hash.
- [x] Python combina entradas y parámetros por período; la preview muestra mínimos, máximos y salidas numéricas en tabla/gráfico con unidades, sin publicar series todavía.
- [x] Se comprueba toda la grilla: faltantes, duplicados, duración incompatible, cobertura insuficiente, valores no finitos y unidades incompatibles bloquean con período/alias. No hay resampling o relleno implícito.
- [x] Un mínimo mayor que un máximo conocido para la misma variable/período se identifica antes del solve, incluyendo la intersección con límites físicos conocidos; no se promete detectar toda infactibilidad.
- [x] Una publicación nueva de una entrada vuelve obsoleta la validación; no mueve el pin. Revalidar la revisión antigua con motivo o seleccionar otra produce nueva evidencia antes de ejecutar.
- [x] Las restricciones horarias llegan a Julia y el snapshot conserva entradas, cálculos, parámetros y lineage; cambios posteriores no alteran una corrida guardada.
- [x] La clasificación añade únicamente las unidades/tipos necesarios que falten, de forma aditiva y compatible con TS-7.
- [x] Un horizonte anual dentro de cuotas y otro que las exceda tienen comportamiento medido y acotado; preview paginada y cancelación no truncan la validación real.

## Demonstration and validation

Calcular máximo como capacidad por disponibilidad y mínimo como fracción de un
afluente permitido por el puerto. Resolver y comprobar ambos límites por período.
Introducir un hueco, una revisión nueva y un cruce mínimo/máximo; verificar los
tres bloqueos en UI/API. Probar persistencia en ambos motores, resultados Julia,
concurrencia durante compilación y mediciones del runtime real.

### Evidencia de implementación (2026-09-22)

Se reutilizaron las interfaces de TDD confirmadas en REG-002: HTTP con SQLite y
PostgreSQL, editor React, runtime OCI real y carga/optimización pública de Julia.
Los ciclos rojo–verde incorporaron pins canónicos, cálculos horarios, bloqueos de
grilla y cotas, snapshots y revalidación. Una prueba de actualización detectó la
colisión con un tipo personalizado en el ID 9: la extensión del catálogo ahora
asigna identidades libres por clave y conserva datos existentes. Chromium detectó
el falso estado de cambios pendientes tras reemplazar una entrada y una lectura
de contexto sin el bloqueo de conexión usado por el worker; ambos se corrigieron.

- Python: **102 pruebas aprobadas sin omisiones** de REG-001/002/003 y catálogo
  TS7-001; **25** pertenecen a REG-003. Los contratos HTTP se ejecutaron sobre
  SQLite y PostgreSQL 18 aislado. Incluyen señales específicas de otra unidad,
  fuentes privadas de otro proyecto, revisiones/hash falsificados, huecos,
  duraciones, zona horaria, cotas físicas, snapshots y publicación concurrente
  durante materialización, sin crear versión/corrida parcial. Se repitieron los
  contratos HTTP afectados tras proteger las lecturas; el caso adicional de
  instantes UTC duplicados con offsets distintos pasó en ambos motores.
- Runtime: Docker 28.5.1 sobre Ubuntu WSL, CPython 3.12.14 y SDK `reg-003.1`, con
  imagen fijada por digest. **8784 períodos**, **17568 filas** y **17568 salidas**
  completos en **4,103 s**; **8785** rechazados en **3,281 s**, medidos como tiempo
  de pared del ejecutor. Cancelar no entrega resultados parciales. Las operaciones
  no lineales sobre datos conocidos también se verificaron en el contenedor.
- Julia: **21 comprobaciones aprobadas** en `test/component_rules.jl`, con
  Julia 1.11.7/HiGHS. Capacidad 20 por disponibilidad `[1, 0.5, 0.75, 1]` produce
  caudales `[20, 10, 15, 20]`; afluente `[8, 12, 16, 20]` por fracción 0.25 produce
  mínimos `[2, 3, 4, 5]`, alcanzados al valorar el agua almacenada. Se conserva
  exactamente el bloque de reglas al guardar el resultado.
- React: **67 pruebas aprobadas** entre `ComponentRules`, `HourlyRules`,
  `RunExperience` y `ProtectedMutationJourney`. Selección en cuatro pasos sin
  escritura anticipada, paginación, unidades, obsolescencia y errores localizados.
  TypeScript, ESLint, Prettier de archivos modificados, build y OpenAPI
  regenerado/`api:check` verificados.
- Chromium: `component-rules-hourly.spec.ts` aprobado con API, OCI y Julia reales
  sobre datos temporales. Selecciona ambas entradas, publica/aplica/resuelve,
  comprueba los cuatro máximos, publica una entrada nueva, bloquea la corrida,
  revalida el pin anterior con motivo y localiza hueco en período 4 y cruce en
  período 3. Comprueba que la versión histórica sigue idéntica. Capturas de
  preview y rechazo revisadas visualmente.

Workflow y [operación/reproducción](../runtime.md) actualizados. No se ejecutó CI
remoto ni se repitieron las suites globales de Julia/frontend. No hubo despliegue
ni cambios en bases de proyectos. La publicación de salidas como series queda
en REG-007; la siguiente issue por orden es REG-004.

## Blocked by

- [REG-002](REG-002-aplicar-limite-caudal.md).
