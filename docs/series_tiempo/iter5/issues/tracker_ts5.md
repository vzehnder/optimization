# BESS TS-5 Issue Tracker

This document is the local tracker for TS-5: migration, unification and
hardening of the common topology/parameters/series/results model, derived
from `docs/series_tiempo/iter5/prd.md`.

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
| BESS-TS5-000 | Review TS-5 PRD And Migration Semantics | HITL | ready-for-agent | Done | 2026-07-09 | 2026-07-09 | None | [BESS-TS5-000-review-ts5-prd-and-migration-semantics.md](BESS-TS5-000-review-ts5-prd-and-migration-semantics.md) |
| BESS-TS5-001 | Extract A Legacy Draft Series Source Into The Generic Catalog | AFK | ready-for-agent | Done | 2026-07-10 | 2026-07-13 | BESS-TS5-000 | [BESS-TS5-001-extract-a-legacy-draft-series-source-into-the-generic-catalog.md](BESS-TS5-001-extract-a-legacy-draft-series-source-into-the-generic-catalog.md) |
| BESS-TS5-002 | Read Legacy Hydraulic Series Through The Common Catalog | AFK | ready-for-agent | Done | 2026-07-14 | 2026-07-15 | BESS-TS5-000 | [BESS-TS5-002-read-legacy-hydraulic-series-through-the-common-catalog.md](BESS-TS5-002-read-legacy-hydraulic-series-through-the-common-catalog.md) |
| BESS-TS5-003 | Route New Hydraulic Series Writes To The Generic Model | AFK | ready-for-agent | Done | 2026-07-16 | 2026-07-17 | BESS-TS5-002 | [BESS-TS5-003-route-new-hydraulic-series-writes-to-the-generic-model.md](BESS-TS5-003-route-new-hydraulic-series-writes-to-the-generic-model.md) |
| BESS-TS5-004 | Migrate Legacy Hydraulic Sets On Demand With Audit Preserved | AFK | ready-for-agent | Done | 2026-07-09 | 2026-07-09 | BESS-TS5-003 | [BESS-TS5-004-migrate-legacy-hydraulic-sets-on-demand-with-audit-preserved.md](BESS-TS5-004-migrate-legacy-hydraulic-sets-on-demand-with-audit-preserved.md) |
| BESS-TS5-005 | Keep Stale Validation Reliable Across Legacy And Migrated Series | AFK | ready-for-agent | Todo | 2026-07-22 | 2026-07-22 | BESS-TS5-001, BESS-TS5-004 | [BESS-TS5-005-keep-stale-validation-reliable-across-legacy-and-migrated-series.md](BESS-TS5-005-keep-stale-validation-reliable-across-legacy-and-migrated-series.md) |
| BESS-TS5-006 | Resolve Scenario And Case Cardinality In Schema And UI | AFK | ready-for-agent | Todo | 2026-07-23 | 2026-07-24 | BESS-TS5-000 | [BESS-TS5-006-resolve-scenario-and-case-cardinality-in-schema-and-ui.md](BESS-TS5-006-resolve-scenario-and-case-cardinality-in-schema-and-ui.md) |
| BESS-TS5-007 | Unify Concept Labels And Deprecation Paths In The UI | AFK | ready-for-agent | Todo | 2026-07-27 | 2026-07-27 | BESS-TS5-006 | [BESS-TS5-007-unify-concept-labels-and-deprecation-paths-in-the-ui.md](BESS-TS5-007-unify-concept-labels-and-deprecation-paths-in-the-ui.md) |
| BESS-TS5-008 | Enforce Consistent Permissions For Sources, Series And Results | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS5-000 | [BESS-TS5-008-enforce-consistent-permissions-for-sources-series-and-results.md](BESS-TS5-008-enforce-consistent-permissions-for-sources-series-and-results.md) |
| BESS-TS5-009 | Add Retention And Cleanup For Rebuildable Derived Data | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-07-30 | BESS-TS5-000 | [BESS-TS5-009-add-retention-and-cleanup-for-rebuildable-derived-data.md](BESS-TS5-009-add-retention-and-cleanup-for-rebuildable-derived-data.md) |
| BESS-TS5-010 | Review Constraints And Indexes For Real Query Patterns | AFK | ready-for-agent | Todo | 2026-07-31 | 2026-07-31 | BESS-TS5-001 through BESS-TS5-005 | [BESS-TS5-010-review-constraints-and-indexes-for-real-query-patterns.md](BESS-TS5-010-review-constraints-and-indexes-for-real-query-patterns.md) |
| BESS-TS5-011 | Finalize TS-5 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-08-03 | 2026-08-03 | BESS-TS5-001 through BESS-TS5-010 | [BESS-TS5-011-finalize-ts5-acceptance-suite-and-docs.md](BESS-TS5-011-finalize-ts5-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS5-000 closes the PRD review and the migration-semantics decision
   record (per-path strategies, `ScenarioDraft` role, hydraulic write
   strategy, cardinality, permission matrix, retention boundaries).
2. BESS-TS5-001 is the tracer bullet: one legacy draft's embedded series
   extract into the generic catalog with origin metadata and bind to a
   variant, idempotently.
3. BESS-TS5-002 exposes legacy hydraulic series through the common catalog
   semantics via a read adapter, without migrating rows.
4. BESS-TS5-003 routes new hydraulic series writes to the generic model so
   the parallel legacy tables stop growing.
5. BESS-TS5-004 adds the on-demand, audit-preserving migration for existing
   legacy hydraulic sets, plus a stable bulk sweep.
6. BESS-TS5-005 proves stale validation stays fail-closed across extracted,
   migrated, adapter-read and native series.
7. BESS-TS5-006 implements the accepted `Scenario -> OptimizationCase`
   cardinality outcome in schema, routes and UI.
8. BESS-TS5-007 unifies concept labels and marks deprecation paths in the UI.
9. BESS-TS5-008 enforces the accepted permission matrix for sources, input
   series, result series and publications across every surface.
10. BESS-TS5-009 adds retention and cleanup for rebuildable derived data,
    closed against the TS-4 rebuild path.
11. BESS-TS5-010 reviews constraints and indexes against the real TS-2
    through TS-4 query patterns with query-shape guard tests.
12. BESS-TS5-011 closes the iteration with the acceptance suite, the final
    architecture document and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-08 | All | Created | Initial local issue set generated from the TS-5 PRD (`docs/series_tiempo/iter5/prd.md`) and the series hierarchy roadmap. |
| 2026-07-08 | BESS-TS5-000 | Todo -> Done | Accepted TS-5 migration semantics in `docs/series_tiempo/iter5/decision_record_ts5_migration_semantics.md`: per-path strategy (extract-on-demand for draft/structured series, adapt-then-migrate-on-demand for hydraulic series, freeze-read-only for historical scenario versions, rebuild-on-demand for artifact-only runs); `ScenarioDraft` stays a compatibility surface; `Scenario -> OptimizationCase` cardinality confirmed one-to-one (no migration); hydraulic write strategy is generic-model writes with adapter reads, no dual write, open-ended per-project compatibility window; permission matrix formalizes the existing internal/client split; retention boundary is the TS-4 result-index tables (rebuildable) versus everything else (immutable audit). No PRD correction required. |
| 2026-07-08 | BESS-TS5-001 | Todo -> Done | Added deep module `app/legacy_series_extraction.py` extracting a draft's already-validated `time_series` source (mapping + `validated_rows`) directly into a generic catalog set (periods/signals/values, entity-scoped signals included), no column-remapping step required. New `AnalystStore.extract_draft_time_series_set` persistence method with a `time_series_set_extractions` origin/idempotency table; re-extraction of unchanged data is a no-op returning the same set, a content-hash mismatch raises instead of duplicating. Fixed a latent gap in the shared TS-2 catalog insert helper (`CatalogValue`/`_insert_time_series_signals_periods_values`) that assumed one signal per `signal_key` per set; now keys on `(signal_key, entity_key)`, needed because legacy drafts can have multiple assets of the same type. New endpoint `POST /api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/extract` and a new "Extract legacy series to catalog" panel in `DraftEditor.tsx`; catalog set detail page shows an "Origen" section for extracted sets. Backend: `tests/test_ts5_draft_series_extraction.py` (8 tests, full suite green). Frontend: `tsc -b`, `eslint .`, `vitest run`, `npm run build` all green (note: `npm run api:check` false-positives as stale due to a pre-existing Windows `core.autocrlf` CRLF/LF mismatch unrelated to this change, confirmed present on the base branch too). Verified live in Chrome against the real PostgreSQL dev DB end-to-end: upload -> validate mapping -> extract -> catalog listing -> origin metadata -> idempotent re-extraction (no duplicate) -> selectable and range-valid in the case's required-signal binding dropdowns. |
| 2026-07-09 | BESS-TS5-002 | Todo -> Done | Added pure deep module `app/hydraulic_time_series_adapter.py` (`build_hydraulic_catalog_summary`/`build_hydraulic_catalog_detail`) reshaping `hydraulic_time_series_sets`/`hydraulic_time_series_points` rows into the generic TS-2 catalog vocabulary (signals/periods/values/horizon, `timestamp_end` computed the same way as `time_series_catalog.py`), tagged with `origin: {kind: "hydraulic_legacy", ...}`. `AnalystStore.list_hydraulic_time_series_sets`/`get_hydraulic_time_series_set` (`app/persistence.py`) do only the DB IO: a `COALESCE` join across `hydraulic_nodes`/`hydraulic_reaches`/`hydraulic_systems` resolves entity/system display names for either a node- or reach-scoped set, then delegate shaping to the adapter; reuses the existing `_load_inflow_series_points` helper so the adapter can never diverge from the legacy read path's notion of a point. New endpoints `GET /api/projects/{project_id}/time-series-sets/hydraulic` and `.../hydraulic/{id}`, registered before the int-typed `.../time-series-sets/{time_series_set_id}` route to avoid a 422 collision. No migration, no write path change; hydro-diagram editor screens and case bindings untouched. Frontend: `TimeSeriesCatalogView` gained a separate "Series hidraulicas (origen legacy)" section (own id space, not merged with the generic list) and a new `HydraulicTimeSeriesSetDetailView` route. Tests: `tests/test_hydraulic_time_series_adapter.py` (2, pure/no DB) and `tests/test_ts5_hydraulic_series_catalog_adapter.py` (5: origin-labeled listing, detail-vs-legacy coexistence via the shared `time_series_set_id`, hydro-diagram read path unchanged, project-scoping 404, reach/`minimum_flow_m3s` case). Backend suite 358 tests (2 skipped, up from 350); frontend 62 vitest (up from 61) + `tsc -b`/`eslint .`/`api:generate`+`api:check`/`build` all green. Chrome + real Postgres (project `TS5-002 Chrome QA`, id 39, scenario 48): created a reservoir's `natural_inflow_series` via the real hydraulic-diagram API (authenticated `fetch()`, not the canvas UI — out of this issue's scope), confirmed it listed in the project catalog labeled "Origen hidraulico", opened its detail page (correct signal/unit/entity/horizon), and confirmed the legacy `GET .../hydraulic-diagram` path still returns the identical `time_series_set_id` and points afterward, zero console errors. Next Todo: TS5-003 (route new hydraulic series writes to the generic model). |
| 2026-07-09 | BESS-TS5-004 | Todo -> Done | Added `hydraulic_time_series_set_migrations` ledger table (`hydraulic_time_series_set_id UNIQUE`, `time_series_set_id`, `content_hash`, `migrated_at`, `migrated_by`) and registered it in `database.py`'s `ID_TABLES` for PostgreSQL `RETURNING id` support (a guard test, `test_all_autoincrement_id_tables_are_registered_for_postgres_returning`, caught the initial omission). Refactored `_write_generic_hydraulic_time_series_set` (TS5-003) to accept optional `status`/`revision_metadata`/`change_summary` instead of hardcoding them, so migration reuses the exact same name/content-hash idempotent insert path rather than duplicating it. New `AnalystStore.migrate_hydraulic_time_series_set` (one legacy set -> one generic set, `status="validated"`, `version_label=f"migrated-{legacy_version_label}"`, revision metadata `{"origin": {"kind": "hydraulic_legacy_migration", hydraulic_time_series_set_id, entity_type, entity_id, signal_key, legacy_version_number, legacy_version_label, legacy_content_hash, migrated_by, migrated_at}}`): checks the ledger first for idempotency (returns `already_migrated: true` pointing at the same generic set on re-run), raises `ValueError` for an empty legacy set (nothing to migrate), never touches the legacy row, `case_hydraulic_time_series_bindings`, `scenario_versions` or `runs`. New `AnalystStore.migrate_all_hydraulic_time_series_sets` sweeps every legacy set of a project, calling the single-set path per id and classifying each into `migrated`/`skipped`/`failed` (catching only `ValueError`, since ids come from the project's own table so `KeyError` cannot occur) -- stable across repeated runs because the single-set path is itself idempotent. New endpoints: `POST /api/projects/{project_id}/time-series-sets/hydraulic/{id}/migrate` (internal analyst or admin, per the accepted permission matrix) and `POST .../hydraulic/migrate-all` (admin-only via `require_admin_user`, matching Decision Record item 6's "bulk migration sweeps -> Admin only"). Tests: `tests/test_ts5_hydraulic_series_migration.py` (6: single migrate with origin metadata, idempotent re-migrate, legacy read path and case binding untouched after migration, bulk sweep migrated/skipped/failed report stable across two runs including one empty legacy set, analyst forbidden from bulk sweep, admin allowed). Backend suite 369 tests (2 skipped, up from 363); frontend 62 vitest + `tsc -b`/`eslint .`/`api:generate`+`api:check`/`build` all green. Frontend: `HydraulicTimeSeriesSetDetailView` gained a "Migracion" section (button + already-migrated/migrated result linking to the generic set); `TimeSeriesCatalogView` gained an admin-only "Migrar todas las series hidraulicas legacy" bulk button (`canBulkMigrateHydraulicSeries` prop, wired from `App.tsx` as `user.role === "admin"`, matching the existing `canManageClientAccess` precedent) with a migrated/skipped/failed count summary; `TimeSeriesSetOriginSummary` extended to render the new `hydraulic_legacy_migration` origin kind alongside the existing TS5-001 `legacy_draft_extraction` one. Chrome + real Postgres (project `TS5-004 Chrome QA`, id 41, scenario 50, case 30): built a reservoir via the real hydro-diagram editor, seeded a legacy `hydraulic_time_series_sets` row (id 10, entity 124, 3 points) directly at the storage layer since the public API can no longer produce legacy rows post-TS5-003, confirmed it read bound and correct (5/6/7 m3/s) before migration, migrated it through the UI button (landed as generic set id 32, `hydro_hydraulic_node_124_natural_inflow_m3s (migrated-v1-legacy)`, origin panel showing legacy set id/version/hash/migrated-by/at), re-clicked migrate and got "Ya estaba migrado a" pointing at the same set 32 (idempotent), confirmed the hydro-diagram editor still showed the original legacy series bound and unchanged with the migrated version now offered as a selectable alternative in the same dropdown, and ran the bulk sweep button getting a stable `Migradas: 0 | Ya migradas: 1 | Fallidas: 0` report. Also found and cleaned up an unrelated stale `uvicorn` process left listening on port 8000 from a prior Chrome-verification session (serving stale code and briefly causing a false 422 during this session's testing before it was killed). Next Todo: TS5-005 (keep stale validation reliable across legacy and migrated series). |
| 2026-07-09 | BESS-TS5-003 | Todo -> Done | `case_hydraulic_time_series_bindings.hydraulic_time_series_set_id` made nullable, new nullable `time_series_set_id` (FK to `time_series_sets`) added alongside it with a `CHECK` requiring exactly one populated (SQLite + PostgreSQL rebuild migrations, following the `_ensure_case_time_series_bindings_entity_scope` precedent) -- a binding now targets one store, never both, no dual write. New `_resolve_hydraulic_inflow_series_binding` (replaces `_resolve_hydraulic_inflow_series_set`): an existing series reference is looked up in whichever store `origin_kind` names (default legacy, so pre-TS5-003 bindings keep working); brand-new points always go through new `_write_generic_hydraulic_time_series_set` into the generic catalog via the shared TS-2 insert helper, keyed by a stable `hydro_{entity_type}_{entity_id}_{signal_key}` catalog name so repeated edits keep chaining the same version sequence and identical resaves are a no-op. Legacy `hydraulic_time_series_sets`/`hydraulic_time_series_points` receive no more new rows. Read side: new `_load_bound_hydraulic_points` dispatch point (collapses 3x duplicated inline SQL across `_reference_inflow_horizon`/`_validate_reach_controls`/`_validate_node_inflow_series`) plus new `_load_generic_hydraulic_series_points`, both returning the identical point shape the legacy loader does, so `generate_hydraulic_v3_preview` needed no changes. `_entity_inflow_series_detail` now merges legacy+generic rows into one `available` list tagged `origin: {"kind": ...}`. Wired `origin` all the way through the wire contract (`HydraulicNaturalInflowSeriesRequest.origin`, `normalize_hydraulic_natural_inflow_series`, and both frontend `Workspace.tsx` write-conversion + version-select sites) after finding via manual Chrome testing that resaving a diagram with an unrelated edit (e.g. renaming a node) would 400 without it, since the frontend wasn't forwarding which store a previously-saved id belonged to. Tests: `tests/test_ts5_hydraulic_series_generic_write.py` (4 new). Updated `tests/test_ts5_hydraulic_series_catalog_adapter.py` (TS5-002) to seed legacy fixtures directly via the store connection, since the public API can no longer produce legacy rows; added a coexistence test proving a seeded legacy set and a freshly-saved generic set surface side by side. Backend suite 363 tests (2 skipped, up from 358); frontend 62 vitest + `tsc -b`/`eslint .`/`api:generate`+`api:check`/`build` all green. Chrome + real Postgres (project `TS5-003 Chrome QA`, id 40, scenario 49): imported a natural-inflow CSV through the real editor upload control, saved, confirmed the set landed in the generic catalog (`GET /api/projects/40/time-series-sets`) and not in the legacy listing; edited an unrelated field and resaved with no error and no duplicate set (proving the origin round-trip fix); ran `POST .../hydraulic-diagram/validate` and got only the expected unrelated `missing_storage_elevation_curve` error, confirming the inflow series itself resolved correctly through the new generic-read path. Julia regression (`julia --project=. -e "import Pkg; Pkg.test()"`) run per tracker guidance for hydraulic write-path slices: 532/532 tests passed. Next Todo: TS5-004 (migrate legacy hydraulic sets on demand with audit preserved). |

## Final TS-5 Verification

Run before considering TS-5 closed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ts5_acceptance -v
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

Julia regression is only required if a TS-5 slice changes artifact formats,
the generated `system_case_json` contract or optimizer behavior; the
hydraulic write-path slices (BESS-TS5-003, BESS-TS5-004) must prove payload
equivalence, so run it when they land:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance, TS-2 catalog, TS-3 variant and TS-4 result
indexing tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

Historical scenario versions, executed snapshots and registered artifacts are
immutable: no TS-5 migration, extraction, cleanup or constraint change may
rewrite or delete them. Extraction and migration always add new objects with
origin metadata; legacy reads must keep working through adapters or frozen
snapshots for as long as the compatibility window is open.

Cleanup may only remove derived data that is provably rebuildable from
artifacts through the existing rebuild path; it must never remove audit data.
