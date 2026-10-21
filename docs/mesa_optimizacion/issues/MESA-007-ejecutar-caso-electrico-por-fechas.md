# MESA-007 · Ejecutar un caso eléctrico por fechas y recuperar su avance

Status: Done
Type: AFK
Triage: ready-for-agent
Assignee: Codex
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-05, HU-11

## What to build

Ejecutar desde la mesa un caso admitido con BESS, demanda y renovables reutilizando la cadena de variantes, validación, snapshot inmutable, run y worker. Incluir el período, la preparación y el seguimiento en el mismo recorrido visible. Reutilizar progreso ya integrado; no crear una segunda cola.

## Acceptance criteria

- [x] Seleccionar inicio, fin, zona y resolución admitida; convertir explícitamente fechas inclusivas a intervalos [inicio, fin) cuando aplique. Se usan fecha/hora y fin explícitamente exclusivo.
- [x] Comprobar cobertura, períodos, cambios de hora y compatibilidad antes de encolar; no aplicar remuestreo implícito.
- [x] Guardar/validar la preparación y congelar variante, revisiones de series, parámetros y rango en el snapshot utilizado por el run.
- [x] El servidor vuelve a comprobar vigencia y permisos al ejecutar y rechaza preparación obsoleta o cambios pendientes. Solo acepta la preparación guardada; la UI bloquea mientras hay edición abierta.
- [x] Doble clic o reintento no crea ejecuciones duplicadas; cada solicitud aceptada devuelve un identificador recuperable.
- [x] Mostrar cola, ejecución, fallo y éxito con avance real; recargar o perder conexión no pierde la referencia al run ni lo lanza nuevamente.
- [x] Tras éxito, las salidas se pueden consultar en la mesa por el mismo run; en fallo se conservan entradas y un mensaje accionable.
- [x] Probar el recorrido con worker/motor de prueba real y fixture pequeña; una prueba visual con mocks no basta para declarar ejecutable.

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

- Inicio: 2026-10-20, por instrucción del usuario. Dependencias MESA-004/MESA-006 Done; interfaces S1/S2 previamente confirmadas.
- Evidencia: [13 ciclos rojo → verde, contratos y revisión](../evidencia/MESA-007/validacion.md).
- Pruebas: 18 HTTP nuevas y tres de navegador nuevas; 151 Python OK y cinco PostgreSQL omitidas; 23 MESA y cinco regresiones de navegador OK. Vitest: 335/336 en suite y 4/4 en el reintento del archivo con foco intermitente; 336 distintas verificadas entre ambas ejecuciones.
- Capturas: preparación a 1440 px, resultado recuperado a 390 px y matriz 2×2. Revisadas, con las referencias originales conservadas.
- Decisiones: se reutilizan variantes, snapshots, cola y progreso. Se corrigieron normalización del hash canónico y timestamps UTC de series específicas. No cambia el motor ni se crean tablas.
- Cierre: **Done**, Codex, 2026-10-20, después de revisión técnica AFK y visual. Límites y fallo intermitente de foco documentados; siguiente MESA-008.
