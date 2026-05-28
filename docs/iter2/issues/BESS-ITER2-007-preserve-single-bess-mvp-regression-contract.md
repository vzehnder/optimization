# BESS-ITER2-007: Preserve Single-BESS MVP Regression Contract

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

18, 26, 27

## What to build

Keep the iteration 1 single-BESS MVP behavior stable while adding system dispatch.

This slice should establish the regression guard used throughout iteration 2. Any refactor needed to reuse battery logic in the system model must preserve the existing public API, input files, outputs, Plotly flow, and acceptance behavior for the original single-BESS case.

## Acceptance criteria

- [ ] Existing single-BESS public functions remain available.
- [ ] Existing YAML and CSV sample case still loads.
- [ ] Existing single-BESS dispatch model still solves.
- [ ] Existing output files and columns remain stable.
- [ ] Existing Plotly report flow remains stable.
- [ ] Existing acceptance scenarios for constant price, low-high-low price, variable duration, terminal condition, degradation, and anti-simultaneity still pass.
- [ ] No iteration 2 JSON requirement is imposed on iteration 1 cases.
- [ ] The tracker documents that this regression suite must be run with every code-changing iteration 2 slice.

## Verification

Run the full existing Julia test suite and the Plotly report smoke test.

## Blocked by

None - can start immediately.
