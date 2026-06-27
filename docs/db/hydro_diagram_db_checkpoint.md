# Hydro Diagram DB Checkpoint

Fecha inicial: 2026-06-26

Este documento es el checkpoint vivo de BBDD para el PRD del editor de diagrama
hidraulico en `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`.

Debe actualizarse en cada issue que agregue, cambie o conecte tablas,
migraciones, indices, constraints, generadores o validaciones persistidas.

## Estado General

| Area | Estado objetivo | Estado implementado | Pendiente | Ultima issue BBDD |
| --- | --- | --- | --- | --- |
| Caso normalizado | `optimization_cases` como fuente editable y `scenario_versions` como snapshot inmutable. | `optimization_cases` implementada y conectada 1:1 con `scenarios` para el editor hidraulico. Campos: `scenario_id`, `case_key`, `display_name`, `validation_payload_json`, auditoria create/update. `validation_payload_json` guarda snapshots exitosos `hydraulic_v3_preview` con `validation_hash`, `system_case`, `julia_validation` y estado `stale`. La promocion v3 crea `scenario_versions` inmutables desde el snapshot validado vigente y registra `generation_metadata.kind = hydraulic_diagram_v3`. | Congelar snapshot visual de layout promovido cuando se implemente `scenario_version_hydraulic_diagram_snapshots`. | BESS-HYDRO-DIAGRAM-006 |
| Red hidraulica base | `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants`, `hydraulic_units`. | Implementadas `hydraulic_systems`, `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants` y `hydraulic_units` (con `intake_node_id`/`discharge_node_id` por unidad). | Fixtures/parametros base avanzados en slices posteriores. | BESS-HYDRO-DIAGRAM-004 |
| Red activa por caso | `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants`, `case_hydraulic_units`. | Implementadas `case_hydraulic_systems`, `case_hydraulic_nodes`, `case_hydraulic_reaches`, `case_hydraulic_plants` (con `non_modeled`, `min_power_mw`, `max_power_mw`) y `case_hydraulic_units` (intake/descarga, limites de potencia/caudal, binding `flow_power`). | Conectar al payload v3 y series/parametros hidraulicos posteriores. | BESS-HYDRO-DIAGRAM-004 |
| Parametros de embalse | `case_hydraulic_reservoir_parameters`. | Implementada con `storage_min_hm3`, `storage_max_hm3`, `initial_storage_hm3`, `terminal_condition` (`none`/`equal_initial`/`min_terminal`), `terminal_storage_min_hm3` y `terminal_water_value_usd_per_hm3` por nodo embalse activo del caso. | Conectar al payload v3 y validar bounds avanzados en slices posteriores. | BESS-HYDRO-DIAGRAM-003 |
| Curvas versionadas | `hydraulic_curve_sets`, `hydraulic_curve_points`, `case_hydraulic_curve_bindings`. | Implementadas para `storage_elevation` (entidad `hydraulic_node`) y `flow_power` (entidad `hydraulic_unit`): curvas versionadas a nivel proyecto (reuso por `content_hash`, version incremental), puntos ordenados y binding por caso con `curve_role` por entidad activa. | Roles de curva preparados restantes (`storage_area`, `flow_head_efficiency`, etc.). | BESS-HYDRO-DIAGRAM-004 |
| Series hidraulicas | `case_time_series_bindings` con entidades hidraulicas activas. | Disenado en propuesta central. | Conectar `natural_inflow_m3s` y `minimum_flow_m3s`. | N/A |
| Layout editable | `case_hydraulic_diagram_layouts`, `case_hydraulic_diagram_items`. | Implementado con viewport, `layout_engine`, `layout_version` como token de revision, posiciones por entidad activa y constraints de unicidad. `case_hydraulic_diagram_items.entity_type` acepta nodos, plantas y reaches. | Crear snapshots de promocion cuando existan versiones v3. | BESS-HYDRO-DIAGRAM-002 |
| Snapshot visual promovido | `scenario_version_hydraulic_diagram_snapshots`. | Disenado en `docs/hydro_diagram/iter1/database_extension.md`; no implementado. | Congelar snapshot al promover. | N/A |
| Validacion topologica | Resultado en `optimization_cases.validation_payload_json.hydraulic_islands`. | Validacion persistida para reaches (tipos y endpoints activos), embalses activos (parametros, curva `storage_elevation`, monotonia/dominio, condicion terminal) y centrales/unidades activas: central activa requiere unidad activa salvo `non_modeled`, unidad activa requiere nodos toma/descarga activos y distintos, binding `flow_power` y curva con caudal creciente y potencia no decreciente. Cada error reporta `entity_type`, `entity_id` y `technical_key`. La validacion v3 genera un preview ejecutable `bess_system_dispatch.v3`, llama validacion Julia, persiste snapshot exitoso y bloquea promocion si el snapshot esta stale. | Agregar islas hidraulicas, ciclos, boundaries y reglas avanzadas en slices posteriores. | BESS-HYDRO-DIAGRAM-006 |

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
| 2026-06-26 | BESS-HYDRO-DIAGRAM-004 | Se implementaron `hydraulic_units` y `case_hydraulic_units`, columnas de agregado/`non_modeled` en `case_hydraulic_plants` y curvas `flow_power` versionadas por unidad; el guardado persiste central, unidades (toma/descarga, limites) y binding `flow_power`; la validacion exige unidades activas, nodos toma/descarga activos y distintos, y curva `flow_power` valida. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram` (13 ok); `.\\.venv\\Scripts\\python.exe -m unittest discover tests` (116 ok); `npm test` (25 ok); `npm run api:check`; `npm run test:browser -- -g "hydraulic diagram persists"` (1 passed). `tsc`/`eslint` ok; `prettier --check` falla solo por CRLF preexistente en el checkout. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-005 | Se implemento generacion deterministica de preview `bess_system_dispatch.v3` desde caso hidraulico normalizado, validacion Julia v3 sin solve, persistencia de snapshot exitoso en `optimization_cases.validation_payload_json` y marcado `stale` cuando un guardado cambia el hash del payload. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram` (14 ok); `.\\.venv\\Scripts\\python.exe -m unittest discover tests` (117 ok, 1 skipped); `npm.cmd test` (25 ok); `npm.cmd run build`; `npm.cmd run api:check`; `julia --project=. test\\runtests.jl` (489 ok); Chrome smoke local verifico preview v3 renderizado. |
| 2026-06-27 | BESS-HYDRO-DIAGRAM-006 | Se conecto promocion v3 desde el snapshot validado de `optimization_cases.validation_payload_json` hacia `scenario_versions`; el preview v3 ahora incluye `time_series.natural_inflow_m3s` minimo ejecutable; Julia ejecuta el contrato `bess_system_dispatch.v3` soportado y escribe artifacts auditables. | `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram tests.test_manual_runs tests.test_draft_generated_system_case -v`; `.\\.venv\\Scripts\\python.exe -m unittest discover tests -v` (118 ok, 1 skipped); `julia --project=. test\\runtests.jl` (513 ok); `npm.cmd test` (25 ok); `npm.cmd run build`; `npm.cmd run api:check`; Chrome/@chrome smoke local promovio version v3 desde el editor. |

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
- `AnalystStore._initialize_schema` auto-crea `hydraulic_units` y
  `case_hydraulic_units`, y agrega via `_ensure_column` las columnas
  `non_modeled`, `min_power_mw` y `max_power_mw` a `case_hydraulic_plants`.
