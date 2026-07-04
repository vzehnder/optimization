# BESS TS-2 Issue Tracker

This document is the local tracker for TS-2: generic time-series catalog in
BBDD, derived from `docs/series_tiempo/iter2/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS2-000 | Review TS-2 PRD And Series Catalog Semantics | HITL | ready-for-agent | Done | 2026-07-06 | 2026-07-06 | None | [BESS-TS2-000-review-ts2-prd-and-series-catalog-semantics.md](BESS-TS2-000-review-ts2-prd-and-series-catalog-semantics.md) |
| BESS-TS2-001 | Import A Minimal CSV Time-Series Set End-To-End | AFK | ready-for-agent | Done | 2026-07-04 | 2026-07-04 | BESS-TS2-000 | [BESS-TS2-001-import-a-minimal-csv-time-series-set-end-to-end.md](BESS-TS2-001-import-a-minimal-csv-time-series-set-end-to-end.md) |
| BESS-TS2-002 | Preview Sources And Map Columns To Canonical Signals | AFK | ready-for-agent | Done | 2026-07-04 | 2026-07-04 | BESS-TS2-001 | [BESS-TS2-002-preview-sources-and-map-columns-to-canonical-signals.md](BESS-TS2-002-preview-sources-and-map-columns-to-canonical-signals.md) |
| BESS-TS2-003 | Enforce Temporal And Physical Value Validation | AFK | ready-for-agent | In Review | 2026-07-13 | 2026-07-14 | BESS-TS2-002 | [BESS-TS2-003-enforce-temporal-and-physical-value-validation.md](BESS-TS2-003-enforce-temporal-and-physical-value-validation.md) |
| BESS-TS2-004 | Add XLSX Import With Sheet Selection | AFK | ready-for-agent | Todo | 2026-07-15 | 2026-07-16 | BESS-TS2-003 | [BESS-TS2-004-add-xlsx-import-with-sheet-selection.md](BESS-TS2-004-add-xlsx-import-with-sheet-selection.md) |
| BESS-TS2-005 | Browse The Project Time-Series Catalog | AFK | ready-for-agent | Todo | 2026-07-17 | 2026-07-20 | BESS-TS2-001 | [BESS-TS2-005-browse-the-project-time-series-catalog.md](BESS-TS2-005-browse-the-project-time-series-catalog.md) |
| BESS-TS2-006 | Edit Set Values Manually With Auditable Revisions | AFK | ready-for-agent | Todo | 2026-07-21 | 2026-07-22 | BESS-TS2-003, BESS-TS2-005 | [BESS-TS2-006-edit-set-values-manually-with-auditable-revisions.md](BESS-TS2-006-edit-set-values-manually-with-auditable-revisions.md) |
| BESS-TS2-007 | Replace A Set Version With A New File Upload | AFK | ready-for-agent | Todo | 2026-07-23 | 2026-07-24 | BESS-TS2-004 | [BESS-TS2-007-replace-a-set-version-with-a-new-file-upload.md](BESS-TS2-007-replace-a-set-version-with-a-new-file-upload.md) |
| BESS-TS2-008 | Harden Bulk Import Performance And Audit Metadata | AFK | ready-for-agent | Todo | 2026-07-27 | 2026-07-28 | BESS-TS2-006, BESS-TS2-007 | [BESS-TS2-008-harden-bulk-import-performance-and-audit-metadata.md](BESS-TS2-008-harden-bulk-import-performance-and-audit-metadata.md) |
| BESS-TS2-009 | Finalize TS-2 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-29 | 2026-07-29 | BESS-TS2-001 through BESS-TS2-008 | [BESS-TS2-009-finalize-ts2-acceptance-suite-and-docs.md](BESS-TS2-009-finalize-ts2-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS2-000 closes the PRD review and the initial canonical signal catalog.
2. BESS-TS2-001 is the tracer bullet: CSV source to persisted set, revision 1 and content hash in BBDD.
3. BESS-TS2-002 adds preview and canonical signal mapping on top of the tracer path.
4. BESS-TS2-003 hardens temporal and physical validation with row/column-tied errors.
5. BESS-TS2-004 extends the same pipeline to XLSX with sheet selection.
6. BESS-TS2-005 can proceed any time after BESS-TS2-001; it makes the catalog browsable.
7. BESS-TS2-006 adds bounded manual edits creating auditable revisions.
8. BESS-TS2-007 adds file-replacement revisions once both formats import cleanly.
9. BESS-TS2-008 closes bulk performance and audit metadata gaps across all paths.
10. BESS-TS2-009 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-04 | All | Created | Initial local issue set generated from the TS-2 PRD and the series hierarchy roadmap. |
| 2026-07-04 | BESS-TS2-000 | Todo -> Done | Accepted TS-2 catalog semantics in `docs/series_tiempo/iter2/decision_record_ts2_catalog_semantics.md`. No PRD correction required. Also removed TS-1 verification scenarios/cases (`TS1-00x provenance/verification` scenarios under projects 1, 5-10) from the `energy_dispatch` database so per-issue manual QA data does not keep accumulating across iterations. |
| 2026-07-04 | BESS-TS2-001 | Todo -> In Review | Implemented TS-2 tracer bullet end-to-end: generic catalog tables, deep import module, persisted source/set/revision/hash path, API readback, and React upload/import confirmation flow. Focused Python backend tests, React tests, OpenAPI generation, API drift check, and production frontend build passed. Chrome control against the local app reached login and project setup on the PostgreSQL-backed app, but final manual import verification was interrupted by another installed browser extension UI blocking automation. |
| 2026-07-04 | BESS-TS2-002 | Todo -> In Review | Extended TS-2 from single-signal tracer bullet to preview-and-map multi-signal imports: the deep import module now accepts plural `signal_mappings`, validates missing/duplicate/unknown columns and unit mismatches with column-tied errors, persists `source_column`/`source_unit` plus revision mapping audit metadata, and writes multiple `time_series_signals`/`time_series_values` rows per set. React now shows explicit preview-and-map rows before import confirmation, supports adding multiple mapped signals, and confirms the created set with all imported canonical signals. Focused TS-2 backend tests, full Python discovery (188 ok, 1 skipped), full Vitest suite (47 ok), production frontend build, `eslint .`, OpenAPI regeneration, and API drift check all passed. Chrome smoke was attempted with both `chrome:control-chrome` and `mcp__chrome_devtools`, but the sandbox could not keep a local PostgreSQL-backed app server alive and Chrome policy rejected navigation to the retry port, so manual browser QA remains pending outside the sandbox. |
| 2026-07-04 | BESS-TS2-001 | In Review -> Done | Review passed: focused TS-2 tests, full Python discovery, Vitest, eslint, build and API drift check green. Pending Chrome QA completed via `chrome-devtools` MCP against the PostgreSQL app on `http://127.0.0.1:8000` (project `TS2 Chrome QA 002`, scenario `Multi-signal import`): dual-price CSV imported end-to-end and PostgreSQL shows set `ts2_qa_dual_price` v1 with 2 signals, 3 periods, 6 values and revision 1. |
| 2026-07-04 | BESS-TS2-002 | In Review -> Done | Same review session: Chrome smoke confirmed source preview (columns plus sample rows), auto-suggested multi-signal mapping (`buy_price`/`sell_price` to import/export price signals with units) and confirmation listing both canonical signals. |
| 2026-07-04 | BESS-TS2-003 | Todo -> In Review | Implemented temporal/physical validation via TDD in `app/time_series_catalog.py`: duplicate timestamps, unordered timestamps and overlapping periods (incoherent durations) now rejected with row-tied errors; malformed timestamps carry row context; nonnumeric, nonpositive-duration, negative-nonnegative and invalid-IANA-timezone rules locked with acceptance tests. Failed imports persist nothing (validation-first plus autocommit cleanup that deletes the set row if child inserts fail). React confirmation now shows the set timezone as `America/Santiago (IANA)`. Suites: TS-2 catalog 14 ok, Python discovery 198 ok/1 skipped, Vitest 47 ok, eslint, build and api:check green. Chrome QA: duplicate-timestamp CSV surfaced `row 3: duplicate timestamp '2026-01-01T00:00:00' (already used by row 2)` with no partial set in PostgreSQL. |

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs and TS-1 hierarchy provenance tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

No slice in TS-2 should touch Julia-facing payloads; if one accidentally does,
the Julia optimizer regression suite must be run.

TS-2 must not migrate or break the existing hydraulic-specific time-series
tables or the draft-embedded CSV/XLSX ingestion; those remain legacy paths
until TS-5.
