# BESS-ITER2-003: Add Curtailment And Curtailment Penalty Scenario

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

11, 12, 13, 21, 23, 24, 25

## What to build

Add an end-to-end renewable curtailment scenario where available renewable generation exceeds feasible storage, load, or export. The optimizer must report used and curtailed renewable energy, and it must include optional curtailment penalties in the objective when configured.

## Acceptance criteria

- [ ] Renewable assets accept `curtailment_penalty_usd_per_mwh`, defaulting to zero when omitted.
- [ ] Negative curtailment penalties are rejected.
- [ ] The model enforces available renewable power equals used plus curtailed power in every period.
- [ ] A case with excess renewable availability curtails the infeasible excess.
- [ ] Curtailment appears in wide system dispatch output.
- [ ] Curtailment appears in long asset dispatch output with the renewable asset ID.
- [ ] Objective value reflects configured curtailment penalties.
- [ ] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Verification

Run a curtailment scenario test, an objective-sign test with positive curtailment penalty, the minimal system test, and existing MVP tests.

## Blocked by

BESS-ITER2-001
