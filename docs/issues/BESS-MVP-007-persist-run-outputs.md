# BESS-MVP-007: Persist Dispatch Results And Run Metadata

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Add a run path that solves a configured case and writes reproducible outputs to a run-specific folder. The output should include per-period dispatch, resolved configuration, summary metadata, and model metadata.

This slice should make the model result usable outside Julia and prepare the output contract for Plotly reporting.

## Acceptance criteria

- [ ] Running the sample case creates a unique output folder for the case and run timestamp.
- [ ] `dispatch.csv` contains the required period columns from the PRD.
- [ ] `summary.json` contains solver status, termination status, objective value, case name, run timestamp, and source identifiers.
- [ ] `config_resolved.yaml` captures the effective configuration used for the run.
- [ ] `model_metadata.json` records active constraint flags, terminal mode, number of periods, and unit conventions.
- [ ] Tests or an automated smoke check verify that the expected files are written.

## Blocked by

- BESS-MVP-004
- BESS-MVP-005
- BESS-MVP-006
