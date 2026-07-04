# BESS-TS1-007: Preserve Legacy Scenario Draft Version And Run Compatibility

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

7, 8, 17 through 20

## What to build

Run a compatibility and hardening slice across the existing modeling paths.
The new hierarchy metadata must not break paste/upload JSON, structured drafts,
hydraulic diagrams, scenario version deletion protections, manual runs,
artifacts, results or publications.

This slice should fill gaps found after the earlier implementation slices and
add regression coverage where compatibility risk is highest.

## Acceptance criteria

- [x] Paste/upload JSON can still create immutable scenario versions.
- [x] Structured drafts can still validate, promote and run.
- [x] Hydraulic diagrams can still validate, promote and run.
- [x] Manual runs still reference scenario versions, not mutable cases.
- [x] Run artifacts and result readers still work for old and new runs.
- [x] Publication flows still resolve scenario version and run lineage.
- [x] Scenario version deletion protections still block versions referenced by runs or publications.
- [x] Compatibility tests cover old versions without hierarchy metadata.
- [x] Full relevant Python web acceptance suite remains green.

## Implementation notes

- Audited every path the TS1-001..006 hierarchy provenance metadata rides
  alongside: paste/upload JSON, structured drafts, hydraulic diagrams, manual
  run creation, run artifacts, result readers, publication drafts and scenario
  version deletion. `generation_metadata_json` is additive and none of these
  paths join on or require its contents, so no production code change was
  needed for compatibility itself.
- Found a real, previously untested gap: `AnalystStore.delete_scenario_version`
  and its `DELETE /api/scenario-versions/{id}` endpoint (`app/persistence.py`,
  `app/main.py`) had zero test coverage in the whole suite, for either the
  block-on-reference path or the allow-when-unreferenced path.
- Added `tests/test_legacy_scenario_version_compatibility.py` (TDD, tracer
  bullet first). It seeds a scenario version the same way pre-TS1-001 data
  would look — inserted directly via SQL with `generation_metadata_json='{}'`,
  bypassing `create_scenario_version` — and proves: (1) an unreferenced legacy
  version is deletable and returns zero deleted run/publication counts; (2) a
  legacy version can still launch a manual run through the API, have the run
  marked succeeded, register artifacts, list them back through
  `/api/runs/{id}/artifacts`, and back a full publication draft with correct
  `scenario_version_id`/`run_id` lineage, after which deletion is correctly
  blocked with a 409 and a "referenced by runs" message.
- Full Python suite: 182 tests green (180 pre-existing + 2 new), 1 skipped
  (Postgres integration test, requires `POSTGRES_TEST_DATABASE_URL`).

## Verification

- `.\.venv\Scripts\python.exe -m unittest tests.test_legacy_scenario_version_compatibility -v`
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` (182 passed, 1 skipped)
- Manual verification against the real PostgreSQL-backed app (`.env`
  credentials) with the real Julia validator/solver via chrome-devtools MCP:
  pasted a system case to create a fresh immutable version (topology/parameter
  provenance rendered correctly), launched a manual run that solved to
  `OPTIMAL` with real HiGHS results and rendered charts/tables, listed and
  downloaded its artifacts, created and published a publication draft with
  correct scenario/run lineage, then attempted to delete that now-referenced
  version through the UI's "Eliminar version" control and confirmed the app
  surfaced the backend's 409 ("scenario versions referenced by runs cannot be
  deleted") as an alert without deleting the version. Also created a second,
  unreferenced version via the API and confirmed it deletes cleanly
  (`deleted_run_count: 0`, `deleted_publication_count: 0`).

## Blocked by

- BESS-TS1-005
- BESS-TS1-006
