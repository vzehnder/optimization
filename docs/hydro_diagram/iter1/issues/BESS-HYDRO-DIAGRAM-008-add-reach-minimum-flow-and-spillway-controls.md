# BESS-HYDRO-DIAGRAM-008: Add Reach Minimum Flow And Spillway Controls

Status: Done
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

- [x] The reach panel supports scalar minimum flow.
- [x] The reach panel supports a series binding for `minimum_flow_m3s` where
      the time-series path exists.
- [x] The reach panel supports `spillway` type and spill penalty.
- [x] Validation rejects negative minimum flow and negative spill penalty.
- [x] Validation rejects series-backed minimum flow with incompatible horizon.
- [x] The v3 solver enforces supported minimum-flow behavior.
- [x] The v3 objective applies supported spillway penalty behavior.
- [x] Results expose reach flow and spill metrics needed to inspect behavior.
- [x] Tests cover scalar minimum flow, series minimum flow, spill penalty and
      invalid inputs.
- [x] The DB checkpoint records reach parameter and binding changes.

## Implementation notes

- Scalar `case_hydraulic_reaches.flow_min_m3s` and
  `spill_penalty_usd_per_hm3` are persisted from the save payload; series-backed
  minimum flow reuses the versioned hydraulic time-series tables with
  `entity_type = 'case_hydraulic_reach'`, `signal_key = 'minimum_flow_m3s'`.
- The v3 preview emits `flow_min_m3s`/`flow_min_source`/`spill_penalty_usd_per_hm3`
  per reach and resolves bound series into per-period
  `time_series[*].minimum_flow_m3s` blocks keyed by reach id.
- The Julia v3 solver enforces minimum flow on the reservoir-source reach
  (turbine flow lower bound, or spill lower bound for spillway reaches),
  subtracts the spillway penalty from the objective, and reports
  `total_spill_penalty_usd` in the run summary.
- Supported MVP scope: minimum flow is enforced only on reaches leaving a
  reservoir; spill penalties are only accepted on `spillway` reaches.

## Blocked by

BESS-HYDRO-DIAGRAM-007

