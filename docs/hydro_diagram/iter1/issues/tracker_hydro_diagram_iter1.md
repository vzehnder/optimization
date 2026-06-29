# BESS Hydro Diagram Iteration 1 Issue Tracker

This document is the local tracker for the hydraulic diagram editor iteration
derived from `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md` and
`docs/hydro_diagram/iter1/database_extension.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-HYDRO-DIAGRAM-000 | Review Hydro Diagram PRD And DB Extension | HITL | ready-for-agent | Done | None | [BESS-HYDRO-DIAGRAM-000-review-hydro-diagram-prd-and-db-extension.md](BESS-HYDRO-DIAGRAM-000-review-hydro-diagram-prd-and-db-extension.md) |
| BESS-HYDRO-DIAGRAM-001 | Create A Minimal Persisted Hydraulic Diagram Case | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-000 | [BESS-HYDRO-DIAGRAM-001-create-a-minimal-persisted-hydraulic-diagram-case.md](BESS-HYDRO-DIAGRAM-001-create-a-minimal-persisted-hydraulic-diagram-case.md) |
| BESS-HYDRO-DIAGRAM-002 | Draw And Validate Directed Hydraulic Reaches | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-001 | [BESS-HYDRO-DIAGRAM-002-draw-and-validate-directed-hydraulic-reaches.md](BESS-HYDRO-DIAGRAM-002-draw-and-validate-directed-hydraulic-reaches.md) |
| BESS-HYDRO-DIAGRAM-003 | Edit Reservoir Parameters And Storage-Elevation Curves | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-002 | [BESS-HYDRO-DIAGRAM-003-edit-reservoir-parameters-and-storage-elevation-curves.md](BESS-HYDRO-DIAGRAM-003-edit-reservoir-parameters-and-storage-elevation-curves.md) |
| BESS-HYDRO-DIAGRAM-004 | Edit Plants, Units, And Flow-Power Curves | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-003 | [BESS-HYDRO-DIAGRAM-004-edit-plants-units-and-flow-power-curves.md](BESS-HYDRO-DIAGRAM-004-edit-plants-units-and-flow-power-curves.md) |
| BESS-HYDRO-DIAGRAM-005 | Generate And Validate A v3 Network Payload | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-004 | [BESS-HYDRO-DIAGRAM-005-generate-and-validate-a-v3-network-payload.md](BESS-HYDRO-DIAGRAM-005-generate-and-validate-a-v3-network-payload.md) |
| BESS-HYDRO-DIAGRAM-006 | Run A Minimal v3 Hydraulic Network Case End To End | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-005 | [BESS-HYDRO-DIAGRAM-006-run-a-minimal-v3-hydraulic-network-case-end-to-end.md](BESS-HYDRO-DIAGRAM-006-run-a-minimal-v3-hydraulic-network-case-end-to-end.md) |
| BESS-HYDRO-DIAGRAM-007 | Bind Natural Inflow Series To Hydraulic Nodes | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-006 | [BESS-HYDRO-DIAGRAM-007-bind-natural-inflow-series-to-hydraulic-nodes.md](BESS-HYDRO-DIAGRAM-007-bind-natural-inflow-series-to-hydraulic-nodes.md) |
| BESS-HYDRO-DIAGRAM-008 | Add Reach Minimum Flow And Spillway Controls | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-007 | [BESS-HYDRO-DIAGRAM-008-add-reach-minimum-flow-and-spillway-controls.md](BESS-HYDRO-DIAGRAM-008-add-reach-minimum-flow-and-spillway-controls.md) |
| BESS-HYDRO-DIAGRAM-009 | Persist Layout And Snapshot Promoted Diagrams | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-006 | [BESS-HYDRO-DIAGRAM-009-persist-layout-and-snapshot-promoted-diagrams.md](BESS-HYDRO-DIAGRAM-009-persist-layout-and-snapshot-promoted-diagrams.md) |
| BESS-HYDRO-DIAGRAM-010 | Reject Unsupported Topologies And Stale Promotions | AFK | ready-for-agent | Done | BESS-HYDRO-DIAGRAM-008, BESS-HYDRO-DIAGRAM-009 | [BESS-HYDRO-DIAGRAM-010-reject-unsupported-topologies-and-stale-promotions.md](BESS-HYDRO-DIAGRAM-010-reject-unsupported-topologies-and-stale-promotions.md) |
| BESS-HYDRO-DIAGRAM-011 | Finalize Acceptance Suite Docs And DB Checkpoint | AFK | ready-for-agent | Todo | BESS-HYDRO-DIAGRAM-001 through BESS-HYDRO-DIAGRAM-010 | [BESS-HYDRO-DIAGRAM-011-finalize-acceptance-suite-docs-and-db-checkpoint.md](BESS-HYDRO-DIAGRAM-011-finalize-acceptance-suite-docs-and-db-checkpoint.md) |

## Recommended Execution Order

1. BESS-HYDRO-DIAGRAM-000
2. BESS-HYDRO-DIAGRAM-001
3. BESS-HYDRO-DIAGRAM-002
4. BESS-HYDRO-DIAGRAM-003
5. BESS-HYDRO-DIAGRAM-004
6. BESS-HYDRO-DIAGRAM-005
7. BESS-HYDRO-DIAGRAM-006
8. BESS-HYDRO-DIAGRAM-007
9. BESS-HYDRO-DIAGRAM-008
10. BESS-HYDRO-DIAGRAM-009 can proceed after the first promoted v3 path exists.
11. BESS-HYDRO-DIAGRAM-010 hardens unsupported graph and stale validation
    behavior after the core path exists.
12. BESS-HYDRO-DIAGRAM-011 closes the iteration.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-06-26 | All | Created | Initial local issue set generated from the hydro diagram PRD, database extension and approved grill-me decisions. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-000 | Todo -> Done | Reviewed and accepted the hydro diagram PRD, database extension, `bess_system_dispatch.v3` decision, MVP solver limitations, issue granularity and DB checkpoint rule against the final objective, completed Iteration 5 hydro workflow, Iteration 6 publication boundary, React migration plan and central database proposal. No corrections were required. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-001 | Todo -> Done | Implemented the first persisted hydraulic diagram path with normalized optimization-case tables, base/active hydraulic nodes and plants, editable layout persistence, stale revision rejection, React editor controls and focused backend/React tests. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-002 | Todo -> Done | Added directed hydraulic reaches with base/active tables, diagram layout items, edit-save-reload API contract, topology validation endpoint, React drag/drop creation, fallback reach editing form, validation display, Playwright coverage and DB checkpoint update. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-003 | Todo -> Done | Added per-case reservoir parameter and versioned `storage_elevation` curve tables, save/reload of storage bounds, terminal condition, terminal water value and curve points (create-or-reuse versions plus select existing version), reservoir validation rules (required parameters and curve, monotonic storage, non-decreasing elevation, curve-domain bounds, terminal settings), React reservoir panel with curve table editor and version select, backend/React/Playwright coverage, OpenAPI regeneration and DB checkpoint update. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-004 | Todo -> Done | Added `hydraulic_units`/`case_hydraulic_units` tables, plant aggregate-limit and `non_modeled` columns, and versioned per-unit `flow_power` curves (shared spec-driven curve persistence). Save persists plant params, units (intake/discharge nodes, power/flow limits, active flag) and `flow_power` bindings; validation requires active units per active plant (unless non-modeled), distinct active intake/discharge nodes, and a valid `flow_power` curve. Added React plant panel with unit subeditor and curve table/version select, backend tests (persist/reload + 4 validation cases), a React plant-panel test, extended Playwright hydraulic e2e (real chromium), OpenAPI regeneration and DB checkpoint update. |
| 2026-06-26 | BESS-HYDRO-DIAGRAM-005 | Todo -> Done | Added deterministic `bess_system_dispatch.v3` preview generation from normalized hydraulic diagrams, Julia validation-only support for valid/malformed v3 network payloads, persisted validation snapshots with stale detection via payload hash, React read-only v3 preview display, OpenAPI regeneration and DB checkpoint update. Verified focused/full Python, React unit/build/API checks, full Julia package tests and Chrome smoke preview rendering. |
| 2026-06-27 | BESS-HYDRO-DIAGRAM-006 | Todo -> Done | Added validated v3 diagram promotion to immutable scenario versions, executable minimal v3 time-series payloads, manual-run acceptance, a Julia v3 hydraulic solver/writer for the supported one-reservoir/one-unit acyclic network, React promotion controls, OpenAPI regeneration and DB checkpoint update. Verified focused/full Python, full Julia package tests, React/API/build checks and Chrome/@chrome promotion smoke. |
| 2026-06-27 | BESS-HYDRO-DIAGRAM-007 | Todo -> Done | Added the full `natural_inflow_m3s` time-series path: versioned `hydraulic_time_series_sets`/`hydraulic_time_series_points`/`case_hydraulic_time_series_bindings`, inline-series save/reload for any active hydraulic node (not only reservoirs), v3 preview resolving bound series into the executable `time_series` block, validation rules (missing required reservoir inflow, negative, nonnumeric, horizon mismatch), Julia water-balance regression proving the bound series drives reservoir storage, a React natural-inflow panel, OpenAPI regeneration, Playwright coverage and DB checkpoint update. Verified focused/full Python (124 ok), full Julia (519 ok), React unit (25 ok), tsc/eslint, OpenAPI regen and the hydraulic Playwright e2e (1 passed). |
| 2026-06-29 | BESS-HYDRO-DIAGRAM-009 | Todo -> Done | Completed layout persistence and promotion snapshots: new `scenario_version_hydraulic_diagram_snapshots` table, pure `build_hydraulic_diagram_layout_snapshot` deep module, snapshot frozen on promotion and read via `GET /api/scenario-versions/{id}/hydraulic-diagram-snapshot`, deterministic autolayout for nodes saved without positions (optional `x`/`y`), and proof that layout-only edits change neither the historical snapshot nor `system_case_json`. Also fixed two pre-existing PostgreSQL defects that blocked the diagram end-to-end (nine hydraulic `id` tables missing from `ID_TABLES`; stale `case_hydraulic_diagram_items` entity-type check constraint) plus an `ID_TABLES` regression guard test. Verified Python (136 ok), Julia (532 ok), React (26 ok), hydraulic Playwright (1 passed), OpenAPI regen + api:check, and a full Chrome DevTools MCP smoke against live PostgreSQL + Julia (save/validate/promote/snapshot/immutability/autolayout). |
| 2026-06-29 | BESS-HYDRO-DIAGRAM-010 | Todo -> Done | Hardened topology validation against MVP-unsupported shapes via the new deep module `_validate_unsupported_topology` plus pure graph helpers `hydraulic_first_cycle`/`hydraulic_weakly_connected_components`: detects unsupported reach routing/travel-time, directed cycles, disconnected islands without a boundary condition (reservoir or natural inflow) and head-dependent/pump-only/reversible unit modes, each with `entity_type`/`entity_id`/`technical_key`. Reaches now persist `routing_method`/`travel_time_hours`; `hydraulic_units` gains `operation_mode`/`generation_mode` (defaults `generation`/`flow_power_curve`) via `_ensure_column`. Stale-after-edit and missing/stale promotion blocks are covered by tests. React renders each validation error as a focus button that selects the affected node/reach (`data-focused`/`aria-current`). Verified Python (155 ok, 1 skipped), Julia (532 ok), React (26 ok), tsc/eslint, OpenAPI regen + api:check, hydraulic Playwright (1 passed) and a Chrome DevTools MCP smoke against live PostgreSQL (cycle/routing/pump/island validation + error-to-component focus). |
| 2026-06-28 | BESS-HYDRO-DIAGRAM-008 | Todo -> Done | Added reach operational controls: persisted scalar `case_hydraulic_reaches.flow_min_m3s`/`spill_penalty_usd_per_hm3`, series-backed reach minimum flow over the versioned hydraulic time-series tables (`entity_type = 'case_hydraulic_reach'`, `signal_key = 'minimum_flow_m3s'`), v3 preview emitting per-reach controls plus per-period `minimum_flow_m3s` blocks, validation (`negative_minimum_flow`, `negative_spill_penalty`, `spill_penalty_requires_spillway`, `minimum_flow_horizon_mismatch`), Julia v3 enforcement of minimum flow on the reservoir-source reach plus spillway penalty in the objective and `total_spill_penalty_usd` in the run summary, a React reach panel with scalar min flow, spill penalty and a minimum-flow series sub-editor, OpenAPI regeneration and DB checkpoint update. Verified focused/full Python (28/131 ok), full Julia (Pkg test), React unit (25 ok), tsc/eslint, OpenAPI regen + api:check and a Chrome smoke. |

## Regression Guard

Every slice that changes Python backend behavior should run focused API and
acceptance tests for the touched route plus the relevant Iteration 3 through 6
regression suites.

Every slice that changes React should run:

```powershell
npm.cmd test
npm.cmd run check
```

Slices that change browser-visible diagram behavior should add or update
Playwright coverage and run:

```powershell
npm.cmd run test:browser
```

Every slice that changes Julia contracts, loader validation, solver behavior or
artifact formats must run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Every slice that creates or changes database tables must update:

```text
docs/db/hydro_diagram_db_checkpoint.md
```

## Dependency Notes

- BESS-HYDRO-DIAGRAM-000 is HITL because the PRD, BBDD extension and issue
  breakdown should be accepted before implementation.
- BESS-HYDRO-DIAGRAM-001 creates the first saved diagram state through BBDD,
  API and React.
- BESS-HYDRO-DIAGRAM-002 adds water connectivity and topology validation.
- BESS-HYDRO-DIAGRAM-003 makes reservoirs executable by adding required
  parameters and quota-volume curves.
- BESS-HYDRO-DIAGRAM-004 adds central and unit detail needed for generation.
- BESS-HYDRO-DIAGRAM-005 creates the first `bess_system_dispatch.v3` payload
  boundary before solving.
- BESS-HYDRO-DIAGRAM-006 proves the minimal v3 network can run end to end.
- BESS-HYDRO-DIAGRAM-007 connects real hydrology time series after the minimal
  run path exists.
- BESS-HYDRO-DIAGRAM-008 adds reach-level operational constraints.
- BESS-HYDRO-DIAGRAM-009 freezes historical visual context after promotion is
  real.
- BESS-HYDRO-DIAGRAM-010 hardens unsupported topologies and stale validation.
- BESS-HYDRO-DIAGRAM-011 is the final proof that the iteration satisfies the
  PRD and preserves previous behavior.
