# BESS-TS4-010: Finalize TS-4 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30

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

- [ ] An acceptance suite covers post-run indexing, all signal families, asset rows, summary KPIs, lineage, idempotent re-indexing, artifact fallback for legacy runs, rebuild and two-run comparison.
- [ ] The README documents the TS-4 result-series model and its boundary with artifacts.
- [ ] `docs/series_tiempo/iter4/pruebas_manuales_ts4.md` records the manual verification checklist.
- [ ] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [ ] The TS-4 tracker and all TS-4 issues are in their closed state.

## Blocked by

BESS-TS4-001 through BESS-TS4-009
