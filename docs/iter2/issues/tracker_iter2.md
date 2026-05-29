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
| BESS-ITER2-000 | Review One-Bus Mathematical Formulation | HITL | ready-for-agent | Done | None | [BESS-ITER2-000-review-one-bus-mathematical-formulation.md](BESS-ITER2-000-review-one-bus-mathematical-formulation.md) |
| BESS-ITER2-001 | Run Minimal Hybrid System End To End | AFK | ready-for-agent | Done | BESS-ITER2-000 | [BESS-ITER2-001-run-minimal-hybrid-system-end-to-end.md](BESS-ITER2-001-run-minimal-hybrid-system-end-to-end.md) |
| BESS-ITER2-002 | Harden Graph And Time-Series Validation | AFK | ready-for-agent | Done | BESS-ITER2-001 | [BESS-ITER2-002-harden-graph-and-time-series-validation.md](BESS-ITER2-002-harden-graph-and-time-series-validation.md) |
| BESS-ITER2-003 | Add Curtailment And Curtailment Penalty Scenario | AFK | ready-for-agent | Done | BESS-ITER2-001 | [BESS-ITER2-003-add-curtailment-and-curtailment-penalty-scenario.md](BESS-ITER2-003-add-curtailment-and-curtailment-penalty-scenario.md) |
| BESS-ITER2-004 | Add Local Load Scenario | AFK | ready-for-agent | Done | BESS-ITER2-001, BESS-ITER2-002 | [BESS-ITER2-004-add-local-load-scenario.md](BESS-ITER2-004-add-local-load-scenario.md) |
| BESS-ITER2-005 | Add Grid Limits And Import Export Anti-Simultaneity | AFK | ready-for-agent | Todo | BESS-ITER2-001 | [BESS-ITER2-005-add-grid-limits-and-import-export-anti-simultaneity.md](BESS-ITER2-005-add-grid-limits-and-import-export-anti-simultaneity.md) |
| BESS-ITER2-006 | Publish Stable Julia API And CLI Contract | AFK | ready-for-agent | Todo | BESS-ITER2-001 | [BESS-ITER2-006-publish-stable-julia-api-and-cli-contract.md](BESS-ITER2-006-publish-stable-julia-api-and-cli-contract.md) |
| BESS-ITER2-007 | Preserve Single-BESS MVP Regression Contract | AFK | ready-for-agent | Done | None | [BESS-ITER2-007-preserve-single-bess-mvp-regression-contract.md](BESS-ITER2-007-preserve-single-bess-mvp-regression-contract.md) |
| BESS-ITER2-008 | Finalize Sample Docs And Acceptance Suite | AFK | ready-for-agent | Todo | BESS-ITER2-002, BESS-ITER2-003, BESS-ITER2-004, BESS-ITER2-005, BESS-ITER2-006, BESS-ITER2-007 | [BESS-ITER2-008-finalize-sample-docs-and-acceptance-suite.md](BESS-ITER2-008-finalize-sample-docs-and-acceptance-suite.md) |

## Recommended Execution Order

1. BESS-ITER2-000
2. BESS-ITER2-007 can run immediately as a regression guard.
3. BESS-ITER2-001
4. BESS-ITER2-002, BESS-ITER2-003, BESS-ITER2-005, and BESS-ITER2-006 can proceed after the minimal end-to-end path.
5. BESS-ITER2-004 should follow the validation-hardening slice.
6. BESS-ITER2-008 closes the iteration once the feature slices are complete.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-05-28 | All | Created | Initial local issue set generated from the iteration 2 PRD and one-bus mathematical model. |
| 2026-05-28 | All | Reworked | Replaced horizontal layer tickets with vertical tracer-bullet slices that each deliver a verifiable end-to-end behavior. |
| 2026-05-28 | BESS-ITER2-000 | Todo -> Done | Reviewed and accepted the one-bus mathematical formulation. No corrections were required in `docs/iter2/mathematical_model.md`. |
| 2026-05-28 | BESS-ITER2-007 | Todo -> Done | Added an explicit single-BESS MVP public contract regression guard and verified the full Julia suite with 163 tests, including the Plotly report smoke test. |
| 2026-05-29 | BESS-ITER2-001 | Todo -> Done | Added the versioned `system_case` loader, normalizer, one-bus system dispatch model, and wide/long outputs for a minimal renewable plus BESS plus grid case. Verified `julia --project=. -e "import Pkg; Pkg.test()"` with 222 tests. |
| 2026-05-29 | BESS-ITER2-002 | Todo -> Done | Hardened schema, graph, edge, time-series, and battery validation before model construction. Verified `julia --project=. -e "import Pkg; Pkg.test()"` with 222 tests. |
| 2026-05-29 | BESS-ITER2-003 | Todo -> Done | Added curtailment penalty validation and an end-to-end excess-renewable scenario covering wide/long outputs and objective impact. Verified `julia --project=. -e "import Pkg; Pkg.test()"` with 253 tests. |
| 2026-05-29 | BESS-ITER2-004 | Todo -> Done | Added local load input validation, normalization, bus-balance consumption, wide/long output reporting, and metadata. Verified `julia --project=. -e "import Pkg; Pkg.test()"` with 253 tests. |

## Regression Guard

Every iteration 2 slice that changes code must run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

This suite is the single-BESS MVP regression guard. It covers the public Julia names, the original YAML and CSV sample case, single-BESS solve behavior, persisted output files and columns, the Plotly report smoke flow, and MVP acceptance scenarios for constant price, low-high-low price, variable duration, terminal condition, degradation, and anti-simultaneity. Iteration 2 JSON inputs must not become a prerequisite for running iteration 1 cases.

## Dependency Notes

- BESS-ITER2-000 is HITL because the mathematical formulation should be accepted before implementation.
- BESS-ITER2-001 creates the first thin vertical path across schema, loader, normalizer, model, solver, and outputs.
- BESS-ITER2-002 hardens invalid-input behavior after the happy path exists.
- BESS-ITER2-003, BESS-ITER2-004, and BESS-ITER2-005 add specific model capabilities as end-to-end slices.
- BESS-ITER2-006 publishes the integration boundary for a future Python backend after the system runner exists.
- BESS-ITER2-007 is intentionally unblocked because the existing MVP regression suite should stay green throughout all code changes.
