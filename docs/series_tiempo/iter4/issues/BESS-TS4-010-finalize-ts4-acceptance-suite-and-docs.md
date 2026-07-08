# BESS-TS4-010: Finalize TS-4 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

## User stories covered

1 through 21 (closing proof)

## What to build

Close the iteration with proof and documentation. An acceptance suite tells
the whole TS-4 story in order: a successful run indexes its dispatch series,
asset rows and summary KPIs with full lineage; artifacts remain registered and
untouched; re-indexing is idempotent; a legacy run keeps serving from
artifacts; the rebuild path indexes a historical run; and two runs of the same
case with different input variants compare through KPI and period-level
diffs.

Documentation closes with a README section describing the result-series model
and its boundary with artifacts, a manual test checklist at
`docs/series_tiempo/iter4/pruebas_manuales_ts4.md` (same shape as the TS-1
through TS-3 checklists), and the tracker and issues moved to their closed
state.

## Acceptance criteria

- [x] An acceptance suite covers post-run indexing, all signal families, asset rows, summary KPIs, lineage, idempotent re-indexing, artifact fallback for legacy runs, rebuild and two-run comparison.
- [x] The README documents the TS-4 result-series model and its boundary with artifacts.
- [x] `docs/series_tiempo/iter4/pruebas_manuales_ts4.md` records the manual verification checklist.
- [x] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [x] The TS-4 tracker and all TS-4 issues are in their closed state.

## Blocked by

BESS-TS4-001 through BESS-TS4-009

## Implementation Notes

Closing proof issue; no production-code hardening was needed because
BESS-TS4-001 through BESS-TS4-009 already implement the TS-4 behavior end to
end. Added `tests.test_ts4_acceptance` (TDD, tracer bullet first) with two
tests: one continuous story proving hybrid signal indexing, asset-dispatch
indexing, summary indexing, frozen variant/range lineage, idempotent
re-indexing, legacy artifact fallback, admin rebuild, hydro-only signal
coverage, and same-case run comparison with KPI and period-level diffs; and a
second test asserting the README, this issue, the tracker and the new manual
checklist are all in their closed/final state. The behavior test passed on
the first run, confirming the implemented TS4-001 through TS4-009 slices
already satisfy the end-to-end TS-4 contract.

Added a new README section ("TS-4: Result Series, Rebuild, And Run
Comparison") documenting the dedicated run-result layer, BBDD-first
per-surface reads with artifact fallback, canonical signal-key indexing,
frozen lineage, rebuild endpoints and the same-case comparison boundary.
Added `docs/series_tiempo/iter4/pruebas_manuales_ts4.md`, a manual checklist
for indexed-result reads, artifact fallback, rebuild, hydro coverage and
comparison, following the same shape as the TS-1 through TS-3 checklists.
Updated `docs/series_tiempo/iter4/issues/tracker_ts4.md` to mark this issue
Done and record the focused acceptance command in the final verification
block.

Verified manually in Chrome against the real PostgreSQL-backed app and React
results workspace: created synthetic smoke runs `27` (`TS4 Project`, legacy
full-artifact run) and `28` (`TS4 Hydro Diagram Project`, hydro-only run) in
the real database, confirmed `Run 27` first rendered as a historical
non-indexed run, rebuilt it into BBDD, temporarily removed its
`dispatch.csv`/`asset_dispatch.csv`/`summary.json` files from disk, and
confirmed the page still rendered the full results view from BBDD; confirmed
`Run 28` rendered hydro-only result families (`total_hydro_power_mw`,
`total_hydro_inflow_m3s`, `total_hydro_storage_hm3`, reservoir elevation and
hydro charts) from indexed data; and opened the real comparison page for
scenario `28`, where runs `21` vs `20` rendered baseline/candidate context,
KPI diffs and a working series selector.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia regression is only required when a later TS-4-adjacent change touches
optimizer behavior, generated `system_case_json`, or artifact formats.
