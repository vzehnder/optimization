# Hydro Diagram Database Extension

Fecha: 2026-06-26

## Objetivo

Definir la extension de BBDD necesaria para la Iteracion 1 del editor de
diagrama hidraulico sin modificar todavia
`docs/db/propuesta_bbdd_componentes_timeseries.md`.

La propuesta central ya contiene la mayoria de las tablas de red hidraulica
futura. Esta extension selecciona el subconjunto requerido para el MVP, agrega
persistencia de layout y define el checkpoint de avance de BBDD.

## Relacion Con La Propuesta Central

La Iteracion 1 usa las decisiones ya documentadas en la propuesta central:

- `optimization_cases` es el caso editable normalizado.
- `scenario_versions` conserva el snapshot inmutable ejecutable.
- La red base vive a nivel proyecto.
- El caso selecciona y parametriza subconjuntos de la red base.
- Las series y curvas usan bindings por `entity_type` y `entity_id`.
- Las curvas hidraulicas son versionables y reutilizables.
- Las islas hidraulicas se calculan en validacion y no se persisten como tabla
  de negocio en el MVP.

## Tablas Existentes En La Propuesta Que Entran Al MVP

Estas tablas deben implementarse o conectarse para la primera ruta vertical:

1. `optimization_cases`
2. `scenario_versions` con referencia al caso normalizado
3. `hydraulic_systems`
4. `hydraulic_nodes`
5. `hydraulic_reaches`
6. `hydraulic_plants`
7. `hydraulic_units`
8. `case_hydraulic_systems`
9. `case_hydraulic_nodes`
10. `case_hydraulic_reservoir_parameters`
11. `case_hydraulic_reaches`
12. `case_hydraulic_plants`
13. `case_hydraulic_units`
14. `hydraulic_curve_sets`
15. `hydraulic_curve_points`
16. `case_hydraulic_curve_bindings`
17. `time_series_sets`
18. `time_series_periods`
19. `time_series_signals`
20. `time_series_values`
21. `case_time_series_bindings`
22. `validation_dependencies`

## Ajustes De Uso Para El MVP

### `hydraulic_nodes`

Tipos minimos requeridos:

- `reservoir`
- `junction`
- `intake`
- `tailrace`
- `river_inflow`
- `other`

`display_name` es editable. `node_key` es estable y se usa en payloads,
bindings y trazabilidad.

### `hydraulic_reaches`

Tipos minimos requeridos:

- `river`
- `canal`
- `tunnel`
- `gate`
- `spillway`
- `bypass`
- `tailrace`
- `other`

En el MVP, `travel_time_hours` y `routing_method` se guardan, pero el solver
solo acepta `routing_method = 'none'` o equivalente sin retardo. Cualquier
retardo no soportado debe fallar antes de promocion.

### `case_hydraulic_reaches`

`flow_min_m3s` representa un caudal minimo escalar del tramo. Si el caudal
minimo es time-varying, usar `case_time_series_bindings` con:

```text
entity_type = 'case_hydraulic_reach'
entity_id = case_hydraulic_reaches.id
signal_key = 'minimum_flow_m3s'
binding_role = 'optimization_input'
```

Para vertederos, `spill_penalty_usd_per_hm3` se usa solo si el `reach_type`
base es `spillway`.

### `hydraulic_curve_sets`

Curvas obligatorias del MVP:

| Entidad base | `curve_key` | Eje x | Eje y |
| --- | --- | --- | --- |
| `hydraulic_node` con `node_type = reservoir` | `storage_elevation` | `storage_hm3` | `elevation_masl` |
| `hydraulic_unit` | `flow_power` | `flow_m3s` | `power_mw` |

Curvas preparadas pero no obligatorias:

- `storage_area`
- `flow_head_efficiency`
- `flow_loss`
- `head_power`

### `case_hydraulic_curve_bindings`

Bindings obligatorios del MVP:

- Cada `case_hydraulic_node` activo de tipo `reservoir` requiere
  `curve_role = 'storage_elevation'`.
- Cada `case_hydraulic_unit` activa requiere
  `curve_role = 'flow_power'`.

### `case_time_series_bindings`

Senales hidraulicas del MVP:

| Entidad activa | `signal_key` | Requerido |
| --- | --- | --- |
| `case_hydraulic_node` | `natural_inflow_m3s` | Requerido para nodos que declaran condicion de afluente o para embalses sin otro input de agua |
| `case_hydraulic_reach` | `minimum_flow_m3s` | Opcional |
| `case_hydraulic_unit` | `unit_availability_factor` | Preparado, no requerido en MVP |

## Tablas Nuevas Para Layout Del Diagrama

### `case_hydraulic_diagram_layouts`

