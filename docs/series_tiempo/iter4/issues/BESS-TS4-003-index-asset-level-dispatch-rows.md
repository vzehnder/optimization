# BESS-TS4-003: Index Asset-Level Dispatch Rows

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-15
Fecha de termino planificada: 2026-07-15

## User stories covered

11

## What to build

Index the per-asset rows of `asset_dispatch.csv` so that each asset's dispatch
series is queryable in BBDD by asset identity. An analyst inspecting a run
should be able to see per-asset dispatch served from BBDD, with the asset id,
name and type preserved on each indexed series, and with the same run linkage
as the case-level series from earlier slices.

The per-asset results surface (the asset dispatch table on the run detail)
must read from BBDD when indexed data exists and fall back to artifacts for
runs without indexed results, rendering identically in both paths.

## Acceptance criteria

- [x] Asset-level dispatch series index in BBDD with asset identity (id, name, type) preserved.
- [x] Per-asset series carry the same run and snapshot linkage as case-level series.
- [x] The asset dispatch endpoint serves indexed data from BBDD with artifact fallback.
- [x] The React asset dispatch table renders identically from indexed data.
- [x] Tests index a multi-asset run's `asset_dispatch.csv` from representative artifacts.

## Blocked by

BESS-TS4-001

## Implementation Notes

New tables `run_asset_dispatch_result_indexes` / `run_asset_dispatch_result_rows`
(`app/persistence.py`), same shape as TS4-001's dispatch tables: keyed by
`run_id`, linked to `scenario_version_id`, replace-on-write. Each row carries
typed `asset_id`/`asset_type` identity columns plus the full original row as
`row_json`. `asset_dispatch.csv` has no separate "asset name" column in this
codebase (confirmed in `src/system_dispatch.jl` and every existing UI label,
e.g. `results.py`'s `build_asset_plot_series`, which already treats `asset_id`
as the display name) — `asset_id` fills that role, no fabricated column added.

`app/result_indexing.py` gained `index_run_asset_dispatch_results`, gated on
`timestamp`/`asset_id`/`asset_type` columns being present. `app/results.py`'s
`read_run_results` now prefers the BBDD asset-dispatch index over
`asset_dispatch.csv` when present, identical pattern to the dispatch table.
`app/runner.py`'s `_index_succeeded_run_results` now indexes both dispatch and
asset-dispatch independently (one failing does not block the other).

No frontend changes needed: `ResultTableView` (`RunResults.tsx`) already
renders any `columns`/`rows` shape generically, so the asset dispatch table
renders identically whether served from BBDD or CSV artifact.

Verification: Python 307 passed/2 skipped (up from 304), frontend 61 passed +
tsc/eslint/api:check/build all green. Chrome + real Postgres + real Julia
(reused project `TS3-005 Chrome QA`, id 24, scenario `Multi-family case`, id
33 — grid + load + renewable + battery): ran a fresh Run 22 (`succeeded`,
HiGHS `OPTIMAL`), confirmed `run_asset_dispatch_result_indexes`/
`run_asset_dispatch_result_rows` populated directly in Postgres (12 rows: 4
assets x 3 periods, correct `asset_id`/`asset_type`, linked to
`scenario_version_id` 32), then renamed the run's `asset_dispatch.csv`
artifact aside and confirmed the Asset Dispatch table on the run detail page
still rendered all 12 rows identically from BBDD before restoring the file.
