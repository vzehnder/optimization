# MESA-003 · Guardar pestañas, paneles y distribución por caso

Status: Todo
Type: AFK
Triage: ready-for-agent
Assignee: —
Source: [Plan de implementación](../plan_implementacion.md)
User stories covered: HU-02, HU-03, HU-10

## What to build

Permitir al analista configurar su mesa y recuperarla después: vista general, pestañas por componente, selección de series y modo de presentación por panel. Persistir solo configuración visual, con esquema y revisión propios, vinculada al usuario y al caso. Un guardado visual no cambia la preparación matemática.

## Acceptance criteria

- [ ] Guardar y recargar título, componente, series, modo gráfico/tabla, orden y distribución por pestaña.
- [ ] Ofrecer 1×1, 1×2, 2×2 y 2×3; al reducir la distribución conservar los paneles ocultos y restaurarlos al ampliarla.
- [ ] Agregar y quitar una vista no crea ni elimina activos, muestras o bindings del caso.
- [ ] Varios paneles pueden consultar el mismo componente; unidades diferentes se separan en ejes/subgráficos inequívocos.
- [ ] Guardar con revisión obsoleta devuelve conflicto recuperable sin sobrescritura silenciosa; las preferencias no se filtran a otro usuario/caso.
- [ ] Al eliminarse un componente, la vista queda identificada como no disponible y permite reconfiguración; no se reasigna por nombre.
- [ ] La matriz 2×2 y controles principales caben a 1440×900; las pestañas, el diálogo y los modos son operables con teclado.
- [ ] Configurar la vista no invalida snapshots ni resultados. La persistencia y la lectura posterior se comprueban por S2/S1.

## Blocked by

- [MESA-002 · Abrir un caso real y consultar demanda en la mesa](MESA-002-abrir-caso-y-demanda-real.md)

## Validación TDD

Interfaces acordadas: S1 + S2

Primer test: guardar cuatro vistas, pasar a una, recargar y restaurar cuatro sin perder las configuraciones. Añadir conflicto de revisión y viewport fijo como comportamientos separados.

Aplicar la [estrategia TDD](../validacion_tdd.md) y la definición de terminado del plan. Las interfaces S1/S2 y S3 condicional fueron confirmadas por el usuario el 2026-10-20; registrar en MESA-001 cualquier interfaz adicional antes de probarla. Cada ciclo implementa un solo comportamiento observable.

## Demostración de cierre

Personalizar dos pestañas distintas, recargar y recuperar cada disposición.

## Evidencia y seguimiento

- Inicio: pendiente.
- Evidencia rojo → verde / revisión HITL: pendiente.
- Pruebas y comandos ejecutados: pendiente.
- Capturas de implementación y diferencias revisadas: pendiente, cuando aplique.
- Decisiones o desviaciones respecto del plan: pendiente.
- Cierre y responsable: pendiente.
