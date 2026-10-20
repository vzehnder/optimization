# MESA-012 · Crear series manuales de apoyo y vincular entradas admitidas

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-08, HU-04

## What to build

Ofrecer desde la mesa un recorrido para crear una serie manual con nombre, unidad, datos y período, conservada en el catálogo canónico asociado al objeto/contexto admitido. Puede organizarse como componente de referencia en la vista. Para influir en la optimización necesita una asociación/binding compatible explícito; no se crea un tipo físico arbitrario.

## Acceptance criteria

- [ ] Crear y publicar la serie mediante el mecanismo canónico, con identidad, unidad, rol, períodos, revisión y procedencia manual.
- [ ] Agregar una pestaña/grupo y paneles que referencien esa serie sin duplicar sus valores en la configuración visual.
- [ ] Editar datos y recuperar la misma revisión después de recargar, con validaciones y permisos equivalentes a las demás entradas.
- [ ] Una serie sin binding se etiqueta como apoyo y no participa en la simulación; no recibe un resultado ficticio.
- [ ] Solo ofrecer destinos/señales compatibles con el tipo de objeto; una asociación inválida se rechaza en servidor.
- [ ] Vincular a una entrada admitida activa la revalidación y hace que la próxima preparación use la revisión publicada.
- [ ] Las ediciones y vinculaciones no alteran snapshots o runs existentes.
- [ ] Demostrar por API/UI la diferencia entre una serie de apoyo persistida y una entrada realmente vinculada.

## Blocked by

- [MESA-003 · Guardar pestañas, paneles y distribución por caso](MESA-003-persistir-pestanas-y-paneles.md)
- [MESA-006 · Editar entradas en tablas y guardar revisiones auditables](MESA-006-editar-entradas-versionadas.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: crear una serie de apoyo y recuperarla sin que cambie el payload ejecutable. Segundo ciclo: vincular una señal admitida y observar la revisión en la preparación pública.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Crear un aporte manual, mostrarlo en la mesa y vincularlo conscientemente a un objeto compatible.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
