# BESS-TS4-005: Record Full Result Lineage With Drift-Proof Constraints

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-17
Fecha de termino planificada: 2026-07-20
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

## User stories covered

4, 5, 20

## What to build

Complete the lineage of indexed results so any result record can be traced to
the exact combination that produced it: run, execution snapshot, case,
topology hash, parameter hash, input variant, date range and the input series
revisions/hashes that TS-3 froze into the run's generation metadata at launch
time. Lineage values must come from that frozen metadata, never from live case
state, so later edits to series, topology or parameters cannot alter what an
existing result claims about its origin.

Constraints (or equivalent write-path guarantees) must prevent result records
from drifting from the run snapshot: results cannot exist without their run,
and cannot disagree with the snapshot's recorded metadata. Legacy runs that
predate TS-3 variant lineage must index with explicitly absent lineage fields
rather than fabricated ones.

## Acceptance criteria

- [x] Result records store run, execution snapshot, case, topology hash, parameter hash, input variant, date range and input series hashes.
- [x] Lineage values are copied from the run's frozen generation metadata, not derived from live case state.
- [x] Constraints or write-path guarantees prevent result records from existing without their run or disagreeing with its snapshot.
- [x] Legacy runs without TS-3 variant lineage index with absent (not fabricated) lineage fields.
- [x] Tests prove lineage presence and consistency, including that later edits to live series, topology or parameters leave indexed lineage unchanged.

## Resolution

Added frozen `lineage_json` persistence for the three TS-4 indexed result
surfaces (`run_dispatch_result_indexes`,
`run_asset_dispatch_result_indexes`, `run_summary_result_indexes`).

The write path now derives lineage only from the immutable
`scenario_versions.generation_metadata_json` snapshot plus the owning
`scenario_version` row, so result indexes cannot drift from later edits to
live drafts or time-series revisions. Legacy runs still index with
`input_variant = null`, `date_range = null` and an empty `input_series` list
instead of fabricated variant lineage.

## Verification

- Added focused backend tests in `tests/test_ts4_result_indexing.py` covering
  full lineage persistence, legacy missing-variant lineage, and frozen lineage
  after later live series/topology/parameter edits.
- Ran `.\.venv\Scripts\python.exe -m unittest tests.test_ts4_result_indexing tests.test_manual_runs -v`.
- Ran `.\.venv\Scripts\python.exe -m unittest tests.test_ts3_acceptance -v`.
- Verified against the real PostgreSQL database from `.env` with a smoke run
  that persisted matching lineage across dispatch, asset-dispatch and summary
  indexes.

## Blocked by

BESS-TS4-001
