# BESS-TS3-009: Finalize TS-3 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30

## User stories covered

22

## What to build

Close the iteration with proof and documentation. An acceptance suite tells
the whole TS-3 story in order: a case with a default variant, binding required
signals, cloning a variant, missing-binding and range/horizon validation
failures with clear errors, stale marking and revalidation, two-variant runs
with distinct snapshots, and complete run lineage.

Documentation closes with a README section describing the variant workflow, a
manual test checklist at `docs/series_tiempo/iter3/pruebas_manuales_ts3.md`
(same shape as the TS-1 and TS-2 checklists), and the tracker and issues moved
to their closed state.

## Acceptance criteria

- [ ] An acceptance suite covers default variant, clone, binding completeness, range and horizon validation, stale detection with revalidation, two-variant runs and run lineage.
- [ ] The README documents the TS-3 case-variant workflow and its boundary with legacy scenario-version runs.
- [ ] `docs/series_tiempo/iter3/pruebas_manuales_ts3.md` records the manual verification checklist.
- [ ] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [ ] The TS-3 tracker and all TS-3 issues are in their closed state.

## Blocked by

BESS-TS3-001 through BESS-TS3-008
