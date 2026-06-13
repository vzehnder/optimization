# BESS-ITER4-009: Finalize Iteration 4 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

All acceptance and regression stories

## What to build

Finalize Iteration 4 with acceptance coverage and documentation proving the
complete structured editor flow, CSV/XLSX ingestion, separate import/export
price behavior, draft promotion, manual execution, result review, and regression
compatibility with the Iteration 3 paste/upload JSON flow.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [x] Documentation explains how to use the structured draft editor.
- [x] Documentation explains supported asset types and one-bus assumptions.
- [x] Documentation explains CSV and XLSX source-file requirements.
- [x] Documentation explains column mapping rules and expected units.
- [x] Documentation explains legacy single price versus separate import/export
      prices.
- [x] Documentation explains draft validation, generated preview, and promotion
      to immutable scenario version.
- [x] Final acceptance coverage proves the CSV flow end to end from draft to
      run results.
- [x] Final acceptance coverage proves the XLSX flow end to end from draft to
      run results.
- [x] Final acceptance coverage proves paste/upload JSON still works.
- [x] Final acceptance coverage proves legacy single-price cases still work.
- [x] Final acceptance coverage proves separate-price economics appear in
      outputs, result tables, and charts.
- [x] Full Python tests pass.
- [x] Full Julia regression tests pass.
- [x] The Iteration 4 tracker includes final verification instructions.

## Implementation notes

- Added `tests/test_iter4_acceptance.py` as the final Iteration 4 acceptance
  suite. It exercises CSV and XLSX structured draft flows through draft
  creation, source upload, mapping, generated-case preview, Julia-backed
  validation, promotion to immutable scenario version, manual run launch,
  artifact registration, result tables, separate-price charts, and artifact
  downloads.
- The final acceptance suite also proves the Iteration 3 paste JSON path, JSON
  upload path, and legacy single-price result chart fallback still work.
- Extended `README.md` with structured draft editor usage, supported one-bus
  assets, CSV/XLSX source requirements, mapping units, legacy versus separate
  price behavior, validation/promotion workflow, error phases, provenance
  metadata, and final Iteration 4 verification commands.
- Updated the Iteration 4 tracker so the closing issue is marked done and the
  final verification checklist stays visible for future regression work.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Chrome DevTools MCP loaded the local structured draft page, confirmed the
rendered editor fields and read-only generated preview, saw HTTP 200 for the
document request, found no console messages, and saved a screenshot under
`.tmp`. The in-app Browser workflow was attempted twice but the local
`node_repl` browser-control runtime failed with `windows sandbox failed: spawn
setup refresh`.

## Blocked by

BESS-ITER4-001, BESS-ITER4-002, BESS-ITER4-003, BESS-ITER4-004, BESS-ITER4-005, BESS-ITER4-006, BESS-ITER4-007, BESS-ITER4-008
