# BESS-ITER5-009: Finalize Iteration 5 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

55, 62, 65 through 68

## What to build

Finalize Iteration 5 with acceptance coverage and documentation proving the
complete simple reservoir hydropower workflow, contract `v2`, linear and
piecewise generation, CSV/XLSX inflow ingestion, generated preview, promotion,
manual execution, hydro result review, and regression compatibility with
legacy `v1` cases.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [x] Documentation explains `bess_system_dispatch.v2` and `v1` compatibility.
- [x] Documentation explains simple reservoir hydro scope and exclusions.
- [x] Documentation explains hydro units and flow-to-volume conversion.
- [x] Documentation explains linear and piecewise generation modes.
- [x] Documentation explains reservoir curves, spill penalty, minimum release,
      terminal condition, and terminal water value.
- [x] Documentation explains structured editor hydro usage and CSV/XLSX inflow
      mapping.
- [x] Documentation explains hydro result tables, charts, and artifacts.
- [x] A final Iteration 5 acceptance suite proves the linear hydro flow end to
      end.
- [x] A final Iteration 5 acceptance suite proves the piecewise hydro flow end
      to end.
- [x] Acceptance coverage proves paste/upload `v1` JSON still works.
- [x] Acceptance coverage proves structured editor cases without hydro still
      work as `v2`.
- [x] Acceptance coverage proves malformed hydro inputs fail clearly.
- [x] Manual test checklist is updated and aligned with implemented behavior.
- [x] Full Python tests pass.
- [x] Full Julia regression tests pass.
- [x] The Iteration 5 tracker includes final verification instructions.

## Implementation notes

Completed on 2026-06-05.

- Extended `tests.test_iter5_acceptance` with the final Iteration 5 closing
  proof. The suite now covers a linear hydro structured draft through mapped
  inflow, generated `v2` preview, Julia-backed validation, promotion, manual
  run, registered resolved-case artifact, hydro result tables, and hydro
  charts.
- Kept the existing piecewise hydro acceptance path for CSV and XLSX mapping,
  nonmonotone breakpoints, promotion, run results, and invalid breakpoint
  rejection.
- Added final regression coverage for paste/upload legacy
  `bess_system_dispatch.v1` JSON, structured editor cases without hydro
  generated as `bess_system_dispatch.v2`, and negative hydro inflow failures
  reported before promotion.
- Expanded `README.md` with `v2`/`v1` compatibility, simple reservoir hydro
  scope, units and flow conversion, linear and piecewise generation modes,
  reservoir curves, spill/minimum-release/terminal economics, structured
  editor inflow mapping, and hydro result artifacts.
- Updated the manual Iteration 5 checklist with a closing automation note.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter5_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Final Iteration 5 acceptance suite: 4 passed.
- Full Python web/API/template/results suite: passed.
- Full Julia optimizer regression suite: passed.

## Blocked by

BESS-ITER5-001, BESS-ITER5-002, BESS-ITER5-003, BESS-ITER5-004, BESS-ITER5-005, BESS-ITER5-006, BESS-ITER5-007, BESS-ITER5-008
