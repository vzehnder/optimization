# BESS-ITER2-009: Preserve Single-BESS MVP Regression Contract

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Keep the iteration 1 single-BESS MVP behavior stable while adding system dispatch.

Any refactor needed to reuse battery logic in the system model must preserve the existing public API, input files, outputs, and tests for the original single-BESS case.

## Acceptance criteria

- [ ] Existing single-BESS public functions remain available.
- [ ] Existing YAML and CSV sample case still loads.
- [ ] Existing single-BESS dispatch model still solves.
- [ ] Existing output files and columns remain stable.
- [ ] Existing Plotly report flow remains stable.
- [ ] Existing acceptance scenarios for constant price, low-high-low price, variable duration, terminal condition, degradation, and anti-simultaneity still pass.
- [ ] No iteration 2 JSON requirement is imposed on iteration 1 cases.

## Verification

Run the full existing Julia test suite after each system-model refactor.

## Blocked by

BESS-ITER2-004
