# Hydro Diagram DB Checkpoint

Fecha inicial: 2026-06-26

Este documento es el checkpoint vivo de BBDD para el PRD del editor de diagrama
hidraulico en `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`.

Debe actualizarse en cada issue que agregue, cambie o conecte tablas,
migraciones, indices, constraints, generadores o validaciones persistidas.

## Estado General

| Area | Estado objetivo | Estado implementado | Pendiente | Ultima issue BBDD |
| --- | --- | --- | --- | --- |
| Caso normalizado | `optimization_cases` como fuente editable y `scenario_versions` como snapshot inmutable. | `optimization_cases` implementada y conectada 1:1 con `scenarios` para el editor hidraulico. Campos: `scenario_id`, `case_key`, `display_name`, `validation_payload_json`, auditoria create/update. | Conectar validacion/promocion v3 contra el caso normalizado en issues posteriores. | BESS-HYDRO-DIAGRAM-001 |
| Red hidraulica base | `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants`, `hydraulic_units`. | Implementadas `hydraulic_systems`, `hydraulic_nodes` y `hydraulic_plants` para nodos visibles reservoir/junction/plant. | Implementar `hydraulic_reaches`, `hydraulic_units` y fixtures/parametros base en slices posteriores. | BESS-HYDRO-DIAGRAM-001 |
| Red activa por caso | `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants`, `case_hydraulic_units`. | Implementadas `case_hydraulic_systems`, `case_hydraulic_nodes` y `case_hydraulic_plants` con labels activos por caso. | Implementar reaches, units, parametros y validacion activa. | BESS-HYDRO-DIAGRAM-001 |
| Parametros de embalse | `case_hydraulic_reservoir_parameters`. | Disenado en propuesta central. | Implementar storage bounds, estado inicial y terminal condition. | N/A |
| Curvas versionadas | `hydraulic_curve_sets`, `hydraulic_curve_points`, `case_hydraulic_curve_bindings`. | Disenado en propuesta central. | Implementar versionado y bindings MVP para `storage_elevation` y `flow_power`. | N/A |
| Series hidraulicas | `case_time_series_bindings` con entidades hidraulicas activas. | Disenado en propuesta central. | Conectar `natural_inflow_m3s` y `minimum_flow_m3s`. | N/A |
| Layout editable | `case_hydraulic_diagram_layouts`, `case_hydraulic_diagram_items`. | Implementado con viewport, `layout_engine`, `layout_version` como token de revision, posiciones por entidad activa y constraints de unicidad. | Extender a reaches y snapshots de promocion cuando existan conexiones/versiones v3. | BESS-HYDRO-DIAGRAM-001 |
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
| 2026-06-26 | BESS-HYDRO-DIAGRAM-001 | Se implementaron tablas normalizadas minimas para caso hidraulico, sistema base, nodos/centrales activos y layout editable. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`; `npm.cmd test -- App.test.tsx -t "opens a persisted hydraulic diagram"`. |

## Migraciones Aplicadas

- `AnalystStore._initialize_schema` auto-crea `optimization_cases`.
- `AnalystStore._initialize_schema` auto-crea `hydraulic_systems`,
  `hydraulic_nodes` y `hydraulic_plants`.
- `AnalystStore._initialize_schema` auto-crea `case_hydraulic_systems`,
  `case_hydraulic_nodes` y `case_hydraulic_plants`.
- `AnalystStore._initialize_schema` auto-crea
  `case_hydraulic_diagram_layouts` y `case_hydraulic_diagram_items`.

## Riesgos Activos

- La propuesta central de BBDD es mas amplia que el MVP; el checkpoint debe
  evitar que tablas aun no implementadas se confundan con estado real.
- Las FK polimorficas por `entity_type` y `entity_id` requieren validacion de
  aplicacion o triggers dedicados.
- El layout visual no debe contaminar la fisica ni el payload ejecutable.
- La promocion debe congelar el layout historico sin hacer que las corridas
  dependan de ese layout.
