# BESS-HYDRO-DIAGRAM-009: Persist Layout And Snapshot Promoted Diagrams

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

19 through 22, 48, 50, 57, 61 through 64

## What to build

Complete layout persistence and historical snapshots. The editable diagram
stores node positions, viewport, zoom and visual state by case. Promotion copies
a lightweight non-executable layout snapshot to the promoted scenario version
so that historical versions can be inspected with the visual arrangement used
at promotion time.

This slice should prove that layout edits do not change solver inputs and that
topology edits still invalidate validation.

## Acceptance criteria

- [x] Diagram positions, viewport and zoom persist by case.
- [x] New entities without saved positions receive deterministic autolayout.
- [x] Layout-only changes do not change generated `system_case_json`.
- [x] Promotion creates a scenario-version layout snapshot.
- [x] Historical version view or API can return the layout snapshot read-only.
- [x] Editing the active case after promotion does not modify the historical
      snapshot.
- [x] Backend tests cover layout persistence, autolayout fallback and snapshot
      immutability.
- [x] React tests cover moving nodes, saving layout and reload.
- [x] The DB checkpoint records layout and snapshot table implementation.

## Implementation notes

- New table `scenario_version_hydraulic_diagram_snapshots` stores a lightweight,
  non-executable visual snapshot (positions, viewport, visible labels and
  connectivity) frozen at promotion time. Built by the pure deep module
  `build_hydraulic_diagram_layout_snapshot` and read through
  `GET /api/scenario-versions/{id}/hydraulic-diagram-snapshot`.
- Promotion (`POST /api/scenarios/{id}/hydraulic-diagram/promote`) now persists
  the snapshot after creating the immutable `scenario_version`.
- `normalize_hydraulic_diagram_nodes` applies deterministic grid autolayout
  (`hydraulic_autolayout_position`) when a node is saved without `x`/`y`; the
  save request now accepts optional positions.
- The snapshot omits hydraulic physics, so editing the active case after
  promotion (including moving nodes) leaves the historical snapshot and the
  executable `system_case_json` unchanged.
- Fixed two pre-existing multi-backend defects that blocked the diagram on
  PostgreSQL: nine hydraulic `id` tables (issues 003/004/007/008) were missing
  from `ID_TABLES` so their inserts never returned an id, and the
  `case_hydraulic_diagram_items` entity-type check constraint predated reach and
  plant support on databases created before those iterations.

## Verification

- `python -m unittest discover tests` (136 ok, 1 skipped; +4 layout/snapshot/
  autolayout tests, +1 `ID_TABLES` guard test).
- `julia --project=. -e "import Pkg; Pkg.test()"` (532 ok).
- `npm test` (26 ok, incl. move-node/save/reload), `npm run build`,
  `eslint .`, `prettier --check` (changed files clean), `npm run api:generate`
  + `npm run api:check`.
- `npm run test:browser -- -g "hydraulic diagram persists"` (1 passed).
- Chrome DevTools MCP end-to-end against live PostgreSQL + Julia: saved a full
  v3 diagram, validated, promoted, fetched the read-only snapshot (positions
  frozen, no physics), then edited the active layout and confirmed both the
  snapshot and the generated `system_case_json` were unchanged; verified
  deterministic autolayout for nodes saved without positions.

## Blocked by

BESS-HYDRO-DIAGRAM-006

