# BESS-ITER3-008: Add Basic Result Charts

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

37, 38, 39, 40

## What to build

Add a minimal internal chart view for completed runs using the existing parsed
results. The charts should help an analyst inspect grid interaction, renewable
curtailment, battery behavior, and period economics without creating a
configurable dashboard system.

The charts must be derived from `dispatch.csv` and `asset_dispatch.csv`.

## Acceptance criteria

- [ ] The run results view includes a grid import/export chart.
- [ ] The run results view includes a renewable used/curtailed chart.
- [ ] The run results view includes a BESS charge/discharge/SOC chart when
      battery columns are available.
- [ ] The run results view includes a period profit chart.
- [ ] Charts use the same artifact-derived data exposed by the results reader.
- [ ] The UI handles missing optional chart columns gracefully.
- [ ] No configurable dashboard or saved dashboard template behavior is added.
- [ ] Tests or template smoke checks verify that chart data is present for a
      completed sample run.

## Blocked by

BESS-ITER3-007
