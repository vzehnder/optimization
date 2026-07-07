# BESS-TS3-009: Finalize TS-3 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

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

- [x] An acceptance suite covers default variant, clone, binding completeness, range and horizon validation, stale detection with revalidation, two-variant runs and run lineage.
- [x] The README documents the TS-3 case-variant workflow and its boundary with legacy scenario-version runs.
- [x] `docs/series_tiempo/iter3/pruebas_manuales_ts3.md` records the manual verification checklist.
- [x] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [x] The TS-3 tracker and all TS-3 issues are in their closed state.

## Blocked by

BESS-TS3-001 through BESS-TS3-008

## Implementation Notes

Closing proof issue; no production code change was needed because
BESS-TS3-001 through BESS-TS3-008 already implement the full variant,
validation, stale, clone and lineage behavior. Added
`tests.test_ts3_acceptance` (TDD, tracer bullet first) with two tests: one
continuous story proving the TS-3 workflow end to end on a hybrid
grid+battery+load+renewable case (lazy default variant creation, required
signal discovery, missing-binding failures, exact range coverage failures,
horizon incompatibility without implicit resampling, stale-on-series-edit,
explicit revalidation, clone divergence, two runs with distinct snapshots and
distinct price hashes, plus the legacy raw-`ScenarioVersion` boundary), and a
second test asserting the README, this issue, the tracker and the new manual
checklist are all in their closed/final state.

Added a new README section ("TS-3: Input Variants, Date Range And Run
Lineage") documenting the case-variant model, required signal discovery,
range and horizon rules, stale semantics, clone workflow, lineage fields and
the explicit boundary with legacy scenario-version runs. Added
`docs/series_tiempo/iter3/pruebas_manuales_ts3.md`, a manual checklist for
the TS-3 variant workflow, error cases, stale/revalidation, two-variant runs
and legacy coexistence, following the same shape as the TS-1 and TS-2
checklists. Updated `docs/series_tiempo/iter3/issues/tracker_ts3.md` to mark
this issue Done and record the focused acceptance command in the final
verification block.

Verified the UI manually through chrome-devtools MCP against the real
PostgreSQL-backed app and React case workspace: confirmed the default variant
appears lazily, required bindings surface in the panel, missing-binding and
range errors block runs with clear messages, stale state appears after a bound
series edit and clears only after revalidation, cloned variants can diverge in
their price binding, run detail shows variant/range/series lineage with the
technical snapshot collapsed by default, and the legacy manual-run path still
works without TS-3 lineage fields.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts3_acceptance -v
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

Julia regression is only required when a later TS-3-adjacent change touches
generated `system_case_json`, optimizer behavior, or artifact formats.
