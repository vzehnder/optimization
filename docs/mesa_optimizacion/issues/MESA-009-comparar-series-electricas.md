# MESA-009 · Comparar entradas y resultados eléctricos con procedencia

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-03, HU-06

## What to build

Entregar el recorrido Antes/Comparar/Después para señales eléctricas desde un contexto de ejecución congelado. Servir y mostrar los dos lados con identidad de magnitud, objeto, unidad, intervalos y revisión/run. Permitir escoger una ejecución de referencia compatible para outputs que no tengan valor previo.

## Acceptance criteria

- [ ] Cada lado identifica su origen; la entrada «antes» procede del snapshot ejecutado, no de la serie mutable actual.
- [ ] Una entrada exógena que no cambia se presenta sin mejora ficticia; un output sin referencia muestra «Sin referencia previa».
- [ ] Comparar y calcular Δ solamente entre igual objeto, magnitud, unidad e intervalos; explicar incompatibilidades.
- [ ] Gráfico y tabla muestran la misma selección y leyendas antes/después; en modo Después las columnas mantienen el nombre de cada serie.
- [ ] Los resultados son de solo lectura. Editar entradas actuales marca la preparación pendiente sin modificar ni borrar el run anterior.
- [ ] Cambiar caso, fechas o referencia no mezcla datos de solicitudes antiguas que llegan tarde.
- [ ] Un test con valores esperados independientes demuestra que editar la fuente después del run no altera su comparación histórica.

## Blocked by

- [MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance](MESA-007-ejecutar-caso-electrico-por-fechas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: una entrada congelada de 10 MW sigue mostrando 10 para el run aunque la revisión actual tenga 12. Probar separadamente ausencia de referencia y alineación inválida.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Comparar dos resultados BESS compatibles y ver una entrada de demanda sin cambio, con su procedencia.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
