# BESS MVP Issue Tracker

This document is the local tracker for the BESS dispatch MVP issues derived from `docs/prd_bess_dispatch.md`.

External issue tracker integration has not been configured, so each issue is stored as a Markdown file in this folder. Update this register as work progresses.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- |
| BESS-MVP-000 | Review Mathematical Formulation Before Implementation | HITL | Done | None | [BESS-MVP-000-review-mathematical-formulation.md](BESS-MVP-000-review-mathematical-formulation.md) |
| BESS-MVP-001 | Bootstrap Julia Package With Smoke Test | AFK | Done | None | [BESS-MVP-001-bootstrap-julia-package.md](BESS-MVP-001-bootstrap-julia-package.md) |
| BESS-MVP-002 | Load And Validate Arbitrage Case Data | AFK | Done | BESS-MVP-001 | [BESS-MVP-002-load-and-validate-case-data.md](BESS-MVP-002-load-and-validate-case-data.md) |
| BESS-MVP-003 | Solve Core Full-Horizon Arbitrage Model | AFK | Done | BESS-MVP-000, BESS-MVP-002 | [BESS-MVP-003-solve-core-arbitrage-model.md](BESS-MVP-003-solve-core-arbitrage-model.md) |
| BESS-MVP-004 | Add Configurable Terminal Condition Modes | AFK | Done | BESS-MVP-003 | [BESS-MVP-004-add-terminal-condition-modes.md](BESS-MVP-004-add-terminal-condition-modes.md) |
| BESS-MVP-005 | Add Binary Anti-Simultaneity Dispatch Mode | AFK | Done | BESS-MVP-003 | [BESS-MVP-005-add-anti-simultaneity-binary-mode.md](BESS-MVP-005-add-anti-simultaneity-binary-mode.md) |
| BESS-MVP-006 | Add Linear Delta-SOC Degradation Cost | AFK | Done | BESS-MVP-003 | [BESS-MVP-006-add-delta-soc-degradation.md](BESS-MVP-006-add-delta-soc-degradation.md) |
| BESS-MVP-007 | Persist Dispatch Results And Run Metadata | AFK | Done | BESS-MVP-004, BESS-MVP-005, BESS-MVP-006 | [BESS-MVP-007-persist-run-outputs.md](BESS-MVP-007-persist-run-outputs.md) |
| BESS-MVP-008 | Generate Plotly Dispatch Report From Run Output | AFK | Todo | BESS-MVP-007 | [BESS-MVP-008-generate-plotly-dispatch-report.md](BESS-MVP-008-generate-plotly-dispatch-report.md) |
| BESS-MVP-009 | Prove MVP With Acceptance Scenario Suite | AFK | Todo | BESS-MVP-007, BESS-MVP-008 | [BESS-MVP-009-prove-mvp-with-acceptance-suite.md](BESS-MVP-009-prove-mvp-with-acceptance-suite.md) |

## Recommended Execution Order

1. BESS-MVP-000
2. BESS-MVP-001
3. BESS-MVP-002
4. BESS-MVP-003
5. BESS-MVP-004, BESS-MVP-005, and BESS-MVP-006 in parallel if desired
6. BESS-MVP-007
7. BESS-MVP-008
8. BESS-MVP-009

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-05-24 | All | Created | Initial local issue set generated from the PRD. |
| 2026-05-24 | BESS-MVP-000 | Todo -> Done | Reviewed PRD and mathematical model together. Approved MVP modeling contract after clarifying terminal minimum configuration, mandatory core constraints, grid-side power convention, and disabled degradation reporting. |
| 2026-05-24 | BESS-MVP-001 | Todo -> In Progress | Started Julia package bootstrap with a TDD smoke-test slice for importing the package. |
| 2026-05-24 | BESS-MVP-001 | In Progress -> Done | Added `Project.toml`, `src/BESSDispatch.jl`, and `test/runtests.jl`. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"`. |
| 2026-05-24 | BESS-MVP-002 | Todo -> In Progress | Started YAML/CSV case loading and validation using TDD. |
| 2026-05-24 | BESS-MVP-002 | In Progress -> Done | Added PRD structs, `load_case`, YAML/CSV sample case, validation for time series, BESS parameters, efficiencies, and terminal config. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"`. |
| 2026-05-25 | BESS-MVP-003 | Todo -> In Progress | Started core full-horizon JuMP arbitrage model using TDD. |
| 2026-05-25 | BESS-MVP-003 | In Progress -> Done | Added `build_dispatch_model` and `solve_dispatch` for the continuous core arbitrage model, with tests for sample model construction, low-high-low dispatch, and variable duration energy balance. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"`. |
| 2026-05-25 | BESS-MVP-004 | Todo -> In Progress | Started configurable terminal condition modes using TDD. |
| 2026-05-25 | BESS-MVP-004 | In Progress -> Done | Added solved-result coverage for `none`, `equal_initial`, and `min_terminal`, and implemented terminal energy constraints in the JuMP model. Existing validation tests cover invalid terminal configuration. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"`. |
| 2026-05-25 | BESS-MVP-005 | Todo -> In Progress | Started binary anti-simultaneity dispatch mode using TDD. |
| 2026-05-25 | BESS-MVP-005 | In Progress -> Done | Added optional `is_charging` binary variables, anti-simultaneity constraints, solved-result mode reporting, and enabled/disabled tests. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"` (72 tests). |
| 2026-05-25 | BESS-MVP-006 | Todo -> In Progress | Started linear delta-SOC degradation formulation using TDD. |
| 2026-05-25 | BESS-MVP-006 | In Progress -> Done | Added optional `delta_soc_abs_mwh` variables, degradation objective penalty, solved-result degradation reporting, and enabled/disabled/no-cycling tests. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"` (89 tests). |
| 2026-05-25 | BESS-MVP-007 | Todo -> In Progress | Started persisted run output writer for dispatch CSV, summary metadata, resolved config, and model metadata. |
| 2026-05-25 | BESS-MVP-007 | In Progress -> Done | Added `run_case` and `write_run_outputs`, persisted dispatch CSV, summary JSON, resolved config YAML, and model metadata JSON with unique run folders. Verification passed with `julia --project=. -e "import Pkg; Pkg.test()"` (117 tests). |

## How To Update This Tracker

When starting an issue:

1. Change its status in this register to `In Progress`.
2. Change the `Status:` line inside the issue file to `In Progress`.
3. Add a row to the progress log with the date and note.

When an issue is ready for review:

1. Change its status in this register to `In Review`.
2. Change the `Status:` line inside the issue file to `In Review`.
3. Link or summarize the verification commands that were run.

When an issue is accepted:

1. Check off completed acceptance criteria inside the issue file.
2. Change status in this register and the issue file to `Done`.
3. Add final verification notes to the progress log.

## Dependency Notes

- BESS-MVP-000 is HITL because implementation should not proceed until the mathematical model is accepted or corrected.
- BESS-MVP-001 can proceed independently because package bootstrapping does not depend on mathematical model approval.
- BESS-MVP-004, BESS-MVP-005, and BESS-MVP-006 are independent once the core model exists.
- BESS-MVP-007 should wait for the full dispatch result shape because it owns the persisted output contract.
- BESS-MVP-009 is the final proof that the MVP satisfies the PRD acceptance criteria.
