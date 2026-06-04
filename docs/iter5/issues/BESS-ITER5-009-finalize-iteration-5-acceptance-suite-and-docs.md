# BESS-ITER5-009: Finalize Iteration 5 Acceptance Suite And Docs

Status: Todo
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

- [ ] Documentation explains `bess_system_dispatch.v2` and `v1` compatibility.
- [ ] Documentation explains simple reservoir hydro scope and exclusions.
- [ ] Documentation explains hydro units and flow-to-volume conversion.
- [ ] Documentation explains linear and piecewise generation modes.
- [ ] Documentation explains reservoir curves, spill penalty, minimum release,
      terminal condition, and terminal water value.
- [ ] Documentation explains structured editor hydro usage and CSV/XLSX inflow
      mapping.
- [ ] Documentation explains hydro result tables, charts, and artifacts.
- [ ] A final Iteration 5 acceptance suite proves the linear hydro flow end to
      end.
- [ ] A final Iteration 5 acceptance suite proves the piecewise hydro flow end
      to end.
- [ ] Acceptance coverage proves paste/upload `v1` JSON still works.
- [ ] Acceptance coverage proves structured editor cases without hydro still
      work as `v2`.
- [ ] Acceptance coverage proves malformed hydro inputs fail clearly.
- [ ] Manual test checklist is updated and aligned with implemented behavior.
- [ ] Full Python tests pass.
- [ ] Full Julia regression tests pass.
- [ ] The Iteration 5 tracker includes final verification instructions.

## Blocked by

BESS-ITER5-001, BESS-ITER5-002, BESS-ITER5-003, BESS-ITER5-004, BESS-ITER5-005, BESS-ITER5-006, BESS-ITER5-007, BESS-ITER5-008
