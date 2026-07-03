# BESS-TS1-002: Add Topology And Parameter Snapshot Metadata For Structured Drafts

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-09

## User stories covered

1 through 12, 15 through 18

## What to build

Extend the structured draft promotion path so it can split the generated model
into topology-like and parameter-like snapshot metadata while still producing
the same executable `system_case_json` as today.

The analyst should be able to promote a structured draft and later inspect that
the resulting version came from a specific topology snapshot and parameter
snapshot, without needing to understand the raw JSON.

## Acceptance criteria

- [ ] Structured draft generation identifies topology-relevant content.
- [ ] Structured draft generation identifies parameter-relevant content.
- [ ] Promotion from structured draft stores topology and parameter snapshot metadata.
- [ ] The generated `system_case_json` remains equivalent to the current structured draft output.
- [ ] Existing CSV/XLSX source-mapping promotion still works.
- [ ] Existing paste/upload JSON flow remains unchanged.
- [ ] Backend tests cover structured draft promotion with hierarchy metadata.
- [ ] Regression tests prove existing Iteration 4/5 structured draft flows still pass.

## Blocked by

BESS-TS1-001
