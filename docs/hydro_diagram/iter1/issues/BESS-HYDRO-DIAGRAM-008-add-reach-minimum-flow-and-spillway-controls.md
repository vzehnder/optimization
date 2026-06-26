# BESS-HYDRO-DIAGRAM-008: Add Reach Minimum Flow And Spillway Controls

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

10, 38 through 41, 45, 49 through 54, 57 through 62, 66

## What to build

Add the first operational reach controls. An analyst can select a reach, define
a scalar `minimum_flow_m3s` or bind a series-backed minimum flow, mark a reach
as `spillway`, set an optional spill penalty and run a v3 case that respects the
supported reach behavior.

The slice should expose reach-specific validation and results so that minimum
flow and spill behavior can be inspected after a run.

## Acceptance criteria

- [ ] The reach panel supports scalar minimum flow.
- [ ] The reach panel supports a series binding for `minimum_flow_m3s` where
      the time-series path exists.
- [ ] The reach panel supports `spillway` type and spill penalty.
- [ ] Validation rejects negative minimum flow and negative spill penalty.
- [ ] Validation rejects series-backed minimum flow with incompatible horizon.
- [ ] The v3 solver enforces supported minimum-flow behavior.
- [ ] The v3 objective applies supported spillway penalty behavior.
- [ ] Results expose reach flow and spill metrics needed to inspect behavior.
- [ ] Tests cover scalar minimum flow, series minimum flow, spill penalty and
      invalid inputs.
- [ ] The DB checkpoint records reach parameter and binding changes.

## Blocked by

BESS-HYDRO-DIAGRAM-007

