# BESS-ITER5-008: Prove Piecewise Hydro From Editor End To End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

26 through 33, 43 through 54, 67

## What to build

Prove the full structured editor workflow for a piecewise hydro case.

The analyst should be able to define nonconvex or nonmonotone generation
breakpoints in the draft editor, upload and map hydro inflows, preview a
generated `v2` case, validate through Julia, promote to an immutable version,
run manually, register artifacts, and review hydro result tables and charts.

## Acceptance criteria

- [ ] A structured piecewise hydro draft can be saved from the UI/API.
- [ ] Nonconvex and nonmonotone generation breakpoints are preserved in the
      generated `v2` preview.
- [ ] Invalid breakpoint data is surfaced clearly before promotion.
- [ ] CSV-backed piecewise hydro generation validates and promotes.
- [ ] XLSX-backed piecewise hydro generation validates and promotes.
- [ ] A promoted piecewise hydro version launches a manual run successfully.
- [ ] Run artifacts contain piecewise hydro outputs and metadata.
- [ ] Result tables show piecewise hydro dispatch values.
- [ ] Result charts show piecewise hydro behavior.
- [ ] Tests prove the piecewise editor path without relying only on the
      lower-level Julia sample case.

## Blocked by

BESS-ITER5-002, BESS-ITER5-005, BESS-ITER5-007
