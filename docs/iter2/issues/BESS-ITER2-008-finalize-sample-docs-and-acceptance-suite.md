# BESS-ITER2-008: Finalize Sample Docs And Acceptance Suite

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

1 through 30

## What to build

Finalize iteration 2 with a complete sample case, run documentation, and acceptance suite proving the full system-dispatch flow from JSON input through validation, normalization, solve, output writing, and CLI execution.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [ ] A sample `system_case.json` exists for renewable plus BESS plus grid.
- [ ] A sample or test scenario covers local load.
- [ ] A sample or test scenario covers renewable curtailment.
- [ ] A sample or test scenario covers grid limits and import/export anti-simultaneity.
- [ ] The valid hybrid system JSON loads and validates.
- [ ] Invalid graph and time-series cases fail before model construction.
- [ ] The graph normalizer preserves asset IDs and aligns time-series data.
- [ ] The renewable plus BESS plus grid scenario solves to optimality.
- [ ] Wide and long dispatch outputs are generated.
- [ ] CLI stdout is parseable JSON and points to generated outputs.
- [ ] Run documentation shows the Julia API flow.
- [ ] Run documentation shows the CLI flow.
- [ ] Run documentation explains the output files.
- [ ] Existing single-BESS regression tests remain green.

## Verification

Run the complete Julia test suite, the documented system CLI command, and the existing single-BESS sample/report flow.

## Blocked by

BESS-ITER2-002, BESS-ITER2-003, BESS-ITER2-004, BESS-ITER2-005, BESS-ITER2-006, BESS-ITER2-007
