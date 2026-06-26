# BESS-HYDRO-DIAGRAM-006: Run A Minimal v3 Hydraulic Network Case End To End

Status: Todo
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

- [ ] A validated v3 hydraulic diagram can be promoted to an immutable
      `scenario_version`.
- [ ] The promoted version stores the generated `system_case_json`.
- [ ] The manual run workflow accepts the v3 scenario version.
- [ ] Julia solves the minimal supported v3 hydraulic network.
- [ ] Run artifacts include resolved v3 input, metadata, dispatch, asset
      dispatch and summary outputs.
- [ ] Results include generation, turbine flow, storage and elevation for the
      supported network.
- [ ] Unsupported v3 features fail with explicit validation errors before solve.
- [ ] Existing v1 and v2 run regressions remain green.
- [ ] Python acceptance tests cover promotion and manual run from the diagram.
- [ ] Julia tests cover v3 load, solve, outputs and legacy regression.

## Blocked by

BESS-HYDRO-DIAGRAM-005