- `AnalystStore.validate_hydraulic_diagram` agrega reglas de central/unidad
  (`plant_without_active_units`, `inactive_or_equal_unit_nodes`,
  `missing_flow_power_curve`, `invalid_flow_power_curve`).
- `AnalystStore.generate_hydraulic_v3_preview` arma el contrato
  `bess_system_dispatch.v3` con nodos, tramos, centrales, unidades, curvas y
  requerimientos `natural_inflow_m3s`; desde BESS-HYDRO-DIAGRAM-006 incluye
  un bloque `time_series` minimo ejecutable con `natural_inflow_m3s`;
  `persist_hydraulic_v3_validation`
  guarda snapshot exitoso y `validation_hash` en
  `optimization_cases.validation_payload_json`.
- `AnalystStore.save_hydraulic_diagram` marca validaciones v3 previas como
  `stale` cuando el payload generado cambia despues de editar el diagrama.
- `/api/scenarios/{scenario_id}/hydraulic-diagram/promote` crea una
  `scenario_version` desde el snapshot v3 validado vigente y revalida el hash
  actual antes de persistir.

## Riesgos Activos

- La propuesta central de BBDD es mas amplia que el MVP; el checkpoint debe
  evitar que tablas aun no implementadas se confundan con estado real.
- Las FK polimorficas por `entity_type` y `entity_id` requieren validacion de
  aplicacion o triggers dedicados.
- El layout visual no debe contaminar la fisica ni el payload ejecutable.
- La promocion debe congelar el layout historico sin hacer que las corridas
  dependan de ese layout.
