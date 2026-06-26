# Hydro Diagram Editor PRD

Fecha: 2026-06-26

## Problem Statement

La aplicacion ya puede crear y ejecutar casos one-bus con BESS, grid,
renovables, carga e hidroelectricidad simple. La hidroelectricidad actual
representa un activo `hydro` como un embalse independiente con una planta
asociada. Ese modelo permite cerrar la Iteracion 5, pero no permite representar
la estructura real de una cuenca con embalses, tramos, centrales, unidades,
vertederos, bypasses, restricciones de caudal y curvas versionadas por
componente.

El usuario necesita construir estos sistemas como un diagrama editable. Debe
poder agregar componentes hidraulicos, conectarlos, hacer clic en un componente
y editar sus caracteristicas. El diagrama debe guardar la topologia activa de
un caso de optimizacion, reutilizar objetos fisicos del proyecto, validar la
red antes de promocion y generar un snapshot ejecutable inmutable.

La BBDD propuesta en
`docs/db/propuesta_bbdd_componentes_timeseries.md` ya define una normalizacion
amplia para red hidraulica futura. Esta iteracion debe convertir esa propuesta
en un alcance producto claro para un editor visual React, un contrato ejecutable
`bess_system_dispatch.v3`, un solver inicial limitado y un checkpoint vivo de
BBDD en `docs/db/hydro_diagram_db_checkpoint.md`.

## Solution

Crear una primera iteracion end-to-end del editor de diagrama hidraulico.

El analista trabajara sobre un caso editable normalizado. El diagrama mostrara
la topologia activa del caso y reutilizara una red base del proyecto. El usuario
podra agregar embalses, nodos de union, tomas, restituciones, centrales y
tramos dirigidos. Las centrales seran nodos visibles; sus unidades se editaran
en el panel lateral de la central.

Cada embalse requerira parametros de almacenamiento y una curva versionada
`storage_elevation`. Cada unidad activa requerira una curva `flow_power` o modo
lineal equivalente. Los tramos tendran tipo operacional, limites opcionales y
caudal minimo opcional. Los afluentes naturales se vincularan como
`natural_inflow_m3s` a cualquier nodo hidraulico.

La UI principal sera React. El editor usara guardado explicito, validacion en
vivo, estado dirty visible, drag-and-drop para crear conexiones y formulario de
respaldo para editar origen/destino. El layout visual se guardara por caso y la
promocion congelara un snapshot liviano no ejecutable del layout junto con el
snapshot `system_case_json`.

El primer solver `v3` sera deliberadamente limitado. Debe ejecutar una red
dirigida simple con embalse, central, unidad, tramo de descarga y afluente
natural. No incluira tiempo de viaje, routing avanzado, bombeo, unidades
reversibles, generacion dependiente de head, superficies 2D ni importacion
masiva de topologia. La BBDD quedara preparada para esas extensiones.

## User Stories

1. As an analyst, I want to open a hydraulic diagram for a scenario case, so
   that I can model water topology visually.
2. As an analyst, I want the diagram to edit the active case topology, so that
   different scenarios can use different subsets of the same physical network.
3. As an analyst, I want the diagram to reuse base hydraulic objects from the
   project, so that physical names and identifiers do not have to be recreated
   in every case.
4. As an analyst, I want to create a reservoir node, so that storage can be
   represented explicitly.
5. As an analyst, I want to create junction, intake, tailrace and river inflow
   nodes, so that the water graph can represent practical topology.
6. As an analyst, I want to create a plant node, so that a hydroelectric plant
   is visible in the diagram.
7. As an analyst, I want to edit units inside the plant panel, so that the main
   diagram stays readable while unit-level parameters remain available.
8. As an analyst, I want each unit to have intake and discharge nodes, so that
   the hydraulic balance is traceable.
9. As an analyst, I want to draw directed reaches between nodes, so that water
   flow direction is explicit.
10. As an analyst, I want reaches to have types such as river, canal, tunnel,
    gate, spillway, bypass and tailrace, so that operational behavior can be
    captured consistently.
