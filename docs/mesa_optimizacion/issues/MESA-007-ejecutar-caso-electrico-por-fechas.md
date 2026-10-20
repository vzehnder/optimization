# MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-05, HU-11

## What to build

Ejecutar desde la mesa un caso admitido con BESS, demanda y renovables reutilizando la cadena de variantes, validación, snapshot inmutable, run y worker. Incluir el período, la preparación y el seguimiento en el mismo recorrido visible. Reutilizar progreso ya integrado; no crear una segunda cola.

## Acceptance criteria

- [ ] Seleccionar inicio, fin, zona y resolución admitida; convertir explícitamente fechas inclusivas a intervalos [inicio, fin) cuando aplique.
- [ ] Comprobar cobertura, períodos, cambios de hora y compatibilidad antes de encolar; no aplicar remuestreo implícito.
- [ ] Guardar/validar la preparación y congelar variante, revisiones de series, parámetros y rango en el snapshot utilizado por el run.
- [ ] El servidor vuelve a comprobar vigencia y permisos al ejecutar y rechaza preparación obsoleta o cambios pendientes.
- [ ] Doble clic o reintento no crea ejecuciones duplicadas; cada solicitud aceptada devuelve un identificador recuperable.
- [ ] Mostrar cola, ejecución, fallo y éxito con avance real; recargar o perder conexión no pierde la referencia al run ni lo lanza nuevamente.
- [ ] Tras éxito, las salidas se pueden consultar en la mesa por el mismo run; en fallo se conservan entradas y un mensaje accionable.
- [ ] Probar el recorrido con worker/motor de prueba real y fixture pequeña; una prueba visual con mocks no basta para declarar ejecutable.

## Blocked by

- [MESA-004 · Consultar BESS, demanda y renovables por componente](MESA-004-consultar-bess-y-renovables.md)
- [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](MESA-006-editar-entradas-versionadas.md)

## Validación TDD

Interfaces acordadas: S1 + S2; S3 solo si cambia el contrato del motor.

Primer test: lanzar un caso conocido, recargar durante la ejecución y recuperar el mismo run. Añadir doble envío, hueco temporal y revisión cambiada como comportamientos separados.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Modificar una entrada, seleccionar fechas, ejecutar y ver el run completar sin navegar fuera de la mesa.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
