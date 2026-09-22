# REG-005: Expresar rampas y relaciones con períodos anteriores

Status: Done
Type: AFK
Triage: ready-for-agent
Source: [Plan](../plan.md), secciones 5 y 7.
User stories covered: HU-05.

## What to build

El analista escribe restricciones entre períodos, empezando por rampas de subida
y bajada de generación o caudal. Declara la política del primer período y
previsualiza cuáles están cubiertos. Las referencias temporales se compilan a
filas afines del mismo contrato y producen resultados observables en la corrida.

## Acceptance criteria

- [x] El SDK permite referencias anteriores y diferencias con índices/instantes verificables; nunca interpreta un índice negativo como el último período.
- [x] Las rampas declaran unidades como MW/h o m³/s por hora, verificadas contra variable y tiempo; las dos direcciones se expresan con restricciones afines separadas.
- [x] El cálculo usa la distancia entre inicios de intervalos definida en el plan, también con duraciones variables; no asume siempre una hora.
- [x] La política inicial es explícita: omitir visiblemente la primera comparación o proporcionar valor inicial con unidad e instante. No se inventa generación/caudal previo.
- [x] Al cambiar horizonte se regeneran referencias y validación; el snapshot conserva política, valor inicial y grilla exactos.
- [x] Preview y errores indican períodos afectados, referencias fuera del horizonte y dimensión incompatible; un solo período se resuelve según la política elegida.
- [x] Julia respeta ambas rampas junto a las restricciones existentes, y la solución permite comprobar sus diferencias temporales.

## Demonstration and validation

Fronteras TDD: se reutilizan las interfaces confirmadas en REG-002/003 — HTTP
autenticado con SQLite/PostgreSQL, editor React, runtime OCI real y carga/solve
públicos de Julia. No se requiere una nueva confirmación de estas fronteras.

Resolver tres intervalos con duraciones distintas y límites de subida/bajada
que modifiquen el despacho. Comparar omisión inicial frente a condición inicial
declarada. Probar horizonte de un período, índice inválido, cambio de rango y
roundtrip de las referencias temporales mediante API, UI y pruebas Julia.

## Evidencia de implementación (2026-09-22)

Implementación con ciclos rojo → verde en las fronteras anteriores. El SDK
`reg-005.1` expone `ctx.transiciones(variable)` con decisiones actual/anterior,
índice, instantes y una cantidad de horas. La política `temporal` se fija en la
revisión y los snapshots. El contrato `affine_temporal.v1` identifica cada término
por objeto, variable y período; servidor y Julia conservan e intersectan esas
referencias. Las versiones anteriores mantienen su restricción de mismo período.

- **15 pruebas nuevas REG-005**: diez HTTP con SQLite/PostgreSQL y cinco de
  runtime OCI real. Verifican caudal y potencia, ambas políticas, un período,
  índices negativos/futuros, unidades, instantes, cambio de horizonte, motor sin
  capacidad temporal y límites sobre decisiones anteriores.
- **136 pruebas Python distintas verificadas**, sin omisiones: REG-001 a REG-005
  y catálogo TS7-001. La tanda completa pasó 134 y detectó dos expectativas del
  catálogo que aún no incluían tiempo/rampas; se actualizaron al contrato nuevo
  y los **19 tests del catálogo** pasaron, incluidos los de PostgreSQL. La
  compilación anual de 8784 períodos pasó en **4,777 s**; 8785 se rechazaron en
  **3,468 s**, tiempos locales de pared del ejecutor OCI.
- **39 comprobaciones Julia/HiGHS** en `test/component_rules.jl`: con intervalos
  de 0,5, 2 y 1 horas, las rampas de 4 y 2 m³/s por hora y un inicial de 2 m³/s
  media hora antes producen **[4, 6, 14] m³/s**. Al limitar el último período a
  1 m³/s, la bajada impone **[4, 5, 1]**; omitir la comparación inicial produce
  **[6, 5, 1]**. Se rechazan referencias inválidas y ausencia de política; los
  offsets se interpretan en UTC conservando las cadenas originales del snapshot.
- **532 comprobaciones generales de Julia** aprobadas en `test/runtests.jl`,
  incluidos los modelos existentes y los recorridos CLI.
- **72 pruebas React** aprobadas en seis archivos, incluidos el formulario
  temporal, cobertura, referencias con instantes, errores y bloqueo al cambiar
  horizonte. Build, TypeScript, ESLint, Prettier de archivos modificados y
  OpenAPI regenerado/`api:check` aprobados.
- **Chromium, API, OCI y Julia reales**: `component-rules-temporal.spec.ts`
  aprobado en datos temporales. Configura las rampas desde el editor, comprueba
  **[4, 5, 1]** con condición inicial y **[6, 5, 1]** al omitirla, verifica el
  bloqueo de aplicación tras cambiar rango y conserva la corrida inicial.
  El primer recorrido detectó que Julia rechazaba timestamps `+00:00`; se
  corrigió la interpretación de offsets y se repitió satisfactoriamente.
  Preview revisada visualmente.
- **53 pruebas de corridas, resultados e indexación** aprobadas. Al repetir el
  recorrido REG-004 se detectó una carrera: el estado `succeeded` se publicaba
  antes del registro de los CSV. El ejecutor registra ahora los artefactos antes
  de marcar la corrida terminada, para que los resultados estén disponibles al
  observar ese estado. El recorrido Chromium REG-004 se repitió y pasó con la
  corrección, incluidas ambas corridas, membresía e historial.

Workflow y [operación/reproducción](../runtime.md) incluyen REG-005. Para adoptar
el SDK se reconstruye la imagen OCI, se fija su digest y se reinicia el worker.
No se ejecutó CI remoto ni hubo despliegue o cambios en bases de proyectos.
La siguiente issue por orden es REG-006: presupuestos de agua y energía.

## Blocked by

- [REG-004](REG-004-relacionar-componentes-hidraulicos.md).