11. As an analyst, I want drag-and-drop reach creation, so that diagram editing
    is fast.
12. As an analyst, I want a form fallback for reach origin and destination, so
    that dense diagrams can still be edited precisely.
13. As an analyst, I want stable technical keys and editable display names, so
    that payloads remain traceable while the UI stays understandable.
14. As an analyst, I want to save diagram edits explicitly, so that partial
    invalid edits are not persisted accidentally.
15. As an analyst, I want visible dirty, saving, saved and failed states, so
    that I know whether the persisted case matches what I see.
16. As an analyst, I want validation feedback while editing, so that topology
    and parameter mistakes are caught before promotion.
17. As an analyst, I want any edit after validation to invalidate promotion, so
    that stale validation cannot produce a scenario version.
18. As an analyst, I want promoted scenario versions to remain immutable, so
    that historical runs are reproducible.
19. As an analyst, I want a promoted version to preserve a diagram layout
    snapshot, so that I can inspect the historical diagram later.
20. As an analyst, I want the editable layout to be separate from the physical
    network, so that moving nodes does not change engineering data.
21. As an analyst, I want automatic layout for new diagrams, so that I can start
    from a readable graph without manual positioning.
22. As an analyst, I want node positions to persist across sessions, so that my
    diagram organization is not lost.
23. As an analyst, I want to edit reservoir storage bounds and initial storage,
    so that the water balance starts from known operating data.
24. As an analyst, I want to edit reservoir terminal conditions, so that the end
    of horizon does not drain water unrealistically.
25. As an analyst, I want to edit terminal water value, so that stored water can
    have economic value.
26. As an analyst, I want to create and edit a reservoir storage-elevation
    curve, so that quota-volume behavior is auditable.
27. As an analyst, I want storage-elevation curves to be versioned, so that
    cases can reuse or freeze specific curve versions.
28. As an analyst, I want reservoir curve points validated for monotonic
    storage and nondecreasing elevation, so that invalid curves fail early.
29. As an analyst, I want each unit to have a flow-power curve, so that
    generation can depend on turbine flow.
30. As an analyst, I want flow-power curves to be editable as points, so that I
    can model nonlinear unit behavior without writing JSON.
31. As an analyst, I want to select existing curve versions, so that I can reuse
    approved engineering data.
32. As an analyst, I want one active flow-power curve per unit in the MVP, so
    that the solver has an unambiguous input.
33. As an analyst, I want future curve roles prepared but not required, so that
    head-dependent generation can be added later.
34. As an analyst, I want to bind natural inflow to any hydraulic node, so that
    lateral inflows and intermediate river inputs can be represented.
35. As an analyst, I want hydro time-series bindings to use versioned sets, so
    that hydrology scenarios can be swapped without changing physical data.
36. As an analyst, I want missing required inflow bindings to fail validation,
    so that generated cases are complete.
37. As an analyst, I want negative inflow values rejected, so that physical
    inputs are sane.
38. As an analyst, I want optional minimum flow on reaches, so that simple
    environmental constraints can be represented.
39. As an analyst, I want minimum flow to be either scalar or series-backed, so
    that constant and time-varying requirements are both possible.
40. As an analyst, I want spillways represented as reaches, so that spilling is
    visible in the same graph as other water movement.
41. As an analyst, I want optional spill penalties on spillway reaches, so that
    objective behavior can discourage spill.
42. As an analyst, I want the editor to allow drawing general directed graphs,
    so that future topologies are not blocked by the UI.
43. As an analyst, I want validation to reject unsupported cycles for the MVP
    solver, so that the executable payload stays within model capability.
44. As an analyst, I want multiple disconnected hydraulic islands allowed only
    with clear boundary conditions, so that incomplete passive graphs do not
    run.
45. As an analyst, I want validation errors to identify the affected component,
    so that I can click into the diagram and fix it.
46. As an analyst, I want a read-only generated `bess_system_dispatch.v3`
    preview, so that I can inspect the exact solver input.
47. As an analyst, I want Julia validation for the `v3` payload, so that app
    validation and optimizer validation agree.
