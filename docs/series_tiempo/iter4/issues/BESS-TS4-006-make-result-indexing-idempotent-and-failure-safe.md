# BESS-TS4-006: Make Result Indexing Idempotent And Failure-Safe

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-21
Fecha de termino planificada: 2026-07-22
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

## User stories covered

2, 19

## What to build

Harden the result-indexing write path so it is safe to retry and can never
damage a successful run. Indexing the same run twice must converge to the same
indexed state without duplicate records. Retrying after a partial failure
(some series written, then an interruption) must complete the index correctly
rather than duplicating or corrupting it.

An indexing failure must never change the run's `succeeded` status, never
touch its registered artifacts and never block the analyst from reading
results through the artifact path. Failures must be visible (status or log
that identifies the affected run) so the run can be re-indexed later, with the
artifacts remaining the source from which BBDD results can be reconstructed.

## Acceptance criteria

- [x] Re-indexing an already-indexed run converges without duplicate records.
- [x] Retrying after a simulated partial failure completes the index correctly.
- [x] An indexing failure leaves the run `succeeded` and its artifacts untouched, and the run's results remain readable from artifacts.
- [x] Indexing failures are surfaced so affected runs can be identified and re-indexed.
- [x] Tests prove idempotent re-indexing and partial-failure retry against representative artifacts.

## Resolution

Added a new `index_run_results` orchestrator in `app/result_indexing.py` that
indexes the three TS-4 result surfaces (dispatch, asset dispatch, summary)
independently per run: a failure on one surface is logged (`app.result_indexing`
logger, with run id, surface and error) and recorded in a returned outcome, but
never raises and never blocks the other surfaces from indexing. `runner.py`'s
`_index_succeeded_run_results` now delegates to this single hardened entry
point instead of three ad hoc `try/except: pass` blocks that silently
swallowed failures with no visibility.

Hardened `replace_run_dispatch_result_index`,
`replace_run_asset_dispatch_result_index` and `replace_run_summary_result_index`
in `app/persistence.py` so that any exception during the write (header upsert,
row delete, row insert) triggers a cleanup of that run's partial index state
(both the header row and any detail rows) before re-raising. This guarantees a
write attempt either leaves a complete, consistent index or no index at all —
never a header paired with missing/partial rows — which matters because
PostgreSQL runs in autocommit mode (see `app/database.py`), so a mid-write
failure can leave earlier statements already durably committed.

## Verification

- Added `ResultIndexingIdempotencyTests` and `ResultIndexingFailureSafetyTests`
  to `tests/test_ts4_result_indexing.py`: re-indexing converges without
  duplicate rows, re-indexing after artifact content changes drops stale rows,
  a naturally-forced partial write failure (duplicate-timestamp dispatch.csv
  triggering the `UNIQUE(run_id, timestamp)` constraint mid-insert) leaves no
  corrupt index and is safe to retry to a correct state, and a malformed
  `summary.json` does not block dispatch/asset-dispatch indexing.
- Added `test_runner_survives_partial_result_indexing_failure_without_raising`
  to `tests/test_manual_runs.py` proving the `JuliaRunExecutor` integration
  point tolerates a partial indexing failure without raising and the run stays
  `succeeded` with artifact-fallback results still correct.
- Ran `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` (319 tests, all green).
- Verified against the real PostgreSQL database from `.env`: a standalone
  script reproduced the duplicate-timestamp partial failure against real
  Postgres (autocommit mode), confirmed no orphan header/rows were left behind,
  confirmed the run stayed `succeeded`, then fixed the artifact and confirmed
  the retry converged to a complete, correct index, and that re-indexing again
  stayed duplicate-free.
- Verified live in Chrome DevTools against the running app (real Postgres,
  real Julia): loaded an existing indexed run's results page as a regression
  check (summary, charts, dispatch and asset-dispatch tables all still
  rendered correctly), then triggered a fresh manual run from a real
  multi-asset scenario version through the UI (Run 26) and confirmed it
  succeeded with all three surfaces (dispatch, asset dispatch, summary)
  indexed via the live pipeline and rendering correctly in the browser with no
  console errors.

## Blocked by

BESS-TS4-001
