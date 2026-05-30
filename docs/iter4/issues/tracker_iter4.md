# BESS Iteration 4 Issue Tracker

This document is the local tracker for the structured editor and time-series
ingestion iteration derived from
`docs/iter4/prd_structured_editor_flow.md`.

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
| BESS-ITER4-000 | Review Structured Editor And Ingestion PRD | HITL | ready-for-agent | Done | None | [BESS-ITER4-000-review-structured-editor-and-ingestion-prd.md](BESS-ITER4-000-review-structured-editor-and-ingestion-prd.md) |
| BESS-ITER4-001 | Run A Separate Import Export Price Case End To End | AFK | ready-for-agent | Done | BESS-ITER4-000 | [BESS-ITER4-001-run-a-separate-import-export-price-case-end-to-end.md](BESS-ITER4-001-run-a-separate-import-export-price-case-end-to-end.md) |
| BESS-ITER4-002 | Create And Edit One Active Scenario Draft | AFK | ready-for-agent | Done | BESS-ITER4-000 | [BESS-ITER4-002-create-and-edit-one-active-scenario-draft.md](BESS-ITER4-002-create-and-edit-one-active-scenario-draft.md) |
| BESS-ITER4-003 | Define One-Bus Assets In The Draft Editor | AFK | ready-for-agent | Todo | BESS-ITER4-002 | [BESS-ITER4-003-define-one-bus-assets-in-the-draft-editor.md](BESS-ITER4-003-define-one-bus-assets-in-the-draft-editor.md) |
| BESS-ITER4-004 | Upload And Preview A CSV Time-Series Source | AFK | ready-for-agent | Todo | BESS-ITER4-002 | [BESS-ITER4-004-upload-and-preview-a-csv-time-series-source.md](BESS-ITER4-004-upload-and-preview-a-csv-time-series-source.md) |
| BESS-ITER4-005 | Generate And Validate A System Case From Draft Plus CSV | AFK | ready-for-agent | Todo | BESS-ITER4-001, BESS-ITER4-003, BESS-ITER4-004 | [BESS-ITER4-005-generate-and-validate-a-system-case-from-draft-plus-csv.md](BESS-ITER4-005-generate-and-validate-a-system-case-from-draft-plus-csv.md) |
| BESS-ITER4-006 | Promote A Validated Draft And Run It Manually | AFK | ready-for-agent | Todo | BESS-ITER4-005 | [BESS-ITER4-006-promote-a-validated-draft-and-run-it-manually.md](BESS-ITER4-006-promote-a-validated-draft-and-run-it-manually.md) |
| BESS-ITER4-007 | Add Basic XLSX Time-Series Ingestion | AFK | ready-for-agent | Todo | BESS-ITER4-004, BESS-ITER4-005 | [BESS-ITER4-007-add-basic-xlsx-time-series-ingestion.md](BESS-ITER4-007-add-basic-xlsx-time-series-ingestion.md) |
| BESS-ITER4-008 | Harden Draft Ingestion Errors And Audit Metadata | AFK | ready-for-agent | Todo | BESS-ITER4-005, BESS-ITER4-007 | [BESS-ITER4-008-harden-draft-ingestion-errors-and-audit-metadata.md](BESS-ITER4-008-harden-draft-ingestion-errors-and-audit-metadata.md) |
| BESS-ITER4-009 | Finalize Iteration 4 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | BESS-ITER4-001 through BESS-ITER4-008 | [BESS-ITER4-009-finalize-iteration-4-acceptance-suite-and-docs.md](BESS-ITER4-009-finalize-iteration-4-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-ITER4-000
2. BESS-ITER4-001 and BESS-ITER4-002 can proceed after PRD review.
3. BESS-ITER4-003 and BESS-ITER4-004 can proceed after draft persistence exists.
4. BESS-ITER4-005 joins separate-price economics, draft assets, and CSV
   ingestion into a generated validated system case.
5. BESS-ITER4-006 closes the first structured editor execution path.
6. BESS-ITER4-007 adds XLSX ingestion after the CSV-backed generation path is
   stable.
7. BESS-ITER4-008 hardens errors and provenance once both ingestion formats
   exist.
8. BESS-ITER4-009 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-05-30 | All | Created | Initial local issue set generated from the Iteration 4 PRD and approved vertical-slice breakdown. |
| 2026-05-30 | BESS-ITER4-000 | Todo -> Done | Reviewed and accepted the structured editor and ingestion PRD against the final objective, completed Iteration 2 optimizer contract, and completed Iteration 3 analyst workflow. No PRD corrections were required. |
| 2026-05-30 | BESS-ITER4-001 | Todo -> In Progress | Started separate import/export price support using TDD, with a Julia end-to-end tracer bullet for validation, solve, output economics, and metadata. |
| 2026-05-30 | BESS-ITER4-001 | In Progress -> Done | Added backward-compatible separate-price economics in Julia, result output columns, summary/metadata price mode, and Python result price-chart fallback behavior. Verified 41 Python tests and 372 Julia tests. Browser and Chrome DevTools MCP attempts were blocked by local runtime/profile errors. |
| 2026-05-30 | BESS-ITER4-002 | Todo -> In Progress | Started one-active-draft persistence using TDD, with API behavior as the first tracer bullet. |
| 2026-05-30 | BESS-ITER4-002 | In Progress -> Done | Added `scenario_drafts` persistence, API read/create/update endpoints, initialization from immutable scenario versions, and a basic SSR draft view/save flow. Verified 44 Python tests and Chrome DevTools page inspection. |

## Regression Guard

Every Iteration 4 slice that changes Julia code must run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Every slice that changes the Python web application should run the relevant
backend/API/template tests introduced for Iteration 3 and Iteration 4.

Slices touching the structured editor should prove that the Iteration 3
paste/upload JSON path still works unless the slice is limited to Julia-only
behavior.

## Final Iteration 4 Verification

The closing acceptance slice must run the full Python web acceptance suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

It must also keep the Julia optimizer regression suite green:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

The final acceptance coverage must prove the structured analyst flow end to end:
draft creation, structured asset editing, CSV upload and mapping, XLSX upload
and mapping, generated `system_case` preview, Julia-backed validation, promotion
to immutable scenario version, manual run launch, successful completion,
artifact registration, separate-price result review, downloads, malformed input
rejection, and preservation of the paste/upload JSON path.

## Dependency Notes

- BESS-ITER4-000 is HITL because the PRD and issue breakdown should be accepted
  before implementation.
- BESS-ITER4-001 is unblocked by draft work because separate-price economics can
  be proved directly through the Julia contract and existing result flow.
- BESS-ITER4-002 creates the persistent draft object needed by all structured
  editor slices.
- BESS-ITER4-003 and BESS-ITER4-004 intentionally split asset editing and CSV
  ingestion so each can be verified before generated-case validation.
- BESS-ITER4-005 is the first generated `system_case` slice and must wait for
  separate prices, draft assets, and CSV ingestion.
- BESS-ITER4-006 connects the generated case to the existing immutable version
  and run workflow.
- BESS-ITER4-007 adds XLSX only after the CSV path has established the common
  ingestion contract.
- BESS-ITER4-008 hardens error taxonomy and provenance after both ingestion
  formats exist.
- BESS-ITER4-009 is the final proof that the iteration satisfies the PRD and
  preserves Iteration 3 behavior.