48. As an analyst, I want to promote a validated hydraulic diagram to an
    immutable scenario version, so that it can be executed and audited.
49. As an analyst, I want a minimal `v3` hydraulic network to run end-to-end, so
    that the diagram is not just documentation.
50. As an analyst, I want run artifacts to include the resolved `v3` case, so
    that the executed network is auditable.
51. As an analyst, I want results to report generation by unit or plant, so that
    dispatch can be reviewed operationally.
52. As an analyst, I want results to report reservoir storage and elevation, so
    that water state is visible.
53. As an analyst, I want results to report turbine flow, reach flow, spill and
    minimum-flow violations or slacks where applicable, so that hydraulic
    constraints are inspectable.
54. As an analyst, I want previous `v1` and `v2` cases to keep running, so that
    this feature does not break existing work.
55. As an analyst, I want topology import from CSV/XLSX left out of the MVP, so
    that the first iteration stays focused.
56. As an analyst, I want curve and time-series import to remain supported, so
    that large numeric inputs do not have to be typed manually.
57. As a maintainer, I want the hydraulic diagram APIs to be reusable by React,
    so that UI and backend contracts stay testable.
58. As a maintainer, I want diagram domain logic separated from the diagram
    rendering library, so that model tests do not depend on canvas internals.
59. As a maintainer, I want topology validation implemented as a deep module, so
    that it can be tested without browser tests.
60. As a maintainer, I want `v3` generation implemented as a deep module, so
    that DB/case state can be tested against stable payloads.
61. As a maintainer, I want BBDD migrations to update a checkpoint document, so
    that the real schema state is visible during implementation.
62. As a maintainer, I want the checkpoint to distinguish target design from
    implemented state, so that docs do not imply unfinished tables are live.
63. As a maintainer, I want no real-time collaborative editing in the MVP, so
    that conflict handling remains simple.
64. As a maintainer, I want optimistic concurrency with `updated_at` or a
    revision token, so that stale saves do not silently overwrite newer data.
65. As a Julia maintainer, I want `bess_system_dispatch.v3` to be distinct from
    `v2`, so that simple hydro and network hydro contracts remain clear.
66. As a Julia maintainer, I want the first solver to reject unsupported routing
    and head-dependent modes, so that future fields do not imply support.
67. As a Julia maintainer, I want regression tests for `v1` and `v2`, so that
    adding `v3` preserves existing contracts.
68. As a product owner, I want issues split into demoable vertical slices, so
    that agents can implement one piece at a time.

## Implementation Decisions

- The editor is an Iteration 1 under `docs/hydro_diagram/iter1/`.
- The editable object is the active topology of an `optimization_case`, not a
  `scenario_version`.
- Base physical objects live at project scope in `hydraulic_systems`,
  `hydraulic_nodes`, `hydraulic_reaches`, `hydraulic_plants` and
  `hydraulic_units`.
- Case activation and parameters live in `case_hydraulic_systems`,
  `case_hydraulic_nodes`, `case_hydraulic_reaches`,
  `case_hydraulic_plants`, `case_hydraulic_units` and specialized parameter
  tables.
- `scenario_versions.system_case_json` remains the immutable executable
  snapshot.
- The executable network-hydro contract is `bess_system_dispatch.v3`.
- `bess_system_dispatch.v1` and `bess_system_dispatch.v2` remain valid and
  executable.
- The first `v3` solver supports a simple directed network: at least one
  reservoir, one plant, one generation-only unit, intake/discharge nodes,
  natural inflow and non-delayed reaches.
- The first `v3` solver does not support travel-time routing, cycles,
  head-dependent generation, pumped storage, reversible units, stochastic
  inflows, topology import or collaborative editing.
- The React UI is the primary surface. The legacy server-rendered editor does
  not get equivalent diagram editing.
- The diagram rendering implementation must keep domain state and validation
  independent from the rendering library.
- The main diagram shows reservoirs, hydraulic nodes, reaches and plants.
  Units are edited inside the plant panel.
- Drag-and-drop creates reaches; a form can edit origin, destination and type.
- Reaches are directed and typed with values such as `river`, `canal`,
  `tunnel`, `gate`, `spillway`, `bypass`, `tailrace` and `other`.
