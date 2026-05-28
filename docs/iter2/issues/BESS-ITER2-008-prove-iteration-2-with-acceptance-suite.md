# BESS-ITER2-008: Prove Iteration 2 With Acceptance Suite

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Add the final acceptance suite for iteration 2.

The suite should prove the full path from JSON input through validation, normalization, JuMP model construction, solve, output writing, and CLI execution.

## Acceptance criteria

- [ ] The valid hybrid system JSON loads and validates.
- [ ] Invalid graph and time-series cases fail before model construction.
- [ ] The graph normalizer preserves asset IDs and aligns time-series data.
- [ ] The renewable plus BESS plus grid scenario solves to optimality.
- [ ] Renewable curtailment is reported when availability exceeds feasible use.
- [ ] Local load is served by the common bus balance in a load scenario.
- [ ] Grid import/export anti-simultaneity is enforced when enabled.
- [ ] Battery charge/discharge anti-simultaneity is enforced when enabled.
- [ ] Battery terminal energy behavior remains correct.
- [ ] Wide and long dispatch outputs are generated.
- [ ] CLI stdout is parseable JSON and points to generated outputs.
- [ ] README or run documentation contains the accepted execution flow.

## Verification

Run the complete Julia test suite and the documented sample CLI command.

## Blocked by

BESS-ITER2-007
