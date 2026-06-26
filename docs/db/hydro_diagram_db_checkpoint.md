# Hydro Diagram DB Checkpoint

Fecha inicial: 2026-06-26

Este documento es el checkpoint vivo de BBDD para el PRD del editor de diagrama
hidraulico en `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`.

Debe actualizarse en cada issue que agregue, cambie o conecte tablas,
migraciones, indices, constraints, generadores o validaciones persistidas.

## Estado General

| Area | Estado objetivo | Estado implementado | Pendiente | Ultima issue BBDD |
| --- | --- | --- | --- | --- |
| Caso normalizado | `optimization_cases` como fuente editable y `scenario_versions` como snapshot inmutable. | Disenado en `docs/db/propuesta_bbdd_componentes_timeseries.md`; no confirmado como migracion aplicada por esta iteracion. | Implementar o conectar tablas reales del caso normalizado para el diagrama. | N/A |
| Red hidraulica base | `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants`, `hydraulic_units`. | Disenado en propuesta central. | Implementar migraciones, APIs y fixtures. | N/A |
| Red activa por caso | `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants`, `case_hydraulic_units`. | Disenado en propuesta central. | Implementar seleccion, parametros y validacion activa. | N/A |
| Parametros de embalse | `case_hydraulic_reservoir_parameters`. | Disenado en propuesta central. | Implementar storage bounds, estado inicial y terminal condition. | N/A |
| Curvas versionadas | `hydraulic_curve_sets`, `hydraulic_curve_points`, `case_hydraulic_curve_bindings`. | Disenado en propuesta central. | Implementar versionado y bindings MVP para `storage_elevation` y `flow_power`. | N/A |
| Series hidraulicas | `case_time_series_bindings` con entidades hidraulicas activas. | Disenado en propuesta central. | Conectar `natural_inflow_m3s` y `minimum_flow_m3s`. | N/A |
| Layout editable | `case_hydraulic_diagram_layouts`, `case_hydraulic_diagram_items`. | Disenado en `docs/hydro_diagram/iter1/database_extension.md`; no implementado. | Crear migraciones, repositorio/API y pruebas. | N/A |
| Snapshot visual promovido | `scenario_version_hydraulic_diagram_snapshots`. | Disenado en `docs/hydro_diagram/iter1/database_extension.md`; no implementado. | Congelar snapshot al promover. | N/A |
| Validacion topologica | Resultado en `optimization_cases.validation_payload_json.hydraulic_islands`. | Disenado en propuesta central. | Implementar modulo de validacion y persistencia de resultado. | N/A |

## Reglas De Actualizacion

Cuando una issue toque BBDD:

1. Actualizar la fila correspondiente de `Estado General`.
2. Agregar una entrada al log.
3. Registrar migraciones o scripts creados.
4. Registrar constraints, indices o validaciones nuevas.
5. Marcar explicitamente lo que queda pendiente.

## Log De Cambios

| Fecha | Issue | Cambio | Verificacion |
| --- | --- | --- | --- |
| 2026-06-26 | N/A | Checkpoint inicial creado desde el PRD y la extension de BBDD. | Documental. |

## Migraciones Aplicadas

Ninguna registrada por esta iteracion todavia.

## Riesgos Activos

- La propuesta central de BBDD es mas amplia que el MVP; el checkpoint debe
  evitar que tablas aun no implementadas se confundan con estado real.
- Las FK polimorficas por `entity_type` y `entity_id` requieren validacion de
  aplicacion o triggers dedicados.
- El layout visual no debe contaminar la fisica ni el payload ejecutable.
- La promocion debe congelar el layout historico sin hacer que las corridas
  dependan de ese layout.

