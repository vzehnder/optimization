# BESS-HYDRO-DIAGRAM-006: Run A Minimal v3 Hydraulic Network Case End To End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

18, 48 through 54, 65 through 68

## What to build

Turn the valid minimal v3 network into an executable scenario version and run
it through the existing manual run workflow. The first supported case should
cover a simple directed network with one reservoir, one plant, one
generation-only unit, intake/discharge nodes, non-delayed reaches and a complete
inflow input.

The solver should remain explicit about unsupported features. Travel time,
cycles, head-dependent generation, pumping and reversible units should fail
before solve.

## Acceptance criteria

- [x] A validated v3 hydraulic diagram can be promoted to an immutable
      `scenario_version`.
- [x] The promoted version stores the generated `system_case_json`.
- [x] The manual run workflow accepts the v3 scenario version.
- [x] Julia solves the minimal supported v3 hydraulic network.
- [x] Run artifacts include resolved v3 input, metadata, dispatch, asset
      dispatch and summary outputs.
- [x] Results include generation, turbine flow, storage and elevation for the
      supported network.
- [x] Unsupported v3 features fail with explicit validation errors before solve.
- [x] Existing v1 and v2 run regressions remain green.
- [x] Python acceptance tests cover promotion and manual run from the diagram.
- [x] Julia tests cover v3 load, solve, outputs and legacy regression.

## Implementation notes

- Added `/api/scenarios/{scenario_id}/hydraulic-diagram/promote`.
- Promotion requires a successful, non-stale `hydraulic_v3_preview` snapshot
  and stores that exact `system_case_json` in an immutable `scenario_version`
  with `hydraulic_diagram_v3` generation metadata.
- The v3 preview now includes a minimal executable `time_series` block with
  `natural_inflow_m3s` values. Real bound inflow series remain scoped to
  BESS-HYDRO-DIAGRAM-007.
- Added a separate Julia execution path for `bess_system_dispatch.v3` that
  validates unsupported routing, pumping/reversibility and head-dependent
  generation before solve, rejects cyclic hydraulic graphs, then solves the
  minimal linear hydraulic network and writes `summary.json`, `dispatch.csv`,
  `asset_dispatch.csv`,
  `system_case_resolved.json` and `model_metadata.json`.
- Added React controls to promote a validated v3 diagram from the hydraulic
  editor and surface the promoted version number.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_hydraulic_diagram tests.test_manual_runs tests.test_draft_generated_system_case -v`
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests -v`
- `julia --project=. test\\runtests.jl`
- `npm.cmd test`
- `npm.cmd run build`
- `npm.cmd run api:check`
- Chrome/@chrome smoke local: promoted a validated v3 hydraulic diagram from
  the editor and verified the created `bess_system_dispatch.v3` scenario
  version metadata.

## Blocked by

BESS-HYDRO-DIAGRAM-005
