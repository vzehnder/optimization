# MESA-002 · Abrir un caso real y consultar demanda en la mesa

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-01, HU-03, HU-10, HU-11

## What to build

Entregar el primer recorrido real desde el escenario a la mesa: seleccionar su contexto, descubrir un componente de demanda y mostrar su entrada en tabla y gráfico desde la misma fuente canónica. Resolver identidad, unidades, cobertura y permisos en el backend. Si se necesita una proyección de lectura nueva, incluirla junto con su consumidor; no crear otro almacén de muestras.

## Acceptance criteria

- [ ] La entrada a la mesa conserva proyecto, escenario, caso y variante seleccionados y no muestra datos de otro contexto.
- [ ] El componente se identifica por su identidad de dominio, no por el nombre visible; la UI distingue dato de entrada, parámetro y resultado.
- [ ] Una misma serie de demanda se observa con idénticos valores, unidad y fechas en tabla y gráfico; aún no se ofrece edición.
- [ ] El inventario y los valores se leen por contratos públicos, con estados vacío, carga, sin cobertura, error y reintento.
- [ ] El servidor rechaza identidades fuera del contexto y permisos insuficientes; la nueva ruta no amplía capacidades de la consola externa.
- [ ] Recargar la página vuelve a consultar los datos reales y conserva un contexto identificable.
- [ ] Un test de navegador/API demuestra el recorrido con una fixture independiente y evidencia rojo → verde.

## Blocked by

- [MESA-001 · Acordar el alcance de la mesa y sus contratos observables](MESA-001-acordar-alcance-y-contratos.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: abrir un caso con demanda conocida, alternar tabla/gráfico y recargar; verificar los mismos valores mediante la interfaz. Añadir un caso de identidad/permisos incorrectos en S2.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Desde un escenario existente se abre la mesa y se consulta una serie real sin visitar otro editor.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
