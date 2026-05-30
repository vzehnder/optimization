# BESS-ITER4-005: Generate And Validate A System Case From Draft Plus CSV

Status: Todo
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

- [ ] A draft with assets, solver settings, a CSV source, and saved mapping can
      generate a complete `system_case_json`.
- [ ] Generated periods include timestamps, durations, and either legacy price
      or separate import/export prices.
- [ ] Generated periods include renewable availability keyed by renewable asset
      ID.
- [ ] Generated periods include load demand keyed by load asset ID.
- [ ] Generated nodes include PCC, grid, battery, renewable, and load assets
      from the structured draft.
- [ ] Generated edges connect all assets to the PCC automatically.
- [ ] The generated JSON preview is read-only in the structured editor.
- [ ] Python validation errors are shown without invoking Julia.
- [ ] Julia validation success and failure are surfaced through API and SSR UI.
- [ ] The existing paste/upload JSON validation path remains intact.
- [ ] Tests cover successful generation, read-only preview, Python validation
      failure, Julia validation failure, and legacy validation compatibility.

## Blocked by

BESS-ITER4-001, BESS-ITER4-003, BESS-ITER4-004
