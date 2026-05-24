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
| BESS-MVP-000 | Review Mathematical Formulation Before Implementation | HITL | Todo | None | [BESS-MVP-000-review-mathematical-formulation.md](BESS-MVP-000-review-mathematical-formulation.md) |
| BESS-MVP-001 | Bootstrap Julia Package With Smoke Test | AFK | Todo | None | [BESS-MVP-001-bootstrap-julia-package.md](BESS-MVP-001-bootstrap-julia-package.md) |
| BESS-MVP-002 | Load And Validate Arbitrage Case Data | AFK | Todo | BESS-MVP-001 | [BESS-MVP-002-load-and-validate-case-data.md](BESS-MVP-002-load-and-validate-case-data.md) |
| BESS-MVP-003 | Solve Core Full-Horizon Arbitrage Model | AFK | Todo | BESS-MVP-000, BESS-MVP-002 | [BESS-MVP-003-solve-core-arbitrage-model.md](BESS-MVP-003-solve-core-arbitrage-model.md) |
| BESS-MVP-004 | Add Configurable Terminal Condition Modes | AFK | Todo | BESS-MVP-003 | [BESS-MVP-004-add-terminal-condition-modes.md](BESS-MVP-004-add-terminal-condition-modes.md) |
| BESS-MVP-005 | Add Binary Anti-Simultaneity Dispatch Mode | AFK | Todo | BESS-MVP-003 | [BESS-MVP-005-add-anti-simultaneity-binary-mode.md](BESS-MVP-005-add-anti-simultaneity-binary-mode.md) |
| BESS-MVP-006 | Add Linear Delta-SOC Degradation Cost | AFK | Todo | BESS-MVP-003 | [BESS-MVP-006-add-delta-soc-degradation.md](BESS-MVP-006-add-delta-soc-degradation.md) |
| BESS-MVP-007 | Persist Dispatch Results And Run Metadata | AFK | Todo | BESS-MVP-004, BESS-MVP-005, BESS-MVP-006 | [BESS-MVP-007-persist-run-outputs.md](BESS-MVP-007-persist-run-outputs.md) |
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
