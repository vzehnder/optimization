# BESS Iteration 3 Issue Tracker

This document is the local tracker for the analyst web flow iteration derived
from `docs/iter3/prd_analyst_web_flow.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the `ready-for-agent`
triage label.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- |
| BESS-ITER3-000 | Review Analyst Web Flow PRD | HITL | ready-for-agent | Done | None | [BESS-ITER3-000-review-analyst-web-flow-prd.md](BESS-ITER3-000-review-analyst-web-flow-prd.md) |
| BESS-ITER3-001 | Validate A System Case From The Web App | AFK | ready-for-agent | Done | BESS-ITER3-000 | [BESS-ITER3-001-validate-a-system-case-from-the-web-app.md](BESS-ITER3-001-validate-a-system-case-from-the-web-app.md) |
| BESS-ITER3-002 | Save A Validated Scenario Version Under A Project | AFK | ready-for-agent | Done | BESS-ITER3-001 | [BESS-ITER3-002-save-a-validated-scenario-version-under-a-project.md](BESS-ITER3-002-save-a-validated-scenario-version-under-a-project.md) |
| BESS-ITER3-003 | Preserve Immutable Version History From Paste Or Upload | AFK | ready-for-agent | Done | BESS-ITER3-002 | [BESS-ITER3-003-preserve-immutable-version-history-from-paste-or-upload.md](BESS-ITER3-003-preserve-immutable-version-history-from-paste-or-upload.md) |
| BESS-ITER3-004 | Launch Manual Runs And Track Success State | AFK | ready-for-agent | Done | BESS-ITER3-003 | [BESS-ITER3-004-launch-manual-runs-and-track-success-state.md](BESS-ITER3-004-launch-manual-runs-and-track-success-state.md) |
| BESS-ITER3-005 | Capture Failed Runs Logs And Input Snapshots | AFK | ready-for-agent | Done | BESS-ITER3-004 | [BESS-ITER3-005-capture-failed-runs-logs-and-input-snapshots.md](BESS-ITER3-005-capture-failed-runs-logs-and-input-snapshots.md) |
| BESS-ITER3-006 | Register And Download Auditable Artifacts | AFK | ready-for-agent | Done | BESS-ITER3-004, BESS-ITER3-005 | [BESS-ITER3-006-register-and-download-auditable-artifacts.md](BESS-ITER3-006-register-and-download-auditable-artifacts.md) |
| BESS-ITER3-007 | Review Run Summary And Result Tables | AFK | ready-for-agent | Done | BESS-ITER3-006 | [BESS-ITER3-007-review-run-summary-and-result-tables.md](BESS-ITER3-007-review-run-summary-and-result-tables.md) |
| BESS-ITER3-008 | Add Basic Result Charts | AFK | ready-for-agent | Done | BESS-ITER3-007 | [BESS-ITER3-008-add-basic-result-charts.md](BESS-ITER3-008-add-basic-result-charts.md) |
| BESS-ITER3-009 | Finalize Iteration 3 Acceptance Suite And Docs | AFK | ready-for-agent | Done | BESS-ITER3-001 through BESS-ITER3-008 | [BESS-ITER3-009-finalize-iteration-3-acceptance-suite-and-docs.md](BESS-ITER3-009-finalize-iteration-3-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-ITER3-000
2. BESS-ITER3-001
3. BESS-ITER3-002
4. BESS-ITER3-003
5. BESS-ITER3-004
6. BESS-ITER3-005
7. BESS-ITER3-006
8. BESS-ITER3-007
9. BESS-ITER3-008
10. BESS-ITER3-009

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-05-29 | All | Created | Initial local issue set generated from the Iteration 3 PRD and approved vertical-slice breakdown. |
| 2026-05-29 | BESS-ITER3-000 | Todo -> Done | Reviewed and accepted the analyst web flow PRD against the final objective and completed Iteration 2 contract. No PRD corrections were required. |
| 2026-05-29 | BESS-ITER3-001 | Todo -> In Progress | Started the first web-to-Julia validation slice using TDD. |
| 2026-05-29 | BESS-ITER3-001 | In Progress -> Done | Added Julia validation CLI plus FastAPI validation page/API. Verified Python web tests with 7 tests and full Julia suite with 351 tests. |
| 2026-05-29 | BESS-ITER3-002 | Todo -> In Progress | Started persisted project/scenario/scenario-version workflow using TDD. |
| 2026-05-29 | BESS-ITER3-003 | Todo -> In Progress | Started paste/upload immutable version history workflow using TDD. |
| 2026-05-29 | BESS-ITER3-002 | In Progress -> Done | Added DATABASE_URL-backed persistence, project/scenario API and UI, validated scenario version saves, metadata extraction, and invalid-case no-save behavior. Verified Python web tests with 17 tests and full Julia suite with 351 tests. |
| 2026-05-29 | BESS-ITER3-003 | In Progress -> Done | Added shared paste/upload version creation, editable prefill from existing versions, version listings, and immutability coverage. Verified Python web tests with 17 tests and full Julia suite with 351 tests. |
| 2026-05-29 | BESS-ITER3-004 | Todo -> In Progress | Started the manual run execution and polling workflow using TDD. |
| 2026-05-29 | BESS-ITER3-004 | In Progress -> Done | Added run persistence, single-worker local queue, Julia execution runner, API/UI launch, status polling, input snapshots, and success payload recording. Verified Python web tests with 22 tests, real backend runner sample success, and full Julia suite with 351 tests. |
| 2026-05-30 | BESS-ITER3-005 | Todo -> In Progress | Started failed-run auditability using TDD after rechecking the BESS-ITER3-004 run flow. |
| 2026-05-30 | BESS-ITER3-005 | In Progress -> Done | Added execution-time snapshot revalidation, failed-run structured errors, stdout/stderr log files, persisted error messages, and failure display in API/UI. Verified Python web tests with 25 tests, browser failure-page check, and full Julia suite with 351 tests. |
| 2026-05-30 | BESS-ITER3-006 | Todo -> In Progress | Started auditable artifact registration and download workflow using TDD after reviewing the BESS-ITER3-005 failure audit path. |
| 2026-05-30 | BESS-ITER3-006 | In Progress -> Done | Added run artifact metadata, artifact-root safety checks, runner registration for success/failure audit files, API listing/download endpoints, and run-page download links. Verified Python web tests with 29 tests, real local run artifact download check, and full Julia suite with 351 tests. |
| 2026-05-30 | BESS-ITER3-007 | Todo -> In Progress | Started table-based run results review after rechecking the BESS-ITER3-006 artifact registration and download path. |
| 2026-05-30 | BESS-ITER3-007 | In Progress -> Done | Added artifact-backed results reader, `/api/runs/{run_id}/results`, completed-run summary rendering, and dispatch/asset table rendering. Verified Python web tests with 35 tests, local HTTP results-page check, and full Julia suite with 351 tests. |
| 2026-05-30 | BESS-ITER3-008 | Todo -> In Progress | Started basic result charts using TDD after rechecking the BESS-ITER3-007 results reader/API/UI path. |
| 2026-05-30 | BESS-ITER3-008 | In Progress -> Done | Added artifact-derived chart payloads, run-page SVG chart panels, missing-column fallbacks, and API/template coverage. Verified Python web tests with 38 tests, local HTTP charts-page check, and full Julia suite with 351 tests. |
| 2026-05-30 | BESS-ITER3-009 | Todo -> In Progress | Started the final Iteration 3 acceptance suite and documentation slice after rechecking the BESS-ITER3-008 chart results path. |
| 2026-05-30 | BESS-ITER3-009 | In Progress -> Done | Added the final private analyst flow acceptance suite and local app documentation, including database/artifact configuration and final verification instructions. Verified Python web tests with 40 tests, local HTTP app checks, and full Julia suite with 351 tests. |

## Regression Guard

Every Iteration 3 slice that changes Julia code must run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Every slice that changes the Python web application should run the relevant
backend/API/template tests introduced for Iteration 3. The final acceptance
slice must prove the complete private analyst flow end to end.

## Final Iteration 3 Verification

The closing acceptance slice must run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

It must also keep the Julia optimizer regression suite green:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The final acceptance coverage must prove the private analyst flow end to end:
project creation, scenario creation, immutable scenario version creation,
Julia-backed validation, manual run launch, successful completion, artifact
registration, summary/table review, chart data, downloads, malformed input
rejection, and failed-run errors/logs.

## Dependency Notes

- BESS-ITER3-000 is HITL because the PRD should be accepted before
  implementation.
- BESS-ITER3-001 creates the first web-to-Julia validation boundary without
  solving.
- BESS-ITER3-002 creates the persisted project/scenario/version path after
  validation exists.
- BESS-ITER3-003 makes version history usable through paste/upload inputs and
  immutability.
- BESS-ITER3-004 creates the first successful manual execution path.
- BESS-ITER3-005 completes the failed-run and audit-log path.
- BESS-ITER3-006 indexes and exposes the auditable artifacts produced by runs.
- BESS-ITER3-007 adds table-based results review from existing output files.
- BESS-ITER3-008 adds minimal charts without creating a dashboard builder.
- BESS-ITER3-009 closes the iteration with docs and acceptance coverage.
