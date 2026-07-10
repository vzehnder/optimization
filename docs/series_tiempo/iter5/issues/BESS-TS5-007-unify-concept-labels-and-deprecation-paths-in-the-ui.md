# BESS-TS5-007: Unify Concept Labels And Deprecation Paths In The UI

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-27
Fecha de termino planificada: 2026-07-27
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

5, 11

## What to build

Close the "UI no longer mixes concepts" half of the TS-5 definition of done.
Everywhere the product surfaces them, the analyst can tell apart case,
topology, parameters, input variant, date range, executable snapshot and run,
using one consistent vocabulary across scenario, case, catalog, run and
comparison screens.

Legacy-origin objects become visibly labeled: adapter-read hydraulic sets,
extracted draft sets and historical scenario versions show where they came
from and, when applicable, their deprecation status. Deprecated workflows
point the analyst to the common-model path so it is always clear which path
to use for new work. Executable snapshots are presented as technical run
inputs — the frozen combination a run used — not as the analyst's main
editing object.

This slice adds no new features; it is naming, labeling and navigation
clarity, protected by frontend tests so the vocabulary contract does not
drift.

## Acceptance criteria

- [x] Case, topology, parameters, input variant and run are labeled consistently across scenario, case, catalog, run and comparison screens.
- [x] Legacy-origin objects are visibly labeled with their origin and, when applicable, their deprecation status.
- [x] Deprecated workflows point the analyst to the common-model path.
- [x] Executable snapshots are presented as technical run inputs, not as the analyst's main editing object.
- [x] Frontend tests cover the labeling contract.

## Blocked by

BESS-TS5-006
