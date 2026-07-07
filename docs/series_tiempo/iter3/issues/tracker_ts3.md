# BESS TS-3 Issue Tracker

This document is the local tracker for TS-3: input series variants per case,
default variant and run date range, derived from
`docs/series_tiempo/iter3/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS3-000 | Review TS-3 PRD And Input Variant Semantics | HITL | ready-for-agent | Done | 2026-07-07 | 2026-07-07 | None | [BESS-TS3-000-review-ts3-prd-and-input-variant-semantics.md](BESS-TS3-000-review-ts3-prd-and-input-variant-semantics.md) |
| BESS-TS3-001 | Run A Case From Its Default Variant End-To-End | AFK | ready-for-agent | Done | 2026-07-08 | 2026-07-09 | BESS-TS3-000 | [BESS-TS3-001-run-a-case-from-its-default-variant-end-to-end.md](BESS-TS3-001-run-a-case-from-its-default-variant-end-to-end.md) |
| BESS-TS3-002 | Discover Required Signals And Surface Missing Bindings | AFK | ready-for-agent | Done | 2026-07-10 | 2026-07-13 | BESS-TS3-001 | [BESS-TS3-002-discover-required-signals-and-surface-missing-bindings.md](BESS-TS3-002-discover-required-signals-and-surface-missing-bindings.md) |
| BESS-TS3-003 | Enforce Range Coverage And Horizon Compatibility Validation | AFK | ready-for-agent | Done | 2026-07-14 | 2026-07-15 | BESS-TS3-002 | [BESS-TS3-003-enforce-range-coverage-and-horizon-compatibility-validation.md](BESS-TS3-003-enforce-range-coverage-and-horizon-compatibility-validation.md) |
| BESS-TS3-004 | Clone Variants And Switch Them From The Case Dropdown | AFK | ready-for-agent | Done | 2026-07-16 | 2026-07-17 | BESS-TS3-001 | [BESS-TS3-004-clone-variants-and-switch-them-from-the-case-dropdown.md](BESS-TS3-004-clone-variants-and-switch-them-from-the-case-dropdown.md) |
| BESS-TS3-005 | Bind All Required Signal Families | AFK | ready-for-agent | Done | 2026-07-20 | 2026-07-21 | BESS-TS3-002 | [BESS-TS3-005-bind-all-required-signal-families.md](BESS-TS3-005-bind-all-required-signal-families.md) |
| BESS-TS3-006 | Mark Variants Stale On Series, Topology Or Parameter Changes | AFK | ready-for-agent | Done | 2026-07-22 | 2026-07-23 | BESS-TS3-003 | [BESS-TS3-006-mark-variants-stale-on-series-topology-or-parameter-changes.md](BESS-TS3-006-mark-variants-stale-on-series-topology-or-parameter-changes.md) |
| BESS-TS3-007 | Show Run Lineage With Variant, Range And Series Hashes | AFK | ready-for-agent | Done | 2026-07-24 | 2026-07-27 | BESS-TS3-001, BESS-TS3-003 | [BESS-TS3-007-show-run-lineage-with-variant-range-and-series-hashes.md](BESS-TS3-007-show-run-lineage-with-variant-range-and-series-hashes.md) |
| BESS-TS3-008 | Run One Case With Two Variants And Preserve Legacy Runs | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS3-004, BESS-TS3-007 | [BESS-TS3-008-run-one-case-with-two-variants-and-preserve-legacy-runs.md](BESS-TS3-008-run-one-case-with-two-variants-and-preserve-legacy-runs.md) |
| BESS-TS3-009 | Finalize TS-3 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-07-30 | BESS-TS3-001 through BESS-TS3-008 | [BESS-TS3-009-finalize-ts3-acceptance-suite-and-docs.md](BESS-TS3-009-finalize-ts3-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS3-000 closes the PRD review and the input-variant semantics decision record.
2. BESS-TS3-001 is the tracer bullet: default variant, one price binding, date range, materialized snapshot and a real run end to end.
3. BESS-TS3-002 adds required-signal discovery and missing-binding surfacing on top of the tracer path.
4. BESS-TS3-003 hardens range coverage and horizon compatibility validation, recording revisions and hashes.
5. BESS-TS3-004 can proceed any time after BESS-TS3-001; it adds clone and the case variant dropdown.
6. BESS-TS3-005 extends bindings to every signal family (load, renewable, hydraulic inflows, minimum flows).
7. BESS-TS3-006 adds stale detection for series revisions and topology/parameter changes, with revalidation.
8. BESS-TS3-007 completes run lineage (variant, range, revisions, hashes) with the technical snapshot hidden by default.
9. BESS-TS3-008 proves two-variant comparison on one case and locks the legacy scenario-version regression contract.
10. BESS-TS3-009 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-06 | All | Created | Initial local issue set generated from the TS-3 PRD (`docs/series_tiempo/iter3/prd.md`) and the series hierarchy roadmap. |
| 2026-07-06 | BESS-TS3-000 | Todo -> Done | Accepted TS-3 input variant semantics in `docs/series_tiempo/iter3/decision_record_ts3_variant_semantics.md`. No PRD corrections needed; clarified that TopologyVersion/ParameterVersion are the existing TS-1 derived hashes and that new generic bindings must not touch the legacy hydraulic binding path. |
| 2026-07-06 | BESS-TS3-001 | Todo -> Done | Default input variant, one price binding (`price_usd_per_mwh`), date-range run and materialization deep module (`app/input_variants.py`) implemented TDD-first. Chrome + real Postgres + real Julia verification found and fixed two real bugs: an unvalidated legacy draft time-series source blocking generation, and TS-2's offset-qualified instants being rejected by Julia's naive-timestamp parser. Run reached `succeeded` end to end. |
| 2026-07-06 | BESS-TS3-002 | Todo -> Done | Required-signal discovery (`app/required_signals.py`) and completeness gating implemented TDD-first; wired into `materialize_system_case_for_variant` and the `GET .../case/default-variant` response, rendered in `CaseInputVariantPanel`. Chrome + real Postgres + real Julia verification: confirmed the missing-signal 400 path names the exact missing signal, confirmed the price-only tracer-bullet path still reaches `succeeded` (Run 9, HiGHS `OPTIMAL`), and confirmed the panel degrades gracefully (empty `required_signals`, no 404) for scenarios without an editor draft yet. Found and documented (not fixed) a pre-existing gap: entity-scoped signal families (`load_demand_mw` and siblings) materialize as flat scalars instead of the `{asset_id: value}` map Julia's legacy contract expects once bound; fixing this needs entity-scoped bindings, which is BESS-TS3-005's stated scope. |
| 2026-07-07 | BESS-TS3-003 | Todo -> Done | Range coverage and horizon compatibility hardening implemented TDD-first. `app/input_variants.py` now rejects missing coverage with binding/set/missing-span messages and rejects cross-signal horizon mismatches with explicit "no implicit resampling" errors. `materialize_system_case_for_variant` records validated set version/revision/hash plus `validated_range` for each binding. `CaseInputVariantPanel` surfaces valid, incomplete-coverage and horizon-incompatible states before launch and disables the run button until the selected range is locally valid. Verification: Python suite 266 passed / 1 skipped; frontend suite 54 passed plus `tsc -b`, `eslint .`, `api:check`, and build. Chrome-devtools MCP against real PostgreSQL project `TS3-003 Chrome QA` confirmed valid range enables run, incomplete coverage and period-boundary mismatch alerts disable run, and live backend 400 names `binding 'price_usd_per_mwh' on time-series set 14 missing coverage for [2026-01-01T03:00:00-03:00, 2026-01-01T04:00:00-03:00)`. Chrome extension control opened the local app; tab-claim verification was blocked by another extension UI, so interaction checks were completed through chrome-devtools MCP. |
| 2026-07-07 | BESS-TS3-004 | Todo -> Done | Variant clone/dropdown flow implemented TDD-first. Backend now exposes case-scoped variant list/create/clone/update endpoints and enforces scenario/case ownership on variant-aware bind/run routes. React now lists all case variants, marks the default in the dropdown, persists the selected variant per scenario, clones from the active variant, and uses the selected variant for binding, validation, and run launch. Verification: Python suite 269 passed / 1 skipped; focused frontend variant tests, `api:check`, and build passed. Real PostgreSQL + chrome-devtools MCP verification on project `TS3-004 Chrome QA` confirmed `Stress clone` can be rebound to set `#17`, Run 10 reaches `succeeded`, and switching back to `Default (default)` still shows set `#16`, proving clone independence. Chrome extension control was also connected and named, but deeper interaction in that surface was blocked by another extension UI, so end-to-end UI checks stayed on chrome-devtools MCP. |
| 2026-07-07 | BESS-TS3-005 | Todo -> Done | Entity-scoped bindings implemented TDD-first (continuing WIP left uncommitted from a prior session): `case_time_series_bindings` gained nullable `entity_type`/`entity_id` with a scoped unique constraint, `discover_required_signals`/`evaluate_variant_completeness` (`app/required_signals.py`) now cover load, renewable, one-bus hydro, hydraulic-node inflow and hydraulic-reach minimum-flow families by entity, and `materialize_variant_time_series` (`app/input_variants.py`) writes entity-scoped signals as `{asset_id: value}` maps per the TS-2 catalog's `entity_type` metadata. Fixed 3 pre-existing test regressions left by the prior session (legacy unscoped-load fixtures no longer matched the new entity-scoped completeness check) and 2 frontend test fixtures missing the new dynamic `required_signals`-driven binding UI. Verification: Python suite 276 passed / 2 skipped; frontend suite 56 passed plus `tsc -b`, `eslint .`, `api:check`, `build`. Chrome-devtools MCP against real PostgreSQL (project `TS3-005 Chrome QA`) found and fixed a real bug: an unscoped price binding 500'd with `psycopg.errors.IndeterminateDatatype` because PostgreSQL can't infer a parameter's type from a bare `? IS NULL` comparison; fixed with an explicit `CAST(? AS TEXT)` and locked in with a new real-PostgreSQL regression test (confirmed RED then GREEN). After the fix, a hybrid case bound with price (unscoped) + `load_demand_mw` (`load_1`) + `renewable_available_power_mw` (`solar_1`) ran end to end to Run 11 `succeeded` (HiGHS `OPTIMAL`), with the asset dispatch table confirming the per-asset values materialized correctly. |
| 2026-07-07 | BESS-TS3-006 | Todo -> Done | Stale detection implemented TDD-first. New generic `validation_dependencies` table (`app/persistence.py`) records per-variant dependency hashes (bound time-series sets' `content_hash`, plus topology/parameters hashes from the existing TS-1 `derive_case_hierarchy_provenance`), compared lazily against current state by a new pure module `app/variant_staleness.py` (`evaluate_variant_staleness`, `VariantStaleError`) rather than write-time triggers on every series/topology/parameter mutation path. `materialize_system_case_for_variant` (the `run` path) now stale-precheck-blocks with a 400 before validating; a new `validate_case_input_variant` (`POST .../variants/{id}/validate`) runs the same completeness/range checks without creating a run and is the only path that clears the stale marker, so a stale variant genuinely cannot self-heal via `run` alone. `staleness` is now included in both `GET .../default-variant` and `GET .../variants` responses. React shows "(desactualizada)" in the variant dropdown and a stale banner with reasons plus a "Revalidar variante" button in the binding editor, disabling "Vincular y correr variante" while stale. Verification: Python suite 291 passed / 2 skipped (up from 276); frontend suite 57 passed plus `tsc -b`, `eslint .`, `api:check`, `build`. Chrome-devtools MCP against real PostgreSQL (project `TS3-006 Chrome QA`, scenario 40) confirmed a manual value edit on a bound set marked an already-validated variant stale with the exact reason text in both the dropdown and the binding-editor alert, that rebinding to a different set produced simultaneous "added"/"no longer bound" reasons, that the run button stayed disabled while stale, that "Revalidar variante" cleared the marker without a reload, and that a subsequent run reached Run 15 `succeeded` (HiGHS `OPTIMAL`) end to end. |
| 2026-07-07 | BESS-TS3-007 | Todo -> Done | Run lineage completed TDD-first. Backend: `run_case_input_variant` (`app/main.py`) now captures the bound variant (not just its id) and stores `input_variant.display_name` alongside `input_variant.id`, `date_range`, and `series_bindings` (signal/entity, set id, version/revision, content hash, validated range) in `generation_metadata_json` at run creation; topology/parameter hashes were already auto-attached by `create_scenario_version`'s `derive_case_hierarchy_provenance` call, so no change was needed there. New backend test proves the full lineage shape and that editing a bound set's values afterward leaves the already-created run's recorded `content_hash` unchanged even though the live set's hash moves on (immutability). Frontend: `RunLineage` (`frontend/src/Workspace.tsx`) now shows "Variante" and "Rango de fechas" rows when `generation_metadata.kind === "case_input_variant"`; a new "Series de entrada" section (`RunSeriesBindingsLineage`) lists each binding's signal, entity, set id, version/revision and truncated hash, with a graceful "no proviene de una variante" fallback for legacy runs; a new "Snapshot tecnico" section (`RunTechnicalSnapshot`) wraps the raw `system_case_json` + `generation_metadata` in a `<details>` disclosure that only renders its (potentially large) JSON into the DOM once opened, so it is genuinely absent by default rather than just CSS-hidden (jsdom does not apply the native `details:not([open])` UA hiding rule, so state-driven conditional rendering was required for both correctness and testability). Verification: Python suite 292 passed / 2 skipped (up from 291); frontend suite 60 passed (up from 57) plus `tsc -b`, `eslint .`, `api:check`, `build`. Chrome-devtools MCP against real PostgreSQL + real Julia (project `TS3-007 Chrome QA`, scenario 41) ran a cloned "Stress prices" variant end to end to Run 16 `succeeded` (HiGHS `OPTIMAL`) and confirmed the run-detail page shows "Stress prices", the exact date range, topology/parameter hashes, the `price_usd_per_mwh` binding's set id/version/revision/hash, and a collapsed "Ver snapshot tecnico" disclosure that reveals the full JSON snapshot on click; a spot-check of legacy run 1 (pre-TS-3, no variant) confirmed the Lineage section omits the variant/range rows and "Series de entrada" shows the "no proviene de una variante de entrada" fallback with no crash. |

## Final TS-3 Verification

Run before considering TS-3 closed:

```powershell
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

Julia regression is only required if a TS-3 slice changes the generated
`system_case_json` contract, optimizer behavior, or artifact formats:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance and TS-2 catalog tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

TS-3 materializes `system_case_json` payloads that the Julia optimizer already
accepts; if any slice changes that contract, the Julia regression suite must
be run.

TS-3 must not remove or break the legacy scenario-version run path; it remains
the regression contract until a later iteration retires it explicitly.