Guarda layout editable por caso. No contiene fisica hidraulica.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `case_id` | `BIGINT FK optimization_cases(id)` | Si | Caso editable. |
| `layout_key` | `TEXT` | Si | Normalmente `default`. |
| `viewport_x` | `DOUBLE PRECISION` | Si | Pan horizontal. |
| `viewport_y` | `DOUBLE PRECISION` | Si | Pan vertical. |
| `zoom` | `DOUBLE PRECISION` | Si | Zoom actual. |
| `layout_engine` | `TEXT` | No | `manual`, `auto_dag`, `auto_force`, etc. |
| `layout_version` | `INTEGER` | Si | Revision del layout. |
| `content_hash` | `TEXT` | No | Hash del payload de layout. |
| `metadata_json` | `JSONB` | Si | Preferencias visuales. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria y control de concurrencia. |
| `updated_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (case_id, layout_key)`.
- `zoom > 0`.
- Guardar layout no debe cambiar `validation_payload_json` salvo que el
  sistema decida tratar layout como parte del estado dirty visual. No debe
  invalidar fisica ejecutable por si solo.

### `case_hydraulic_diagram_items`

Guarda posicion y estilo por entidad activa del caso.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `diagram_layout_id` | `BIGINT FK case_hydraulic_diagram_layouts(id)` | Si | Layout padre. |
| `entity_type` | `TEXT` | Si | `case_hydraulic_node`, `case_hydraulic_reach`, `case_hydraulic_plant`. |
| `entity_id` | `BIGINT` | Si | ID de la entidad activa. |
| `x` | `DOUBLE PRECISION` | Si | Posicion x. |
| `y` | `DOUBLE PRECISION` | Si | Posicion y. |
| `width` | `DOUBLE PRECISION` | No | Ancho visual opcional. |
| `height` | `DOUBLE PRECISION` | No | Alto visual opcional. |
| `z_index` | `INTEGER` | Si | Orden visual. |
| `collapsed` | `BOOLEAN` | Si | Estado visual. |
| `style_json` | `JSONB` | Si | Estilos no semanticos. |
| `metadata_json` | `JSONB` | Si | Metadata visual. |
| `updated_at` | `TIMESTAMPTZ` | Si | Auditoria. |

Restricciones:

- `UNIQUE (diagram_layout_id, entity_type, entity_id)`.
- Validar por aplicacion que `entity_id` exista en la tabla indicada.
- Las unidades no aparecen como nodos principales en el MVP; su estado visual
  vive en el panel de la central o en `metadata_json` de la planta si hace
  falta.

### `scenario_version_hydraulic_diagram_snapshots`

Guarda el snapshot visual no ejecutable de una version promovida.

| Campo | Tipo sugerido | Requerido | Descripcion |
| --- | --- | --- | --- |
| `id` | `BIGSERIAL PK` | Si | Identificador. |
| `scenario_version_id` | `BIGINT FK scenario_versions(id)` | Si | Version promovida. |
| `source_case_id` | `BIGINT FK optimization_cases(id)` | No | Caso editable de origen. |
| `layout_key` | `TEXT` | Si | Normalmente `default`. |
| `layout_snapshot_json` | `JSONB` | Si | Nodos, arcos, viewport y labels visibles al promover. |
| `layout_content_hash` | `TEXT` | No | Hash del snapshot. |
| `created_at` | `TIMESTAMPTZ` | Si | Auditoria. |
| `created_by` | `TEXT` | Si | Usuario o servicio. |

Restricciones:

- `UNIQUE (scenario_version_id, layout_key)`.
- Este snapshot no participa en la ejecucion. El contrato ejecutable sigue
  siendo `scenario_versions.system_case_json`.

## Checkpoint Vivo De BBDD

Crear y mantener `docs/db/hydro_diagram_db_checkpoint.md`.

Cada issue que cree o cambie tablas debe actualizar:

- Estado objetivo.
- Estado implementado.
- Pendiente.
- Ultima issue que toco BBDD.
- Migraciones o scripts aplicados.
- Validaciones de integridad nuevas.

El checkpoint no reemplaza las migraciones ni la propuesta central. Es una foto
operacional para saber que parte del PRD ya existe realmente en la base de
datos del proyecto.

## Indices Recomendados Adicionales

| Tabla | Indice |
| --- | --- |
| `case_hydraulic_diagram_layouts` | `(case_id, layout_key)` |
| `case_hydraulic_diagram_items` | `(diagram_layout_id, entity_type, entity_id)` |
| `scenario_version_hydraulic_diagram_snapshots` | `(scenario_version_id, layout_key)` |

## Validaciones Nuevas Del MVP

- Todo item de layout debe apuntar a una entidad activa del caso.
- El layout puede omitir entidades nuevas; la UI debe aplicar autolayout para
  entidades sin posicion guardada.
- El snapshot de layout debe generarse en la misma promocion que congela el
  `system_case_json`.
- Cambios de layout puro no deben cambiar el resultado del solver.
- Cambios de topologia, parametros, curvas o series invalidan la validacion
  vigente.

