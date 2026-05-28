# BESS-ITER2-005: Persist System Dispatch Outputs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Add run output writing for system dispatch cases.

The system writer should produce machine-readable outputs suitable for analysts today and a Python backend later.

## Acceptance criteria

- [ ] A system run creates a run-specific output folder.
- [ ] `summary.json` includes case name, run timestamp, solver, termination status, objective value, and source identifiers.
- [ ] `model_metadata.json` identifies the one-bus system model, active constraint flags, asset counts, period count, and unit conventions.
- [ ] A resolved system input JSON is persisted.
- [ ] A wide `dispatch.csv` is written with key system totals and economics per period.
- [ ] A long `asset_dispatch.csv` is written with timestamp, asset ID, asset type, variable, value, and unit.
- [ ] Output files preserve asset IDs from the input graph.
- [ ] Repeated runs with the same timestamp produce unique output folders.

## Verification

Run writer tests against a solved system case and assert files, columns, summary fields, metadata fields, and unique output behavior.

## Blocked by

BESS-ITER2-004
