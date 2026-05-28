# BESS Iteration 2 Issue Tracker

This document is the local tracker for the hybrid system dispatch iteration derived from `docs/iter2/prd_bess_system_dispatch.md`.

External issue tracker integration has not been configured, so each issue is stored as a Markdown file in this folder. All issues carry the `ready-for-agent` triage label.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-ITER2-000 | Review One-Bus Mathematical Formulation | HITL | ready-for-agent | Todo | None | [BESS-ITER2-000-review-one-bus-mathematical-formulation.md](BESS-ITER2-000-review-one-bus-mathematical-formulation.md) |
| BESS-ITER2-001 | Define Versioned System Case JSON Schema | AFK | ready-for-agent | Todo | BESS-ITER2-000 | [BESS-ITER2-001-define-versioned-system-case-json-schema.md](BESS-ITER2-001-define-versioned-system-case-json-schema.md) |
| BESS-ITER2-002 | Load And Validate System Graph Cases | AFK | ready-for-agent | Todo | BESS-ITER2-001 | [BESS-ITER2-002-load-and-validate-system-graph-cases.md](BESS-ITER2-002-load-and-validate-system-graph-cases.md) |
| BESS-ITER2-003 | Normalize Graph Data Into Optimization Case Data | AFK | ready-for-agent | Todo | BESS-ITER2-002 | [BESS-ITER2-003-normalize-graph-data-into-optimization-case-data.md](BESS-ITER2-003-normalize-graph-data-into-optimization-case-data.md) |
| BESS-ITER2-004 | Build One-Bus Hybrid System JuMP Model | AFK | ready-for-agent | Todo | BESS-ITER2-003 | [BESS-ITER2-004-build-one-bus-hybrid-system-jump-model.md](BESS-ITER2-004-build-one-bus-hybrid-system-jump-model.md) |
| BESS-ITER2-005 | Persist System Dispatch Outputs | AFK | ready-for-agent | Todo | BESS-ITER2-004 | [BESS-ITER2-005-persist-system-dispatch-outputs.md](BESS-ITER2-005-persist-system-dispatch-outputs.md) |
| BESS-ITER2-006 | Add Stable System Case CLI | AFK | ready-for-agent | Todo | BESS-ITER2-005 | [BESS-ITER2-006-add-stable-system-case-cli.md](BESS-ITER2-006-add-stable-system-case-cli.md) |
| BESS-ITER2-007 | Add Hybrid System Sample Case And Run Docs | AFK | ready-for-agent | Todo | BESS-ITER2-006 | [BESS-ITER2-007-add-hybrid-system-sample-case-and-run-docs.md](BESS-ITER2-007-add-hybrid-system-sample-case-and-run-docs.md) |
| BESS-ITER2-008 | Prove Iteration 2 With Acceptance Suite | AFK | ready-for-agent | Todo | BESS-ITER2-007 | [BESS-ITER2-008-prove-iteration-2-with-acceptance-suite.md](BESS-ITER2-008-prove-iteration-2-with-acceptance-suite.md) |
| BESS-ITER2-009 | Preserve Single-BESS MVP Regression Contract | AFK | ready-for-agent | Todo | BESS-ITER2-004 | [BESS-ITER2-009-preserve-single-bess-mvp-regression-contract.md](BESS-ITER2-009-preserve-single-bess-mvp-regression-contract.md) |

## Recommended Execution Order

1. BESS-ITER2-000
2. BESS-ITER2-001
3. BESS-ITER2-002
4. BESS-ITER2-003
5. BESS-ITER2-004
6. BESS-ITER2-005
7. BESS-ITER2-006
8. BESS-ITER2-007
9. BESS-ITER2-008 and BESS-ITER2-009

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-05-28 | All | Created | Initial local issue set generated from the iteration 2 PRD and one-bus mathematical model. |

## Dependency Notes

- BESS-ITER2-000 is HITL because the mathematical formulation should be accepted before implementation.
- BESS-ITER2-001 should follow model review so the schema reflects the approved formulation.
- BESS-ITER2-003 is the deep-module slice that isolates UI-facing graph data from solver-facing optimization data.
- BESS-ITER2-004 should depend on normalized data, not raw JSON.
- BESS-ITER2-009 can be run after model refactors begin and should remain green through the rest of the iteration.
