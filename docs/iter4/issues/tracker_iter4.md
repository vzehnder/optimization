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
| BESS-ITER4-003 | Define One-Bus Assets In The Draft Editor | AFK | ready-for-agent | Done | BESS-ITER4-002 | [BESS-ITER4-003-define-one-bus-assets-in-the-draft-editor.md](BESS-ITER4-003-define-one-bus-assets-in-the-draft-editor.md) |
| BESS-ITER4-004 | Upload And Preview A CSV Time-Series Source | AFK | ready-for-agent | Done | BESS-ITER4-002 | [BESS-ITER4-004-upload-and-preview-a-csv-time-series-source.md](BESS-ITER4-004-upload-and-preview-a-csv-time-series-source.md) |
| BESS-ITER4-005 | Generate And Validate A System Case From Draft Plus CSV | AFK | ready-for-agent | Done | BESS-ITER4-001, BESS-ITER4-003, BESS-ITER4-004 | [BESS-ITER4-005-generate-and-validate-a-system-case-from-draft-plus-csv.md](BESS-ITER4-005-generate-and-validate-a-system-case-from-draft-plus-csv.md) |
| BESS-ITER4-006 | Promote A Validated Draft And Run It Manually | AFK | ready-for-agent | Done | BESS-ITER4-005 | [BESS-ITER4-006-promote-a-validated-draft-and-run-it-manually.md](BESS-ITER4-006-promote-a-validated-draft-and-run-it-manually.md) |
| BESS-ITER4-007 | Add Basic XLSX Time-Series Ingestion | AFK | ready-for-agent | Done | BESS-ITER4-004, BESS-ITER4-005 | [BESS-ITER4-007-add-basic-xlsx-time-series-ingestion.md](BESS-ITER4-007-add-basic-xlsx-time-series-ingestion.md) |
| BESS-ITER4-008 | Harden Draft Ingestion Errors And Audit Metadata | AFK | ready-for-agent | Done | BESS-ITER4-005, BESS-ITER4-007 | [BESS-ITER4-008-harden-draft-ingestion-errors-and-audit-metadata.md](BESS-ITER4-008-harden-draft-ingestion-errors-and-audit-metadata.md) |
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
| 2026-05-31 | BESS-ITER4-003 | Todo -> In Progress | Started structured one-bus asset editing with TDD, using the generated system-case preview endpoint as the first API tracer bullet. |
| 2026-05-31 | BESS-ITER4-003 | In Progress -> Done | Added structured draft editor generation for PCC, grid, battery, renewable, load, and solver settings; added SSR form editing, duplicate ID and solver-options errors, source-version asset prefill, and Chrome DevTools UI verification. Verified 48 Python tests and 372 Julia tests. |
| 2026-06-01 | BESS-ITER4-004 | Todo -> In Progress | Started CSV time-series source ingestion using TDD, with API upload, safe source-file storage, preview, and mapping suggestions as the first tracer bullet. |
| 2026-06-01 | BESS-ITER4-004 | In Progress -> Done | Added CSV source storage under configured input-source root, preview rows and columns, mapping suggestions, manual mapping save, mapped-row validation, SSR upload/mapping UI, and draft-stored ingestion metadata. Verified 52 Python tests, 372 Julia tests, and Chrome DevTools MCP page inspection. |
| 2026-06-01 | BESS-ITER4-005 | Todo -> In Progress | Started generated system-case validation from structured draft assets plus CSV mapping using TDD, with an API generation/validation tracer bullet. |
| 2026-06-01 | BESS-ITER4-005 | In Progress -> Done | Added generated periods from validated CSV rows, generated-case API and SSR validation endpoints, draft-stored generated-case validation snapshots, Python validation short-circuiting, read-only preview coverage, and paste/upload JSON regression coverage. Verified 57 Python tests, 372 Julia tests, and Chrome DevTools MCP page inspection. In-app Browser was attempted but blocked by local `node_repl` sandbox startup failure. |
| 2026-06-02 | BESS-ITER4-006 | Todo -> In Progress | Started validated draft promotion using TDD, with an API draft-to-version-to-run tracer bullet. |
| 2026-06-02 | BESS-ITER4-006 | In Progress -> Done | Added API and SSR promotion from current successful generated-case validation snapshots, reused immutable scenario-version persistence and manual run flow, preserved editable drafts and paste/upload JSON regression coverage. Verified 59 Python tests, local Julia-backed smoke run success, and Chrome DevTools MCP console inspection. In-app Browser was attempted but blocked by local `node_repl` sandbox startup failure. |
| 2026-06-02 | BESS-ITER4-007 | Todo -> In Progress | Started basic XLSX ingestion using TDD, with API upload/default-sheet preview and mapping validation as the first tracer bullet. |
| 2026-06-02 | BESS-ITER4-007 | In Progress -> Done | Added XLSX upload storage, first-sheet/default and selected-sheet parsing, preview rows and columns, CSV-shared mapping/validation, generated-case reuse, unsupported workbook errors, and SSR upload support. Verified 63 Python tests, 372 Julia tests, and Chrome DevTools MCP page inspection. In-app Browser was attempted but blocked by local `node_repl` sandbox startup failure. |
| 2026-06-02 | BESS-ITER4-008 | Todo -> In Progress | Started draft ingestion hardening using TDD, with source-file error taxonomy as the first API tracer bullet. |
| 2026-06-02 | BESS-ITER4-008 | In Progress -> Done | Added source-file, mapping, Python validation, and Julia validation error categories; added safe editor-promotion provenance metadata on scenario versions; preserved the Iteration 3 execution failure audit path. Verified 65 Python tests, 372 Julia tests, and Chrome DevTools MCP API/UI inspection. In-app Browser was attempted but blocked by local `node_repl` sandbox startup failure. |

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
