# MESA-009 · Comparar entradas y resultados eléctricos con procedencia

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-03, HU-06

## What to build

Entregar el recorrido Antes/Comparar/Después para señales eléctricas desde un contexto de ejecución congelado. Servir y mostrar los dos lados con identidad de magnitud, objeto, unidad, intervalos y revisión/run. Permitir escoger una ejecución de referencia compatible para outputs que no tengan valor previo.

## Acceptance criteria

- [x] Cada lado identifica su origen; la entrada «antes» procede del snapshot ejecutado, no de la serie mutable actual.
- [x] Una entrada exógena que no cambia se presenta sin mejora ficticia; un output sin referencia muestra «Sin referencia previa».
- [x] Comparar y calcular Δ solamente entre igual objeto, magnitud, unidad e intervalos; explicar incompatibilidades.
- [x] Gráfico y tabla muestran la misma selección y leyendas antes/después; en modo Después las columnas mantienen el nombre de cada serie.
- [x] Los resultados son de solo lectura. Editar entradas actuales marca la preparación pendiente sin modificar ni borrar el run anterior.
- [x] Cambiar caso, fechas o referencia no mezcla datos de solicitudes antiguas que llegan tarde.
- [x] Un test con valores esperados independientes demuestra que editar la fuente después del run no altera su comparación histórica.

## Blocked by

- [MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance](MESA-007-ejecutar-caso-electrico-por-fechas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: una entrada congelada de 10 MW sigue mostrando 10 para el run aunque la revisión actual tenga 12. Probar separadamente ausencia de referencia y alineación inválida.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Comparar dos resultados BESS compatibles y ver una entrada de demanda sin cambio, con su procedencia.

## Evidencia y seguimiento

- Inicio: 2026-10-21. Dependencia MESA-007 Done; interfaces S1/S2 confirmadas. Primer ciclo: comparación HTTP de demanda congelada tras editar la fuente actual.
- Evidencia rojo → verde / revisión HITL: nueve ciclos en S1/S2, detallados en [validación](../evidencia/MESA-009/validacion.md). Revisión técnica AFK.
- Pruebas y comandos ejecutados: diez pruebas HTTP nuevas y cuatro de navegador; regresiones y resultados en la evidencia.
- Capturas de implementación y diferencias revisadas: comparación con cuatro paneles a 1440×900 y tabla a 390 px; procedencia y escalas legibles, sin desbordamiento global. Referencias originales conservadas.
- Decisiones o desviaciones respecto del plan: contrato de lectura aditivo; consulta actual separada de la comparación congelada. Sin cambios de motor o persistencia. La comparación hidráulica sigue en MESA-010.
- Cierre y responsable: 2026-10-21, Codex. Revisión AFK completada: 145 pruebas Python distintas verificadas entre suite y reintentos, 30/30 navegador MESA, cinco regresiones generales y 336/336 Vitest. OpenAPI, build, TypeScript/ESLint y formato de cambios OK; dieciséis archivos ajenos mantienen formato pendiente. Siguiente: MESA-010.
