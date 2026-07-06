# BESS-TS2-009: Finalize TS-2 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-29
Fecha de termino planificada: 2026-07-29
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

1 through 23

## What to build

Close TS-2 with acceptance coverage, documentation and tracker updates. The
iteration is complete when time-series sets are first-class database objects:
importable from CSV and XLSX, versioned with labels and revisions, hashed,
correctable manually or by file replacement, and browsable per project, even
though no optimization case uses them yet.

No new product behavior should be introduced in this slice beyond final
hardening required by acceptance tests. Documentation should explain the
catalog model and make explicit that case bindings, dropdown runs and result
series remain deferred to TS-3 and TS-4.

## Acceptance criteria

- [x] A focused TS-2 acceptance test proves the library story end to end: CSV import, XLSX import, manual edit revision, file replacement revision and catalog visibility.
- [x] Acceptance coverage proves validation failures are tied to source row and column.
- [x] Acceptance coverage proves revisions and content hashes are stable audit anchors across edits and replacements.
- [x] Documentation explains the final TS-2 catalog model and the work deferred to TS-3 and TS-4.
- [x] A manual test checklist is added under `docs/series_tiempo/iter2/`.
- [x] The issue tracker progress log is updated and final verification commands are recorded.
- [x] The README or relevant docs point to the TS-2 catalog documentation if appropriate.
- [x] No case binding or run-from-series behavior is introduced early.

## Blocked by

BESS-TS2-001 through BESS-TS2-008

## Implementation Notes

Closing proof issue; no production code change was needed since TS2-001..008
already implement the full CSV/XLSX import, versioning, manual-edit,
file-replacement and catalog-browsing behavior. Added
`tests.test_ts2_acceptance` (TDD, tracer bullet first) with two tests: one
continuous story that imports a multi-signal CSV set and a single-signal
XLSX set (with sheet selection), confirms both are listed and detailed via
the project catalog endpoints, edits a value on the CSV set (new revision,
new hash, prior revision's hash stable) and replaces the XLSX set's source
file (new revision, identity stable, prior revision's hash stable), and
proves that an import, a manual edit and a file replacement each carrying a
validation failure (duplicate timestamp / negative value for a nonnegative
signal) are all rejected with source-file/row or edit/period context and
leave no partial mutation behind; and a second test asserting the README,
this issue, the tracker and the new manual checklist are all in their
closed/final state. The behavior test passed on the first run, confirming
BESS-TS2-001 through BESS-TS2-008 already satisfy this slice's acceptance
criteria end to end.

Added a new README section ("TS-2: Generic Time-Series Catalog") documenting
the catalog model, the version/revision distinction, the shared signal
validation/error-context rules, how the catalog is browsed, and what remains
deferred to TS-3 (case bindings, dropdown runs) and TS-4 (result series).
Added `docs/series_tiempo/iter2/pruebas_manuales_ts2.md`, a manual checklist
for catalog import/browse/edit/replace flows and legacy-iteration
regressions, following the same shape as the TS-1 manual checklist. Updated
`docs/series_tiempo/iter2/issues/tracker_ts2.md` to mark this issue Done and
recorded final verification commands.

Verified end-to-end via chrome-devtools MCP against the real
PostgreSQL-backed app: imported a multi-signal CSV set and a single-signal
XLSX set (sheet selection) into a fresh project, confirmed both appear in the
project catalog with correct summary fields, edited a value on the CSV set
(new revision, new hash, prior revision's hash intact in history), replaced
the XLSX set's source with a corrected file (new revision, name/version_label
unchanged, prior revision's hash intact), and confirmed an invalid import, an
invalid manual edit and an invalid replacement were each rejected with
row/edit context and left the affected set at its prior revision and hash.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts2_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Julia regression was not required for this slice because no Julia-facing
contracts, optimizer behavior, or artifact formats changed.