- Reservoirs require `storage_elevation` curve bindings.
- Units require one active `flow_power` curve binding in the MVP.
- Curves are stored in `hydraulic_curve_sets` and `hydraulic_curve_points`.
  Editing a curve creates or updates a versioned curve set according to the
  status rules adopted during implementation.
- `natural_inflow_m3s` is a time-series signal for any active
  `case_hydraulic_node`.
- `minimum_flow_m3s` on reaches can be scalar through case reach parameters or
  series-backed through `case_time_series_bindings`.
- Layout is persisted separately from hydraulic physics.
- A promoted version stores a lightweight non-executable layout snapshot for
  historical review.
- Saving is explicit. The UI validates locally and through backend APIs, but
  database writes happen through intentional save actions.
- Edits after validation mark the case stale and block promotion until
  revalidation.
- No real-time collaborative editing is included. API updates use `updated_at`
  or a revision token to reject stale writes.
- Every issue that creates or changes BBDD tables must update
  `docs/db/hydro_diagram_db_checkpoint.md` with target, implemented, pending
  and last DB-touching issue.
- The local issue tracker is Markdown under
  `docs/hydro_diagram/iter1/issues/` because no external issue tracker
  integration is configured.

## Testing Decisions

- Tests should assert external behavior and contracts, not implementation
  details or rendering-library internals.
- Topology validation should be tested as a pure/deep module: active entities
  in, validation errors and warnings out.
- `v3` generation should be tested as a pure/deep module: normalized case in,
  stable `system_case_json` out.
- Backend API tests should cover create, update, save, stale save rejection,
  validation, generated preview, promotion and layout snapshot behavior.
- React component tests should focus on editor state, dirty/save behavior,
  panel edits, curve table editing, reach creation form fallback and accessible
  validation summaries.
- Browser tests should cover the primary diagram workflow: create nodes, draw a
  reach, edit panel fields, save, reload, validate, promote and run the minimal
  network.
- Julia tests should cover `bess_system_dispatch.v3` parsing, validation,
  solving for the minimal network, artifacts and `v1`/`v2` regression.
- Time-series tests should prove `natural_inflow_m3s` can bind to any hydraulic
  node, rejects missing/negative values and participates in a `v3` run.
- Reach constraint tests should prove scalar and series-backed minimum flow
  behavior, plus spillway penalty behavior where supported.
- Checkpoint tests are manual/documentary: any DB-touching PR must update
  `docs/db/hydro_diagram_db_checkpoint.md`.

## Out of Scope

- Importacion masiva de topologia desde CSV/XLSX.
- Edicion colaborativa en tiempo real, presencia, comentarios o merge de
  conflictos.
- Redes electricas multi-bus.
- Routing hidraulico avanzado, tiempo de viaje y retardos discretos.
- Ciclos hidraulicos ejecutables en el MVP.
- Generacion dependiente de head o cota.
- Superficies 2D de eficiencia.
- Bombeo, unidades reversibles y pumped storage.
- Optimizacion estocastica, rolling horizon o forecast avanzado.
- Editor equivalente en UI server-rendered legacy.
- Migracion completa desde `scenario_drafts` JSON hacia BBDD normalizada para
  todos los tipos de activo.
- Consolidar la extension dentro de
  `docs/db/propuesta_bbdd_componentes_timeseries.md` durante esta pasada
  documental.

## Further Notes

La iteracion debe ser tratada como el puente entre hidro simple y red
hidraulica normalizada. El resultado deseado no es un simulador hidraulico
general: es una primera ruta producto que permite dibujar, guardar, validar,
promover y ejecutar una red hidraulica simple, dejando extensiones preparadas
sin prometerlas al solver.

El checkpoint de BBDD en `docs/db/hydro_diagram_db_checkpoint.md` es parte del
producto de esta iteracion. Debe mantenerse vivo a medida que avancen las
issues para mostrar que esta disenado, que esta implementado, que esta
pendiente y cual fue la ultima issue que modifico BBDD.

