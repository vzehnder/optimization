# BESS-ITER3-007: Review Run Summary And Result Tables

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

34, 35, 36

## What to build

Add basic browser review of completed run results. The UI/API should read the
existing Julia output artifacts and present the run summary, system dispatch
table, and asset dispatch table without modifying the source files.

This is the first results-review slice and should remain table-focused.

## Acceptance criteria

- [ ] A completed run detail page shows key fields from `summary.json`.
- [ ] The API exposes parsed summary data for a completed run.
- [ ] The UI can show `dispatch.csv` as a period-level table.
- [ ] The UI can show `asset_dispatch.csv` as an asset-level table.
- [ ] Table rendering handles the current Iteration 2 output columns.
- [ ] Missing or malformed result artifacts surface clear errors.
- [ ] The results reader does not mutate artifact files.
- [ ] Tests cover summary parsing, dispatch table parsing, asset table parsing,
      API responses, and template smoke rendering.

## Blocked by

BESS-ITER3-006
