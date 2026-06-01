# BESS-ITER4-005: Generate And Validate A System Case From Draft Plus CSV

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

30 through 49, 56 through 60

## What to build

Connect structured draft data and CSV mapping into a generated
`system_case_json` candidate.

The app should produce a read-only preview of the generated JSON, run Python
editor/ingestion validation first, delegate final contract validation to Julia,
and surface clear errors by phase.

## Acceptance criteria

- [x] A draft with assets, solver settings, a CSV source, and saved mapping can
      generate a complete `system_case_json`.
- [x] Generated periods include timestamps, durations, and either legacy price
      or separate import/export prices.
- [x] Generated periods include renewable availability keyed by renewable asset
      ID.
- [x] Generated periods include load demand keyed by load asset ID.
- [x] Generated nodes include PCC, grid, battery, renewable, and load assets
      from the structured draft.
- [x] Generated edges connect all assets to the PCC automatically.
- [x] The generated JSON preview is read-only in the structured editor.
- [x] Python validation errors are shown without invoking Julia.
- [x] Julia validation success and failure are surfaced through API and SSR UI.
- [x] The existing paste/upload JSON validation path remains intact.
- [x] Tests cover successful generation, read-only preview, Python validation
      failure, Julia validation failure, and legacy validation compatibility.

## Implementation notes

- Extended draft system-case generation so the active validated CSV source
  becomes the candidate `time_series` when explicit draft periods are absent.
- Preserved the previous generated graph behavior for PCC, grid, battery,
  renewable, load, solver settings, and automatic PCC edges.
- Added generated-case validation endpoints:
  `/api/scenarios/{scenario_id}/draft/generated-system-case/validate` and
  `/scenarios/{scenario_id}/draft/generated-system-case/validate`.
- Stored the generated `system_case` and Julia validation snapshot under the
  mutable draft document as `generated_system_case` for downstream promotion.
- Kept Python ingestion errors in the generation phase, so invalid mappings fail
  before the Julia validation service is invoked.
- Kept the Iteration 3 paste/upload JSON scenario-version path unchanged and
  covered by a regression test.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web/API/template tests: 57 passed.
- Julia package tests: 372 passed.
- Chrome DevTools MCP loaded a draft page with a mapped CSV source, confirmed a
  read-only generated preview containing separate import/export prices,
  renewable availability, load demand, and PCC edges, submitted generated-case
  validation, saw `Valid: Validation succeeded`, found no console messages, and
  saved screenshots under `.tmp`.

Browser note: attempted the requested in-app Browser workflow, but the
`node_repl` runtime failed locally with `windows sandbox failed: spawn setup
refresh`. Chrome DevTools MCP validation was completed successfully.

## Blocked by

BESS-ITER4-001, BESS-ITER4-003, BESS-ITER4-004
