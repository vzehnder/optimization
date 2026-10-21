# MESA-006 · Editar entradas en tablas y guardar revisiones auditables

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-04, HU-10, HU-11

## What to build

Completar el recorrido de una edición real desde una tabla de la mesa hasta una revisión canónica recuperable. Reutilizar publicación/edición de series y control de concurrencia del dominio; si el recorrido canónico requiere preparación o confirmación, integrarlo en la mesa. Iniciar con una entrada de demanda y mantener el contrato extensible a señales admitidas.

## Acceptance criteria

- [x] Solo las celdas de entradas permitidas son editables; outputs, parámetros no expuestos y referencias históricas permanecen de solo lectura.
- [x] Indicar cambios pendientes y permitir guardar o descartar; advertir antes de cambiar contexto con cambios sin guardar.
- [x] Validar número, unidad, límites semánticos, intervalos, huecos y cobertura según el descriptor de señal, sin reglas genéricas incorrectas.
- [x] Antes de guardar, informar si se modifica una serie compartida y aplicar el alcance/copia que disponga el mecanismo canónico.
- [x] Guardar genera una revisión con actor y procedencia, confirmada por una lectura posterior; cancelar no publica datos.
- [x] Un conflicto de revisión no sobrescribe cambios ajenos y permite recargar/comparar. La API no depende de un control exclusivo del navegador.
- [x] El guardado deja la preparación pendiente de revalidación y conserva los runs históricos intactos.
- [x] Un test rojo → verde comprueba edición, recarga y procedencia; otro comprueba el rechazo de una edición concurrente.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: cambiar un literal conocido, guardar y obtener la nueva revisión por API; comprobar en UI que la entrada cambió. No consultar tablas internas para validar persistencia.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Editar una hora en la tabla, guardar, recargar y ver la misma revisión en gráfico y tabla.

## Evidencia y seguimiento

- Inicio: 2026-10-20, por instrucción del usuario. Dependencia MESA-002 Done;
  S1 navegador y S2 HTTP confirmadas en MESA-001. Se preservan los cambios locales previos.
- Evidencia: [quince ciclos rojo → verde, comandos y revisión AFK](../evidencia/MESA-006/validacion.md).
- Verificación: quince pruebas HTTP y cinco de navegador nuevas. Suite amplia:
  142 Python OK, 62 PostgreSQL omitidas; 20 MESA, cinco regresiones de navegador
  y 336 Vitest OK. Build, OpenAPI, TypeScript, ESLint y formato modificado OK;
  formato global pendiente en 16 archivos ajenos preexistentes.
- Capturas a 1440/390 px inspeccionadas, accesibilidad y teclado comprobados.
  El diálogo concentra tabla, alcance, motivo y confirmación. Referencias originales intactas.
- Alcance: copia local canónica para esta variante, revisiones sucesivas cuando
  sigue siendo exclusiva, control de concurrencia servidor y guardado atómico.
  Solo valores: unidad, intervalos y cobertura completos se conservan. Incluye
  demanda, disponibilidad renovable y aporte hidráulico canónicos vigentes.
  No cambia el motor ni crea tablas; preparación y ejecución en mesa siguen en MESA-007/008.
- Cierre: 2026-10-20, Codex. In Progress → In Review → Done tras revisión técnica
  AFK, comprobaciones y capturas. Siguiente recomendada: MESA-007.
