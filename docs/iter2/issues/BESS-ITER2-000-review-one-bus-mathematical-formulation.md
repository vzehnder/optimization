# BESS-ITER2-000: Review One-Bus Mathematical Formulation

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Review and approve the one-bus hybrid system mathematical formulation before implementation starts.

The review should confirm that the formulation supports renewable generation, BESS, grid import/export, optional load, curtailment, battery terminal conditions, battery degradation, and anti-simultaneity constraints while remaining a single logical bus model.

## Acceptance criteria

- [ ] The one-bus balance convention is accepted or corrected.
- [ ] Renewable used and curtailed variables are accepted or corrected.
- [ ] Grid import/export variables and anti-simultaneity behavior are accepted or corrected.
- [ ] Battery physics reuse from iteration 1 is accepted or corrected.
- [ ] Objective terms and sign conventions are accepted or corrected.
- [ ] Validation requirements are accepted or corrected.
- [ ] Out-of-scope network behavior remains excluded.

## Verification

Document the accepted decisions in this issue and update the mathematical model if corrections are needed.

## Blocked by

None - can start immediately.
