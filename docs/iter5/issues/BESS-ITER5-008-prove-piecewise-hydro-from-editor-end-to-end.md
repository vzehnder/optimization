# BESS-ITER5-008: Prove Piecewise Hydro From Editor End To End

Status: Done
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

- [x] A structured piecewise hydro draft can be saved from the UI/API.
- [x] Nonconvex and nonmonotone generation breakpoints are preserved in the
      generated `v2` preview.
- [x] Invalid breakpoint data is surfaced clearly before promotion.
- [x] CSV-backed piecewise hydro generation validates and promotes.
- [x] XLSX-backed piecewise hydro generation validates and promotes.
- [x] A promoted piecewise hydro version launches a manual run successfully.
- [x] Run artifacts contain piecewise hydro outputs and metadata.
- [x] Result tables show piecewise hydro dispatch values.
- [x] Result charts show piecewise hydro behavior.
- [x] Tests prove the piecewise editor path without relying only on the
      lower-level Julia sample case.

## Implementation notes

- Added `tests.test_iter5_acceptance` coverage for the full piecewise hydro
  structured editor path from UI/API draft save through CSV/XLSX source mapping,
  generated `bess_system_dispatch.v2` preview, Julia-backed validation,
  promotion, manual run, artifact registration, result tables, and hydro charts.
- The acceptance test preserves a nonmonotone piecewise generation curve in the
  generated preview and proves duplicate flow breakpoints surface as Julia
  validation errors before promotion.
- The test uses a run-process fixture that registers `system_case_resolved.json`
  and model metadata with `piecewise_linear` generation mode, so the web result
  reader and run page prove the same artifact contract used by promoted hydro
  runs.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter5_acceptance -v
```

## Blocked by

BESS-ITER5-002, BESS-ITER5-005, BESS-ITER5-007
