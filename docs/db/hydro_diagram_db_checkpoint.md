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
| Red hidraulica base | `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants`, `hydraulic_units`. | Implementadas `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches` y `hydraulic_plants` para nodos visibles reservoir/junction/plant y tramos dirigidos tipados. | Implementar `hydraulic_units` y fixtures/parametros base en slices posteriores. | BESS-HYDRO-DIAGRAM-002 |
| Red activa por caso | `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants`, `case_hydraulic_units`. | Implementadas `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches` y `case_hydraulic_plants` con labels activos por caso. | Implementar units, parametros hidraulicos y validaciones ejecutables v3 posteriores. | BESS-HYDRO-DIAGRAM-002 |
| Parametros de embalse | `case_hydraulic_reservoir_parameters`. | Implementada con `storage_min_hm3`, `storage_max_hm3`, `initial_storage_hm3`, `terminal_condition` (`none`/`equal_initial`/`min_terminal`), `terminal_storage_min_hm3` y `terminal_water_value_usd_per_hm3` por nodo embalse activo del caso. | Conectar al payload v3 y validar bounds avanzados en slices posteriores. | BESS-HYDRO-DIAGRAM-003 |
| Curvas versionadas | `hydraulic_curve_sets`, `hydraulic_curve_points`, `case_hydraulic_curve_bindings`. | Implementadas para `storage_elevation`: curvas versionadas a nivel proyecto (reuso por `content_hash`, version incremental), puntos ordenados y binding por caso con `curve_role = 'storage_elevation'`. | Implementar `flow_power` por unidad y demas roles de curva. | BESS-HYDRO-DIAGRAM-003 |
| Series hidraulicas | `case_time_series_bindings` con entidades hidraulicas activas. | Disenado en propuesta central. | Conectar `natural_inflow_m3s` y `minimum_flow_m3s`. | N/A |
| Layout editable | `case_hydraulic_diagram_layouts`, `case_hydraulic_diagram_items`. | Implementado con viewport, `layout_engine`, `layout_version` como token de revision, posiciones por entidad activa y constraints de unicidad. `case_hydraulic_diagram_items.entity_type` acepta nodos, plantas y reaches. | Crear snapshots de promocion cuando existan versiones v3. | BESS-HYDRO-DIAGRAM-002 |
| Snapshot visual promovido | `scenario_version_hydraulic_diagram_snapshots`. | Disenado en `docs/hydro_diagram/iter1/database_extension.md`; no implementado. | Congelar snapshot al promover. | N/A |
| Validacion topologica | Resultado en `optimization_cases.validation_payload_json.hydraulic_islands`. | Validacion persistida para reaches (tipos y endpoints activos) y para embalses activos: requiere parametros y binding `storage_elevation`, rechaza puntos de almacenamiento no crecientes, cota decreciente, bounds fuera del dominio de la curva y condiciones terminales invalidas, con `entity_type`, `entity_id` y `technical_key`. | Agregar islas hidraulicas, ciclos, boundaries y reglas v3 en slices posteriores. | BESS-HYDRO-DIAGRAM-003 |

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
| 2026-06-26 | BESS-HYDRO-DIAGRAM-002 | Se implementaron tramos hidraulicos dirigidos base/activos, layout para reaches, validacion topologica inicial y API/UI de guardado/validacion. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`; `.\\.venv\\Scripts\\python.exe -m unittest discover tests`; `npm.cmd test`; `npm.cmd run test:browser`. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-003 | Se implementaron `case_hydraulic_reservoir_parameters`, `hydraulic_curve_sets`, `hydraulic_curve_points` y `case_hydraulic_curve_bindings`; el guardado persiste parametros de embalse y curvas `storage_elevation` versionadas con binding por caso; la validacion exige parametros y curva, y rechaza curvas/condiciones terminales invalidas. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram`; `.\\.venv\\Scripts\\python.exe -m unittest discover tests`; `npm.cmd test`; `npm.cmd run check`; `npm.cmd run api:check`; `npx playwright test`. |

## Migraciones Aplicadas

- `AnalystStore._initialize_schema` auto-crea `optimization_cases`.
- `AnalystStore._initialize_schema` auto-crea `hydraulic_systems`,
  `hydraulic_nodes` y `hydraulic_plants`.
- `AnalystStore._initialize_schema` auto-crea `case_hydraulic_systems`,
  `case_hydraulic_nodes` y `case_hydraulic_plants`.
- `AnalystStore._initialize_schema` auto-crea
  `case_hydraulic_diagram_layouts` y `case_hydraulic_diagram_items`.
- `AnalystStore._initialize_schema` auto-crea `hydraulic_reaches` y
  `case_hydraulic_reaches`.
- `AnalystStore._ensure_hydraulic_diagram_items_support_reaches` migra SQLite
  local para aceptar `case_hydraulic_reach` en
  `case_hydraulic_diagram_items.entity_type`.
- `AnalystStore._initialize_schema` auto-crea
  `case_hydraulic_reservoir_parameters`, `hydraulic_curve_sets`,
  `hydraulic_curve_points` y `case_hydraulic_curve_bindings`.
- `AnalystStore.validate_hydraulic_diagram` persiste el resultado de
  validacion de topologia en `optimization_cases.validation_payload_json`,
  incluyendo reglas de embalse (parametros, curva `storage_elevation`,
  monotonia, dominio y condicion terminal).

## Riesgos Activos

- La propuesta central de BBDD es mas amplia que el MVP; el checkpoint debe
  evitar que tablas aun no implementadas se confundan con estado real.
- Las FK polimorficas por `entity_type` y `entity_id` requieren validacion de
  aplicacion o triggers dedicados.
- El layout visual no debe contaminar la fisica ni el payload ejecutable.
- La promocion debe congelar el layout historico sin hacer que las corridas
  dependan de ese layout.
