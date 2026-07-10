# BESS-TS5-009: Add Retention And Cleanup For Rebuildable Derived Data

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

9

## What to build

Implement the retention rules accepted in BESS-TS5-000 so the database does
not grow without control, while immutable audit data stays untouchable. The
core distinction: derived data that can be rebuilt (run result indexes and
similar) may be cleaned; audit data that cannot (artifacts, scenario version
snapshots, sources, revision history) may not.

An admin can remove rebuildable derived data for a run or a project, and the
system refuses — with a clear reason — to delete immutable audit data through
the cleanup path. The end-to-end proof closes the loop with TS-4: clean a
run's indexed results, verify the run still renders from artifacts, then
rebuild its indexes from artifacts using the existing rebuild path and verify
BBDD-first reads return.

Cleanup decisions live in a deep module testable without the UI, cleanup is
idempotent, and each execution reports removed, kept and failed items stably.
Retention rules are documented for admins.

## Acceptance criteria

- [x] An admin can remove rebuildable derived data for a run or project without deleting artifacts, snapshots, sources or revision history.
- [x] Cleaned run results keep rendering from artifacts and can be re-indexed using the existing rebuild path.
- [x] The cleanup path refuses to remove immutable audit data and reports why.
- [x] Cleanup is idempotent and reports removed/kept/failed stably across repeated runs.
- [x] Retention rules are documented for admins.

## Blocked by

BESS-TS5-000

## Resolution

Added deep module `app/result_retention.py` with a deliberately small surface:
`cleanup_run_result_data` and `cleanup_project_result_data`. The accepted
retention boundary is enforced there, not in the UI: only TS-4 result indexes
(`dispatch_table`, `asset_dispatch_table`, `summary`) are removable, while
immutable audit targets (`artifacts`, `scenario_versions`,
`time_series_sources`, `time_series_set_revisions`) are refused with stable
`kept` reasons.

`AnalystStore` gained the minimal persistence primitives this needs:
`list_project_succeeded_runs`, `delete_run_dispatch_result_index`,
`delete_run_asset_dispatch_result_index`, and
`delete_run_summary_result_index`. No audit table, artifact row, scenario
version row, source row, or revision row is deleted or rewritten by cleanup.

Admin-only API endpoints were added:

- `POST /api/admin/runs/{run_id}/cleanup-results`
- `POST /api/admin/projects/{project_id}/cleanup-results`

Both accept `{"targets": [...]}` and default to the rebuildable result-index
set when omitted. Cleanup is idempotent: repeated calls converge to
`already absent` for previously removed derived surfaces while immutable
targets remain under `kept`.

Admin documentation now lives in
`docs/series_tiempo/iter5/admin_retention_runbook.md`, including the accepted
boundary, supported targets, request/response examples, and the restore path
through TS-4 rebuild endpoints.

## Verification

- Backend full suite: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
  -> 392 tests passed, 2 skipped.
- Focused new proof: `tests/test_ts5_result_retention.py` (5 tests) covers
  run cleanup, project cleanup, immutable-target refusal, idempotence,
  rebuild restore, and admin-only endpoints.
- Targeted regressions also stayed green:
  `tests.test_ts4_result_indexing`, `tests.test_ts4_acceptance`,
  `tests.test_ts5_permission_matrix`.
- Frontend contract/build:
  `npm.cmd run api:generate`, `npm.cmd run api:check`, `npm.cmd run build`
  all green (for OpenAPI generation/check, `DATABASE_URL` was forced to
  `sqlite:///:memory:` so import-time app creation could not contend with the
  live PostgreSQL dev DB).
- Real Chrome + real PostgreSQL verification on local `uvicorn`:
  logged in as admin with the `.env` credentials, used
  `chrome:control-chrome` plus `chrome-devtools`, and exercised run `28`
  in project `37` (`TS4 Hydro Diagram Project`):
  `GET /api/runs/28/results` -> 200, then
  `POST /api/admin/runs/28/cleanup-results` removing
  `dispatch_table`/`asset_dispatch_table`/`summary` while refusing
  `artifacts`, then `GET /api/runs/28/results` -> still 200 from artifact
  fallback, then `POST /api/admin/runs/28/rebuild-results` -> 200 with all
  three surfaces re-indexed. Also verified
  `POST /api/admin/projects/37/cleanup-results` on `summary` + refused
  `artifacts`, followed by a successful rebuild of run `28`.
- Direct PostgreSQL check after browser verification confirmed final state:
  run `28` ended with `has_dispatch = true`, `has_asset = true`,
  `has_summary = true`, `artifact_count = 3`.
