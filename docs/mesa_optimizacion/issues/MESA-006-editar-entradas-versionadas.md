# MESA-006 · Editar entradas en tablas y guardar revisiones auditables

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-04, HU-10, HU-11

## What to build

Completar el recorrido de una edición real desde una tabla de la mesa hasta una revisión canónica recuperable. Reutilizar publicación/edición de series y control de concurrencia del dominio; si el recorrido canónico requiere preparación o confirmación, integrarlo en la mesa. Iniciar con una entrada de demanda y mantener el contrato extensible a señales admitidas.

## Acceptance criteria

- [ ] Solo las celdas de entradas permitidas son editables; outputs, parámetros no expuestos y referencias históricas permanecen de solo lectura.
- [ ] Indicar cambios pendientes y permitir guardar o descartar; advertir antes de cambiar contexto con cambios sin guardar.
- [ ] Validar número, unidad, límites semánticos, intervalos, huecos y cobertura según el descriptor de señal, sin reglas genéricas incorrectas.
- [ ] Antes de guardar, informar si se modifica una serie compartida y aplicar el alcance/copia que disponga el mecanismo canónico.
- [ ] Guardar genera una revisión con actor y procedencia, confirmada por una lectura posterior; cancelar no publica datos.
- [ ] Un conflicto de revisión no sobrescribe cambios ajenos y permite recargar/comparar. La API no depende de un control exclusivo del navegador.
- [ ] El guardado deja la preparación pendiente de revalidación y conserva los runs históricos intactos.
- [ ] Un test rojo → verde comprueba edición, recarga y procedencia; otro comprueba el rechazo de una edición concurrente.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: cambiar un literal conocido, guardar y obtener la nueva revisión por API; comprobar en UI que la entrada cambió. No consultar tablas internas para validar persistencia.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Editar una hora en la tabla, guardar, recargar y ver la misma revisión en gráfico y tabla.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
