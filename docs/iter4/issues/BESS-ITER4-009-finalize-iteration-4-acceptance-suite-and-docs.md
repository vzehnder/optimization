# BESS-ITER4-009: Finalize Iteration 4 Acceptance Suite And Docs

Status: Todo
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

- [ ] Documentation explains how to use the structured draft editor.
- [ ] Documentation explains supported asset types and one-bus assumptions.
- [ ] Documentation explains CSV and XLSX source-file requirements.
- [ ] Documentation explains column mapping rules and expected units.
- [ ] Documentation explains legacy single price versus separate import/export
      prices.
- [ ] Documentation explains draft validation, generated preview, and promotion
      to immutable scenario version.
- [ ] Final acceptance coverage proves the CSV flow end to end from draft to
      run results.
- [ ] Final acceptance coverage proves the XLSX flow end to end from draft to
      run results.
- [ ] Final acceptance coverage proves paste/upload JSON still works.
- [ ] Final acceptance coverage proves legacy single-price cases still work.
- [ ] Final acceptance coverage proves separate-price economics appear in
      outputs, result tables, and charts.
- [ ] Full Python tests pass.
- [ ] Full Julia regression tests pass.
- [ ] The Iteration 4 tracker includes final verification instructions.

## Blocked by

BESS-ITER4-001, BESS-ITER4-002, BESS-ITER4-003, BESS-ITER4-004, BESS-ITER4-005, BESS-ITER4-006, BESS-ITER4-007, BESS-ITER4-008
